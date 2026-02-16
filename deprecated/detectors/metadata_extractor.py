"""Metadata Extractor.

Extracts and validates first-page/header metadata (student info, course, project).
Emits findings for missing or malformed metadata.
"""

import re
from typing import Any, Dict, List, Optional

from ..schemas.finding import Finding, Stat
from ..schemas.ir import Document
from .base_detector import BaseDetector

DEFAULTS = dict(
    header_block_limit=10,
    expected_course=None,  # "ifj" or "ipp" - if None, skips course-specific validation
)


class MetadataExtractor(BaseDetector):
    code = "METADATA"
    name = "MetadataExtractor"
    version = "0.2"
    param_spec = {
        "header_block_limit": "Number of blocks to check from document start",
        "expected_course": "Course identifier (ifj/ipp). If set, validates that document header mentions it.",
    }

    # TODO: osobne cislo?
    # TODO: name?
    PATTERNS = {
        "login": [
            r"login:\s*([xX][a-zA-Z]{3,6}\d{2})",  # "Login: xlogin00"
            r"\b([xX][a-zA-Z]{3,6}\d{2})\b",  # Standalone xlogin00
        ],
    }

    def __init__(self, *, run_id: Optional[str] = None, params: Optional[dict] = None):
        updated_params = DEFAULTS.copy()
        if params:
            updated_params.update(
                {key: value for key, value in params.items() if key in DEFAULTS}
            )
        super().__init__(run_id=run_id, params=updated_params)
        self.cfg = updated_params

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        findings: List[Finding] = []

        # Extract text from first N blocks using base detector utility
        header_text = self.extract_text(
            doc,
            block_types=["Heading", "Paragraph"],
            start_idx=0,
            end_idx=self.cfg["header_block_limit"],
        )

        # Try to extract metadata
        metadata = self._extract_metadata(header_text)

        # Validate required fields based on configuration
        findings.extend(self._validate_metadata(doc, doc_hash, metadata, header_text))

        return findings

    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """Extract metadata fields using regex patterns."""
        metadata = {}

        for pattern in self.PATTERNS["login"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["login"] = (
                    match.group(1) if match.lastindex else match.group(0)
                )
                break

        return metadata

    def _validate_metadata(
        self,
        doc: Document,
        doc_hash: str,
        metadata: Dict[str, Any],
        header_text: str,
    ) -> List[Finding]:
        """Validate that required metadata fields are present.

        Check for:
        1. Login (xlogin00)
        2. Course (IFJ/IPP) mentioned in header (if expected_course is set)
        """
        findings: List[Finding] = []
        missing_fields = []

        # Always validate login is present
        if not metadata.get("login"):
            missing_fields.append("login (xlogin00)")

        # Only validate course if expected_course is configured
        expected_course = self.cfg.get("expected_course")
        if expected_course and expected_course.lower() not in header_text.lower():
            missing_fields.append(f"course identification ({expected_course.upper()})")

        if missing_fields:
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug=f"header_missing:{expected_course or 'unknown'}",
                    title="Missing or invalid header metadata",
                    message=f"Document header validation failed: {', '.join(missing_fields)}",
                    severity_rank=2,
                    confidence=0.85,
                    tags=["metadata", "header", expected_course or "unknown"],
                    extra_evidence=[
                        Stat(name="missing_fields_count", value=len(missing_fields)),
                        Stat(
                            name="expected_course",
                            value=expected_course or "not-configured",
                        ),
                        Stat(name="found_login", value=bool(metadata.get("login"))),
                    ],
                )
            )

        return findings

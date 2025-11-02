"""Metadata Extractor.

Extracts and validates first-page/header metadata (student info, course, project).
Emits findings for missing or malformed metadata.
"""

import re
from typing import List, Optional, Dict, Any

from .base_detector import BaseDetector
from ..schemas.ir import Document, Paragraph, Heading, Block
from ..schemas.finding import Finding, Stat


DEFAULTS = dict(
    header_block_limit=10,
    expected_course=None,  # "ifj" or "ipp" - if None, will auto-detect from document
)


class MetadataExtractor(BaseDetector):
    code = "METADATA"
    name = "MetadataExtractor"
    version = "0.2"
    param_spec = {
        "header_block_limit": "Number of blocks to check from document start",
        "expected_course": "Course identifier (ifj/ipp). If None, auto-detects from document.",
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

        # Determine course: use config if provided, otherwise auto-detect
        course = self.cfg["expected_course"]
        if not course:
            course = self._detect_course(header_text)

        # Validate required fields
        findings.extend(
            self._validate_metadata(doc, doc_hash, metadata, course, header_text)
        )

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

    def _detect_course(self, text: str) -> Optional[str]:
        """Detect which course this document is for."""
        text_lower = text.lower()

        ifj_pos = text_lower.find("ifj")
        ipp_pos = text_lower.find("ipp")

        # Neither found
        if ifj_pos == -1 and ipp_pos == -1:
            return None

        # Only one found
        if ifj_pos != -1 and ipp_pos == -1:
            return "ifj"
        if ipp_pos != -1 and ifj_pos == -1:
            return "ipp"

        # Both found - return whichever appears first
        return "ifj" if ifj_pos < ipp_pos else "ipp"

    def _validate_metadata(
        self,
        doc: Document,
        doc_hash: str,
        metadata: Dict[str, Any],
        course: Optional[str],
        header_text: str,
    ) -> List[Finding]:
        """Validate that required metadata fields are present.

        Check for:
        1. Login (xlogin00)
        2. Course (IFJ/IPP)
        """
        findings: List[Finding] = []

        missing_fields = []

        if not metadata.get("login"):
            missing_fields.append("login (xlogin00)")

        if not course:
            missing_fields.append("course identification (IFJ/IPP)")

        if missing_fields:
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug=f"header_missing:{course or 'unknown'}",
                    title="Missing header metadata",
                    message=f"Document header is missing required fields: {', '.join(missing_fields)}",
                    severity_rank=2,
                    confidence=0.85,
                    tags=["metadata", "header", course or "unknown"],
                    extra_evidence=[
                        Stat(name="missing_fields_count", value=len(missing_fields)),
                        Stat(name="detected_course", value=course or "unknown"),
                        Stat(name="found_login", value=bool(metadata.get("login"))),
                    ],
                )
            )

        return findings

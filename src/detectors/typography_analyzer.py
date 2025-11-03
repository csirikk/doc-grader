"""Typography Analyzer.

Basic typography checks for document formatting compliance.
Detects issues like improper code formatting and line length violations. TODO: add mdlines soft break checks
"""

import re
from typing import List, Optional
from pathlib import Path

from .base_detector import BaseDetector
from ..schemas.ir import Document, Paragraph, CodeBlock, Block
from ..schemas.finding import Finding, Stat
from ..logger import debug

DEFAULTS = dict(
    max_md_line_length=120,
    min_unlabeled_code_threshold=3,
)


class TypographyAnalyzer(BaseDetector):
    code = "TYPO"
    name = "TypographyAnalyzer"
    version = "0.2"
    param_spec = {
        "max_md_line_length": "Maximum line length for markdown files",
        "min_unlabeled_code_threshold": "Minimum unlabeled code blocks before flagging",
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

        if doc.source_path.endswith((".md", ".markdown")):
            findings.extend(self._check_md_line_length(doc, doc_hash))

        # Check code blocks for monospace font hint (metadata-based check)
        findings.extend(self._check_code_formatting(doc, doc_hash))

        return findings

    def _check_md_line_length(self, doc: Document, doc_hash: str) -> List[Finding]:
        """Check for markdown line length violations."""
        findings: List[Finding] = []

        # Read source file if available
        source_path = Path(doc.source_path)
        if not source_path.exists():
            return findings

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            violations = []
            for line_num, line in enumerate(lines, 1):
                # Strip newline but keep other whitespace for accurate length
                line_content = line.rstrip("\n\r")
                if len(line_content) > self.cfg["max_md_line_length"]:
                    violations.append((line_num, len(line_content)))

            if violations:
                # Report only if significant violations
                if len(violations) > 3:  # More than 3 violations
                    findings.append(
                        self.emit(
                            doc=doc,
                            doc_hash=doc_hash,
                            slug="markdown_line_length_exceeded",
                            title="Markdown line length violations",
                            message=f"Found {len(violations)} lines exceeding {self.cfg['max_md_line_length']} characters (max: {max(v[1] for v in violations)} chars)",
                            severity_rank=3,
                            confidence=0.90,
                            tags=["typography", "markdown", "line_length"],
                            extra_evidence=[
                                Stat(name="violation_count", value=len(violations)),
                                Stat(
                                    name="max_line_length",
                                    value=self.cfg["max_md_line_length"],
                                ),
                                Stat(
                                    name="longest_line",
                                    value=max(v[1] for v in violations),
                                ),
                                Stat(
                                    name="first_violation_line", value=violations[0][0]
                                ),
                            ],
                        )
                    )
        except Exception:
            debug(
                "TypographyAnalyzer: Failed to read source file for line length check."
            )
            pass

        return findings

    def _check_code_formatting(self, doc: Document, doc_hash: str) -> List[Finding]:
        """Check if code blocks are properly formatted."""
        findings: List[Finding] = []

        code_blocks = self.get_blocks(doc, "CodeBlock")

        # For now, just count code blocks without language hint
        unlabeled_code = [cb for cb in code_blocks if not cb.language]

        if (
            unlabeled_code
            and len(unlabeled_code) >= self.cfg["min_unlabeled_code_threshold"]
        ):
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="code_not_labeled",
                    title="Code blocks without language labels",
                    message=f"Found {len(unlabeled_code)} code blocks without language specification",
                    severity_rank=3,
                    confidence=0.75,
                    tags=["typography", "code", "formatting"],
                    extra_evidence=[
                        Stat(name="unlabeled_code_blocks", value=len(unlabeled_code)),
                        Stat(name="total_code_blocks", value=len(code_blocks)),
                    ],
                )
            )

        return findings

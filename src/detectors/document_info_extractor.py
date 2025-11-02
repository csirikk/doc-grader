"""Document Info Extractor.

Extracts file metadata and validates document type.
Emits findings for wrong document type, format violations, or missing documents.
"""

from pathlib import Path
from typing import List, Optional

from .base_detector import BaseDetector
from ..schemas.ir import Document
from ..schemas.finding import Finding, Stat
from ..util import compute_doc_hash


# Thresholds based on rough average
DEFAULTS = dict(
    accepted_extensions=[".pdf", ".md", ".markdown"],
    max_file_size_mb=1.5,
    min_file_size_kb=1.0,
    min_content_blocks=5,
)


class DocumentInfoExtractor(BaseDetector):
    code = "DOCINFO"
    name = "DocumentInfoExtractor"
    version = "0.2"
    runs_before_parsing = True  # Can check file metadata before parsing
    param_spec = {
        "accepted_extensions": "List of accepted file extensions",
        "max_file_size_mb": "Maximum file size in MB before flagging",
        "min_file_size_kb": "Minimum file size in KB before flagging as empty",
        "min_content_blocks": "Minimum number of blocks to be considered valid content",
    }

    def __init__(self, *, run_id: Optional[str] = None, params: Optional[dict] = None):
        updated_params = DEFAULTS.copy()
        if params:
            updated_params.update(
                {key: value for key, value in params.items() if key in DEFAULTS}
            )
        super().__init__(run_id=run_id, params=updated_params)
        self.cfg = updated_params

    def detect_file(self, file_path: Path) -> List[Finding]:
        """Check file metadata before parsing."""
        findings: List[Finding] = []
        doc_hash = compute_doc_hash(str(file_path))

        # Create minimal document ref for findings
        from ..schemas.ir import Document

        doc = Document(source_path=str(file_path), blocks=[])

        # Check if source path exists
        if not file_path.exists():
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="document_missing",
                    title="Document file not found",
                    message=f"Document file does not exist: {file_path}",
                    severity_rank=1,
                    confidence=1.0,
                    tags=["docinfo", "missing"],
                )
            )
            return findings

        # Check document type
        file_ext = file_path.suffix.lower()
        if file_ext not in self.cfg["accepted_extensions"]:
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="wrong_doc_type",
                    title="Unsupported document type",
                    message=f"Document has unsupported extension '{file_ext}'. Expected one of: {', '.join(self.cfg['accepted_extensions'])}",
                    severity_rank=1,
                    confidence=0.95,
                    tags=["docinfo", "format"],
                    extra_evidence=[
                        Stat(name="file_extension", value=file_ext),
                        Stat(
                            name="accepted_extensions",
                            value=self.cfg["accepted_extensions"],
                        ),
                    ],
                )
            )

        # Extract file stats
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        file_size_kb = file_size / 1024

        # Check for format violations (e.g., extremely large file)
        if file_size_mb > self.cfg["max_file_size_mb"]:
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="format_violation",
                    title="File size exceeds limit",
                    message=f"Document file size ({file_size_mb:.2f} MB) exceeds maximum allowed ({self.cfg['max_file_size_mb']} MB)",
                    severity_rank=2,
                    confidence=0.9,
                    tags=["docinfo", "format", "size"],
                    extra_evidence=[
                        Stat(name="file_size_mb", value=round(file_size_mb, 2)),
                        Stat(name="max_allowed_mb", value=self.cfg["max_file_size_mb"]),
                    ],
                )
            )

        # Check for suspiciously small documents (likely empty or corrupted)
        if file_size_kb < self.cfg["min_file_size_kb"]:
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="document_missing",
                    title="Document appears empty or corrupted",
                    message=f"Document file size ({file_size_kb:.2f} KB) is suspiciously small, likely empty or corrupted",
                    severity_rank=1,
                    confidence=0.95,
                    tags=["docinfo", "missing", "size"],
                    extra_evidence=[
                        Stat(name="file_size_kb", value=round(file_size_kb, 2)),
                        Stat(
                            name="min_expected_kb", value=self.cfg["min_file_size_kb"]
                        ),
                    ],
                )
            )

        return findings

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        """Check parsed document content."""
        findings: List[Finding] = []

        block_count = self.count_blocks(doc)

        if block_count < self.cfg["min_content_blocks"]:
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="document_missing",
                    title="Document has insufficient content",
                    message=f"Document has only {block_count} content blocks, likely missing substantial text",
                    severity_rank=1,
                    confidence=0.90,
                    tags=["docinfo", "missing", "content"],
                    extra_evidence=[
                        Stat(name="block_count", value=block_count),
                        Stat(
                            name="min_expected_blocks",
                            value=self.cfg["min_content_blocks"],
                        ),
                    ],
                )
            )

        return findings

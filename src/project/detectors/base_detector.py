"""Base detector interface.

Provides a `BaseDetector` with helpers for building findings and outputting them. 
Subclasses implement `detect`.
"""

from pathlib import Path
from typing import List, Optional, Any

from ..schemas.ir import Document, Span, Block
from ..schemas.finding import (
    Finding, DetectorInfo, DocumentRef, Location, SpanRef,
    BlockRef, TextSpan,
)
from ..util import compute_doc_hash

# --- Helpers
# ID format: 'CODE:hash8:slug'
def _build_finding_id(code: str, doc_hash: str, slug: str) -> str:
    return f"{code.upper()}:{doc_hash[7:15]}:{slug}"

# IR to Finding helpers
def _build_spanref(s: Span) -> SpanRef:
    return SpanRef(
        line_start=s.line_start, line_end=s.line_end,
        byte_start=s.byte_start, byte_end=s.byte_end,
        page=getattr(s, "page", None), # optional
    )

def _build_location(block: Optional[Block] = None, span: Optional[Span] = None) -> Location:
    return Location(
        block_id=(block.id if block else None),
        span=(_build_spanref(span) if span else None),
    )

class BaseDetector:

    # override in subclasses
    code: str = "BASE"
    name: str = "BaseDetector"
    version: str = "0.1"

    def __init__(self, *, run_id: Optional[str] = None):
        self.info = DetectorInfo(code=self.code, name=self.name, version=self.version, run_id=run_id)

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        """Run detector on the given document and return a list of findings."""
        raise NotImplementedError

    def write_findings(self, findings: List[Finding], outdir: Path) -> List[Path]:
        """
        Write each finding as a JSON file in `outdir`.
        Returns the list of written file paths.
        """
        outp = outdir
        outp.mkdir(parents=True, exist_ok=True)
        written: List[Path] = []
        for f in findings:
            path = outp / (f.finding_id.replace(":", "-") + ".json")
            path.write_text(f.model_dump_json(indent=2), encoding="utf-8")
            written.append(path)
        return written

    def emit(
        self,
        *,
        doc: Document,
        doc_hash: str,
        slug: str,
        title: str,
        message: str,
        severity: str = "warning",
        anchor_block: Optional[Block] = None,
        anchor_span: Optional[Span] = None,
        tags: Optional[List[str]] = None,
        confidence: Optional[float] = None,
        extra_evidence: Optional[List[Any]] = None,
    ) -> Finding:
        loc = None
        if anchor_block or anchor_span:
            loc = _build_location(anchor_block, anchor_span)

        evidence: List[Any] = []
        if anchor_span:
            evidence.append(TextSpan(text=None, span=_build_spanref(anchor_span)))
        if anchor_block:
            evidence.append(BlockRef(block_ids=[anchor_block.id]))
        if extra_evidence:
            evidence.extend(extra_evidence)

        return Finding(
            detector=self.info,
            document=DocumentRef(source_path=doc.source_path, hash=doc_hash),
            finding_id=_build_finding_id(self.code, doc_hash, slug),
            doc_id=doc_hash,
            code=self.code,
            title=title,
            message=message,
            severity=severity,
            confidence=confidence,
            locations=([loc] if loc else None),
            evidence=evidence,
            tags=(tags or []),
        )

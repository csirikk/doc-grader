# detectors/base_detector.py

from pathlib import Path
from typing import List, Optional, Any

from ..parsers.md_parser import parse_markdown
from ..schemas.ir import Document, Span, Block
from ..schemas.finding import (
    Finding, DetectorInfo, DocumentRef, Location, SpanRef,
    BlockRef, TextSpan,
)
from ..util import doc_hash


# helpers ------------------------------------------------------------

# ID format: 'CODE:hash8:slug'
def make_finding_id(code: str, doc_hash_value: str, slug: str) -> str:
    return f"{code.upper()}:{doc_hash_value[7:15]}:{slug}"

# IR to Finding helpers
def _spanref(s: Span) -> SpanRef:
    return SpanRef(
        line_start=s.line_start, line_end=s.line_end,
        byte_start=s.byte_start, byte_end=s.byte_end,
        page=getattr(s, "page", None), # optional
    )

def _location(block: Optional[Block] = None, span: Optional[Span] = None) -> Location:
    return Location(
        block_id=(block.id if block else None),
        span=(_spanref(span) if span else None),
    )


# base_detector ------------------------------------------------------------

class BaseDetector:

    # override in subclasses
    code: str = "BASE"
    name: str = "BaseDetector"
    version: str = "0.0.1"

    def __init__(self, *, run_id: Optional[str] = None):
        self.info = DetectorInfo(code=self.code, name=self.name, version=self.version, run_id=run_id)

    def detect(self, path: Path) -> List[Finding]:
        """Parse a file to IR, compute hash, run detector on IR."""
        doc: Document = parse_markdown(path)
        h = doc_hash(path)
        return self.detect_on_ir(doc, h)

    def write_findings(self, findings: List[Finding], outdir: Path) -> List[Path]:
        """Write findings to JSON files in the specified output directory."""
        outp = outdir
        outp.mkdir(parents=True, exist_ok=True)
        written: List[Path] = []
        for f in findings:
            path = outp / (f.finding_id.replace(":", "-") + ".json")
            path.write_text(f.model_dump_json(indent=2), encoding="utf-8")
            written.append(path)
        return written

    # override in subclasses ------------------------------------------------------------

    def detect_on_ir(self, doc: Document, doc_hash_value: str) -> List[Finding]:
        raise NotImplementedError

    def emit(
        self,
        *,
        doc: Document,
        doc_hash_value: str,
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
            loc = _location(anchor_block, anchor_span)

        evidence: List[Any] = []
        if anchor_span:
            evidence.append(TextSpan(text=None, span=_spanref(anchor_span)))
        if anchor_block:
            evidence.append(BlockRef(block_ids=[anchor_block.id]))
        if extra_evidence:
            evidence.extend(extra_evidence)

        return Finding(
            detector=self.info,
            document=DocumentRef(source_path=doc.source_path, hash=doc_hash_value),
            finding_id=make_finding_id(self.code, doc_hash_value, slug),
            doc_id=doc_hash_value,
            code=self.code,
            title=title,
            message=message,
            severity=severity,
            confidence=confidence,
            locations=([loc] if loc else None),
            evidence=evidence,
            tags=(tags or []),
        )

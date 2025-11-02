"""Base detector interface.

Provides a `BaseDetector` with helpers for building findings and outputting them.
Subclasses implement `detect`.
"""

from pathlib import Path
from typing import List, Optional, Any, Dict, Union, Literal, Type

from ..schemas.ir import (
    Document,
    Span,
    Block,
    Heading,
    Paragraph,
    ListBlock,
    ListItem,
    CodeBlock,
    Quote,
    Table,
    Figure,
)
from ..schemas.finding import (
    Finding,
    DetectorInfo,
    DocumentRef,
    Location,
    SpanRef,
    BlockRef,
    TextSpan,
)
from ..util import compute_doc_hash

BlockType = Literal[
    "Heading", "Paragraph", "List", "CodeBlock", "Quote", "Table", "Figure"
]


# --- Helpers
# ID format: 'CODE:hash8:slug'
def _build_finding_id(code: str, doc_hash: str, slug: str) -> str:
    return f"{code.upper()}:{doc_hash[7:15]}:{slug}"


# IR to Finding helpers
def _build_spanref(s: Span) -> SpanRef:
    return SpanRef(
        line_start=s.line_start,
        line_end=s.line_end,
        byte_start=s.byte_start,
        byte_end=s.byte_end,
        page=getattr(s, "page", None),
        bbox=getattr(s, "bbox", None),
    )


def _build_location(
    block: Optional[Block] = None, span: Optional[Span] = None
) -> Location:
    return Location(
        block_id=(block.id if block else None),
        span=(_build_spanref(span) if span else None),
    )


class BaseDetector:

    # override in subclasses
    code: str = "BASE"
    name: str = "BaseDetector"
    version: str = "0.1"

    # Subclasses may define a param_spec
    param_spec: Dict[str, Any] = {}

    runs_before_parsing: bool = False

    def __init__(
        self, *, run_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ):
        self.params: Dict[str, Any] = params or {}
        self.info = DetectorInfo(
            code=self.code,
            name=self.name,
            version=self.version,
            run_id=run_id,
            params=(self.params or None),
        )

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        """Run detector on the given document and return a list of findings."""
        raise NotImplementedError

    def detect_file(self, file_path: Path) -> List[Finding]:
        """Run detector on a file before parsing (optional)."""
        if not self.runs_before_parsing:
            return NotImplementedError
        return []

    def get_blocks(
        self,
        doc: Document,
        block_types: Optional[Union[BlockType, List[BlockType]]] = None,
        start_idx: Optional[int] = None,
        end_idx: Optional[int] = None,
    ) -> List[Block]:
        """Get blocks from document, optionally filtered by type and range."""
        # Apply range slicing
        blocks = doc.blocks[start_idx:end_idx]

        # Apply type filtering
        if block_types is None:
            return blocks

        # Normalize to list
        if isinstance(block_types, str):
            block_types = [block_types]

        return [b for b in blocks if b.type in block_types]

    def count_blocks(
        self,
        doc: Document,
        block_types: Optional[Union[BlockType, List[BlockType]]] = None,
    ) -> int:
        """Count blocks in document, optionally filtered by type."""
        return len(self.get_blocks(doc, block_types))

    def extract_text(
        self,
        doc: Document,
        block_types: Optional[Union[BlockType, List[BlockType]]] = None,
        start_idx: Optional[int] = None,
        end_idx: Optional[int] = None,
        separator: str = "\n",
    ) -> str:
        """Extract text from blocks, optionally filtered by type and range."""
        blocks = self.get_blocks(doc, block_types, start_idx, end_idx)
        texts = []

        for block in blocks:
            text = self._extract_text_from_block(block)
            if text:
                texts.append(text)

        return separator.join(texts)

    def _extract_text_from_block(self, block: Block) -> str:
        """
        Extract text content from a single block.
        Handles all block types appropriately.
        """
        if isinstance(block, (Heading, Paragraph, Quote, CodeBlock)):
            return block.text or ""

        if isinstance(block, ListBlock):
            # Extract text from all list items recursively
            texts = []
            for item in block.items:
                if item.text:
                    texts.append(item.text)
                # Handle nested lists
                if item.sublists:
                    for sublist in item.sublists:
                        texts.append(self._extract_text_from_block(sublist))
            return " ".join(texts)

        if isinstance(block, Table):
            # Extract text from table cells
            texts = []
            if block.header:
                texts.extend(block.header)
            if block.rows:
                for row in block.rows:
                    texts.extend(row)
            return " ".join(texts)

        if isinstance(block, Figure):
            # Extract alt text, title, or caption
            return block.caption or block.alt or block.title or ""

        return ""

    def count_words(self, text: str) -> int:
        return len(text.split())

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
        severity_rank: int = 2,
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
            severity_rank=severity_rank,
            confidence=confidence,
            locations=([loc] if loc else None),
            evidence=evidence,
            tags=(tags or []),
        )

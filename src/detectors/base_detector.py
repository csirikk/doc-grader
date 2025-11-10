"""Base detector interface.

Provides a `BaseDetector` with helpers for building findings and outputting them.
Subclasses implement `detect`.
"""

import re
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
from ..schemas.ir import DocumentMeta, SectionBoundary
from ..util import compute_doc_hash

BlockType = Literal[
    "Heading", "Paragraph", "List", "CodeBlock", "Quote", "Table", "Figure"
]

# Constants for block type filtering
CONTENT_BLOCK_TYPES = ["Paragraph", "List", "CodeBlock", "Quote", "Table"]
HEADING_BLOCK_TYPES = ["Heading"]

# Patterns for detecting table of contents sections
TOC_PATTERNS = [
    r"\btable\s+of\s+contents\b",
    r"\bobsah\b",
    r"\bcontents\b",
    r"\btoc\b",
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
        self._slug_counts = {}
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

    def ensure_meta(self, doc: Document) -> DocumentMeta:
        """Ensure document has metadata object, creating if needed."""
        if doc.meta is None:
            doc.meta = DocumentMeta()
        return doc.meta

    def _is_toc_heading(self, heading_text: str) -> bool:
        """Check if a heading indicates a table of contents."""
        text_lower = heading_text.lower().strip()
        for pattern in TOC_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _is_toc_block(self, block: Block) -> bool:
        """Check if a block is part of a TOC section."""
        if block.meta is None:
            return False
        return block.meta.get("is_toc_content", False)

    def get_section_boundaries(self, doc: Document) -> List[SectionBoundary]:
        """Get or compute section boundaries.

        Computes once and caches in document metadata for reuse by other detectors.
        Also marks all blocks in TOC sections with metadata for easy identification.
        """
        meta = self.ensure_meta(doc)

        if meta.section_boundaries is not None:
            return meta.section_boundaries

        # Compute section boundaries
        headings = self.get_blocks(doc, "Heading")
        if not headings:
            meta.section_boundaries = []
            return []

        # Build block index for O(1) lookup
        if meta.block_to_index is None:
            meta.block_to_index = {b.id: i for i, b in enumerate(doc.blocks)}

        sections = []
        for i, heading in enumerate(headings):
            start_idx = meta.block_to_index[heading.id]
            # Next headings position or end of document
            end_idx = (
                meta.block_to_index[headings[i + 1].id]
                if i + 1 < len(headings)
                else len(doc.blocks)
            )

            # Count content blocks in this section
            section_blocks = doc.blocks[start_idx + 1 : end_idx]
            content_count = sum(
                1 for b in section_blocks if b.type in CONTENT_BLOCK_TYPES
            )

            is_toc = self._is_toc_heading(heading.text)

            sections.append(
                SectionBoundary(
                    heading_id=heading.id,
                    heading_text=heading.text,
                    heading_level=heading.level,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    content_block_count=content_count,
                    is_toc=is_toc,
                )
            )

        # Mark all blocks in TOC sections with metadata for easy identification
        for section in sections:
            if section.is_toc:
                for block_idx in range(section.start_idx, section.end_idx):
                    block = doc.blocks[block_idx]
                    if block.meta is None:
                        block.meta = {}
                    block.meta["is_toc_content"] = True

        # Cache for future use
        meta.section_boundaries = sections
        meta.total_headings = len(headings)

        # Compute simple structure statistics for downstream use
        content_counts = [s.content_block_count for s in sections]
        if content_counts:
            meta.empty_section_count = sum(1 for c in content_counts if c == 0)
            meta.avg_content_blocks_per_section = sum(content_counts) / len(
                content_counts
            )
        else:
            meta.empty_section_count = 0
            meta.avg_content_blocks_per_section = 0.0

        if meta.heading_to_index is None:
            meta.heading_to_index = {h.id: i for i, h in enumerate(headings)}

        return sections

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

    def _make_slug(self, doc_hash: str, slug: str) -> str:
        key = (self.code, doc_hash, slug)
        count = self._slug_counts.get(key, 0)
        self._slug_counts[key] = count + 1
        if count == 0:
            return slug
        return f"{slug}-{count}"

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

        new_slug = self._make_slug(doc_hash, slug)

        return Finding(
            detector=self.info,
            document=DocumentRef(source_path=doc.source_path, hash=doc_hash),
            finding_id=_build_finding_id(self.code, doc_hash, new_slug),
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

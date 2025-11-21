"""Text normalization for parsed IR documents.

Applies post-parse normalization to text content in IR blocks.
"""

from __future__ import annotations

import re
from ..schemas.ir import (
    Block,
    CodeBlock,
    Document,
    Heading,
    ListBlock,
    Paragraph,
    Quote,
    Table,
)


def _normalize_text(text: str) -> str:
    """Strip repeated punctuation, collapse whitespace."""
    text = re.sub(r"[.\-–—…•·]{2,}", " ", text)  # repeated punctuation to space
    text = re.sub(r"\s+", " ", text)  # collapse whitespace
    return text.strip()


def _normalize_list(list_block: ListBlock) -> None:
    """Recursively normalize list items and sublists."""
    for item in list_block.items:
        item.text = _normalize_text(item.text)
        if item.sublists:
            for sublist in item.sublists:
                _normalize_list(sublist)


def _normalize_table(table: Table) -> None:
    """Normalize table header and rows."""
    if table.header:
        table.header = [_normalize_text(cell) for cell in table.header]
    if table.rows:
        table.rows = [[_normalize_text(cell) for cell in row] for row in table.rows]


def normalize_document(doc: Document) -> Document:
    """Normalize all text content in document blocks in-place. Returns doc for chaining."""
    for block in doc.blocks:
        if isinstance(block, (Heading, Paragraph, Quote)):
            block.text = _normalize_text(block.text)
        elif isinstance(block, ListBlock):
            _normalize_list(block)
        elif isinstance(block, Table):
            _normalize_table(block)
        # omit CodeBlock and Figure
    return doc

"""Intermediate Representation schema."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from .base import StrictModel

if TYPE_CHECKING:
    from docling_core.types.doc.document import (
        DoclingDocument,
        DocumentOrigin,
    )


class DocumentRef(StrictModel):
    """Reference to the source document."""

    source_path: str
    origin: DocumentOrigin | None = None
    binary_hash: int | None = Field(
        default=None,
        description=("Docling content hash (binary_hash)."),
    )


class Document(StrictModel):
    """Docling Document wrapper for custom stats and metadata."""

    doc_ref: DocumentRef
    docling_doc: DoclingDocument = Field(
        exclude=True, description="The underlying Docling document"
    )

    # Custom stats
    total_words: int = Field(default=0, description="Total detected words")
    total_chars: int = Field(default=0, description="Total detected characters")
    total_paragraphs: int = Field(default=0, description="Total detected paragraphs")
    total_headings: int = Field(default=0, description="Total detected headings")
    text_items: dict[str, Any] = Field(
        default_factory=dict,
        exclude=True,
        description="Map of cref to Docling TextItem",
    )

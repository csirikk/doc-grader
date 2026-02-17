"""Intermediate Representation schema."""

from __future__ import annotations

from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel
from pydantic import Field

from .base import StrictModel


class DocumentRef(StrictModel):
    """Reference to the source document."""

    source_path: str
    sha256: str | None = Field(default=None, description="sha256:<64hex> hash")
    mimetype: str | None = None


class Document(StrictModel):
    """Docling Document wrapper for custom stats and metadata."""

    document_ref: DocumentRef
    docling_doc: DoclingDocument = Field(
        exclude=True, description="The underlying Docling document"
    )

    # Custom stats
    total_words: int = Field(default=0, description="Total detected words")
    total_paragraphs: int = Field(default=0, description="Total detected paragraphs")
    total_headings: int = Field(default=0, description="Total detected headings")

    @classmethod
    def from_docling(
        cls,
        doc: DoclingDocument,
        source_path: str,
        sha256: str | None,
        mimetype: str | None = None,
    ) -> Document:
        """Calculates custom stats instantly after creation."""

        words, paras, headings = 0, 0, 0
        paragraph_labels = {DocItemLabel.TEXT, DocItemLabel.PARAGRAPH}

        for item, _ in doc.iterate_items():
            if item.label == DocItemLabel.SECTION_HEADER:
                headings += 1

            if item.label in paragraph_labels:
                paras += 1

            if item.text:
                words += len(item.text.split())

        return cls(
            document_ref=DocumentRef(
                source_path=source_path,
                sha256=sha256,
                mimetype=mimetype,
            ),
            docling_doc=doc,
            total_words=words,
            total_paragraphs=paras,
            total_headings=headings,
        )

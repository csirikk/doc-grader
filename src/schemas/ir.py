from typing import Optional

from docling.datamodel.document import DoclingDocument, TextItem
from docling_core.types.doc.labels import DocItemLabel
from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    """Docling Document wrapper for custom stats and metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    source_path: str = Field(description="Original file path")
    sha256: str = Field(description="sha256:<64hex> hash of the file")
    mimetype: Optional[str] = Field(default=None)

    docling_doc: DoclingDocument = Field(description="The underlying Docling document")

    # Custom stats
    total_words: int = Field(default=0, description="Total detected words")
    total_paragraphs: int = Field(default=0, description="Total detected paragraphs")
    total_headings: int = Field(default=0, description="Total detected headings")

    @classmethod
    def from_docling(
        cls,
        doc: DoclingDocument,
        source_path: str,
        sha256: str,
        mimetype: Optional[str] = None,
    ) -> "Document":
        """Calculates custom stats instantly after creation."""
        words, paras, headings = 0, 0, 0

        for item, _ in doc.iterate_items():
            if isinstance(item, TextItem):
                if item.label == DocItemLabel.TEXT:
                    paras += 1
                elif item.label == DocItemLabel.SECTION_HEADER:
                    headings += 1

                if item.text:
                    words += len(item.text.split())

        return cls(
            docling_doc=doc,
            source_path=source_path,
            sha256=sha256,
            mimetype=mimetype,
            total_words=words,
            total_paragraphs=paras,
            total_headings=headings,
        )

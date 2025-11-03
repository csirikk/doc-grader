"""Internal representation (IR) models for parsed documents."""

from typing import Annotated, Literal, Optional, Union, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class BBox(BaseModel):
    """Bounding box in page coordinates for PDFs."""

    x0: float
    y0: float
    x1: float
    y1: float
    model_config = dict(extra="forbid")


class Span(BaseModel):
    source_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    byte_start: Optional[int] = None
    byte_end: Optional[int] = None
    page: Optional[int] = None
    bbox: Optional[BBox] = None
    model_config = dict(extra="forbid")

    @field_validator("line_end")
    @classmethod
    def _line_end_ge_start(cls, v, info):
        ls = info.data.get("line_start")
        if v is not None and ls is not None and v < ls:
            raise ValueError("line_end must be >= line_start")
        return v

    @field_validator("byte_end")
    @classmethod
    def _byte_end_ge_start(cls, v, info):
        bs = info.data.get("byte_start")
        if v is not None and bs is not None and v < bs:
            raise ValueError("byte_end must be >= byte_start")
        return v


class Heading(BaseModel):
    type: Literal["Heading"] = "Heading"
    id: str
    level: int
    text: str
    span: Span
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


class Paragraph(BaseModel):
    type: Literal["Paragraph"] = "Paragraph"
    id: str
    text: str
    span: Span
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


class ListItem(BaseModel):
    text: str
    sublists: Optional[List["ListBlock"]] = None
    span: Optional[Span] = None
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


class ListBlock(BaseModel):
    type: Literal["List"] = "List"
    id: str
    ordered: bool
    start: Optional[int] = None
    items: List[ListItem]
    span: Span
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


class CodeBlock(BaseModel):
    type: Literal["CodeBlock"] = "CodeBlock"
    id: str
    language: Optional[str] = None
    text: str
    span: Span
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


class Quote(BaseModel):
    type: Literal["Quote"] = "Quote"
    id: str
    text: str
    span: Span
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


class Table(BaseModel):
    type: Literal["Table"] = "Table"
    id: str
    header: Optional[List[str]] = None
    rows: Optional[List[List[str]]] = None
    span: Span
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


class Figure(BaseModel):
    type: Literal["Figure"] = "Figure"
    id: str
    kind: Literal["image"] = "image"
    src: str
    alt: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    span: Span
    meta: Optional[Dict[str, Any]] = None
    model_config = dict(extra="forbid")


Block = Annotated[
    Union[Heading, Paragraph, ListBlock, CodeBlock, Quote, Table, Figure],
    Field(discriminator="type"),
]


class SectionBoundary(BaseModel):
    """A document section defined by a heading and its content range."""

    heading_id: str
    heading_text: str
    heading_level: int
    start_idx: int  # Block index where section starts (the heading itself)
    end_idx: int  # Block index where section ends
    content_block_count: int
    is_toc: bool = False  # True if this section is the table of contents

    model_config = dict(extra="forbid")


class DocumentMeta(BaseModel):
    """Structured metadata enriched by detectors during analysis."""

    # Enriched by StructureAnalyzer
    section_boundaries: Optional[List[SectionBoundary]] = None
    heading_to_index: Optional[Dict[str, int]] = None
    block_to_index: Optional[Dict[str, int]] = None
    total_headings: Optional[int] = None

    # Enriched by LengthAnalyzer
    total_words: Optional[int] = None
    total_paragraphs: Optional[int] = None

    # Others can be added here
    model_config = dict(extra="allow")


class Document(BaseModel):
    schema_version: Literal["md-ir/0.2"] = "md-ir/0.2"
    source_path: str
    meta: Optional[DocumentMeta] = None
    blocks: List[Block]
    model_config = dict(extra="forbid")


# --- Self-test
if __name__ == "__main__":
    from pydantic import ValidationError

    try:
        test = Document(
            source_path="test.md",
            blocks=[
                Heading(
                    id="h-1",
                    level=1,
                    text="Title",
                    span=Span(
                        source_path="test.md",
                        line_start=1,
                        line_end=1,
                        byte_start=0,
                        byte_end=5,
                    ),
                ),
                Paragraph(
                    id="p-1",
                    text="Hello world.",
                    span=Span(
                        source_path="test.md",
                        line_start=3,
                        line_end=3,
                        byte_start=12,
                        byte_end=24,
                    ),
                ),
                ListBlock(
                    id="l-1",
                    ordered=False,
                    items=[ListItem(text="item 1"), ListItem(text="item 2")],
                    span=Span(source_path="test.md", line_start=5, line_end=6),
                ),
                CodeBlock(
                    id="c-1",
                    language="python",
                    text="print('hi')",
                    span=Span(source_path="test.md", line_start=8, line_end=10),
                ),
                Quote(
                    id="q-1",
                    text="A quoted line.",
                    span=Span(source_path="test.md", line_start=12, line_end=12),
                ),
                Table(
                    id="t-1",
                    header=["A", "B"],
                    rows=[["1", "2"], ["3", "4"]],
                    span=Span(source_path="test.md", line_start=14, line_end=17),
                ),
                Figure(
                    id="f-1",
                    kind="image",
                    src="img/example.png",
                    alt="example",
                    caption="Figure 1: example image",
                    span=Span(source_path="test.md", line_start=19, line_end=19),
                ),
            ],
        )
        print(test.model_dump_json(indent=2))
        print(f"OK: {test.schema_version} instance with {len(test.blocks)} blocks.")
    except ValidationError as e:
        print("ValidationError:", e)
        raise

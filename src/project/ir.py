from typing import Annotated, Literal, Optional, Union, List
from pydantic import BaseModel, Field

class Span(BaseModel):
    source_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    byte_start: Optional[int] = None
    byte_end: Optional[int] = None

class Heading(BaseModel):
    type: Literal["Heading"] = "Heading"
    id: str
    level: int
    text: str
    span: Span

class Paragraph(BaseModel):
    type: Literal["Paragraph"] = "Paragraph"
    id: str
    text: str
    span: Span

class ListItem(BaseModel):
    text: str
    children: Optional[List["ListItem"]] = None

class ListBlock(BaseModel):
    type: Literal["List"] = "List"
    id: str
    ordered: bool
    items: List[ListItem]
    span: Span

class CodeBlock(BaseModel):
    type: Literal["CodeBlock"] = "CodeBlock"
    id: str
    language: Optional[str] = None
    text: str
    span: Span

class Quote(BaseModel):
    type: Literal["Quote"] = "Quote"
    id: str
    text: str
    span: Span

class Table(BaseModel):
    type: Literal["Table"] = "Table"
    id: str
    header: Optional[List[str]] = None
    rows: Optional[List[List[str]]] = None
    span: Span

class Figure(BaseModel):
    type: Literal["Figure"] = "Figure"
    id: str
    kind: Literal["image"] = "image"
    src: str
    alt: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    span: Span

Block = Annotated[
    Union[Heading, Paragraph, ListBlock, CodeBlock, Quote, Table, Figure],
    Field(discriminator="type")
]

class Document(BaseModel):
    schema_version: Literal["md-ir/0.2"] = "md-ir/0.2"
    source_path: str
    meta: Optional[dict] = None
    blocks: List[Block]

# test ---------------------------------------------------------------
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
                    span=Span(source_path="test.md", line_start=1, line_end=1, byte_start=0, byte_end=5),
                ),
                Paragraph(
                    id="p-1",
                    text="Hello world.",
                    span=Span(source_path="test.md", line_start=3, line_end=3, byte_start=12, byte_end=24),
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

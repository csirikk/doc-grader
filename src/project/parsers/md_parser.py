from pathlib import Path
from ..ir import Document, Paragraph, Span

def parse_markdown(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    span = Span(
        source_path=str(path),
        line_start=1,
        line_end=len(lines) if lines else 1,
        byte_start=0,
        byte_end=len(text.encode("utf-8"))
    )
    doc = Document(source_path=str(path), blocks=[
        Paragraph(id="p-1", text=text.strip(), span=span)
    ])
    return doc

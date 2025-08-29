import pprint
from pathlib import Path
from typing import List
from markdown_it import MarkdownIt
from markdown_it.token import Token

from ..ir import Document, Paragraph, Span, Heading

# global parser instance
md = MarkdownIt("commonmark") # no plugins yet

def _byte_starts(text: str) -> List[int]:
    """Return UTF-8 byte offsets at each line start (0-based)."""
    starts = [0]
    acc = 0
    for line in text.splitlines(keepends=True):
        acc += len(line.encode("utf-8"))
        starts.append(acc)
    return starts

def _span(path: Path, tok: Token, byte_starts: List[int]) -> Span:
    """Build a Span from a token line map, falling back if absent."""
    if tok.map is None:
        return Span(source_path=str(path))
    s, e = tok.map  # 0-based, end exclusive
    return Span(
        source_path=str(path),
        line_start=s + 1,
        line_end=max(s + 1, e),
        byte_start=byte_starts[s],
        byte_end=byte_starts[e],
    )

def parse_markdown(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    tokens = md.parse(text)
    bs = _byte_starts(text)

    # DEBUG
    for idx, t in enumerate(tokens):
        print(f"--- token {idx} ---")
        pprint.pp(t.as_dict())

    blocks = []
    i = 0
    while i < len(tokens):
        t = tokens[i]

        # Headings: heading_open, inline, heading_close
        if t.type == "heading_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
            title = inline.content if inline else ""
            span = _span(path, t, bs)
            level = int(t.tag[1])  # 'h1' -> 1
            blocks.append(Heading(
                id=f"h-{len(blocks)+1}",
                level=level,
                text=title,
                span=span,
            ))
            i += 3
            continue

        # Paragraphs: paragraph_open, inline, paragraph_close
        if t.type == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
            content = inline.content if inline else ""
            span = _span(path, t, bs)
            # normalize internal whitespace a bit
            content = " ".join(content.split())
            blocks.append(Paragraph(
                id=f"p-{len(blocks)+1}",
                text=content,
                span=span,
            ))
            i += 3
            continue

        i += 1

    if not blocks: # just a fallback: whole doc becomes 1 block
        lines = text.splitlines()
        blocks.append(Paragraph(
            id="p-1",
            text=text.strip(),
            span=Span(
                source_path=str(path),
                line_start=1,
                line_end=len(lines) if lines else 1,
                byte_start=0,
                byte_end=len(text.encode("utf-8")),
            ),
        ))

    return Document(source_path=str(path), blocks=blocks)

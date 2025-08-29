import pprint
from pathlib import Path
from typing import List, Tuple, Optional
from markdown_it import MarkdownIt
from markdown_it.token import Token

from ..ir import Document, Paragraph, Span, Heading, CodeBlock, ListBlock, ListItem, Quote

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


def _parse_list(tokens: List[Token], i: int, path: Path, bs: List[int]) -> Tuple[ListBlock, int]:
    """Parse a list starting at tokens[i] (a list_open). Returns (ListBlock, index_after_close)."""
    t = tokens[i]
    is_ordered = (t.type == "ordered_list_open")
    span = _span(path, t, bs)
    start: Optional[int] = None
    if is_ordered and getattr(t, "attrs", None):
        try:
            start = int(t.attrs.get("start")) if t.attrs.get("start") is not None else None
        except Exception:
            start = None

    items: List[ListItem] = []
    j = i + 1
    close_type = "ordered_list_close" if is_ordered else "bullet_list_close"

    while j < len(tokens) and tokens[j].type != close_type:
        if tokens[j].type == "list_item_open":
            item_span = _span(path, tokens[j], bs)
            k = j + 1
            depth = 0
            parts: List[str] = []
            sublists: List[ListBlock] = []

            while k < len(tokens) and tokens[k].type != "list_item_close":
                current_token = tokens[k]
                if current_token.type in ("bullet_list_open", "ordered_list_open"):
                    depth += 1
                    if depth == 1:
                        sublist, k = _parse_list(tokens, k, path, bs)
                        sublists.append(sublist)
                        continue
                elif current_token.type in ("bullet_list_close", "ordered_list_close"):
                    depth -= 1

                if depth == 0 and current_token.type == "inline" and current_token.content:
                    parts.append(current_token.content)
                k += 1

            item = ListItem(
                text=" ".join(" ".join(parts).split()),
                span=item_span,
                sublists=sublists or None,
            )
            items.append(item)
            j = k + 1
        else:
            j += 1

    list_block = ListBlock(
        id=f"l-{len(items)}-{(span.line_start or 0)}",
        ordered=is_ordered,
        start=start,
        items=items,
        span=span,
    )
    return list_block, j + 1

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
        
        # Codeblocks: fence
        if t.type == "fence":
            span = _span(path, t, bs)
            blocks.append(CodeBlock(
                id=f"c-{len(blocks)+1}",
                language=(t.info or "").strip() or None,
                text=t.content,
                span=span,
            ))
            i += 1
            continue

        # Lists
        if t.type in ("bullet_list_open", "ordered_list_open"):
            list_block, new_i = _parse_list(tokens, i, path, bs)
            blocks.append(list_block)
            i = new_i
            continue

        # Quotes
        if t.type == "blockquote_open":
            span = _span(path, t, bs)
            j = i + 1
            text_parts: list[str] = []
            while j < len(tokens) and tokens[j].type != "blockquote_close":
                if tokens[j].type == "inline":
                    text_parts.append(tokens[j].content)
                j += 1
            text = " ".join(" ".join(text_parts).split())
            blocks.append(Quote(
                id=f"q-{len(blocks)+1}",
                text=text,
                span=span,
            ))
            i = j + 1
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

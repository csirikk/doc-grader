import pprint
from pathlib import Path
from typing import List, Tuple, Optional
from markdown_it import MarkdownIt
from markdown_it.token import Token

from ..ir import Document, Paragraph, Span, Heading, CodeBlock, ListBlock, ListItem, Quote

# global parser instance
md = MarkdownIt("commonmark") # no plugins yet

def compute_byte_starts(text: str) -> List[int]:
    """Return UTF-8 byte offsets at each line start (0-based)."""
    starts = [0]
    acc = 0
    for line in text.splitlines(keepends=True):
        acc += len(line.encode("utf-8"))
        starts.append(acc)
    return starts

def build_span(path: Path, tok: Token, byte_starts: List[int]) -> Span:
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


def _parse_list(tokens: List[Token], idx_outer: int, path: Path, byte_starts: List[int]) -> Tuple[ListBlock, int]:
    """Parse a list starting at tokens[idx_outer] (a list_open). Returns (ListBlock, index_after_close)."""
    tok_list_open = tokens[idx_outer]
    is_ordered = (tok_list_open.type == "ordered_list_open")
    span = build_span(path, tok_list_open, byte_starts)
    start: Optional[int] = None
    if is_ordered and getattr(tok_list_open, "attrs", None):
        try:
            start = int(tok_list_open.attrs.get("start")) if tok_list_open.attrs.get("start") is not None else None
        except Exception:
            start = None

    items: List[ListItem] = []
    idx_inner = idx_outer + 1
    close_type = "ordered_list_close" if is_ordered else "bullet_list_close"

    while idx_inner < len(tokens) and tokens[idx_inner].type != close_type:
        if tokens[idx_inner].type == "list_item_open":
            item_span = build_span(path, tokens[idx_inner], byte_starts)
            idx_child = idx_inner + 1
            nested_depth = 0
            parts: List[str] = []
            sublists: List[ListBlock] = []

            while idx_child < len(tokens) and tokens[idx_child].type != "list_item_close":
                tok_inner = tokens[idx_child]
                if tok_inner.type in ("bullet_list_open", "ordered_list_open"):
                    nested_depth += 1
                    if nested_depth == 1:
                        sublist, idx_child = _parse_list(tokens, idx_child, path, byte_starts)
                        sublists.append(sublist)
                        continue
                elif tok_inner.type in ("bullet_list_close", "ordered_list_close"):
                    nested_depth -= 1

                if nested_depth == 0 and tok_inner.type == "inline" and tok_inner.content:
                    parts.append(tok_inner.content)
                idx_child += 1

            item = ListItem(
                text=" ".join(" ".join(parts).split()),
                span=item_span,
                sublists=sublists or None,
            )
            items.append(item)
            idx_inner = idx_child + 1
        else:
            idx_inner += 1

    list_block = ListBlock(
        id=f"l-{len(items)}-{(span.line_start or 0)}",
        ordered=is_ordered,
        start=start,
        items=items,
        span=span,
    )
    idx_after = idx_inner + 1
    return list_block, idx_after

def parse_markdown(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    tokens = md.parse(text)
    byte_starts = compute_byte_starts(text)

    # DEBUG
    for idx, tok_outer in enumerate(tokens):
        print(f"--- token {idx} ---")
        pprint.pp(tok_outer.as_dict())

    blocks = []
    idx_outer = 0
    while idx_outer < len(tokens):
        tok_outer = tokens[idx_outer]

        # Headings: heading_open, inline, heading_close
        if tok_outer.type == "heading_open":
            inline = tokens[idx_outer + 1] if idx_outer + 1 < len(tokens) and tokens[idx_outer + 1].type == "inline" else None
            title = inline.content if inline else ""
            span = build_span(path, tok_outer, byte_starts)
            level = int(tok_outer.tag[1])  # 'h1' -> 1
            blocks.append(Heading(
                id=f"h-{len(blocks)+1}",
                level=level,
                text=title,
                span=span,
            ))
            idx_outer += 3
            continue

        # Paragraphs: paragraph_open, inline, paragraph_close
        if tok_outer.type == "paragraph_open":
            inline = tokens[idx_outer + 1] if idx_outer + 1 < len(tokens) and tokens[idx_outer + 1].type == "inline" else None
            content = inline.content if inline else ""
            span = build_span(path, tok_outer, byte_starts)
            # normalize internal whitespace a bit
            content = " ".join(content.split())
            blocks.append(Paragraph(
                id=f"p-{len(blocks)+1}",
                text=content,
                span=span,
            ))
            idx_outer += 3
            continue
        
        # Codeblocks: fence
        if tok_outer.type == "fence":
            span = build_span(path, tok_outer, byte_starts)
            blocks.append(CodeBlock(
                id=f"c-{len(blocks)+1}",
                language=(tok_outer.info or "").strip() or None,
                text=tok_outer.content,
                span=span,
            ))
            idx_outer += 1
            continue

        # Lists
        if tok_outer.type in ("bullet_list_open", "ordered_list_open"):
            list_block, idx_after = _parse_list(tokens, idx_outer, path, byte_starts)
            blocks.append(list_block)
            idx_outer = idx_after
            continue

        # Quotes
        if tok_outer.type == "blockquote_open":
            span = build_span(path, tok_outer, byte_starts)
            idx_inner = idx_outer + 1
            text_parts: list[str] = []
            while idx_inner < len(tokens) and tokens[idx_inner].type != "blockquote_close":
                if tokens[idx_inner].type == "inline":
                    text_parts.append(tokens[idx_inner].content)
                idx_inner += 1
            text = " ".join(" ".join(text_parts).split())
            blocks.append(Quote(
                id=f"q-{len(blocks)+1}",
                text=text,
                span=span,
            ))
            idx_outer = idx_inner + 1
            continue


        idx_outer += 1

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

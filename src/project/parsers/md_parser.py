import pprint
from pathlib import Path
from typing import List, Optional, Tuple

from markdown_it import MarkdownIt
from markdown_it.token import Token

from ..schemas.ir import (
    Document,
    Paragraph,
    Span,
    Heading,
    CodeBlock,
    ListBlock,
    ListItem,
    Quote,
    Figure,
    Table,
)
from ..util import next_id
from .. import logger

# global parser instance
md = MarkdownIt("commonmark").enable('table')

# Utilities ---------------------------------------------------------------------------

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

def _norm(text: str) -> str:
    """Normalize whitespace."""
    return " ".join((text or "").split())

def _append_figure_from_image_token(img_tok: Token, span: Span, blocks: List) -> None:
    """Create and append a Figure from a markdown-it image token."""
    attrs = getattr(img_tok, "attrs", None) or {}

    src = (
        (attrs.get("src") if isinstance(attrs, dict) else None)
        or (img_tok.attrGet("src") if hasattr(img_tok, "attrGet") else None)
        or ""
    )
    title = (
        (attrs.get("title") if isinstance(attrs, dict) else None)
        or (img_tok.attrGet("title") if hasattr(img_tok, "attrGet") else None)
        or None
    )

    # alt text is in the token content
    alt = (img_tok.content or "").strip() or None

    blocks.append(
        Figure(
            id=next_id("f"),
            kind="image",
            src=src,
            alt=alt,
            title=title,
            caption=title or alt,
            span=span,
        )
    )


def _emit_figures_from_inline(inline_tok: Token, span: Span, blocks: List) -> int:
    """
    Emit Figure(s) for any images in this inline token. Supports plain images and link-wrapped images: link_open. image, link_close.
    Returns number of figures emitted.
    """
    kids = inline_tok.children or []
    count = 0
    idx = 0
    while idx < len(kids):
        t = kids[idx]
        if t.type == "image":
            _append_figure_from_image_token(t, span, blocks)
            count += 1
            idx += 1
            continue
        if (
            t.type == "link_open"
            and idx + 2 < len(kids)
            and kids[idx + 1].type == "image"
            and kids[idx + 2].type == "link_close"
        ):
            _append_figure_from_image_token(kids[idx + 1], span, blocks)
            count += 1
            idx += 3
            continue
        idx += 1
    return count


def _inline_is_image_only(inline: Token) -> bool:
    """True if inline children contain only images/link-wrapped images/whitespace."""
    kids = inline.children or []
    contains_image = False
    idx = 0
    while idx < len(kids):
        t = kids[idx]
        if t.type in ("softbreak", "hardbreak") or (t.type == "text" and (t.content or "").strip() == ""):
            idx += 1
            continue
        if t.type == "image":
            contains_image = True
            idx += 1
            continue
        if idx + 2 < len(kids) and t.type == "link_open" and kids[idx + 1].type == "image" and kids[idx + 2].type == "link_close":
            contains_image = True
            idx += 3
            continue
        return False
    return contains_image


# Token handling ---------------------------------------------------------------------------

class TokenCursor:
    """Tiny cursor to navigate markdown-it tokens."""
    def __init__(self, tokens: List[Token], i: int = 0):
        self.tokens = tokens
        self.i = i

    def current(self) -> Optional[Token]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def peek(self, k: int = 1) -> Optional[Token]:
        j = self.i + k
        return self.tokens[j] if j < len(self.tokens) else None

    def advance(self, n: int = 1) -> None:
        self.i = min(self.i + n, len(self.tokens))

    def is_at_end(self) -> bool:
        return self.i >= len(self.tokens)


def consume_triplet(cursor: TokenCursor, open_type: str, close_type: str) -> Tuple[Optional[Token], Optional[Token]]:
    """
    Consume a block shaped as: open_type, (optional inline), close_type. Advances the cursor past the close token.
    Returns (open_tok, inline_tok_or_None).
    """
    t0 = cursor.current()
    if not t0 or t0.type != open_type:
        # advance one to avoid loop on malformed/unexpected tokens
        cursor.advance(1)
        return t0, None

    has_inline = cursor.peek(1) is not None and cursor.peek(1).type == "inline"
    if has_inline and cursor.peek(2) is not None and cursor.peek(2).type == close_type:
        open_tok = t0
        inline_tok = cursor.peek(1)
        cursor.advance(3)
        return open_tok, inline_tok

    if (not has_inline) and cursor.peek(1) is not None and cursor.peek(1).type == close_type:
        open_tok = t0
        cursor.advance(2)
        return open_tok, None

    # Unexpected -> advance one and return
    cursor.advance(1)
    return t0, None


def consume_container(cursor: TokenCursor, open_type: str, close_type: str) -> List[Token]:
    """
    Consume a container block from open_type to its matching close_type (inclusive), 
    returning the list of tokens inside the container (excluding the close). Advances the cursor to just after the close.
    """
    inside: List[Token] = []
    t0 = cursor.current()
    if not t0 or t0.type != open_type:
        # advance one to avoid loop on malformed/unexpected tokens
        cursor.advance(1)
        return inside

    depth = 0
    cursor.advance(1)  # move past the _open

    while not cursor.is_at_end():
        tok = cursor.current()
        if tok.type == open_type:
            depth += 1
            inside.append(tok)
            cursor.advance(1)
            continue
        if tok.type == close_type:
            if depth == 0:
                # consume the close and stop
                cursor.advance(1)
                break
            # keep going
            depth -= 1
            inside.append(tok)
            cursor.advance(1)
            continue
        inside.append(tok)
        cursor.advance(1)

    return inside


# Handlers (each consumes from the cursor and appends IR blocks) ---------------------------------------------------------------------------

def _handle_heading(cursor: TokenCursor, path: Path, byte_starts: List[int], blocks: List) -> None:
    open_tok, inline = consume_triplet(cursor, "heading_open", "heading_close")
    if not open_tok:
        return
    span = build_span(path, open_tok, byte_starts)
    level = int(open_tok.tag[1])  # 'h1' -> 1
    title = inline.content if inline else ""
    if inline:
        _emit_figures_from_inline(inline, span, blocks)
    blocks.append(Heading(id=next_id("h"), level=level, text=title, span=span))


def _handle_paragraph(cursor: TokenCursor, path: Path, byte_starts: List[int], blocks: List) -> None:
    open_tok, inline = consume_triplet(cursor, "paragraph_open", "paragraph_close")
    if not open_tok:
        return
    span = build_span(path, open_tok, byte_starts)
    if inline:
        _emit_figures_from_inline(inline, span, blocks)
        if _inline_is_image_only(inline):
            return
    content = _norm(inline.content) if inline and inline.content else ""
    blocks.append(Paragraph(id=next_id("p"), text=content, span=span))


def _handle_fence(cursor: TokenCursor, path: Path, byte_starts: List[int], blocks: List) -> None:
    tok = cursor.current()
    if not tok:
        cursor.advance(1)
        return
    span = build_span(path, tok, byte_starts)
    blocks.append(
        CodeBlock(
            id=next_id("c"),
            language=(tok.info or "").strip() or None,
            text=tok.content,
            span=span,
        )
    )
    cursor.advance(1)


def _parse_list_block(cursor: TokenCursor, path: Path, byte_starts: List[int], blocks: List) -> ListBlock:
    """Parse a list at the current cursor (assumes *_list_open). Returns a ListBlock and advances past close."""
    tok_open = cursor.current()
    is_ordered = tok_open.type == "ordered_list_open"
    span = build_span(path, tok_open, byte_starts)
    list_id = next_id("l")

    start: Optional[int] = None
    if is_ordered and getattr(tok_open, "attrs", None):
        try:
            start = int(tok_open.attrs.get("start")) if tok_open.attrs.get("start") is not None else None
        except Exception:
            start = None

    items: List[ListItem] = []

    # Consume the container and process its inner tokens
    inside = consume_container(
        cursor,
        "ordered_list_open" if is_ordered else "bullet_list_open",
        "ordered_list_close" if is_ordered else "bullet_list_close",
    )

    idx = 0
    while idx < len(inside):
        child_tok = inside[idx]
        if child_tok.type == "list_item_open":
            # consume one list item
            subcur = TokenCursor(inside, idx)
            item_tokens = consume_container(subcur, "list_item_open", "list_item_close")
            idx = subcur.i  # move idx to after the list_item_close within 'inside'

            item_span = build_span(path, child_tok, byte_starts)
            parts: List[str] = []
            sublists: List[ListBlock] = []
            emitted_figures = 0
            child_idx = 0
            while child_idx < len(item_tokens):
                child_tok = item_tokens[child_idx]
                if child_tok.type in ("bullet_list_open", "ordered_list_open"):
                    # recursive dive into nested list
                    nested_cur = TokenCursor(item_tokens, child_idx)
                    sublist = _parse_list_block(nested_cur, path, byte_starts, blocks)
                    sublists.append(sublist)
                    child_idx = nested_cur.i
                    continue
                if child_tok.type == "inline":
                    emitted_figures += _emit_figures_from_inline(child_tok, item_span, blocks)
                    if child_tok.content:
                        parts.append(child_tok.content)
                child_idx += 1

            text_value = None if (not parts and emitted_figures > 0) else _norm(" ".join(parts))
            items.append(
                ListItem(
                    text=text_value,
                    span=item_span,
                    sublists=sublists or None,
                )
            )
            continue

        # advance one to avoid loop on malformed/unexpected tokens
        idx += 1

    return ListBlock(
        id=list_id,
        ordered=is_ordered,
        start=start,
        items=items,
        span=span,
    )


def _handle_list(cursor: TokenCursor, path: Path, byte_starts: List[int], blocks: List) -> None:
    blocks.append(_parse_list_block(cursor, path, byte_starts, blocks))


def _handle_blockquote(cursor: TokenCursor, path: Path, byte_starts: List[int], blocks: List) -> None:
    tok_open = cursor.current()
    if not tok_open:
        cursor.advance(1)
        return
    span = build_span(path, tok_open, byte_starts)

    inside = consume_container(cursor, "blockquote_open", "blockquote_close")
    parts: List[str] = []
    for t in inside:
        if t.type == "inline":
            _emit_figures_from_inline(t, span, blocks)
            if t.content:
                parts.append(t.content)
    blocks.append(Quote(id=next_id("q"), text=_norm(" ".join(parts)), span=span))

def _handle_table(cursor: TokenCursor, path: Path, byte_starts: List[int], blocks: List) -> None:
    tok_open = cursor.current()
    if not tok_open:
        cursor.advance(1)
        return

    # table_open, ... , table_close
    span = build_span(path, tok_open, byte_starts)
    inside = consume_container(cursor, "table_open", "table_close")

    header: Optional[List[str]] = None
    rows: List[List[str]] = []

    idx = 0
    def _collect_cells_for_row(idx: int, cell_open_type: str, cell_close_type: str) -> Tuple[List[str], int]:
        cells: List[str] = []
        # cell_open, inline, cell_close
        while idx < len(inside) and inside[idx].type != "tr_close":
            if inside[idx].type == cell_open_type:
                # one cell
                jdx = idx + 1
                parts: List[str] = []
                while jdx < len(inside) and inside[jdx].type != cell_close_type:
                    if inside[jdx].type == "inline" and inside[jdx].content:
                        parts.append(inside[jdx].content)
                    jdx += 1
                cells.append(_norm(" ".join(parts)))
                idx = jdx + 1  # skip cell_close
            else:
                idx += 1
        return cells, idx

    while idx < len(inside):
        tok = inside[idx]

        if tok.type == "thead_open":
            idx += 1
            while idx < len(inside) and inside[idx].type != "thead_close":
                if inside[idx].type == "tr_open":
                    idx += 1
                    cells, idx = _collect_cells_for_row(idx, "th_open", "th_close")
                    header = cells
                else:
                    idx += 1
            idx += 1
            continue

        if tok.type == "tbody_open":
            idx += 1
            while idx < len(inside) and inside[idx].type != "tbody_close":
                if inside[idx].type == "tr_open":
                    idx += 1
                    cells, idx = _collect_cells_for_row(idx, "td_open", "td_close")
                    rows.append(cells)
                else:
                    idx += 1
            idx += 1
            continue

        idx += 1

    blocks.append(
        Table(
            id=next_id("t"),
            header=header or None,
            rows=rows or None,
            span=span,
        )
    )


# Map ---------------------------------------------------------------------------

HANDLERS = {
    "heading_open": _handle_heading,
    "paragraph_open": _handle_paragraph,
    "fence": _handle_fence,
    "bullet_list_open": _handle_list,
    "ordered_list_open": _handle_list,
    "blockquote_open": _handle_blockquote,
    "table_open": _handle_table,
}


# Main ---------------------------------------------------------------------------

def parse_markdown(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    tokens = md.parse(text)
    byte_starts = compute_byte_starts(text)

    for idx, tok in enumerate(tokens):
        logger.debug("token %d type=%s map=%s nesting=%s", idx, tok.type, getattr(tok, 'map', None), getattr(tok, 'nesting', None))
        logger.debug("token %d full=%s", idx, tok.as_dict())

    blocks: List = []
    cursor = TokenCursor(tokens)

    while not cursor.is_at_end():
        tok = cursor.current()
        if not tok:
            break
        handler = HANDLERS.get(tok.type)
        if handler:
            handler(cursor, path, byte_starts, blocks)
        else:
            cursor.advance(1)

    return Document(source_path=str(path), blocks=blocks)

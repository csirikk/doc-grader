"""PDF parser producing an IR (internal representation).

Parses text and image blocks from PDF using PyMuPDF and converts them to typed blocks with span information.
Currently just paragraphs and figures are supported.
"""

from pathlib import Path
from typing import List, Dict, Any

from ..schemas.ir import (
    Document,
    Paragraph,
    Span,
    Figure,
    BBox,
)
from ..util import next_id, norm
from .. import logger

import pymupdf

DPI = 300

# --- Utilities


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _rasterize_clip(page, bbox: "BBox", outdir: Path, base: str, dpi: int = DPI) -> str:
    """Rasterize a clipped region of a page to a PNG and return its path."""
    rect = pymupdf.Rect(bbox.x0, bbox.y0, bbox.x1, bbox.y1)
    pixmap = page.get_pixmap(clip=rect, dpi=dpi, alpha=True)
    out_path = outdir / f"{base}.png"
    _ensure_dir(out_path.parent)
    pixmap.save(str(out_path))
    return str(out_path)

def _to_bbox(b: List[float]) -> BBox:
    x0, y0, x1, y1 = b
    return BBox(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1))


def build_span(path: Path, page_index: int, bbox: BBox) -> Span:
    """Build a Span for a PDF block"""
    return Span(source_path=str(path), page=page_index + 1, bbox=bbox)


def _get_page_sizes(pdf) -> List[List[float]]:
    sizes: List[List[float]] = []
    for i in range(len(pdf)):
        rectangle = pdf[i].rect
        sizes.append([float(rectangle.width), float(rectangle.height)])
    return sizes


def _aggregate_text_from_block(block: Dict[str, Any]) -> str:
    """Join text spans within a text block into a normalized paragraph string."""
    lines = block.get("lines", []) or []
    parts: List[str] = []
    for line in lines:
        spans = line.get("spans", []) or []
        line_text = "".join(s.get("text", "") for s in spans).strip()
        if line_text:
            parts.append(line_text)
    return norm(" ".join(parts))


# --- Block handlers

def _handle_text_block(path: Path, page_index: int, block: Dict[str, Any], bbox: BBox, out: List[Any]) -> None:
    text = _aggregate_text_from_block(block)
    if not text:
        return

    # Collect font hints for later
    fonts: List[str] = []
    sizes: List[float] = []
    for line in block.get("lines", []) or []:
        for span in line.get("spans", []) or []:
            font = span.get("font")
            if font and font not in fonts:
                fonts.append(font)
            span_size = span.get("size")
            if isinstance(span_size, (int, float)):
                sizes.append(float(span_size))

    span = build_span(path, page_index, bbox)
    out.append(
        Paragraph(
            id=next_id("p"),
            text=text,
            span=span,
            meta={
                "pdf": {
                    "font_names": fonts[:5],
                    "font_size_max": (max(sizes) if sizes else None),
                    "font_size_min": (min(sizes) if sizes else None),
                }
            },
        )
    )


def _handle_image_block(path: Path, page_index: int, bbox: BBox, out: List[Any], page) -> None:
    """Handle an image block by rasterizing its bounding box to a PNG."""
    span = build_span(path, page_index, bbox)

    # Output folder (name-without-ext)/images/
    root = Path(path).with_suffix("")
    outdir = root / "images"
    base = f"{Path(path).stem}-p{page_index+1}-{next_id('img')}"

    png_path = _rasterize_clip(page, bbox, outdir, base, dpi=DPI)

    out.append(
        Figure(
            id=next_id("f"),
            kind="image",
            src=png_path,
            alt=None,
            title=None,
            caption=None,
            span=span,
            meta={"pdf": {"note": "image block"}},
        )
    )


# --- Entry point

def parse_pdf(path: Path) -> Document:

    logger.debug("parse_pdf: opening %s", path)
    with pymupdf.open(str(path)) as pdf:
        page_count = len(pdf)
        page_sizes = _get_page_sizes(pdf)

        blocks: List[Any] = []

        for page_index in range(page_count):
            page = pdf[page_index]
            pdata = page.get_text("dict")
            page_blocks = pdata.get("blocks", []) or []
            for block in page_blocks:
                btype = block.get("type", 0)
                bbox_list = block.get("bbox")
                if not bbox_list:
                    continue
                bbox = _to_bbox(bbox_list)

                if btype == 0:
                    _handle_text_block(path, page_index, block, bbox, blocks)
                elif btype == 1:
                    _handle_image_block(path, page_index, bbox, blocks, page=page)
                else:
                    # other block types dont exist
                    logger.debug("parse_pdf: skipping unknown block type %s on page %d", btype, page_index + 1)
                    continue

        meta: Dict[str, Any] = {
            "parser": "pdf",
            "pdf": {
                "engine": "pymupdf",
                "page_count": page_count,
                "page_sizes": page_sizes,
            },
        }

        logger.debug("parse_pdf: built %d blocks from %d pages", len(blocks), page_count)
        return Document(source_path=str(path), blocks=blocks, meta=meta)

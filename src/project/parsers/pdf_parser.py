"""PDF parser producing an IR (internal representation).

Parses text and image blocks from PDF using PyMuPDF and converts them to typed blocks with span information.
Currently just paragraphs and figures are supported.
"""

from pathlib import Path
from typing import List, Dict, Any

from ..schemas.ir import (
    Document,
    Paragraph,
    Heading,
    Span,
    Figure,
    Table,
    BBox,
)
from ..util import next_id, norm
from ..logger import debug

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


def _extract_font_sizes_from_block(block: Dict[str, Any]) -> List[float]:
    """Extract all font sizes from a text block."""
    sizes: List[float] = []
    for line in block.get("lines", []) or []:
        for span in line.get("spans", []) or []:
            span_size = span.get("size")
            if isinstance(span_size, (int, float)):
                sizes.append(float(span_size))
    return sizes


def _calculate_avg_font_size(blocks: List[Dict[str, Any]]) -> float:
    """Calculate average font size across all text blocks."""
    all_sizes: List[float] = []
    for block in blocks:
        if block.get("type", 0) == 0:  # text block
            all_sizes.extend(_extract_font_sizes_from_block(block))
    
    if not all_sizes:
        return 12.0  # default fallback
    
    return sum(all_sizes) / len(all_sizes)


def _classify_text_block(block: Dict[str, Any], avg_font_size: float) -> tuple[str, int | None]:
    """
    Classify a text block as heading or paragraph based on font size.
    
    Returns (block_type, heading_level)
        block_type = 'heading' | 'paragraph'
        heading_level = 1-6 if heading, otherwise None
    """
    sizes = _extract_font_sizes_from_block(block)
    
    if not sizes:
        return "paragraph", None
    
    max_size = max(sizes)

    if max_size > avg_font_size * 1.2:
        # Map font size ratio to heading levels (1 = largest, 6 = smallest heading)
        ratio = max_size / avg_font_size
        
        if ratio >= 2.0:
            level = 1
        elif ratio >= 1.7:
            level = 2
        elif ratio >= 1.5:
            level = 3
        elif ratio >= 1.4:
            level = 4
        elif ratio >= 1.35:
            level = 5
        else:
            level = 6
        
        return "heading", level
    
    return "paragraph", None

def _find_caption_for_figure(fig: Figure, paragraphs: List[Paragraph]) -> str | None:
    if not fig.span.bbox or not fig.span.page:
        return None
    
    fig_width = fig.span.bbox.x1 - fig.span.bbox.x0
    fig_height = fig.span.bbox.y1 - fig.span.bbox.y0
    fig_area = fig_width * fig_height
    if fig_area < 10000:
        return None
    
    max_distance = 50.0  # max vertical distance in points
    img_bottom = fig.span.bbox.y1
    
    best_dist = float("inf")
    best_text = None

    for para in paragraphs:
        if not para.span.bbox or para.span.page != fig.span.page:
            continue
        
        para_top = para.span.bbox.y0
        distance = para_top - img_bottom

        if 0 < distance < max_distance and distance < best_dist:
            best_dist, best_text = distance, para.text

    return best_text


def _bboxes_collide(bbox1: BBox, bbox2: BBox, proximity: float = 20.0) -> bool:
    """Check if two bboxes overlap or are within proximity distance."""
    return (
        bbox1.x1 + proximity >= bbox2.x0 and
        bbox2.x1 + proximity >= bbox1.x0 and
        bbox1.y1 + proximity >= bbox2.y0 and
        bbox2.y1 + proximity >= bbox1.y0
    )


def _merge_bboxes(bboxes: List[BBox]) -> BBox:
    """Merge multiple bboxes into one bbox."""
    if not bboxes:
        raise ValueError("Cannot merge empty bbox list")
    return BBox(
        x0=min(b.x0 for b in bboxes),
        y0=min(b.y0 for b in bboxes),
        x1=max(b.x1 for b in bboxes),
        y1=max(b.y1 for b in bboxes),
    )


def _bbox_contains(outer: BBox, inner: BBox, margin: float = 5.0) -> bool:
    """Check if outer bbox contains inner bbox, margin for rounding."""
    return (
        inner.x0 >= outer.x0 - margin and
        inner.y0 >= outer.y0 - margin and
        inner.x1 <= outer.x1 + margin and
        inner.y1 <= outer.y1 + margin
    )


def _filter_redundant_clusters(
    cluster_info: List[tuple[List[tuple], BBox, float]]
) -> List[List[tuple]]:
    """Filter out redundant clusters: those contained in larger ones or too small."""
    if not cluster_info:
        return []
    
    max_area = max(ci[2] for ci in cluster_info)
    filtered = []
    
    for i, (cluster_i, bbox_i, area_i) in enumerate(cluster_info):
        # Skip clusters much smaller than the largest (likely fragments)
        if area_i < max_area * 0.1 and area_i < 10000:
            continue
        
        # Skip clusters contained in larger clusters
        is_contained = False
        for j, (_, bbox_j, area_j) in enumerate(cluster_info):
            if i != j and _bbox_contains(bbox_j, bbox_i) and area_j > area_i:
                is_contained = True
                break
        
        if not is_contained:
            filtered.append(cluster_i)
    
    return filtered


def _cluster_drawings_by_proximity(
    drawings: List[Dict[str, Any]],
    proximity: float = 20.0
) -> List[List[Dict[str, Any]]]:
    """Cluster vector drawings by spatial proximity to prevent fragmentation.s
    Returns list of clusters, each cluster is a list of drawing dicts."""
    if not drawings:
        return []
    
    # Convert to bboxes for easier handling
    drawings_with_bbox = []
    for d in drawings:
        rect = d.get("rect")
        if rect:
            bbox = BBox(x0=float(rect.x0), y0=float(rect.y0),
                       x1=float(rect.x1), y1=float(rect.y1))
            drawings_with_bbox.append((d, bbox))
    
    if not drawings_with_bbox:
        return []
    
    clusters = []
    used = set()
    
    for i, (d1, bbox1) in enumerate(drawings_with_bbox):
        if i in used:
            continue
        
        # Start new cluster with this drawing
        cluster = [(d1, bbox1)]
        used.add(i)
        cluster_bboxes = [bbox1]
        
        # Find all overlapping/adjacent drawings
        for j, (d2, bbox2) in enumerate(drawings_with_bbox[i+1:], start=i+1):
            if j in used:
                continue
            
            # Check if d2 overlaps with any drawing in current cluster
            if any(_bboxes_collide(b, bbox2, proximity) for b in cluster_bboxes):
                cluster.append((d2, bbox2))
                used.add(j)
                cluster_bboxes.append(bbox2)
        
        clusters.append(cluster)
    
    # Build cluster info and filter redundant ones
    cluster_info = []
    for cluster in clusters:
        bboxes = [b for _, b in cluster]
        bbox = _merge_bboxes(bboxes)
        area = (bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0)
        cluster_info.append((cluster, bbox, area))
    
    return _filter_redundant_clusters(cluster_info)


# --- Block handlers

def _handle_text_block(
    path: Path,
    page_index: int,
    block: Dict[str, Any],
    bbox: BBox,
    out: List[Any],
    block_type: str = "paragraph",
    heading_level: int | None = None,
) -> None:
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
    
    meta = {
        "pdf": {
            "font_names": fonts[:5],
            "font_size_max": (max(sizes) if sizes else None),
            "font_size_min": (min(sizes) if sizes else None),
        }
    }
    
    if block_type == "heading" and heading_level is not None:
        out.append(
            Heading(
                id=next_id("h"),
                level=heading_level,
                text=text,
                span=span,
                meta=meta,
            )
        )
    else:
        out.append(
            Paragraph(
                id=next_id("p"),
                text=text,
                span=span,
                meta=meta,
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


def _handle_vector_drawings(path: Path, page_index: int, page, out: List[Any], *, min_cluster_area: float = 100.0, proximity: float = 25.0) -> None:
    drawings = page.get_drawings()
    
    if not drawings:
        return

    filtered_drawings = []
    for d in drawings:
        rect = d.get("rect")
        if not rect:
            continue
        w = max(0.0, rect.x1 - rect.x0)
        h = max(0.0, rect.y1 - rect.y0)
        if (w * h) > 0:  # Keep anything with non-zero area
            filtered_drawings.append(d)
    
    if not filtered_drawings:
        return
    
    debug("parse_pdf: found %d vector drawings (excluding hairlines)", len(filtered_drawings))
    
    # Cluster drawings by spatial proximity, fuses overlapping/adjacent elements
    clusters = _cluster_drawings_by_proximity(filtered_drawings, proximity)
    
    debug("parse_pdf: clustered into %d groups", len(clusters))
    
    root = Path(path).with_suffix("")
    outdir = root / "images"
    
    # Rasterize each cluster with meaningful size
    for cluster in clusters:
        if not cluster:
            continue
        
        if len(cluster) == 1:
            d = cluster[0][0]
            rect = d.get("rect")
            bbox = BBox(x0=float(rect.x0), y0=float(rect.y0), 
                       x1=float(rect.x1), y1=float(rect.y1))
        else:
            bboxes = [b for _, b in cluster]
            bbox = _merge_bboxes(bboxes)
        
        cluster_w = bbox.x1 - bbox.x0
        cluster_h = bbox.y1 - bbox.y0
        cluster_area = cluster_w * cluster_h
        
        if cluster_area < min_cluster_area:
            continue
        span = build_span(path, page_index, bbox)
        base = f"{Path(path).stem}-p{page_index+1}-{next_id('vec')}"
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
                meta={"pdf": {"kind": "vector"}},
            )
        )


def _handle_tables(path: Path, page_index: int, page, out: List[Any]) -> None:
    """Extract tables from a page using PyMuPDF's find_tables()."""
    tables = page.find_tables()
    
    for table in tables:
        data = table.extract()
        bbox_tuple = table.bbox
        
        if not data or len(data) == 0:
            continue
        
        # Convert None cells to empty strings
        cleaned_data = []
        for row in data:
            cleaned_row = [cell if cell is not None else "" for cell in row]
            cleaned_data.append(cleaned_row)
        
        # Separate header from rows
        header = cleaned_data[0] if cleaned_data else None
        rows = cleaned_data[1:] if len(cleaned_data) > 1 else []
        
        # Skip tables that are too small - false positives
        if not header or len(rows) == 0:
            continue
        
        bbox = _to_bbox(bbox_tuple)
        span = build_span(path, page_index, bbox)
        
        out.append(
            Table(
                id=next_id("t"),
                header=header,
                rows=rows,
                span=span,
                meta={"pdf": {"method": "pymupdf"}},
            )
        )


# --- Entry point

def parse_pdf(path: Path) -> Document:

    debug("parse_pdf: opening %s", path)
    with pymupdf.open(str(path)) as pdf:
        page_count = len(pdf)
        page_sizes = _get_page_sizes(pdf)

        # Collect all text blocks for font size analysis
        all_text_blocks: List[Dict[str, Any]] = []

        for page_index in range(page_count):
            page = pdf[page_index]
            pdata = page.get_text("dict")
            page_blocks = pdata.get("blocks", []) or []
            for block in page_blocks:
                if block.get("type", 0) == 0:  # text block
                    all_text_blocks.append(block)
        
        # Calculate average font size
        avg_font_size = _calculate_avg_font_size(all_text_blocks)
        debug("parse_pdf: calculated avg font size = %.2f", avg_font_size)

        # Process blocks and classify text as heading or paragraph
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
                    block_type, heading_level = _classify_text_block(block, avg_font_size)
                    _handle_text_block(
                        path, page_index, block, bbox, blocks,
                        block_type=block_type,
                        heading_level=heading_level,
                    )
                elif btype == 1:
                    _handle_image_block(path, page_index, bbox, blocks, page=page)
                else:
                    # other block types dont exist
                    debug("parse_pdf: skipping unknown block type %s on page %d", btype, page_index + 1)
                    continue
            _handle_vector_drawings(path, page_index, page, blocks)
            _handle_tables(path, page_index, page, blocks)

        figures = [b for b in blocks if isinstance(b, Figure)]
        paragraphs = [b for b in blocks if isinstance(b, Paragraph)]
        captions_found = 0
        
        for fig in figures:
            caption = _find_caption_for_figure(fig, paragraphs)
            if caption:
                fig.caption = caption
                captions_found += 1

        # Count blocks for logging
        heading_count = sum(1 for b in blocks if isinstance(b, Heading))
        para_count = sum(1 for b in blocks if isinstance(b, Paragraph))
        figure_count = len(figures)
        table_count = sum(1 for b in blocks if isinstance(b, Table))
        
        meta: Dict[str, Any] = {
            "parser": "pdf",
            "pdf": {
                "engine": "pymupdf",
                "page_count": page_count,
                "page_sizes": page_sizes,
                "avg_font_size": round(avg_font_size, 2),
            },
        }

        debug(
            "parse_pdf: built %d blocks from %d pages (%d headings, %d paragraphs, %d tables, %d figures with %d captions)",
            len(blocks), page_count, heading_count, para_count, table_count, figure_count, captions_found
        )
        return Document(source_path=str(path), blocks=blocks, meta=meta)

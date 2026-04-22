"""Intermediate Representation schema.

Author: Matúš Csirik
"""

import logging
from typing import Any

from docling_core.types.doc.document import (
    DoclingDocument,  # noqa: TC002
    DocumentOrigin,  # noqa: TC002
)
from pydantic import Field

from .base import StrictModel

logger = logging.getLogger(__name__)


class DocumentRef(StrictModel):
    """Reference to the source document."""

    source_path: str
    student_id: str | None = Field(
        default=None,
        description=("Student identifier derived from the input folder or filename."),
    )
    origin: DocumentOrigin | None = None
    binary_hash: int | None = Field(
        default=None,
        description=("Docling content hash (binary_hash)."),
    )


class Document(StrictModel):
    """Docling Document wrapper for custom stats and metadata."""

    doc_ref: DocumentRef
    docling_doc: DoclingDocument = Field(
        exclude=True, description="The underlying Docling document"
    )

    # Custom stats
    total_words: int = Field(default=0, description="Total detected words")
    total_chars: int = Field(default=0, description="Total detected characters")
    total_paragraphs: int = Field(default=0, description="Total detected paragraphs")
    total_headings: int = Field(default=0, description="Total detected headings")
    total_pictures: int = Field(default=0, description="Total detected pictures")
    section_paths: dict[str, str] = Field(
        default_factory=dict,
        exclude=True,
        description=("Map of cref to section heading path string for each text item"),
    )
    md_image_uris: list[str] = Field(
        default_factory=list,
        exclude=True,
        description=("Ordered list of image URIs extracted from a Markdown source."),
    )
    language: str = Field(
        default="en",
        description=(
            "Detected dominant language of the document as a BCP-47 code. (en, cs, sk)"
        ),
    )


def get_picture_pil(doc: Document, idx: int, item: Any) -> Any:
    """Resolve a Docling PictureItem to a PIL image.

    The resolution attempts the following in order: an in-memory
    ``pil_image`` on the item, the item's URI, the Markdown image URI list
    stored on the document, and finally a local file path resolved
    relative to the document source directory.

    Args:
        doc: Document wrapper containing md_image_uris and document reference.
        idx: Index of the picture in the Docling picture list.
        item: The PictureItem-like object to resolve.

    Returns:
        A PIL Image instance when the image could be loaded, otherwise
        ``None``.
    """
    from pathlib import Path
    from urllib.parse import unquote

    from PIL import Image

    if item.image is not None and item.image.pil_image is not None:
        return item.image.pil_image

    img_path_str: str | None = None
    if item.image is not None and getattr(item.image, "uri", None):
        img_path_str = str(item.image.uri)
    elif getattr(item, "uri", None):
        img_path_str = str(item.uri)

    if img_path_str is None and doc.md_image_uris and idx < len(doc.md_image_uris):
        img_path_str = doc.md_image_uris[idx]

    if not img_path_str:
        return None

    if img_path_str.startswith("file://"):
        img_path_str = img_path_str[7:]
    img_path_str = unquote(img_path_str)

    source_dir = Path(doc.doc_ref.source_path).parent
    base_resolved = source_dir.resolve()
    img_path = (base_resolved / img_path_str).resolve()

    if not img_path.is_relative_to(base_resolved) or not img_path.is_file():
        return None
    try:
        if img_path.suffix.lower() == ".svg":
            import io

            import cairosvg

            png_bytes = cairosvg.svg2png(url=str(img_path))
            if not png_bytes:
                return None
            return Image.open(io.BytesIO(png_bytes))
        return Image.open(img_path)
    except Exception as exc:
        logger.warning("Failed to load local image %s: %s", img_path, exc)
        return None

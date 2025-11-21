"""Parser interface."""

# TODO: clean up after parse?
# e.g. make short paragraphs count as headings
from pathlib import Path
from typing import Optional

from .md_parser import parse_markdown
from .pdf_parser import parse_pdf
from .normalizer import normalize_document
from ..logger import debug
from ..schemas.ir import Document
from ..util import reset_id_counters

# --- Public parse function


def parse(path: Path) -> Optional[Document]:
    """
    Parse an input file into a Document IR and apply text normalization.
    Returns None if the path does not exist or the extension is unsupported.
    """
    if not path.exists():
        return None
    # Reset IDs per parsed document so they are deterministic per file.
    reset_id_counters()
    ext = path.suffix.lower()
    doc: Optional[Document] = None
    if ext in {".md", ".markdown"}:
        debug("parsing markdown file %s", path)
        doc = parse_markdown(path)
    elif ext == ".pdf":
        debug("parsing pdf file %s", path)
        doc = parse_pdf(path)

    # Apply normalization after parsing
    if doc is not None:
        debug("normalizing text content in %s", path)
        normalize_document(doc)

    return doc

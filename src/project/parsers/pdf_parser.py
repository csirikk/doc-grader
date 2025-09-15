"""PDF parsing stub.

TODO:
"""

from pathlib import Path

from ..schemas.ir import Document
from ..logger import debug

def parse_pdf(path: Path) -> Document:
    """STUB"""
    debug("parse_pdf stub called for %s", path)
    return Document(source_path=str(path), blocks=[], meta={"parser": "pdf-stub", "note": "PDF parsing not implemented"})

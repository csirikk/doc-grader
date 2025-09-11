# TODO: STUB
from pathlib import Path
from typing import List

from ..schemas.ir import Document, Block 
from ..logger import debug

def parse_pdf(path: Path) -> Document:
    debug("parse_pdf stub called for %s", path)
    return Document(source_path=str(path), blocks=[], meta={"parser": "pdf-stub", "note": "PDF parsing not implemented"})

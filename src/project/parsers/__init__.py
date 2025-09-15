from pathlib import Path
from typing import Optional

from .md_parser import parse_markdown
from .pdf_parser import parse_pdf
from ..logger import debug
from ..schemas.ir import Document

# main parse function -------------------------------

def parse(path: Path) -> Optional[Document]:
    """
    Parse an input file into a Document IR.
    Returns None if the path does not exist or the extension is unsupported.
    """
    if not path.exists():
        return None
    ext = path.suffix.lower()
    if ext in {".md", ".markdown"}:
        debug("parsing markdown file %s", path)
        return parse_markdown(path)
    if ext == ".pdf":
        debug("parsing pdf file %s", path)
        return parse_pdf(path)
    return None

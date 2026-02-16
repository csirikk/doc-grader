"""Parser interface."""

from pathlib import Path
from typing import Any, Optional

from ..logger import debug
from .docling_parser import DoclingParser

_parser = DoclingParser()


def parse(path: Path) -> Optional[Any]:
    if not path.exists():
        return None

    try:
        debug(f"Parsing {path} with Docling...")
        return _parser.parse(path)
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        return None

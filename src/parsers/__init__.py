"""Parser interface."""

import logging
from pathlib import Path
from typing import Optional

from docling.datamodel.document import DoclingDocument

from .docling_parser import DoclingParser

logger = logging.getLogger(__name__)

_parser = DoclingParser()


def parse(path: Path) -> Optional[DoclingDocument]:
    if not path.exists():
        return None

    try:
        logger.debug(f"Parsing {path} with Docling...")
        return _parser.parse(path)
    except Exception as e:
        logger.error(f"Error parsing {path}: {e}")
        return None

"""Utility helpers."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from docling_core.types.doc.document import DoclingDocument
from pydantic import BaseModel
from rich.logging import RichHandler


def configure_logging(level: int) -> None:
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
        datefmt="[%H:%M:%S]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        force=True,
    )


def _to_jsonable(x: Any) -> Any:
    """Convert various objects to JSON-serializable Python structures."""
    if isinstance(x, DoclingDocument):  # uses by_alias=True, exclude_none=True
        return _to_jsonable(x.export_to_dict())
    if isinstance(x, BaseModel):
        return _to_jsonable(x.model_dump(by_alias=True, exclude_none=True))
    if isinstance(x, datetime):
        return x.isoformat()
    if isinstance(x, Path):
        return str(x)
    if isinstance(x, dict):
        return {k: _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]
    return x


def write_json(path: Path, payload: Any) -> None:
    """Write any JSON-serializable payload to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_json = _to_jsonable(payload)
    path.write_text(
        json.dumps(payload_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def log_json(logger: logging.Logger, label: str, payload: Any) -> None:
    """Log any JSON-serializable payload"""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    try:
        payload_json = _to_jsonable(payload)
        text = json.dumps(payload_json, indent=2, ensure_ascii=False)
        logger.debug("[%s]\n%s", label, text)
    except Exception:
        logger.exception("Failed to dump JSON for %s", label)


_id_counters: dict[str, int] = {}


def next_id(prefix: str) -> str:
    """Return the next sequential id for the given prefix."""
    n = _id_counters.get(prefix, 0) + 1
    _id_counters[prefix] = n
    return f"{prefix}-{n}"


def reset_id_counters(*prefixes: str) -> None:
    """
    Reset internal id counters.
    Without arguments resets all prefixes. If one or more `prefixes` are
    provided only those counters are cleared.
    """
    if not prefixes:
        _id_counters.clear()
        return
    for p in prefixes:
        _id_counters.pop(p, None)


def compute_doc_hash(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def compute_config_hash(config: dict) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

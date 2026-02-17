"""Utility helpers."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter
from rich.logging import RichHandler


def configure_logging(level: int) -> None:
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
        datefmt="[%H:%M:%S]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        force=True,
    )


def log_model_json(
    logger: logging.Logger,
    label: str,
    model: BaseModel | None,
    *,
    indent: int = 2,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    if model is None:
        logger.debug("[%s] <None>", label)
        return
    try:
        logger.debug("[%s]\n%s", label, model.model_dump_json(indent=indent))
    except Exception:
        logger.exception("Failed to dump model JSON for %s", label)


def write_json(path: Path, payload: Any) -> None:
    """Write any JSON to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        TypeAdapter(Any)
        .dump_json(
            payload,
            indent=2,
            ensure_ascii=False,
            fallback=str,
        )
        .decode("utf-8")
    )
    path.write_text(text + "\n", encoding="utf-8")


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

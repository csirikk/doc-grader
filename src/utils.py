"""Utility helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docling_core.types.doc.document import DoclingDocument
from pydantic import BaseModel
from rich.logging import RichHandler

if TYPE_CHECKING:
    from .schemas.finding import Finding


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


def format_finding_short(finding: Finding) -> str:
    """Return a summary of a Finding."""
    lines = [
        f"[{finding.finding_id}]:",
        f"{finding.summary}",
    ]

    metrics = []
    if finding.severity is not None:
        metrics.append(f"severity={finding.severity:.2f}")
    if finding.confidence is not None:
        metrics.append(f"confidence={finding.confidence:.2f}")
    if metrics:
        lines.append(f"{', '.join(metrics)}")

    if finding.stats:
        stats_str = ", ".join(
            f"{s.name}={s.value}{' ' + s.unit if s.unit else ''}" for s in finding.stats
        )
        lines.append(f"  Stats: {stats_str}")

    if finding.anchors:
        for i, anchor in enumerate(finding.anchors, 1):
            me = (
                finding.model_evals[i - 1] if i - 1 < len(finding.model_evals) else None
            )
            if anchor.snippet:
                snippet = anchor.snippet.replace("\n", " ")
                if len(snippet) > 500:
                    snippet = snippet[:500] + "..."
                lines.append(f'  Evidence [{i}]: "{snippet}"')
            else:
                lines.append(f"  Evidence [{i}]: (No snippet provided)")
            if me and me.raw and (spec_text := me.raw.get("spec_text")):
                spec_text = spec_text.replace("\n", " ")
                if len(spec_text) > 500:
                    spec_text = spec_text[:500] + "..."
                lines.append(f'  Spec match: "{spec_text}"')

    if finding.notes:
        lines.append(f"  Notes: {', '.join(finding.notes)}")

    return "\n".join(lines)


def compute_config_hash(config: dict) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- CSV export ---

# Column order mirrors clean_ipp_data.csv produced by dataset_parser.py
# Columns (grade points, year, variant) are left as None.
CSV_COLUMNS: list[str] = [
    "id",
    "year",
    "task_variant",
    "code",
    "impact",
    "impact_has_sign",
    "impact_source",
    "impact_shared",
    "comment",
    "raw_text",
    "source_file",
    "doc_points",
    "doc_type",
    "bonus_points",
    # Extras
    "severity",
    "confidence",
    "finding_id",
]


def findings_to_csv_rows(path: Path, findings: list[Finding]) -> list[dict[str, Any]]:
    """Convert a list of Findings for one document into CSV-ready row dicts."""
    doc_type = path.suffix.lstrip(".").lower() or None
    rows: list[dict[str, Any]] = []
    for f in findings:
        rows.append(
            {
                "id": path.stem,
                "year": None,
                "task_variant": None,
                "code": f.ac_code,
                "impact": None,
                "impact_has_sign": False,
                "impact_source": None,
                "impact_shared": False,
                "comment": f.summary,
                "raw_text": f.summary,
                "source_file": path.name,
                "doc_points": None,
                "doc_type": doc_type,
                "bonus_points": None,
                "severity": f.severity,
                "confidence": f.confidence,
                "finding_id": f.finding_id,
            }
        )
    return rows


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> None:
    """Write row dicts to a CSV file. Uses CSV_COLUMNS if fieldnames is None."""
    path.parent.mkdir(parents=True, exist_ok=True)
    csv_columns = fieldnames or CSV_COLUMNS
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

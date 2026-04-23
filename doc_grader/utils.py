"""Utility helpers for logging, JSON/CSV I/O and small utilities.

Author: Matúš Csirik

This module centralises logging configuration and provides helpers to
serialise domain objects to JSON, write CSV exports and generate simple
identifiers. It is intended for use by the grader pipeline and test code.
"""

import csv
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docling_core.types.doc.document import DoclingDocument
from pydantic import BaseModel
from rich.logging import RichHandler

if TYPE_CHECKING:
    from .schemas.finding import Finding


def configure_logging(level: int = logging.INFO) -> None:
    """Configure module logging.

    Sets up a compact formatter for Jupyter environments and a ``richer``
    handler for terminal use. The `level` argument controls the
    `doc_grader` logger level, other libraries remain at WARNING by
    default.

    Args:
        level: Logging level to set for the `doc_grader` logger.

    Returns:
        None
    """

    is_notebook = False
    try:
        from IPython.core.getipython import get_ipython

        if get_ipython() is not None:
            is_notebook = True
    except ImportError:
        pass

    if is_notebook:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            "%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(fmt)
    else:
        handler = RichHandler(
            rich_tracebacks=True, markup=True, show_time=True, show_level=True
        )

    logging.basicConfig(
        level=logging.WARNING,  # default to WARNING to avoid noisy logs from deps
        handlers=[handler],
        force=True,
    )
    logging.getLogger("doc_grader").setLevel(level)


def _to_jsonable(x: Any) -> Any:
    """Convert domain objects to JSON-serialisable structures.

    The function recursively converts Pydantic models, pathlib `Path`
    objects and datetime instances so that the result can be passed to
    `json.dumps`.

    Args:
        x: Domain object to convert.

    Returns:
        A JSON-serialisable representation of ``x``.
    """
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
    """Write a JSON-serialisable payload to `path`.

    Args:
        path: Destination file path.
        payload: Any domain object that can be converted to JSON via
            :func:`_to_jsonable`.

    Returns:
        None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_json = _to_jsonable(payload)
    path.write_text(
        json.dumps(payload_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def log_json(logger: logging.Logger, label: str, payload: Any) -> None:
    """Log a JSON-serialisable payload at DEBUG level.

    This helper guards the potentially expensive JSON serialization so
    that it only occurs when the logger is set to DEBUG.

    Args:
        logger: Logger instance to use.
        label: Short label included in the log message.
        payload: Payload to serialise and log.

    Returns:
        None
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return
    try:
        payload_json = _to_jsonable(payload)
        text = json.dumps(payload_json, indent=2, ensure_ascii=False)
        logger.debug("[%s]\n%s", label, text)
    except Exception:
        logger.exception("Failed to dump JSON for %s", label)


def model_eval_spec_text(raw: Any) -> str:
    """Return embedded spec text from ModelEval.raw when present."""
    if not isinstance(raw, dict):
        return ""
    spec_text = raw.get("spec_text", "")
    return spec_text if isinstance(spec_text, str) else ""


def summarise_usage_payload(by_model: dict[str, Any]) -> dict[str, Any]:
    """Return a serialisable usage summary with per-model cost convenience data."""
    from .llm_client import summarise_usage

    summary = summarise_usage(by_model)
    summary["costs_by_model_eur"] = {
        model: entry.get("cost_eur") for model, entry in summary["by_model"].items()
    }
    return summary


def merge_stage_timings(
    aggregate: dict[str, dict[str, float | int]],
    stage_times: dict[str, float],
) -> dict[str, dict[str, float | int]]:
    """Accumulate per-document stage timings into a run-level aggregate."""
    merged = {stage: dict(stats) for stage, stats in aggregate.items()}
    for stage, seconds in stage_times.items():
        seconds = round(float(seconds), 2)
        existing = merged.get(stage)
        if existing is None:
            merged[stage] = {
                "calls": 1,
                "total_seconds": seconds,
                "min_seconds": seconds,
                "max_seconds": seconds,
            }
            continue
        existing_calls = int(existing["calls"])
        existing_total = float(existing["total_seconds"])
        existing_min = float(existing["min_seconds"])
        existing_max = float(existing["max_seconds"])
        merged[stage] = {
            "calls": existing_calls + 1,
            "total_seconds": round(existing_total + seconds, 2),
            "min_seconds": round(min(existing_min, seconds), 2),
            "max_seconds": round(max(existing_max, seconds), 2),
        }
    return merged


def summarise_stage_timings(
    aggregate: dict[str, dict[str, float | int]],
) -> dict[str, Any]:
    """Summarise run-level timing aggregates into a compact JSON payload."""
    by_stage: dict[str, dict[str, float | int]] = {}
    total_tracked_seconds = 0.0
    total_invocations = 0
    for stage in sorted(aggregate):
        stats = aggregate[stage]
        calls = int(stats["calls"])
        total_seconds = round(float(stats["total_seconds"]), 2)
        min_seconds = round(float(stats["min_seconds"]), 2)
        max_seconds = round(float(stats["max_seconds"]), 2)
        avg_seconds = round(total_seconds / calls, 2) if calls else 0.0
        by_stage[stage] = {
            "calls": calls,
            "total_seconds": total_seconds,
            "avg_seconds": avg_seconds,
            "min_seconds": min_seconds,
            "max_seconds": max_seconds,
        }
        total_tracked_seconds += total_seconds
        total_invocations += calls
    return {
        "by_stage": by_stage,
        "total_tracked_seconds": round(total_tracked_seconds, 2),
        "total_stage_invocations": total_invocations,
    }


def build_doc_info(
    *,
    input_payload: dict[str, Any],
    run_id: str,
    config_hash: str,
    course: str | None,
    max_doc_points: int | None,
    parse_payload: dict[str, Any],
    parser_findings_count: int,
    finding_count: int,
    usage_by_model: dict[str, Any],
    stage_times: dict[str, float],
    elapsed_seconds: float,
    document_stats: dict[str, Any] | None = None,
    analyser_errors: dict[str, list[str]] | None = None,
    extra_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical per-document info.json payload."""
    info = {
        "input": input_payload,
        "run": {"run_id": run_id, "config_hash": config_hash},
        "config": {
            "course": course,
            "max_doc_points": max_doc_points,
        },
        "parse": parse_payload,
        "counts": {
            "n_parser_findings": parser_findings_count,
            "n_findings": finding_count,
        },
        "stage_times": {
            stage: round(float(seconds), 2) for stage, seconds in stage_times.items()
        },
        "usage": summarise_usage_payload(usage_by_model),
        "elapsed_seconds": round(elapsed_seconds, 2),
    }
    if extra_summary:
        info.update(extra_summary)
    if document_stats is not None:
        info["document"] = document_stats
    if analyser_errors:
        info["analyser_errors"] = analyser_errors
    return info


def build_run_summary(
    *,
    run_id: str,
    config_hash: str,
    config_path: Path,
    output_dir: Path,
    counts: dict[str, Any],
    usage_by_model: dict[str, Any],
    stage_timings: dict[str, dict[str, float | int]],
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Build the canonical aggregated run summary JSON payload."""
    return {
        "run": {
            "run_id": run_id,
            "config_hash": config_hash,
            "config_path": str(config_path),
            "output_dir": str(output_dir),
        },
        "counts": counts,
        "stage_times": summarise_stage_timings(stage_timings),
        "usage": summarise_usage_payload(usage_by_model),
        "elapsed_seconds": round(elapsed_seconds, 2),
    }


_id_counters: dict[str, int] = {}


def next_id(prefix: str) -> str:
    """Return the next sequential identifier for ``prefix``.

    Args:
        prefix: Prefix string used to build the id.

    Returns:
        A new identifier string "{prefix}-{n}".
    """
    n = _id_counters.get(prefix, 0) + 1
    _id_counters[prefix] = n
    return f"{prefix}-{n}"


def reset_id_counters(*prefixes: str) -> None:
    """Reset internal identifier counters.

    Without arguments this clears all counters. If one or more
    ``prefixes`` are provided only those counters are removed.

    Args:
        *prefixes: Optional list of prefixes whose counters should be
            reset.

    Returns:
        None
    """
    if not prefixes:
        _id_counters.clear()
        return
    for p in prefixes:
        _id_counters.pop(p, None)


def compute_doc_hash(path: str | Path) -> str:
    """Compute a SHA-256 digest for a file.

    Args:
        path: Path or string pointing to the file to hash.

    Returns:
        Hex-encoded digest prefixed with "sha256:".
    """
    hasher = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def format_finding_short(finding: Finding) -> str:
    """Return a concise multi-line summary for a ``Finding``.

    The summary includes the finding id, summary text and selected
    numeric metrics. Long snippets are truncated to keep the output compact.

    Args:
        finding: Finding object to format.

    Returns:
        A single string containing the formatted summary.
    """
    lines = [
        f"[{finding.finding_id}]:",
        f"{finding.summary}",
    ]

    metrics = []
    if finding.severity is not None:
        metrics.append(f"severity={finding.severity:.2f}")
    if finding.confidence is not None:
        metrics.append(f"confidence={finding.confidence:.2f}")
    if finding.impact is not None:
        metrics.append(f"impact={finding.impact:+.2f}pts")
    metrics.append(f"judge_status={finding.judge_status}")
    metrics.append(f"human_status={finding.human_status}")
    lines.append(", ".join(metrics))

    if finding.stats:
        stats_str = ", ".join(
            f"{s.name}={s.value}{' ' + s.unit if s.unit else ''}" for s in finding.stats
        )
        lines.append(f"  Stats: {stats_str}")

    if finding.anchors:
        for i, anchor in enumerate(finding.anchors, 1):
            model_eval = (
                finding.model_evals[i - 1] if i - 1 < len(finding.model_evals) else None
            )
            if anchor.snippet:
                snippet = anchor.snippet.replace("\n", " ")
                if len(snippet) > 500:
                    snippet = snippet[:500] + "..."
                lines.append(f'  Evidence [{i}]: "{snippet}"')
            else:
                lines.append(f"  Evidence [{i}]: (No snippet provided)")
            if model_eval and (spec_text := model_eval_spec_text(model_eval.raw)):
                spec_text = spec_text.replace("\n", " ")
                if len(spec_text) > 500:
                    spec_text = spec_text[:500] + "..."
                lines.append(f'  Spec match: "{spec_text}"')

    if finding.notes:
        lines.append(f"  Notes: {', '.join(finding.notes)}")

    return "\n".join(lines)


def compute_config_hash(config: dict) -> str:
    """Compute a canonical SHA-256 hash for a configuration mapping.

    The mapping is deterministically serialised so identical structures
    always yield the same digest.

    Args:
        config: Mapping representing the configuration.

    Returns:
        Hex-encoded digest prefixed with "sha256:".
    """
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    "severity",
    "confidence",
    "judge_status",
    "human_status",
    "finding_id",
]


def findings_to_csv_rows(
    path: Path,
    findings: list[Finding],
    student_id: str | None = None,
    max_doc_points: int | None = None,
) -> list[dict[str, Any]]:
    """Convert a list of Findings for one document into CSV-ready row dicts.

    If `student_id` is provided use it for the `id` column; otherwise fall
    back to the document filename stem.
    """
    doc_type = path.suffix.lstrip(".").lower() or None
    id_value = student_id if student_id is not None else path.stem
    total_impact = sum(f.impact for f in findings if f.impact is not None)
    doc_points = (
        round(max_doc_points + total_impact, 2) if max_doc_points is not None else None
    )
    rows: list[dict[str, Any]] = []
    for f in findings:
        rows.append(
            {
                "id": id_value,
                "year": None,
                "task_variant": None,
                "code": f.ac_code,
                "impact": f.impact,
                "impact_has_sign": False,
                "impact_source": None,
                "impact_shared": False,
                "comment": f.summary,
                "raw_text": f.summary,
                "source_file": path.name,
                "doc_points": doc_points,
                "doc_type": doc_type,
                "bonus_points": None,
                "severity": f.severity,
                "confidence": f.confidence,
                "judge_status": f.judge_status,
                "human_status": f.human_status,
                "finding_id": f.finding_id,
            }
        )
    return rows


def findings_to_grader_row(
    path: Path, findings: list[Finding], max_doc_points: int | None = None
) -> dict[str, Any]:
    """Convert a document's findings into a single legacy grader style CSV row."""
    doc_type = path.suffix.lstrip(".").lower() or None
    total_impact = sum(f.impact for f in findings if f.impact is not None)
    points = (
        round(max_doc_points + total_impact, 2) if max_doc_points is not None else None
    )
    parts: list[str] = []
    for f in findings:
        section = f.anchors[0].section_path or "" if f.anchors else ""
        parts.append(f"{f.ac_code} ({section}, {f.summary})")

    comment = ", ".join(parts) if parts else ""
    return {
        "points": points,
        "comment": comment,
        "bonus_points": None,
        "points_mentioned_in_comment": None,
        "id": path.stem,
        "doc_type": doc_type,
    }


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> None:
    """Write row dicts to a CSV file. Uses CSV_COLUMNS if fieldnames is None."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames:
        csv_columns = fieldnames
    elif rows:
        csv_columns = list(rows[0].keys())
    else:
        csv_columns = CSV_COLUMNS

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

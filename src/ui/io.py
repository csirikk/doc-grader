"""Data-layer helpers for the review UI.

Loads pre-generated pipeline output from an ``out/<stem>/`` directory.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

FINDINGS_FILE = "findings.json"
JUDGED_FILE = "judged_findings.json"
RAW_FILE = "raw_findings.json"
INFO_FILE = "info.json"

PIPELINE_STAGES: list[tuple[str, str]] = [
    ("Final", FINDINGS_FILE),
    ("Judged", JUDGED_FILE),
    ("Raw", RAW_FILE),
]


def available_stages(out_dir: Path) -> list[str]:
    """Return the stage labels that have an output file in out_dir."""
    return [label for label, fname in PIPELINE_STAGES if (out_dir / fname).exists()]


def load_run(out_dir: Path, stage: str = "Final") -> tuple[list[dict], dict]:
    """Load findings and run info from out_dir.

    Returns:
        findings: list of finding dicts (mutable, ready for session state).
        info: contents of ``info.json`` (or empty dict if absent).
    """
    stage_file = dict(PIPELINE_STAGES).get(stage, FINDINGS_FILE)
    source = out_dir / stage_file
    findings: list[dict] = json.loads(source.read_text(encoding="utf-8"))

    info_path = out_dir / INFO_FILE
    info: dict = (
        json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    )

    return findings, info


def source_path_from_info(info: dict) -> str | None:
    """Extract the original document path from an ``info.json`` dict."""
    return info.get("input", {}).get("source_path")

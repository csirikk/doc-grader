"""Data-layer helpers for the review UI.

Author: Matúš Csirik

Loads pre-generated pipeline output from an ``out/<stem>/`` directory.
"""

import json
from pathlib import Path

FINDINGS_FILE = "findings.json"
JUDGED_FILE = "judged_findings.json"
RAW_FILE = "raw_findings.json"
INFO_FILE = "info.json"

PIPELINE_STAGES: dict[str, str] = {
    "Final": FINDINGS_FILE,
    "Judged": JUDGED_FILE,
    "Raw": RAW_FILE,
}


def available_stages(out_dir: Path) -> list[str]:
    """Return the pipeline stage labels available in ``out_dir``.

    Args:
        out_dir: Directory containing pipeline output files.

    Returns:
        A list of stage names that have corresponding output files present.
    """
    return [
        label for label, fname in PIPELINE_STAGES.items() if (out_dir / fname).exists()
    ]


def load_run(out_dir: Path, stage: str = "Final") -> tuple[list[dict], dict]:
    """Load findings and run info for a given pipeline stage.

    Args:
        out_dir: Directory with the run output files.
        stage: Stage label to load (e.g. 'Final', 'Judged', 'Raw').

    Returns:
        A tuple (findings, info) where ``findings`` is a list of finding
        dictionaries and ``info`` is the run metadata mapping.
    """
    stage_file = PIPELINE_STAGES.get(stage, FINDINGS_FILE)
    source = out_dir / stage_file
    findings: list[dict] = json.loads(source.read_text(encoding="utf-8"))

    info_path = out_dir / INFO_FILE
    info: dict = (
        json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    )

    return findings, info


def source_path_from_info(info: dict) -> str | None:
    """Extract the original document path from an ``info.json`` mapping.

    Args:
        info: Run metadata mapping loaded from ``info.json``.

    Returns:
        The original document source path string, or ``None`` when absent.
    """
    return info.get("input", {}).get("source_path")


def run_display_name(out_dir: Path) -> str:
    """Return a short, human-friendly label for a run directory.

    The function prefers a student id stored in the run info, then the
    original source file name, and finally falls back to the directory name.

    Args:
        out_dir: Path to the run output directory.

    Returns:
        A displayable string identifying the run.
    """
    info_path = out_dir / INFO_FILE
    if info_path.exists():
        info = json.loads(info_path.read_text(encoding="utf-8"))
        input_info = info.get("input", {})
        student_id = input_info.get("student_id")
        if student_id:
            return student_id
        source = input_info.get("source_path")
        if source:
            return Path(source).name
    return out_dir.name

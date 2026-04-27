"""Data-layer helpers for the review UI.

Author: Matúš Csirik

Loads pre-generated pipeline output from an ``out/<stem>/`` directory.
"""

import json
from functools import lru_cache
from pathlib import Path

FINDINGS_FILE = "findings.json"
JUDGED_FILE = "judged_findings.json"
RAW_FILE = "raw_findings.json"
INFO_FILE = "info.json"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

PIPELINE_STAGES: dict[str, str] = {
    "Final": FINDINGS_FILE,
    "Judged": JUDGED_FILE,
    "Raw": RAW_FILE,
}

VISIBLE_PIPELINE_STAGES: list[str] = ["Final", "Judged"]

_COURSE_RULEBOOK_FILES: dict[str, list[str]] = {
    "ipp": ["rulebook_ipp2526.json", "rulebook.json"],
    "ifj": ["rulebook_ifj.json", "rulebook.json"],
}

_DEFAULT_RULEBOOK_FILES: list[str] = [
    "rulebook.json",
    "rulebook_ipp2526.json",
    "rulebook_ifj.json",
]


def available_stages(out_dir: Path) -> list[str]:
    """Return the pipeline stage labels available in ``out_dir``.

    Args:
        out_dir: Directory containing pipeline output files.

    Returns:
        A list of stage names that have corresponding output files present.
    """
    return [
        label
        for label in VISIBLE_PIPELINE_STAGES
        if (out_dir / PIPELINE_STAGES[label]).exists()
    ]


def load_run(out_dir: Path, stage: str = "Final") -> tuple[list[dict], dict]:
    """Load findings and run info for a given pipeline stage.

    Args:
        out_dir: Directory with the run output files.
        stage: Stage label to load (e.g. 'Final' or 'Judged').

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


def load_dismissed_candidates(out_dir: Path) -> list[dict]:
    """Load dismissed findings from the judged stage.

    Returns a list of findings with ``judge_status == 'judged_dismissed'`` that
    are present in ``judged_findings.json`` but not present in final
    ``findings.json``.
    """
    final_findings, _ = load_run(out_dir, stage="Final")
    final_ids = {str(f.get("finding_id", "")) for f in final_findings}

    judged_path = out_dir / JUDGED_FILE
    if not judged_path.exists():
        return []

    judged_findings, _ = load_run(out_dir, stage="Judged")
    dismissed: list[dict] = []
    for finding in judged_findings:
        finding_id = str(finding.get("finding_id", ""))
        if (
            finding.get("judge_status") == "judged_dismissed"
            and finding_id
            and finding_id not in final_ids
        ):
            candidate = dict(finding)
            candidate["is_dismissed_candidate"] = True
            dismissed.append(candidate)

    return dismissed


def source_path_from_info(info: dict) -> str | None:
    """Extract the original document path from an ``info.json`` mapping.

    Args:
        info: Run metadata mapping loaded from ``info.json``.

    Returns:
        The original document source path string, or ``None`` when absent.
    """
    return info.get("input", {}).get("source_path")


def run_display_name(out_dir: Path) -> str:
    """Return the full run directory name for picker display.

    Args:
        out_dir: Path to the run output directory.

    Returns:
        A displayable string identifying the run.
    """
    return out_dir.name


@lru_cache(maxsize=2048)
def _run_info(out_dir: Path) -> dict:
    """Load and cache ``info.json`` for a run directory."""
    info_path = out_dir / INFO_FILE
    if not info_path.exists():
        return {}
    return json.loads(info_path.read_text(encoding="utf-8"))


def run_student_prefix(out_dir: Path) -> str | None:
    """Return the first 6-character student prefix for a run, if available.

    The value is resolved from ``info.json`` first and falls back to the run
    directory name.
    """
    info = _run_info(out_dir)
    student_id = info.get("input", {}).get("student_id")
    if isinstance(student_id, str):
        clean_student_id = student_id.strip()
        if clean_student_id:
            return clean_student_id[:6]

    clean_name = out_dir.name.strip()
    if clean_name:
        return clean_name[:6]
    return None


@lru_cache(maxsize=4)
def rubric_lookup(
    course: str | None = None,
) -> dict[str, dict[str, str | float | None]]:
    """Return a rubric lookup keyed by assessment criterion code.

    Args:
        course: Optional course identifier used for preferred rulebook order.

    Returns:
        Mapping from AC code to a compact metadata mapping with title and
        plain-language criterion guidance.
    """
    course_key = (course or "").strip().lower()
    file_names = _COURSE_RULEBOOK_FILES.get(course_key, _DEFAULT_RULEBOOK_FILES)

    lookup: dict[str, dict[str, str | float | None]] = {}
    for file_name in file_names:
        rulebook_path = _PROJECT_ROOT / "config" / file_name
        if not rulebook_path.exists():
            continue

        raw_data = json.loads(rulebook_path.read_text(encoding="utf-8"))
        rules = raw_data.get("rules", [])
        for rule in rules:
            ac_code = rule.get("ac_code")
            if not ac_code or ac_code in lookup:
                continue

            title = rule.get("title") or ac_code
            criterion_text = rule.get("prompt_instruction") or ""
            severity_weight_raw = rule.get("severity_weight")
            try:
                severity_weight = (
                    float(severity_weight_raw)
                    if severity_weight_raw is not None
                    else None
                )
            except TypeError, ValueError:
                severity_weight = None
            lookup[ac_code] = {
                "title": title,
                "criterion_text": criterion_text,
                "severity_weight": severity_weight,
            }

    return lookup

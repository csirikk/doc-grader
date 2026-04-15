"""Evaluate pipeline output against the IPP gold dataset.

The pipeline must be run on the student documents before running this script.
Results show code-level and impact-level agreement/disagreement between the
tool and human graders.

IMPORTANT: Disagreement does not imply the tool is wrong. The gold dataset is
not a perfect reference -- it reflects one grader's judgement per submission.

Usage::

    python notebooks/scripts/evaluate_gold.py --par-dir PATH --int-dir PATH [options]
    python notebooks/scripts/evaluate_gold.py --par-dir PATH [options]  # par only
    python notebooks/scripts/evaluate_gold.py --int-dir PATH [options]  # int only

Arguments:
    --par-dir   Output directory for task variant 'par' (each subdir is a student_id
                containing findings.json produced by the pipeline).
    --int-dir   Output directory for task variant 'int' (same structure).
    --gold      Path to gold CSV (default: data/judge_gold/gold_ipp_data.csv).
    --variant   par | int | all  (default: all)
    --out-dir   Where to write reports (default: outputs/).
    --verbose   Enable DEBUG logging.
"""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
from analysis import MAX_DOC_POINTS, load_clean_data
from dataset_parser import DOC_CODES, normalise_code_alias

from doc_grader.utils import configure_logging, write_csv, write_json

logger = logging.getLogger(__name__)

# Maps normalised legacy DOC_CODES to their canonical rulebook equivalents.
# Identical to LEGACY_TO_CANONICAL in compute_severity_weights.py.
#
# Only PENALTY codes are mapped. Bonus codes (DP, EX, NV, OOP, OK) are
# intentionally omitted: they represent positive grader awards, not
# violations, so mapping them would corrupt the gold violation set.
_LEGACY_TO_CANONICAL: dict[str, str] = {
    "BLOK": "SAZBA",
    "DOCTYPE": "SAZBA",
    "FORM": "SAZBA",
    "FORMAT": "SAZBA",
    "HOW": "HOV",
    "MDLINES": "SAZBA",
    "MEZ": "SAZBA",
    "MISSING": "STRUCT",
    "NVPDOC": "BADDP",
    "PRED": "SAZBA",
    "SINGLETON": "BADDP",
    "SPACETAB": "SAZBA",
    "UML": "NOUML",
    "WHY": "JAK",
}


def _to_canonical(code: str) -> str:
    """Normalise a legacy code and map it to its canonical rulebook form."""
    normalised = normalise_code_alias(code)
    return _LEGACY_TO_CANONICAL.get(normalised, normalised)


def _load_findings(
    output_dir: Path | None, student_id: str, task_variant: str
) -> list[dict] | None:
    """Load findings.json from the dir that corresponds to this task variant.

    Returns None (and warns) when the dir was not supplied or the file is absent.
    """
    if output_dir is None:
        logger.warning(
            "No output dir supplied for variant '%s' -- skipping student %s",
            task_variant,
            student_id,
        )
        return None
    path = output_dir / student_id / "findings.json"
    if not path.exists():
        logger.warning(
            "findings.json not found for student %s (%s) at %s -- skipping",
            student_id,
            task_variant,
            path,
        )
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _compare_student(
    student_id: str,
    task_variant: str,
    gold_rows: pd.DataFrame,
    tool_findings: list[dict],
    max_pts: int,
) -> dict:
    """Build a per-student comparison record.

    Parameters
    ----------
    gold_rows:
        Rows from the gold CSV for this student, already filtered to DOC_CODES.
    tool_findings:
        Deserialised list of Finding dicts from findings.json.
    max_pts:
        Maximum documentation points for this task variant, used to normalise
        both gold and tool impacts for cross-task comparability.
    """
    # --- Gold side ---
    gold_codes: set[str] = set()
    for code in gold_rows["code"]:
        gold_codes.add(_to_canonical(str(code)))

    # Compute gold impact sum:
    # - Non-shared rows: use impact_normalised directly.
    # - Shared rows: divide the event's impact equally among the codes that
    #   share it (identified by identical raw_text within the same student).
    #   This avoids both double-counting and silently discarding information.
    signed = gold_rows[
        gold_rows["impact"].notna() & gold_rows["impact_has_sign"].fillna(False)
    ]
    non_shared_sum = float(
        signed.loc[~signed["impact_shared"].fillna(False), "impact_normalised"].sum()
    )
    shared_rows = signed[signed["impact_shared"].fillna(False)]
    shared_sum = 0.0
    if not shared_rows.empty:
        # Each unique grading event (identified by raw_text) contributes its
        # impact exactly once, regardless of how many codes share it.
        shared_sum = float(
            shared_rows.groupby("raw_text", sort=False)["impact_normalised"]
            .first()
            .sum()
        )
    gold_impact_sum = non_shared_sum + shared_sum

    # --- Tool side ---
    tool_codes: set[str] = set()
    tool_impact_raw = 0.0
    for f in tool_findings:
        if f.get("judge_status") == "judged_dismissed":
            continue
        ac = f.get("ac_code") or ""
        if ac:
            tool_codes.add(ac)
        impact = f.get("impact")
        if impact is not None:
            tool_impact_raw += float(impact)

    tool_impact_sum = (tool_impact_raw / max_pts) if max_pts > 0 else 0.0

    # --- Set arithmetic ---
    overlap = gold_codes & tool_codes
    missed = gold_codes - tool_codes
    added = tool_codes - gold_codes

    doc_pts_val = gold_rows["doc_points"].iloc[0] if not gold_rows.empty else None
    doc_pts: int | None = int(doc_pts_val) if pd.notna(doc_pts_val) else None

    return {
        "student_id": student_id,
        "task_variant": task_variant,
        "doc_points": doc_pts,
        "max_doc_points": max_pts,
        "gold_code_count": len(gold_codes),
        "tool_code_count": len(tool_codes),
        "overlap_count": len(overlap),
        "missed_count": len(missed),
        "added_count": len(added),
        "gold_impact_sum": round(gold_impact_sum, 4),
        "tool_impact_sum": round(tool_impact_sum, 4),
        "impact_delta": round(tool_impact_sum - gold_impact_sum, 4),
        "gold_codes": "|".join(sorted(gold_codes)),
        "tool_codes": "|".join(sorted(tool_codes)),
        "overlap_codes": "|".join(sorted(overlap)),
        "missed_codes": "|".join(sorted(missed)),
        "added_codes": "|".join(sorted(added)),
    }


def _aggregate_code_stats(rows: list[dict]) -> dict[str, dict]:
    """Aggregate per-code agreement/missed/added counts across all students."""
    stats: dict[str, dict] = {}

    def _ensure(code: str) -> None:
        if code not in stats:
            stats[code] = {
                "agreement": 0,
                "missed_by_tool": 0,
                "added_by_tool": 0,
                "total_in_gold": 0,
                "total_in_tool": 0,
            }

    for row in rows:
        for col, stat_key in (
            ("overlap_codes", "agreement"),
            ("missed_codes", "missed_by_tool"),
            ("added_codes", "added_by_tool"),
        ):
            for c in row[col].split("|") if row[col] else []:
                _ensure(c)
                stats[c][stat_key] += 1

        for c in row["gold_codes"].split("|") if row["gold_codes"] else []:
            _ensure(c)
            stats[c]["total_in_gold"] += 1

        for c in row["tool_codes"].split("|") if row["tool_codes"] else []:
            _ensure(c)
            stats[c]["total_in_tool"] += 1

    return dict(sorted(stats.items()))


_PER_STUDENT_FIELDNAMES: list[str] = [
    "student_id",
    "task_variant",
    "doc_points",
    "max_doc_points",
    "gold_code_count",
    "tool_code_count",
    "overlap_count",
    "missed_count",
    "added_count",
    "gold_impact_sum",
    "tool_impact_sum",
    "impact_delta",
    "gold_codes",
    "tool_codes",
    "overlap_codes",
    "missed_codes",
    "added_codes",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate pipeline output against the IPP gold dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--par-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Output directory for the 'par' (parser) task variant. Each subdir "
            "must be a student_id containing findings.json."
        ),
    )
    parser.add_argument(
        "--int-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Output directory for the 'int' (interpreter) task variant. Each "
            "subdir must be a student_id containing findings.json."
        ),
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to gold CSV (default: data/judge_gold/gold_ipp_data.csv).",
    )
    parser.add_argument(
        "--variant",
        choices=["par", "int", "all"],
        default="all",
        help="Task variant to evaluate (default: all).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs"),
        metavar="PATH",
        help="Directory for output reports (default: outputs/).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    args = parser.parse_args()

    configure_logging(logging.DEBUG if args.verbose else logging.INFO)

    # Resolve gold path
    gold_path: Path = args.gold or (
        Path(__file__).resolve().parent.parent.parent
        / "data"
        / "judge_gold"
        / "gold_ipp_data.csv"
    )
    if not gold_path.exists():
        logger.error("Gold CSV not found: %s", gold_path)
        raise SystemExit(1)

    variant_dirs: dict[str, Path | None] = {
        "par": args.par_dir,
        "int": args.int_dir,
    }
    if not any(variant_dirs.values()):
        logger.error("Provide at least one of --par-dir or --int-dir.")
        raise SystemExit(1)
    for vname, vdir in variant_dirs.items():
        if vdir is not None and not vdir.exists():
            logger.error("Output directory for '%s' not found: %s", vname, vdir)
            raise SystemExit(1)

    # --- Load and filter gold data ---
    df = load_clean_data(gold_path)

    # Keep only documentation-related codes (DOC_CODES).
    # Codes such as COMMENT, SRCFORMAT, DECOMPOSE, AUTHOR are intentionally
    # excluded because they relate to source code quality, not documentation.
    df = df[df["code"].apply(lambda c: normalise_code_alias(str(c)) in DOC_CODES)]

    if args.variant != "all":
        df = df[df["task_variant"] == args.variant]

    if df.empty:
        logger.error("No gold data found after filtering (variant=%s).", args.variant)
        raise SystemExit(1)

    # Iterate by (id, task_variant) pairs -- the same student ID can appear in
    # both 'par' and 'int' if they completed both tasks.
    student_variants: list[tuple[str, str]] = list(
        df[["id", "task_variant"]].drop_duplicates().itertuples(index=False, name=None)
    )
    logger.info(
        "Evaluating %d (student, variant) pair(s) from gold data (variant=%s)",
        len(student_variants),
        args.variant,
    )

    # --- Per-student comparison ---
    per_student_rows: list[dict] = []
    skipped: list[str] = []

    for student_id, task_variant in student_variants:
        student_df = df[(df["id"] == student_id) & (df["task_variant"] == task_variant)]
        year_str = str(student_df["year"].iloc[0])
        max_pts = MAX_DOC_POINTS.get((year_str, task_variant), 100)

        tool_findings = _load_findings(
            variant_dirs.get(task_variant), student_id, task_variant
        )
        if tool_findings is None:
            skipped.append(f"{student_id}/{task_variant}")
            continue

        row = _compare_student(
            student_id, task_variant, student_df, tool_findings, max_pts
        )
        per_student_rows.append(row)

    if skipped:
        logger.warning(
            "%d (student, variant) pair(s) skipped: %s",
            len(skipped),
            ", ".join(skipped),
        )

    if not per_student_rows:
        logger.error(
            "No students evaluated successfully -- nothing to write. "
            "Have you run the pipeline on the gold documents first?"
        )
        raise SystemExit(1)

    # --- Code-level aggregate stats ---
    code_stats = _aggregate_code_stats(per_student_rows)

    evaluated = len(per_student_rows)
    total_overlap = sum(r["overlap_count"] for r in per_student_rows)
    total_gold_codes = sum(r["gold_code_count"] for r in per_student_rows)
    total_tool_codes = sum(r["tool_code_count"] for r in per_student_rows)

    summary: dict = {
        "note": (
            "Disagreement does not imply the tool is wrong. "
            "The gold dataset reflects one grader's judgement and is not a perfect reference."
        ),
        "gold_csv": str(gold_path),
        "output_dirs": {k: str(v) for k, v in variant_dirs.items() if v is not None},
        "variant": args.variant,
        "total_students_in_gold": len(student_variants),
        "students_evaluated": evaluated,
        "students_skipped": len(skipped),
        "skipped_ids": skipped,
        "overall": {
            "total_gold_code_instances": total_gold_codes,
            "total_tool_code_instances": total_tool_codes,
            "total_overlap_instances": total_overlap,
            "overlap_rate_vs_gold": round(total_overlap / total_gold_codes, 4)
            if total_gold_codes
            else None,
        },
        "per_code": code_stats,
    }

    csv_path = args.out_dir / "eval_gold_per_student.csv"
    json_path = args.out_dir / "eval_gold_summary.json"
    write_csv(csv_path, per_student_rows, fieldnames=_PER_STUDENT_FIELDNAMES)
    write_json(json_path, summary)

    logger.info("Wrote per-student report to %s", csv_path)
    logger.info("Wrote summary report to %s", json_path)


if __name__ == "__main__":
    main()

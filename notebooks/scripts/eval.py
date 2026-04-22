"""Evaluate pipeline output against the IPP gold dataset.

Author: Matúš Csirik

The pipeline must be run on the student documents before running this script.
Results show code-level and impact-level agreement/disagreement between the
tool and human graders.

"""

import json
import logging
from collections import defaultdict
from pathlib import Path

import pandas as pd
from scipy.stats import pearsonr

from doc_grader.utils import write_csv, write_json

from .constants import BONUS_CODES, DOC_CODES, LEGACY_TO_CANONICAL, MAX_DOC_POINTS
from .dataset_analysis import load_clean_data
from .dataset_parser import normalise_code_alias

logger = logging.getLogger(__name__)


def _to_canonical(code: str) -> str:
    """Normalise a legacy code and map it to its canonical rulebook form."""
    normalised = normalise_code_alias(code)
    return LEGACY_TO_CANONICAL.get(normalised, normalised)


def _load_all_stages(
    output_dir: Path | None, student_id: str, task_variant: str
) -> tuple[list[dict] | None, list[dict], list[dict], dict, dict]:
    """Load the relevant .json files for one student.

    Returns (final, raw, judged, info, ir).
    final is None when the file is missing, skip that student.
    raw, judged, info, and ir return empty collections when absent.
    """
    if output_dir is None:
        logger.warning(
            "No output dir supplied for variant '%s', skipping student %s",
            task_variant,
            student_id,
        )
        return None, [], [], {}, {}

    base = output_dir / student_id
    stage_files: dict[str, str] = {
        "final": "findings.json",
        "raw": "raw_findings.json",
        "judged": "judged_findings.json",
        "info": "info.json",
        "ir": "ir.json",
    }
    stage_defaults: dict[str, list[dict] | dict | None] = {
        "final": None,
        "raw": [],
        "judged": [],
        "info": {},
        "ir": {},
    }

    loaded: dict[str, list[dict] | dict | None] = {}
    for key, filename in stage_files.items():
        path = base / filename
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                loaded[key] = json.load(fh)
        else:
            loaded[key] = stage_defaults[key]

    if loaded["final"] is None:
        logger.warning(
            "findings.json not found for student %s (%s) at %s, skipping",
            student_id,
            task_variant,
            base / stage_files["final"],
        )
        return None, [], [], {}, {}

    final: list[dict] = loaded["final"] if isinstance(loaded["final"], list) else []
    raw: list[dict] = loaded["raw"] if isinstance(loaded["raw"], list) else []
    judged: list[dict] = loaded["judged"] if isinstance(loaded["judged"], list) else []
    info: dict = loaded["info"] if isinstance(loaded["info"], dict) else {}
    ir: dict = loaded["ir"] if isinstance(loaded["ir"], dict) else {}

    return final, raw, judged, info, ir


def _compare_student(
    student_id: str,
    task_variant: str,
    gold_rows: pd.DataFrame,
    tool_findings: list[dict],
    max_pts: int,
    raw_findings: list[dict],
) -> dict:
    """Build a per-student comparison record against the gold CSV rows."""
    gold_codes = {_to_canonical(str(c)) for c in gold_rows["code"]}

    # Sum normalised impacts, deduplicating shared events by raw_text so each
    # grading event is counted exactly once even when multiple codes share it.
    signed = gold_rows[
        gold_rows["impact"].notna() & gold_rows["impact_has_sign"].fillna(False)
    ]
    non_shared_sum = float(
        signed.loc[~signed["impact_shared"].fillna(False), "impact_normalised"].sum()
    )
    shared_rows = signed[signed["impact_shared"].fillna(False)]
    shared_sum = 0.0
    if not shared_rows.empty:
        shared_sum = float(
            shared_rows.groupby("raw_text", sort=False)["impact_normalised"]
            .first()
            .sum()
        )
    gold_impact_sum = non_shared_sum + shared_sum

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

    overlap = gold_codes & tool_codes
    missed = gold_codes - tool_codes
    added = tool_codes - gold_codes

    doc_pts_val = gold_rows["doc_points"].iloc[0] if not gold_rows.empty else None
    doc_pts: int | None = int(doc_pts_val) if pd.notna(doc_pts_val) else None

    # impact = -(severity_weight * severity * max_doc_points), so max_pts + sum(impacts)
    # gives an estimated score on the same integer scale as doc_points.
    tool_raw_points = round(max_pts + tool_impact_raw)
    points_delta: int | None = (
        tool_raw_points - doc_pts if doc_pts is not None else None
    )
    tool_score_pct: float | None = (
        round((tool_raw_points / max_pts) * 100, 2) if max_pts > 0 else None
    )
    doc_score_pct: float | None = (
        round((doc_pts / max_pts) * 100, 2)
        if doc_pts is not None and max_pts > 0
        else None
    )
    points_delta_pct: float | None = (
        round((points_delta / max_pts) * 100, 2)
        if points_delta is not None and max_pts > 0
        else None
    )

    raw_codes = {f.get("ac_code") for f in raw_findings if f.get("ac_code")}
    raw_overlap = gold_codes & raw_codes

    generator_models = {
        f.get("generator_model") for f in raw_findings if f.get("generator_model")
    }
    judge_models = {f.get("judge_model") for f in tool_findings if f.get("judge_model")}

    return {
        "student_id": student_id,
        "task_variant": task_variant,
        "doc_points": doc_pts,
        "max_doc_points": max_pts,
        "tool_raw_points": tool_raw_points,
        "doc_score_pct": doc_score_pct,
        "tool_score_pct": tool_score_pct,
        "points_delta": points_delta,
        "points_delta_pct": points_delta_pct,
        "generator_models": ", ".join(sorted(m for m in generator_models if m)),
        "judge_models": ", ".join(sorted(m for m in judge_models if m)),
        "gold_code_count": len(gold_codes),
        "tool_code_count": len(tool_codes),
        "raw_code_count": len(raw_codes),
        "overlap_count": len(overlap),
        "missed_count": len(missed),
        "added_count": len(added),
        "raw_overlap_count": len(raw_overlap),
        "raw_missed_count": len(gold_codes - raw_codes),
        "raw_added_count": len(raw_codes - gold_codes),
        "gold_impact_sum": round(gold_impact_sum, 4),
        "tool_impact_sum": round(tool_impact_sum, 4),
        "impact_delta": round(tool_impact_sum - gold_impact_sum, 4),
        "gold_codes": "|".join(sorted(gold_codes)),
        "tool_codes": "|".join(sorted(tool_codes)),
        "overlap_codes": "|".join(sorted(overlap)),
        "missed_codes": "|".join(sorted(missed)),
        "added_codes": "|".join(sorted(added)),
    }


def _operational_fields(info: dict, generator_models: str, judge_models: str) -> dict:
    """Extract operational metrics from info.json for inclusion in a per-student row."""
    usage = info.get("usage", {})
    by_model = usage.get("by_model", {})
    n_api_calls = sum(m.get("calls", 0) for m in by_model.values())

    gen_models_set = set(generator_models.split(", ")) if generator_models else set()
    judge_models_set = set(judge_models.split(", ")) if judge_models else set()

    gen_cost = (
        sum(m.get("cost_eur", 0) for k, m in by_model.items() if k in gen_models_set)
        if gen_models_set
        else None
    )
    judge_cost = (
        sum(m.get("cost_eur", 0) for k, m in by_model.items() if k in judge_models_set)
        if judge_models_set
        else None
    )

    mimetype = info.get("input", {}).get("origin", {}).get("mimetype", "")
    if "pdf" in mimetype:
        doc_type = "pdf"
    elif "markdown" in mimetype:
        doc_type = "md"
    else:
        doc_type = None

    stage_times = info.get("stage_times", {})
    analyser_time = (
        round(sum(v for k, v in stage_times.items() if k not in ("parse", "judge")), 2)
        or None
    )
    doc_stats = info.get("document", {})

    return {
        "doc_type": doc_type,
        "cost_eur": usage.get("total_cost_eur"),
        "generator_cost_eur": gen_cost,
        "judge_cost_eur": judge_cost,
        "prompt_tokens": usage.get("total_prompt_tokens"),
        "completion_tokens": usage.get("total_completion_tokens"),
        "cached_tokens": usage.get("total_cached_tokens"),
        "n_api_calls": n_api_calls if by_model else None,
        "elapsed_seconds": info.get("elapsed_seconds"),
        "parse_time": stage_times.get("parse"),
        "analyser_time": analyser_time,
        "judge_time": stage_times.get("judge"),
        "total_words": doc_stats.get("total_words"),
        "total_pictures": doc_stats.get("total_pictures"),
    }


def _col_counts(df: pd.DataFrame, col: str) -> pd.Series:
    """Return value counts for a pipe-separated code column."""
    return df[col].replace("", pd.NA).dropna().str.split("|").explode().value_counts()


def _aggregate_code_stats(df: pd.DataFrame) -> dict[str, dict]:
    """Aggregate per-code agreement/missed/added counts across all students."""
    agreement = _col_counts(df, "overlap_codes")
    missed = _col_counts(df, "missed_codes")
    added = _col_counts(df, "added_codes")
    total_gold = _col_counts(df, "gold_codes")
    total_tool = _col_counts(df, "tool_codes")

    all_codes = sorted(
        set(agreement.index)
        | set(missed.index)
        | set(added.index)
        | set(total_gold.index)
        | set(total_tool.index)
    )

    stats: dict[str, dict] = {}
    for code in all_codes:
        n_agree = int(agreement.get(code, 0))
        n_gold = int(total_gold.get(code, 0))
        n_tool = int(total_tool.get(code, 0))
        precision = round(n_agree / n_tool, 4) if n_tool else None
        recall = round(n_agree / n_gold, 4) if n_gold else None
        f1: float | None = None
        if precision and recall:
            f1 = round(2 * precision * recall / (precision + recall), 4)
        stats[code] = {
            "agreement": n_agree,
            "missed_by_tool": int(missed.get(code, 0)),
            "added_by_tool": int(added.get(code, 0)),
            "total_in_gold": n_gold,
            "total_in_tool": n_tool,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return stats


_PER_STUDENT_FIELDNAMES: list[str] = [
    "student_id",
    "task_variant",
    "directory_alias",
    "generator_models",
    "judge_models",
    "doc_points",
    "max_doc_points",
    "tool_raw_points",
    "doc_score_pct",
    "tool_score_pct",
    "points_delta",
    "points_delta_pct",
    "has_gold_bonus",
    "gold_code_count",
    "tool_code_count",
    "raw_code_count",
    "overlap_count",
    "missed_count",
    "added_count",
    "raw_overlap_count",
    "raw_missed_count",
    "raw_added_count",
    "gold_impact_sum",
    "tool_impact_sum",
    "impact_delta",
    "doc_type",
    "doc_language",
    "doc_language",
    "cost_eur",
    "generator_cost_eur",
    "judge_cost_eur",
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "n_api_calls",
    "elapsed_seconds",
    "parse_time",
    "analyser_time",
    "judge_time",
    "total_words",
    "total_pictures",
    "gold_codes",
    "tool_codes",
    "overlap_codes",
    "missed_codes",
    "added_codes",
]


def _aggregate_pipeline_stats(pipeline_accumulator: dict[str, dict]) -> dict[str, dict]:
    """Add survival_rate to each code entry and sort by raw count descending."""
    return {
        code: {
            **counts,
            "survival_rate": round(counts["final"] / counts["raw"], 4)
            if counts["raw"]
            else None,
        }
        for code, counts in sorted(
            pipeline_accumulator.items(), key=lambda kv: -kv[1]["raw"]
        )
    }


def _aggregate_operational_stats(df: pd.DataFrame) -> dict:
    """Aggregate cost, token, and latency metrics."""
    if df.empty:
        return {}

    total_findings = int(df["overlap_count"].sum() + df["added_count"].sum())
    total_cost = df["cost_eur"].sum()

    per_variant_cost: dict[str, dict] = {}
    for variant in ("par", "int"):
        var_costs = df[df["task_variant"] == variant]["cost_eur"].dropna()
        per_variant_cost[variant] = {
            "n": len(var_costs),
            "mean_cost_eur": round(float(var_costs.mean()), 4)
            if not var_costs.empty
            else None,
            "total_cost_eur": round(float(var_costs.sum()), 4)
            if not var_costs.empty
            else None,
        }

    mean_cost = df["cost_eur"].mean()
    mean_elapsed = df["elapsed_seconds"].mean()

    def _col_mean(col: str) -> float | None:
        s = df[col].dropna()
        return round(float(s.mean()), 4) if not s.empty else None

    # Cache hit rate: fraction of prompt tokens served from cache.
    cache_hit_rate: float | None = None
    valid_prompts = df["prompt_tokens"].dropna()
    if not valid_prompts.empty:
        cache_hit_rate = round(
            float((df["cached_tokens"] / df["prompt_tokens"]).mean()), 4
        )

    return {
        "n_with_operational_data": int(df["cost_eur"].notna().sum()),
        "total_cost_eur": round(float(total_cost), 4)
        if pd.notna(total_cost) and total_cost
        else None,
        "mean_cost_eur": round(float(mean_cost), 4) if pd.notna(mean_cost) else None,
        "per_variant_cost": per_variant_cost,
        "projected_cohort_cost_eur": round(float(mean_cost) * 600, 2)
        if pd.notna(mean_cost)
        else None,
        "cost_per_finding_eur": round(float(total_cost) / total_findings, 6)
        if total_cost and total_findings
        else None,
        "mean_prompt_tokens": _col_mean("prompt_tokens"),
        "mean_completion_tokens": _col_mean("completion_tokens"),
        "mean_cached_tokens": _col_mean("cached_tokens"),
        "mean_cache_hit_rate": cache_hit_rate,
        "mean_api_calls": _col_mean("n_api_calls"),
        "mean_elapsed_seconds": round(float(mean_elapsed), 4)
        if pd.notna(mean_elapsed)
        else None,
        "max_elapsed_seconds": round(float(df["elapsed_seconds"].max()), 4)
        if not df["elapsed_seconds"].dropna().empty
        else None,
        "estimated_docs_per_hour": round(3600 / float(mean_elapsed), 1)
        if pd.notna(mean_elapsed)
        else None,
    }


def _aggregate_score_correlations(df: pd.DataFrame) -> dict:
    """
    Pearson r between gold doc_points and tool_raw_points,
    overall and per-variant.
    """
    result: dict[str, dict] = {}
    subsets = [
        ("all", df),
        ("par", df[df["task_variant"] == "par"]),
        ("int", df[df["task_variant"] == "int"]),
    ]
    for label, subset in subsets:
        valid = subset.dropna(subset=["doc_points", "tool_raw_points"])
        if len(valid) < 3:
            result[label] = {"pearson_r": None, "p_value": None, "n": len(valid)}
            continue
        res = pearsonr(valid["doc_points"], valid["tool_raw_points"])
        result[label] = {
            "pearson_r": round(float(res[0]), 4),  # type: ignore
            "p_value": round(float(res[1]), 4),  # type: ignore
            "n": len(valid),
        }
    return result


def _point_stats(df: pd.DataFrame) -> dict:
    """MAE and mean delta for a subset of the per-student DataFrame."""
    col = pd.to_numeric(df["points_delta"], errors="coerce").dropna()
    col_pct = (
        pd.to_numeric(df["points_delta_pct"], errors="coerce").dropna()
        if "points_delta_pct" in df.columns
        else pd.Series(dtype=float)
    )
    if col.empty:
        return {
            "n": len(col),
            "mean_delta": None,
            "mae": None,
            "mean_delta_pct": None,
            "mae_pct": None,
        }
    return {
        "n": len(col),
        "mean_delta": round(float(col.mean()), 2),
        "mae": round(float(col.abs().mean()), 2),
        "mean_delta_pct": (
            round(float(col_pct.mean()), 2) if not col_pct.empty else None
        ),
        "mae_pct": round(float(col_pct.abs().mean()), 2) if not col_pct.empty else None,
    }


def _aggregate_bonus_split(df: pd.DataFrame, df_all: pd.DataFrame) -> dict:
    """Split points-delta stats by whether the student received a gold bonus award."""
    bonus_students = set(
        df_all.loc[
            df_all["code"].isin(BONUS_CODES)
            & df_all["impact_has_sign"].fillna(False)
            & (pd.to_numeric(df_all["impact"], errors="coerce") > 0),
            "id",
        ]
    )
    mask = df["student_id"].isin(bonus_students)
    return {
        "with_bonus": _point_stats(df[mask]),
        "without_bonus": _point_stats(df[~mask]),
    }


def _aggregate_by_column(df: pd.DataFrame, column_name: str) -> dict:
    """Group by one column and aggregate point stats, P/R/F1, and score correlation."""
    result: dict[str, dict] = {}
    if column_name not in df.columns:
        return result

    if column_name == "task_variant":
        group_values = [
            value for value in ("par", "int") if value in set(df[column_name])
        ]
    else:
        group_values = df[column_name].dropna().unique().tolist()

    for group_value in group_values:
        if not group_value:
            continue
        subset = df[df[column_name] == group_value]
        if subset.empty:
            continue
        code_stats = _aggregate_code_stats(subset)
        corr = _aggregate_score_correlations(subset)
        result[group_value] = {
            **_aggregate_point_stats(subset),
            **_aggregate_prf_stats(code_stats),
            "pearson_r": corr["all"]["pearson_r"],
            "pearson_p": corr["all"]["p_value"],
            "n": len(subset),
        }
    return result


def _aggregate_point_stats(df: pd.DataFrame) -> dict:
    """MAE and mean delta over doc_points vs tool_raw_points."""
    stats = _point_stats(df)
    return {
        "points_mae": stats["mae"],
        "points_mean_delta": stats["mean_delta"],
        "points_mae_pct": stats["mae_pct"],
        "points_mean_delta_pct": stats["mean_delta_pct"],
    }


def _aggregate_prf_stats(code_stats: dict[str, dict]) -> dict:
    """Compute macro average precision, recall, and F1 across all codes."""
    precisions = [
        s["precision"] for s in code_stats.values() if s["precision"] is not None
    ]
    recalls = [s["recall"] for s in code_stats.values() if s["recall"] is not None]
    f1s = [s["f1"] for s in code_stats.values() if s["f1"] is not None]
    return {
        "macro_precision": round(sum(precisions) / len(precisions), 4)
        if precisions
        else None,
        "macro_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
    }


def _log_summary(summary: dict) -> None:
    overall = summary["overall"]
    logger.info(
        "Students evaluated: %d (skipped: %d) | variant: %s",
        summary["students_evaluated"],
        summary["students_skipped"],
        summary["variant"],
    )
    if (rate := overall.get("overlap_rate_vs_gold")) is not None:
        logger.info(
            "Code overlap vs gold: %.1f%% (%d/%d instances)",
            rate * 100,
            overall["total_overlap_instances"],
            overall["total_gold_code_instances"],
        )
    if (mae := overall.get("points_mae")) is not None:
        mae_pct = overall.get("points_mae_pct")
        delta_pct = overall.get("points_mean_delta_pct")
        if mae_pct is not None and delta_pct is not None:
            logger.info(
                (
                    "Points MAE: %.1f pts (%.2f%% pts) | "
                    "mean delta: %+.1f pts (%+.2f%% pts)"
                ),
                mae,
                mae_pct,
                overall["points_mean_delta"],
                delta_pct,
            )
        else:
            logger.info(
                "Points MAE: %.1f pts | mean delta: %+.1f pts",
                mae,
                overall["points_mean_delta"],
            )
    if (f1 := overall.get("macro_f1")) is not None:
        logger.info(
            "Macro P/R/F1: %.3f / %.3f / %.3f",
            overall["macro_precision"],
            overall["macro_recall"],
            f1,
        )

    per_code = summary["per_code"]
    top_missed = sorted(
        per_code.items(), key=lambda kv: kv[1]["missed_by_tool"], reverse=True
    )[:5]
    top_added = sorted(
        per_code.items(), key=lambda kv: kv[1]["added_by_tool"], reverse=True
    )[:5]
    logger.info(
        "Top missed codes: %s",
        ", ".join(
            f"{c}({s['missed_by_tool']})" for c, s in top_missed if s["missed_by_tool"]
        ),
    )
    logger.info(
        "Top added codes:  %s",
        ", ".join(
            f"{c}({s['added_by_tool']})" for c, s in top_added if s["added_by_tool"]
        ),
    )
    op = summary.get("operational", {})
    if op.get("mean_cost_eur") is not None:
        logger.info(
            "Cost: mean %.4f EUR/doc | total %.4f EUR | projected cohort %.2f EUR",
            op["mean_cost_eur"],
            op["total_cost_eur"],
            op["projected_cohort_cost_eur"],
        )
    if op.get("mean_elapsed_seconds") is not None:
        logger.info(
            "Latency: mean %.1fs/doc | ~%.0f docs/hour",
            op["mean_elapsed_seconds"],
            op["estimated_docs_per_hour"],
        )


def evaluate_pipeline(
    variant_dirs: dict[str, Path | None] | None = None,
    par_dir: Path | None = None,
    int_dir: Path | None = None,
    gold_path: Path | None = None,
    variant: str = "all",
    out_dir: Path = Path("outputs/gold_eval"),
) -> tuple[pd.DataFrame, dict]:
    """Evaluate pipeline output against the IPP gold dataset."""
    # Resolve gold path
    if gold_path is None:
        gold_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data"
            / "judge_gold"
            / "gold_ipp_data.csv"
        )
    if not gold_path.exists():
        logger.error("Gold CSV not found: %s", gold_path)
        raise SystemExit(1)

    if variant_dirs is None:
        variant_dirs = {
            "par": par_dir,
            "int": int_dir,
        }

    if not any(variant_dirs.values()):
        logger.error("Provide at least one of par_dir or int_dir.")
        raise SystemExit(1)
    for vname, vdir in variant_dirs.items():
        if vdir is not None and not vdir.exists():
            logger.error("Output directory for '%s' not found: %s", vname, vdir)
            raise SystemExit(1)

    # Load and filter gold data
    # df_all is kept unfiltered for bonus-code detection
    df_all = load_clean_data(gold_path)
    df = df_all[
        df_all["code"].apply(lambda c: normalise_code_alias(str(c)) in DOC_CODES)
    ]

    if variant != "all":
        df = df[df["task_variant"] == variant]

    if df.empty:
        logger.error("No gold data found after filtering (variant=%s).", variant)
        raise SystemExit(1)

    # Iterate by (id, task_variant) pairs
    student_variants: list[tuple[str, str]] = list(
        df[["id", "task_variant"]].drop_duplicates().itertuples(index=False, name=None)
    )
    logger.info(
        "Evaluating %d (student, variant) pair(s) from gold data (variant=%s)",
        len(student_variants),
        variant,
    )

    # Per-student comparison
    per_student_rows: list[dict] = []
    skipped: list[str] = []
    # Accumulate raw/dismissed/adjusted/final counts per code for pipeline stats
    pipeline_acc: dict[str, dict] = defaultdict(
        lambda: {"raw": 0, "dismissed": 0, "adjusted": 0, "final": 0}
    )

    for alias, vdir in variant_dirs.items():
        if vdir is None:
            continue

        actual_task_variant = "par" if alias.startswith("par") else "int"

        for student_id, task_variant in student_variants:
            if task_variant != actual_task_variant:
                continue

            student_df = df[
                (df["id"] == student_id) & (df["task_variant"] == task_variant)
            ]
            year_str = str(student_df["year"].iloc[0])
            max_pts = MAX_DOC_POINTS.get((year_str, task_variant), 100)

            final, raw, judged, info, ir = _load_all_stages(
                vdir, student_id, task_variant
            )
            if final is None:
                skipped.append(f"{student_id}/{alias}")
                continue

            for f in raw:
                if code := f.get("ac_code"):
                    pipeline_acc[code]["raw"] += 1
            for f in judged:
                if code := f.get("ac_code"):
                    status = f.get("judge_status")
                    if status == "judged_dismissed":
                        pipeline_acc[code]["dismissed"] += 1
                    elif status == "judged_adjusted":
                        pipeline_acc[code]["adjusted"] += 1
            for f in final:
                if code := f.get("ac_code"):
                    pipeline_acc[code]["final"] += 1

            row = _compare_student(
                student_id, task_variant, student_df, final, max_pts, raw_findings=raw
            )
            row["directory_alias"] = alias
            row.update(
                _operational_fields(
                    info, row.get("generator_models", ""), row.get("judge_models", "")
                )
            )
            row["doc_language"] = ir.get("language")
            per_student_rows.append(row)

    if skipped:
        logger.warning(
            "%d (student, variant) pair(s) skipped: %s",
            len(skipped),
            ", ".join(skipped),
        )

    if not per_student_rows:
        logger.error(
            "No students evaluated successfully, nothing to write. "
            "Have you run the pipeline on the gold documents first?"
        )
        raise SystemExit(1)

    # Annotate each row with whether the student received a bonus
    bonus_students: set[str] = set(
        df_all.loc[
            df_all["code"].isin(BONUS_CODES)
            & df_all["impact_has_sign"].fillna(False)
            & (pd.to_numeric(df_all["impact"], errors="coerce") > 0),
            "id",
        ]
    )
    for row in per_student_rows:
        row["has_gold_bonus"] = row["student_id"] in bonus_students

    df_students = pd.DataFrame(per_student_rows)

    code_stats = _aggregate_code_stats(df_students)

    evaluated = len(df_students)
    total_overlap = int(df_students["overlap_count"].sum())
    total_gold_codes = int(df_students["gold_code_count"].sum())
    total_tool_codes = int(df_students["tool_code_count"].sum())

    summary: dict = {
        "gold_csv": str(gold_path),
        "output_dirs": {k: str(v) for k, v in variant_dirs.items() if v is not None},
        "variant": variant,
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
            **_aggregate_point_stats(df_students),
            **_aggregate_prf_stats(code_stats),
            "score_correlations": _aggregate_score_correlations(df_students),
            "bonus_split": _aggregate_bonus_split(df_students, df_all),
        },
        "per_variant": _aggregate_by_column(df_students, "task_variant"),
        "per_format": _aggregate_by_column(df_students, "doc_type"),
        "per_language": _aggregate_by_column(df_students, "doc_language"),
        "per_generator_model": _aggregate_by_column(df_students, "generator_models"),
        "per_judge_model": _aggregate_by_column(df_students, "judge_models"),
        "pipeline_stats": _aggregate_pipeline_stats(pipeline_acc),
        "operational": _aggregate_operational_stats(df_students),
        "per_code": code_stats,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "eval_gold_per_student.csv"
    json_path = out_dir / "eval_gold_summary.json"
    write_csv(csv_path, per_student_rows, fieldnames=_PER_STUDENT_FIELDNAMES)
    write_json(json_path, summary)

    _log_summary(summary)
    logger.info("Wrote per-student report to %s", csv_path)
    logger.info("Wrote summary report to %s", json_path)
    return df_students, summary

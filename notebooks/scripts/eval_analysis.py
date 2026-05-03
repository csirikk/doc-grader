"""Human-reference evaluation visualisation and analysis.

Author: Matúš Csirik
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

from .visual_utils import (
    _FIG_H,
    _FIG_H_PER_ITEM,
    _FIG_W,
    AGREEMENT_PALETTE,
    EXECUTION_STAGE_PALETTE,
    FORMAT_PALETTE,
    LANGUAGE_PALETTE,
    METRIC_PALETTE,
    OPERATIONAL_METRIC_PALETTE,
    REFERENCE_LINE_ALPHA,
    REFERENCE_LINE_COLOR,
    REFERENCE_LINE_STYLE,
    REFERENCE_LINE_WIDTH,
    STAGE_PALETTE,
    TASK_VARIANT_PALETTE,
    _save_or_show,
    _validate_data,
    add_horizontal_reference_line,
    add_identity_reference_line,
    add_vertical_reference_line,
    format_facet_grid,
    move_legend_if_present,
    render_plot,
    set_integer_count_ticks,
    wrap_category_tick_labels,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from matplotlib.axes import Axes

logger = logging.getLogger(__name__)

_MODEL_NAME_MAP: dict[str, str] = {
    "ft:gpt-4.1-2025-04-14:personal:baduml-classifier-gold:DU8txcxh": "FT Vision",
    "gpt-5.4-nano-2026-03-17": "GPT 5.4 Nano",
    "gpt-5.4-mini-2026-03-17": "GPT 5.4 Mini",
    "gpt-5.4-2026-03-05": "GPT 5.4",
}

_CODE_SOURCE_PALETTE: dict[str, str] = {
    "human": "#3B3B3B",
    "tool (final)": "#1f77b4",
    "tool (raw)": "#9ecae1",
}

_DEFAULT_EVAL_DIR = Path(__file__).parent.parent.parent / "outputs" / "gold_eval"
_DEFAULT_DOCLING_BENCHMARK_DIR = (
    Path(__file__).parent.parent.parent / "outputs" / "docling_parser_benchmark"
)
_PARSER_MODE_ORDER = ["base", "tables_only", "ocr_only", "ocr_and_tables"]
_PARSER_MODE_LABELS = {
    "base": "base",
    "tables_only": "tables",
    "ocr_only": "ocr",
    "ocr_and_tables": "tables + ocr",
}
_PARSER_MODE_PALETTE = {
    "base": "#6c757d",
    "tables": "#4c78a8",
    "ocr": "#f28e2b",
    "tables + ocr": "#c44e52",
}


def load_eval_data(
    eval_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Load per-student CSV and summary JSON from an eval.py output directory."""
    if eval_dir is None:
        eval_dir = _DEFAULT_EVAL_DIR
    csv_path = eval_dir / "eval_gold_per_student.csv"
    json_path = eval_dir / "eval_gold_summary.json"

    df = pd.read_csv(csv_path)
    df["task_variant"] = df["task_variant"].astype("category")
    df["has_gold_bonus"] = df["has_gold_bonus"].map(
        {True: True, False: False, "True": True, "False": False}
    )

    for col in (
        "doc_points",
        "max_doc_points",
        "tool_raw_points",
        "points_delta",
        "gold_impact_sum",
        "tool_impact_sum",
        "impact_delta",
        "cost_eur",
        "prompt_tokens",
        "completion_tokens",
        "cached_tokens",
        "n_api_calls",
        "elapsed_seconds",
    ):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for model_col in ("generator_models", "judge_models"):
        if model_col in df.columns:
            df[model_col] = df[model_col].apply(
                lambda value: _format_model_name(value) if pd.notna(value) else value
            )

    df = _add_percentage_score_columns(df)

    summary: dict = {}
    if json_path.exists():
        with json_path.open(encoding="utf-8") as fh:
            summary = json.load(fh)

    return df, summary


def _add_percentage_score_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Derive score percentage columns for cross-variant comparability."""
    if "max_doc_points" not in df.columns:
        return df

    max_points = pd.to_numeric(df["max_doc_points"], errors="coerce")
    max_points = max_points.where(max_points > 0)

    if "doc_points" in df.columns:
        df["doc_score_pct"] = (
            pd.to_numeric(df["doc_points"], errors="coerce") / max_points
        ) * 100
    if "tool_raw_points" in df.columns:
        df["tool_score_pct"] = (
            pd.to_numeric(df["tool_raw_points"], errors="coerce") / max_points
        ) * 100
    if "points_delta" in df.columns:
        df["points_delta_pct"] = (
            pd.to_numeric(df["points_delta"], errors="coerce") / max_points
        ) * 100

    return df


def prepare_per_student_metrics(per_student_df: pd.DataFrame) -> pd.DataFrame:
    """Derive shared per-student quality columns used across evaluation charts."""

    required_cols = [
        "tool_code_count",
        "gold_code_count",
        "overlap_count",
        "points_delta",
        "points_delta_pct",
        "generator_models",
        "judge_models",
    ]
    missing_cols = sorted(set(required_cols) - set(per_student_df.columns))
    if missing_cols:
        missing_str = ", ".join(missing_cols)
        raise ValueError(f"prepare_per_student_metrics requires columns: {missing_str}")

    df = per_student_df.copy()
    tool_code_count = pd.to_numeric(df["tool_code_count"], errors="coerce")
    gold_code_count = pd.to_numeric(df["gold_code_count"], errors="coerce")
    overlap_count = pd.to_numeric(df["overlap_count"], errors="coerce")
    points_delta = pd.to_numeric(df["points_delta"], errors="coerce")
    points_delta_pct = pd.to_numeric(df["points_delta_pct"], errors="coerce")

    df["student_precision"] = (overlap_count / tool_code_count).where(
        tool_code_count > 0
    )
    df["student_recall"] = (overlap_count / gold_code_count).where(gold_code_count > 0)
    df["abs_points_delta"] = points_delta.abs()
    df["abs_points_delta_pct"] = points_delta_pct.abs()
    df["grader_judge_pair"] = (
        df["generator_models"].fillna("").astype(str)
        + " | "
        + df["judge_models"].fillna("").astype(str)
    )

    return df


def _per_code_df(summary: dict) -> pd.DataFrame:
    """Extract the per_code block from a summary dict into a tidy DataFrame."""
    if "per_code" not in summary:
        return pd.DataFrame()
    return pd.DataFrame.from_dict(summary["per_code"], orient="index").reset_index(
        names="code"
    )


def _pipeline_stats_df(summary: dict) -> pd.DataFrame:
    """Extract the pipeline_stats block from a summary dict into a tidy DataFrame."""
    if "pipeline_stats" not in summary:
        return pd.DataFrame()
    return pd.DataFrame.from_dict(
        summary["pipeline_stats"], orient="index"
    ).reset_index(names="code")


def load_docling_parser_benchmark(
    benchmark_dir: Path | None = None,
) -> pd.DataFrame:
    """Load the saved Docling parser benchmark timings table."""
    if benchmark_dir is None:
        benchmark_dir = _DEFAULT_DOCLING_BENCHMARK_DIR

    csv_path = benchmark_dir / "docling_parser_timings.csv"
    df = pd.read_csv(csv_path)
    if "mode" in df.columns:
        df["mode"] = pd.Categorical(
            df["mode"], categories=_PARSER_MODE_ORDER, ordered=True
        )
    return df


def visualise_score_scatter(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Scatter plot of human vs tool score as percentage of max points."""
    df = _add_percentage_score_columns(per_student_df.copy())
    df = df.dropna(subset=["doc_score_pct", "tool_score_pct"])
    x_lo = min(0.0, df["doc_score_pct"].min() - 2.0)
    x_hi = max(100.0, df["doc_score_pct"].max() + 2.0)
    y_lo = min(0.0, df["tool_score_pct"].min() - 5.0)
    y_hi = max(100.0, df["tool_score_pct"].max() + 5.0)

    def _plot_score_scatter(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.scatterplot(data=data, ax=ax, **kwargs)
        add_identity_reference_line(ax, label="_nolegend_")
        ax.set_xlim(x_lo, x_hi)
        ax.set_ylim(y_lo, y_hi)
        move_legend_if_present(ax, title="Task variant")

    return render_plot(
        _plot_score_scatter,
        data=df,
        title="Human Vs Tool Score Comparison (Normalised)",
        xlabel="Human Score (% of max points)",
        ylabel="Tool Score (% of max points)",
        save_path=save_path,
        x="doc_score_pct",
        y="tool_score_pct",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        s=80,
        zorder=3,
    )


def _ordered_variants(values: pd.Series) -> list[str]:
    """Return stable task-variant order limited to variants present in data."""

    return [variant for variant in ["par", "int"] if variant in values.unique()]


def _overlay_box_and_strip(
    ax: Axes,
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    *,
    order: list[str],
    palette: Mapping[str, tuple | str] | None = None,
    colour: tuple | str | None = None,
    point_alpha: float = 0.45,
    point_size: float = 4,
    horizontal: bool = False,
) -> None:
    x_axis = y_col if horizontal else x_col
    y_axis = x_col if horizontal else y_col
    boxplot_kwargs = {
        "data": data,
        "x": x_axis,
        "y": y_axis,
        "order": order,
        "showfliers": False,
        "fill": False,
        "linewidth": 1.5,
        "zorder": 2,
        "legend": False,
        "ax": ax,
    }
    stripplot_kwargs = {
        "data": data,
        "x": x_axis,
        "y": y_axis,
        "order": order,
        "dodge": False,
        "alpha": point_alpha,
        "size": point_size,
        "legend": False,
        "ax": ax,
    }

    if palette is not None:
        boxplot_kwargs["hue"] = x_col
        boxplot_kwargs["hue_order"] = order
        boxplot_kwargs["palette"] = palette
        stripplot_kwargs["hue"] = x_col
        stripplot_kwargs["hue_order"] = order
        stripplot_kwargs["palette"] = palette
    elif colour is not None:
        boxplot_kwargs["color"] = colour
        stripplot_kwargs["color"] = colour

    sns.boxplot(**boxplot_kwargs)
    sns.stripplot(**stripplot_kwargs)


def _visualise_student_metric_by_variant(
    per_student_df: pd.DataFrame,
    metric_col: str,
    title: str,
    ylabel: str,
    save_path: Path | None = None,
) -> Axes | None:
    """Box and strip plot of a single student-quality metric by task variant."""
    df = _validate_data(
        per_student_df,
        ["task_variant", metric_col],
        f"_visualise_student_metric_by_variant[{metric_col}]",
    )
    if df is None:
        return None

    variant_order = _ordered_variants(df["task_variant"])
    fig, ax = plt.subplots(figsize=(7, 4.5), layout="constrained")
    _overlay_box_and_strip(
        ax,
        df,
        "task_variant",
        metric_col,
        order=variant_order,
        palette=TASK_VARIANT_PALETTE,
    )
    ax.set_title(title)
    ax.set_xlabel("Task variant")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    _save_or_show(fig, save_path)
    return ax


def visualise_student_precision_by_variant(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Box and strip plot of student precision by task variant."""
    return _visualise_student_metric_by_variant(
        per_student_df,
        metric_col="student_precision",
        title="Student Precision by Variant",
        ylabel="Precision",
        save_path=save_path,
    )


def visualise_student_recall_by_variant(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Box and strip plot of student recall by task variant."""
    return _visualise_student_metric_by_variant(
        per_student_df,
        metric_col="student_recall",
        title="Student Recall by Variant",
        ylabel="Recall",
        save_path=save_path,
    )


def visualise_absolute_score_error_by_variant(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Box and strip plot of absolute score error by task variant."""
    df = _validate_data(
        per_student_df,
        ["task_variant", "abs_points_delta_pct"],
        "visualise_absolute_score_error_by_variant",
    )
    if df is None:
        return None

    variant_order = _ordered_variants(df["task_variant"])
    fig, ax = plt.subplots(figsize=(7, 4.5), layout="constrained")
    _overlay_box_and_strip(
        ax,
        df,
        "task_variant",
        "abs_points_delta_pct",
        order=variant_order,
        palette=TASK_VARIANT_PALETTE,
    )
    ax.set_title("Absolute Score Error by Variant")
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Absolute score error (% points)")
    _save_or_show(fig, save_path)
    return ax


def visualise_per_code_precision_recall(
    summary: dict,
    save_path: Path | None = None,
    max_codes: int = 15,
) -> Axes | None:
    """Grouped per-code precision and recall bars for the most frequent gold codes."""
    df = _per_code_df(summary)
    if df.empty:
        logger.warning(
            "per_code block is empty, skipping visualise_per_code_precision_recall"
        )
        return None

    plot_df = df.sort_values("total_in_gold", ascending=False).head(max_codes).copy()
    plot_df["precision"] = plot_df["precision"].fillna(0.0)
    melted = plot_df.melt(
        id_vars=["code"],
        value_vars=["precision", "recall"],
        var_name="metric",
        value_name="value",
    ).assign(
        metric=lambda d: d["metric"].map({"precision": "Precision", "recall": "Recall"})
    )

    def _plot_per_code_precision_recall(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.barplot(data=data, ax=ax, **kwargs)
        ax.set_ylim(0, 1.05)
        ax.tick_params(axis="x", rotation=45)
        move_legend_if_present(ax, title="Metric")

    return render_plot(
        _plot_per_code_precision_recall,
        data=melted,
        title="Per-code Precision and Recall (Top 15 by Gold Frequency)",
        xlabel="Code",
        ylabel="Metric value (%)",
        save_path=save_path,
        figsize=(12, 5),
        x="code",
        y="value",
        hue="metric",
        hue_order=["Precision", "Recall"],
        palette=METRIC_PALETTE,
        errorbar=None,
        y_pct=True,
    )


def summarise_group_quality(
    df: pd.DataFrame, group_col: str, min_n: int = 5
) -> pd.DataFrame:
    """Aggregate precision, recall, and absolute score error by grouping column."""
    grouped = df.groupby(group_col, observed=True)
    rows = []
    for name, group in grouped:
        if not isinstance(name, str):
            continue
        clean_name = " ".join(name.split())
        if clean_name in {"", "|"}:
            continue
        if len(group) < min_n:
            continue
        tool_total = group["tool_code_count"].sum()
        gold_total = group["gold_code_count"].sum()
        precision = (
            group["overlap_count"].sum() / tool_total if tool_total > 0 else pd.NA
        )
        recall = group["overlap_count"].sum() / gold_total if gold_total > 0 else pd.NA
        rows.append(
            {
                "group": clean_name,
                "n": len(group),
                "precision": precision,
                "recall": recall,
                "mae_pct": group["abs_points_delta_pct"].mean(),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["group", "n", "precision", "recall", "mae_pct"])

    return pd.DataFrame(rows).sort_values(["n", "precision"], ascending=[False, False])


def visualise_group_quality_bars(
    df: pd.DataFrame,
    title: str,
    label_formatter,
    save_path: Path | None = None,
) -> Axes | None:
    """Horizontal grouped bars for precision, recall, and normalised MAE."""
    if df.empty:
        logger.warning("No rows available for %s", title)
        return None

    plot_df = df.copy()
    plot_df["label"] = plot_df.apply(label_formatter, axis=1)
    plot_df["normalised_mae"] = plot_df["mae_pct"] / 100.0
    metric_order = ["precision", "recall", "normalised_mae"]
    metric_labels = {
        "precision": "Precision",
        "recall": "Recall",
        "normalised_mae": "Normalised MAE",
    }
    melted = plot_df.melt(
        id_vars=["label"],
        value_vars=metric_order,
        var_name="metric",
        value_name="value",
    )
    melted["metric"] = pd.Categorical(
        melted["metric"], categories=metric_order, ordered=True
    )
    melted["metric_label"] = melted["metric"].map(metric_labels)

    fig_height = max(4.5, 0.6 * len(plot_df))

    def _plot_group_quality_bars(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.barplot(data=data, ax=ax, **kwargs)
        ax.set_xlim(0.0, 1.0)
        move_legend_if_present(ax, title="Metric", loc="lower right")

    return render_plot(
        _plot_group_quality_bars,
        data=melted,
        title=title,
        xlabel="Metric value (%)",
        ylabel="Group",
        save_path=save_path,
        figsize=(12, fig_height),
        y="label",
        x="value",
        hue="metric_label",
        order=plot_df["label"].tolist(),
        hue_order=[metric_labels[key] for key in metric_order],
        palette=METRIC_PALETTE,
        errorbar=None,
        orient="h",
        x_pct=True,
    )


def summarise_stage_time_composition(per_student_df: pd.DataFrame) -> pd.DataFrame:
    """Return mean parse, analyser, and judge times grouped by grader model."""
    df = _validate_data(
        per_student_df,
        ["parse_time", "analyser_time", "judge_time", "generator_models"],
        "summarise_stage_time_composition",
    )
    if df is None:
        return pd.DataFrame()

    return (
        df.groupby("generator_models", observed=True)[
            ["parse_time", "analyser_time", "judge_time"]
        ]
        .mean()
        .sort_values("judge_time", ascending=False)
    )


def visualise_operational_metric_by_model(
    per_student_df: pd.DataFrame,
    metric_key: str,
    save_path: Path | None = None,
) -> Axes | None:
    """Single operational box and strip plot by model for one metric."""
    metric_specs = {
        "generator_cost": {
            "x_col": "generator_models",
            "y_col": "generator_cost_eur",
            "colour": OPERATIONAL_METRIC_PALETTE["generator_cost"],
            "title": "Generator Cost by Grader Model",
            "xlabel": "Generator cost (EUR)",
            "ylabel": "Grader model",
        },
        "judge_cost": {
            "x_col": "judge_models",
            "y_col": "judge_cost_eur",
            "colour": OPERATIONAL_METRIC_PALETTE["judge_cost"],
            "title": "Judge Cost by Judge Model",
            "xlabel": "Judge cost (EUR)",
            "ylabel": "Judge model",
        },
        "latency": {
            "x_col": "generator_models",
            "y_col": "elapsed_seconds",
            "colour": OPERATIONAL_METRIC_PALETTE["latency"],
            "title": "Latency by Grader Model",
            "xlabel": "Elapsed seconds",
            "ylabel": "Grader model",
        },
    }
    if metric_key not in metric_specs:
        raise ValueError(
            "metric_key must be one of 'generator_cost', 'judge_cost', or 'latency'"
        )

    spec = metric_specs[metric_key]
    df = _validate_data(
        per_student_df,
        [spec["x_col"], spec["y_col"]],
        f"visualise_operational_metric_by_model[{metric_key}]",
    )
    if df is None:
        return None

    order_counts = (
        df.groupby(spec["x_col"], observed=True)
        .size()
        .to_frame(name="n_rows")
        .sort_values("n_rows", ascending=False)
    )
    order = order_counts.index.tolist()
    fig_h = max(4.5, 1.5 + 0.7 * len(order))
    fig, ax = plt.subplots(figsize=(8.5, fig_h), layout="constrained")
    _overlay_box_and_strip(
        ax,
        df.dropna(subset=[spec["x_col"], spec["y_col"]]),
        spec["x_col"],
        spec["y_col"],
        order=order,
        colour=spec["colour"],
        horizontal=True,
    )
    ax.set_title(spec["title"])
    ax.set_xlabel(spec["xlabel"])
    ax.set_ylabel(spec["ylabel"])
    wrap_category_tick_labels(ax, axis="y", width=20)
    ax.tick_params(axis="y", labelsize=10, pad=8)
    _save_or_show(fig, save_path)
    return ax


def visualise_stage_time_composition(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Stacked mean stage-time bars by grader model."""
    stage_summary = summarise_stage_time_composition(per_student_df)
    if stage_summary.empty:
        logger.warning(
            "No stage-time rows available, skipping visualise_stage_time_composition"
        )
        return None

    plot_df = stage_summary.rename(
        columns={
            "parse_time": "parse",
            "analyser_time": "analysers",
            "judge_time": "judge",
        }
    )
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    plot_df[["parse", "analysers", "judge"]].plot(
        kind="bar",
        stacked=True,
        color=[
            EXECUTION_STAGE_PALETTE["parse"],
            EXECUTION_STAGE_PALETTE["analysers"],
            EXECUTION_STAGE_PALETTE["judge"],
        ],
        ax=ax,
    )
    ax.set_title("Mean Stage-Time Composition by Grader Model")
    ax.set_xlabel("Grader model")
    ax.set_ylabel("Mean latency (s)")
    wrap_category_tick_labels(ax, axis="x", width=14)
    ax.tick_params(axis="x", labelsize=10, pad=4)
    ax.legend(loc="best")
    _save_or_show(fig, save_path)
    return ax


def visualise_docling_parser_timing_by_mode(
    benchmark_df: pd.DataFrame,
    save_path: Path | list[Path] | tuple[Path, ...] | None = None,
    doc_type: str = "pdf",
) -> Axes | None:
    """Show parser timing spread by Docling configuration for one document type."""
    df = _validate_data(
        benchmark_df,
        ["doc_type", "mode", "elapsed_seconds"],
        "visualise_docling_parser_timing_by_mode",
    )
    if df is None:
        return None

    plot_df = df[df["doc_type"] == doc_type].copy()
    if plot_df.empty:
        logger.warning(
            "No Docling benchmark rows for doc_type=%s, skipping parser timing chart",
            doc_type,
        )
        return None

    plot_df["mode"] = pd.Categorical(
        plot_df["mode"], categories=_PARSER_MODE_ORDER, ordered=True
    )
    plot_df = plot_df.sort_values("mode")
    plot_df["mode_label"] = plot_df["mode"].map(_PARSER_MODE_LABELS)
    mode_order = [
        _PARSER_MODE_LABELS[mode]
        for mode in _PARSER_MODE_ORDER
        if (plot_df["mode"] == mode).any()
    ]

    fig, ax = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
    _overlay_box_and_strip(
        ax,
        plot_df.dropna(subset=["mode_label", "elapsed_seconds"]),
        "mode_label",
        "elapsed_seconds",
        order=mode_order,
        palette=_PARSER_MODE_PALETTE,
        point_alpha=0.35,
        point_size=3.5,
    )
    format_facet_grid(
        ax,
        xlabel="Parser configuration",
        ylabel="Parse time (s)",
        titles="Docling PDF Parse Time by Parser Configuration",
    )
    wrap_category_tick_labels(ax, axis="x", width=12)
    _save_or_show(fig, save_path)
    return ax


def visualise_impact_delta_scatter(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Scatter of normalised human impact vs tool impact with identity line."""
    df = per_student_df.dropna(subset=["gold_impact_sum", "tool_impact_sum"])
    all_vals = pd.concat([df["gold_impact_sum"], df["tool_impact_sum"]])
    lo, hi = all_vals.min() - 0.02, all_vals.max() + 0.02

    def _plot_impact_delta_scatter(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.scatterplot(data=data, ax=ax, **kwargs)
        add_identity_reference_line(ax, label="_nolegend_")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        move_legend_if_present(ax, title="Task variant")

    return render_plot(
        _plot_impact_delta_scatter,
        data=df,
        title="Human Vs Tool Impact Score Comparison",
        xlabel="Human Impact Score (%)",
        ylabel="Tool Impact Score (%)",
        save_path=save_path,
        x="gold_impact_sum",
        y="tool_impact_sum",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        s=80,
        zorder=3,
        x_pct=True,
        y_pct=True,
    )


def visualise_per_code_agreement(
    summary: dict,
    save_path: Path | None = None,
    max_codes: int | None = 15,
) -> Axes | None:
    """
    Diverging stacked horizontal bar chart:
    overlap / missed / added per code, sorted by human count.
    """
    df = _per_code_df(summary)
    if df.empty:
        logger.warning("per_code block is empty, skipping visualise_per_code_agreement")
        return None

    df = df.assign(
        total_gold=df["total_in_gold"],
        total_tool=df["total_in_tool"],
        missed_neg=-df["missed_by_tool"],
        total_disagreement=df["missed_by_tool"] + df["added_by_tool"],
        net_bias=df["added_by_tool"] - df["missed_by_tool"],
    ).sort_values(["total_disagreement", "total_in_gold"], ascending=True)

    if max_codes is not None and max_codes > 0 and len(df) > max_codes:
        df = df.nlargest(max_codes, ["total_disagreement", "total_in_gold"])
        df = df.sort_values(["total_disagreement", "total_in_gold"], ascending=True)

    order = df["code"].tolist()

    plot_df = df.set_index("code")[["missed_neg", "agreement", "added_by_tool"]]
    plot_df = plot_df.loc[order]

    colors = [
        AGREEMENT_PALETTE["missed"],
        AGREEMENT_PALETTE["overlap"],
        AGREEMENT_PALETTE["added"],
    ]

    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, len(order) * _FIG_H_PER_ITEM)),
        layout="constrained",
    )
    plot_df.plot(kind="barh", stacked=True, color=colors, ax=ax, width=0.8)

    add_vertical_reference_line(ax, x=0, label="Reference: Zero Balance")

    ax.set_xlabel("Number of Students (count; Negative = Missed by Tool)")
    ax.set_ylabel("Code")
    set_integer_count_ticks(ax, axis="x")
    ax.set_title("Per-Code Agreement")
    ax.legend(
        handles=[
            Patch(facecolor=AGREEMENT_PALETTE["missed"], label="Missed"),
            Patch(facecolor=AGREEMENT_PALETTE["overlap"], label="Overlap"),
            Patch(facecolor=AGREEMENT_PALETTE["added"], label="Added"),
            Line2D(
                [0],
                [0],
                label="Reference: Zero Balance",
                color=REFERENCE_LINE_COLOR,
                linestyle=REFERENCE_LINE_STYLE,
                linewidth=REFERENCE_LINE_WIDTH,
                alpha=REFERENCE_LINE_ALPHA,
            ),
        ],
        title="Category",
    )
    _save_or_show(fig, save_path)
    return ax


def visualise_precision_recall_bubble(
    summary: dict, save_path: Path | None = None
) -> Axes | None:
    """Bubble chart of per-code precision vs recall, sized by human occurrence count."""
    df = _per_code_df(summary).dropna(subset=["precision", "recall"])
    if df.empty:
        logger.warning("No codes with both precision and recall, skipping bubble chart")
        return None

    df = df.assign(size=df["total_in_gold"].clip(lower=1))

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    ax.scatter(
        df["recall"],
        df["precision"],
        s=df["size"] * 60,
        alpha=0.7,
        color=AGREEMENT_PALETTE["added"],
    )
    for _, row in df.iterrows():
        ax.annotate(
            row["code"],
            xy=(row["recall"], row["precision"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlim(-0.05, 1.1)
    ax.set_ylim(-0.05, 1.1)
    add_horizontal_reference_line(ax, y=0.5, label="Threshold: Precision 50%")
    add_vertical_reference_line(ax, x=0.5, label="Threshold: Recall 50%")
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_xlabel("Recall (%)")
    ax.set_ylabel("Precision (%)")
    ax.set_title("Per-Code Precision Vs Recall (Bubble Size = Human Occurrence Count)")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="Reference")
    _save_or_show(fig, save_path)
    return ax


def visualise_code_frequency_comparison(
    summary: dict,
    save_path: Path | None = None,
    max_codes: int | None = 15,
) -> Axes | None:
    """
    Two-panel bar chart for code frequency:
    full range (left) and outlier-excluded detail view (right).
    """
    df = _per_code_df(summary)
    pipeline = _pipeline_stats_df(summary)

    if df.empty:
        logger.warning("per_code block is empty, skipping frequency comparison")
        return None

    combined = df.merge(
        pipeline[["code", "raw"]].rename(columns={"raw": "raw_count"}),
        on="code",
        how="left",
    ).assign(raw_count=lambda d: d["raw_count"].fillna(0).astype(int))

    if max_codes is not None and max_codes > 0 and len(combined) > max_codes:
        combined = combined.assign(
            max_count=lambda d: d[["total_in_gold", "total_in_tool", "raw_count"]].max(
                axis=1
            )
        )
        combined = combined.nlargest(max_codes, ["max_count", "total_in_gold"]).drop(
            columns=["max_count"]
        )

    combined = combined.sort_values("total_in_gold", ascending=False)
    order = combined["code"].tolist()

    melted = combined.melt(
        id_vars="code",
        value_vars=["total_in_gold", "total_in_tool", "raw_count"],
        var_name="source",
        value_name="count",
    ).assign(
        source=lambda d: d["source"].map(
            {
                "total_in_gold": "human",
                "total_in_tool": "tool (final)",
                "raw_count": "tool (raw)",
            }
        ),
        code=lambda d: pd.Categorical(d["code"], categories=order, ordered=True),
    )

    per_code_max = combined.set_index("code")[
        ["total_in_gold", "total_in_tool", "raw_count"]
    ].max(axis=1)
    outlier_code = per_code_max.idxmax()
    detail_melted = melted[melted["code"] != outlier_code].copy()
    detail_order = [code for code in order if code != outlier_code]
    if detail_melted.empty:
        detail_melted = melted.copy()
        detail_order = order.copy()
        outlier_code = ""

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(_FIG_W * 1.9, max(_FIG_H, len(order) * _FIG_H_PER_ITEM)),
        layout="constrained",
    )
    ax_full, ax_detail = axes[0], axes[1]

    sns.barplot(
        data=melted,
        y="code",
        x="count",
        hue="source",
        hue_order=["human", "tool (final)", "tool (raw)"],
        palette=_CODE_SOURCE_PALETTE,
        order=order,
        orient="h",
        ax=ax_full,
    )
    sns.barplot(
        data=detail_melted,
        y="code",
        x="count",
        hue="source",
        hue_order=["human", "tool (final)", "tool (raw)"],
        palette=_CODE_SOURCE_PALETTE,
        order=detail_order,
        orient="h",
        legend=False,
        ax=ax_detail,
    )
    ax_detail.set_xlabel("Occurrence Count (Students)")
    ax_detail.set_ylabel("")
    detail_max = detail_melted["count"].max() if not detail_melted.empty else 0
    ax_detail.set_xlim(0, max(1, detail_max * 1.1))

    detail_title = (
        f"Detail View (Excluding Outlier: {outlier_code})"
        if outlier_code
        else "Detail View"
    )
    format_facet_grid(
        axes,
        xlabel="Occurrence Count (Students)",
        ylabel=["Code", ""],
        titles=["Code Frequency: Full Scale (Human Vs Tool)", detail_title],
        x_int=True,
    )

    ax_full.legend(title="Source")

    _save_or_show(fig, save_path)
    return ax_full


def visualise_pipeline_waterfall(
    summary: dict, save_path: Path | None = None
) -> Axes | None:
    """
    Stacked horizontal bar chart of raw findings composition:
    final / adjusted / dismissed.
    """
    df = _pipeline_stats_df(summary)
    if df.empty:
        logger.warning("pipeline_stats block is empty, skipping waterfall")
        return None

    df = df.assign(
        adjusted_only=df["adjusted"],
        dismissed_only=df["dismissed"],
    ).sort_values("raw", ascending=True)

    order = df["code"].tolist()

    plot_df = df.set_index("code")[["final", "adjusted_only", "dismissed_only"]]
    plot_df = plot_df.loc[order]

    colors = [
        STAGE_PALETTE["final"],
        STAGE_PALETTE["adjusted"],
        STAGE_PALETTE["dismissed"],
    ]

    per_code_max = df.set_index("code")[
        ["raw", "final", "adjusted_only", "dismissed_only"]
    ].max(axis=1)
    outlier_code = per_code_max.idxmax()

    detail_plot_df = plot_df.drop(index=outlier_code, errors="ignore")
    if detail_plot_df.empty:
        detail_plot_df = plot_df.copy()
        outlier_code = ""

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(_FIG_W * 1.9, max(_FIG_H, len(order) * _FIG_H_PER_ITEM)),
        layout="constrained",
    )
    ax_full, ax_detail = axes[0], axes[1]

    plot_df.plot(kind="barh", stacked=True, color=colors, ax=ax_full, width=0.8)
    detail_plot_df.plot(
        kind="barh", stacked=True, color=colors, ax=ax_detail, width=0.8, legend=False
    )
    ax_detail.set_xlabel("Number of Findings (count; Total = Raw Count)")
    ax_detail.set_ylabel("")
    detail_max = detail_plot_df.sum(axis=1).max() if not detail_plot_df.empty else 0
    ax_detail.set_xlim(0, max(1, detail_max * 1.1))

    detail_title = (
        f"Detail View (Excluding Outlier: {outlier_code})"
        if outlier_code
        else "Detail View"
    )
    format_facet_grid(
        axes,
        xlabel="Number of Findings (count; Total = Raw Count)",
        ylabel=["Code", ""],
        titles=["Pipeline Attrition: Full Scale", detail_title],
        x_int=True,
    )

    ax_full.legend(["Final", "Adjusted", "Dismissed"], title="Stage")

    _save_or_show(fig, save_path)
    return ax_full


def visualise_judge_survival_rate(
    summary: dict, save_path: Path | None = None
) -> Axes | None:
    """Horizontal bar chart of judge survival rate per code, sorted ascending."""
    df = _pipeline_stats_df(summary).dropna(subset=["survival_rate"])
    if df.empty:
        logger.warning("pipeline_stats block is empty, skipping survival rate chart")
        return None

    df = df.sort_values("survival_rate", ascending=True)

    def _plot_judge_survival_rate(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.barplot(data=data, ax=ax, **kwargs)
        add_vertical_reference_line(ax, x=0.5, label="Threshold: 50% Survival")
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles=handles, labels=labels, title="Reference")

    return render_plot(
        _plot_judge_survival_rate,
        data=df,
        title="Judge Survival Rate per Code",
        xlabel="Survival Rate (Final / Raw)",
        ylabel="Code",
        save_path=save_path,
        figsize=(_FIG_W, max(_FIG_H, len(df) * _FIG_H_PER_ITEM)),
        y="code",
        x="survival_rate",
        orient="h",
        color=STAGE_PALETTE["final"],
        x_pct=True,
    )


def visualise_cost_by_variant(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Strip and box plot of cost per document by variant."""
    df = _validate_data(per_student_df, ["cost_eur"], "visualise_cost_by_variant")
    if df is None:
        return None
    df = df[df["task_variant"] == "int"].copy()
    if hasattr(df["task_variant"], "cat"):
        df["task_variant"] = df["task_variant"].cat.remove_unused_categories()
    ax = _plot_distribution(
        df,
        "task_variant",
        "cost_eur",
        "task_variant",
        "Total Pipeline Cost per Document by Task Variant",
        TASK_VARIANT_PALETTE,
        save_path,
        order=["int"],
    )
    if ax is None:
        return None
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Cost (EUR)")
    return ax


def visualise_cost_vs_doc_points(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Scatter of human doc_points vs cost per document."""
    df = _validate_data(
        per_student_df,
        ["doc_points", "generator_cost_eur", "generator_models"],
        "visualise_cost_vs_doc_points",
    )
    if df is None:
        return None
    return _plot_scatter_with_trendlines(
        df,
        "doc_points",
        "generator_cost_eur",
        "Pipeline Cost Vs Student Score (Human)",
        "Human Score",
        "Cost (EUR)",
        save_path,
    )


def visualise_latency_by_variant(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Strip and box plot of elapsed_seconds per document by variant."""
    df = _validate_data(
        per_student_df, ["elapsed_seconds"], "visualise_latency_by_variant"
    )
    if df is None:
        return None
    df = df[df["task_variant"] == "int"].copy()
    if hasattr(df["task_variant"], "cat"):
        df["task_variant"] = df["task_variant"].cat.remove_unused_categories()
    ax = _plot_distribution(
        df,
        "task_variant",
        "elapsed_seconds",
        "task_variant",
        "Total Pipeline Latency per Document by Task Variant",
        TASK_VARIANT_PALETTE,
        save_path,
        order=["int"],
    )
    if ax is None:
        return None
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Latency (s)")
    return ax


def summarise_token_usage_by_variant(per_student_df: pd.DataFrame) -> pd.DataFrame:
    """Return mean token usage per task variant as a table."""
    df = _validate_data(
        per_student_df,
        ["prompt_tokens", "completion_tokens", "cached_tokens", "task_variant"],
        "summarise_token_usage_by_variant",
    )
    if df is None:
        return pd.DataFrame()

    summary_df = (
        df.groupby("task_variant", observed=True)[
            ["prompt_tokens", "completion_tokens", "cached_tokens"]
        ]
        .mean()
        .rename(
            columns={
                "prompt_tokens": "mean_prompt_tokens",
                "completion_tokens": "mean_completion_tokens",
                "cached_tokens": "mean_cached_tokens",
            }
        )
        .assign(
            total_mean_tokens=lambda d: (
                d["mean_prompt_tokens"] + d["mean_completion_tokens"]
            )
        )
        .round(2)
        .reset_index()
    )
    logger.info(
        "Mean token usage per document by task variant:\n%s",
        summary_df.to_string(index=False),
    )
    return summary_df


def visualise_per_variant_metrics(
    summary: dict, save_path: Path | None = None
) -> tuple[Axes, Axes] | None:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for par vs int."""
    axes = _plot_performance_metrics(
        summary, "per_variant", "Task variant", TASK_VARIANT_PALETTE, save_path
    )
    return axes


def visualise_per_language_metrics(
    summary: dict, save_path: Path | None = None
) -> tuple[Axes, Axes] | None:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for document language."""
    axes = _plot_performance_metrics(
        summary, "per_language", "Language", LANGUAGE_PALETTE, save_path
    )
    return axes


def visualise_per_format_metrics(
    summary: dict, save_path: Path | None = None
) -> tuple[Axes, Axes] | None:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for PDF vs MD."""
    axes = _plot_performance_metrics(
        summary, "per_format", "Format", FORMAT_PALETTE, save_path
    )
    return axes


def visualise_mae_by_score_quartile(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Box plot of absolute percentage-point delta grouped by score quartile."""
    df = _add_percentage_score_columns(per_student_df.copy())
    df = df.dropna(subset=["doc_score_pct", "points_delta_pct"]).copy()
    df["abs_delta_pct"] = df["points_delta_pct"].abs()
    df["score_quartile"] = pd.qcut(
        df["doc_score_pct"], q=4, labels=["Q1 (low)", "Q2", "Q3", "Q4 (high)"]
    )

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.boxplot(
        data=df,
        x="score_quartile",
        y="abs_delta_pct",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        ax=ax,
        fill=False,
        flierprops={"alpha": 0.5},
    )
    ax.set_xlabel("Human Score Quartile (% of max points)")
    ax.set_ylabel("Absolute Score Delta (% points)")
    ax.set_title("Tool Error (|Score Delta|) by Human Score Quartile (Normalised)")
    move_legend_if_present(ax, title="Task variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_format_comparison(
    per_student_df: pd.DataFrame,
    save_path: Path | None = None,
    directory_aliases: tuple[str, ...] | None = ("par", "int"),
) -> Axes | None:
    """Strip+box plots comparing PDF vs Markdown on cost and latency only."""
    df = _validate_data(per_student_df, ["doc_type"], "visualise_format_comparison")
    if df is None:
        return None

    if directory_aliases is not None and "directory_alias" in df.columns:
        df = df[df["directory_alias"].isin(directory_aliases)].copy()
        if df.empty:
            logger.warning(
                "No rows remain after filtering format comparison by aliases: %s",
                ", ".join(directory_aliases),
            )
            return None

    metrics: list[tuple[str, str]] = []
    if "cost_eur" in df.columns and df["cost_eur"].notna().any():
        metrics.append(("cost_eur", "Cost (EUR)"))
    if "elapsed_seconds" in df.columns and df["elapsed_seconds"].notna().any():
        metrics.append(("elapsed_seconds", "Latency (s)"))

    if not metrics:
        logger.warning("No suitable columns for format_comparison")
        return None

    n = len(metrics)
    fig, axes = plt.subplots(1, n, figsize=(_FIG_W, _FIG_H), layout="constrained")
    if n == 1:
        axes = [axes]

    for ax, (col, label) in zip(axes, metrics):
        sub = df.dropna(subset=[col])
        sns.boxplot(
            data=sub,
            x="doc_type",
            y=col,
            hue="doc_type",
            palette=FORMAT_PALETTE,
            legend=False,
            ax=ax,
            fill=False,
            showfliers=False,
        )
        sns.stripplot(
            data=sub,
            x="doc_type",
            y=col,
            hue="doc_type",
            palette=FORMAT_PALETTE,
            legend=False,
            ax=ax,
            alpha=0.7,
            size=6,
            jitter=True,
        )

    format_facet_grid(
        axes,
        xlabel="Format",
        ylabel=[label for _, label in metrics],
        titles=[label for _, label in metrics],
        suptitle="PDF Vs Markdown: Cost and Latency",
    )

    _save_or_show(fig, save_path)
    return axes[0]


def summarise_format_comparison_scope(per_student_df: pd.DataFrame) -> pd.DataFrame:
    """Summarise which aliases/models are represented in format-comparison data."""
    required_cols = [
        "directory_alias",
        "task_variant",
        "doc_type",
        "generator_models",
        "judge_models",
    ]
    df = _validate_data(
        per_student_df,
        ["directory_alias", "task_variant", "doc_type"],
        "summarise_format_comparison_scope",
    )
    if df is None:
        return pd.DataFrame(columns=[*required_cols, "n_students"])

    for col in ("generator_models", "judge_models"):
        if col not in df.columns:
            df[col] = ""

    scope_input = df[required_cols].copy()
    for col in required_cols:
        scope_input[col] = scope_input[col].astype("string")

    scope_counts = (
        scope_input.fillna("")
        .groupby(required_cols, dropna=False, observed=True)
        .size()
        .rename("n_students")
    )
    scope_df = scope_counts.reset_index().sort_values("n_students", ascending=False)
    return scope_df


def visualise_stage_times(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """
    Box-and-strip plot showing the distribution of
    parse / analyser / judge times per student.
    """
    df = _validate_data(
        per_student_df,
        ["parse_time", "analyser_time", "judge_time"],
        "visualise_stage_times",
    )
    if df is None:
        return None

    melted = df.melt(
        id_vars="student_id",
        value_vars=["parse_time", "analyser_time", "judge_time"],
        var_name="stage",
        value_name="seconds",
    ).assign(
        stage=lambda d: d["stage"].map(
            {"parse_time": "parse", "analyser_time": "analysers", "judge_time": "judge"}
        )
    )
    stage_order = ["parse", "analysers", "judge"]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.boxplot(
        data=melted,
        x="seconds",
        y="stage",
        order=stage_order,
        hue="stage",
        hue_order=stage_order,
        palette=EXECUTION_STAGE_PALETTE,
        dodge=False,
        showfliers=False,
        fill=False,
        linewidth=1.5,
        zorder=2,
        legend=False,
        ax=ax,
    )
    sns.stripplot(
        data=melted,
        x="seconds",
        y="stage",
        order=stage_order,
        hue="stage",
        hue_order=stage_order,
        palette=EXECUTION_STAGE_PALETTE,
        dodge=False,
        alpha=0.25,
        size=3,
        legend=False,
        ax=ax,
    )
    format_facet_grid(
        ax,
        xlabel="Latency (s)",
        ylabel="Stage",
        titles="Pipeline Stage Latency by Stage",
    )
    _save_or_show(fig, save_path)
    return ax


def _format_model_name(name: str) -> str:
    """Prettify model names for visualisation."""
    parts = [part.strip() for part in str(name).split(",") if part.strip()]
    formatted_parts = [_MODEL_NAME_MAP.get(part, part) for part in parts]
    return "\n+ ".join(formatted_parts)


def _plot_performance_metrics(
    summary: dict,
    key_name: str,
    category_label: str,
    palette,
    save_path: Path | None = None,
) -> tuple[Axes, Axes] | None:
    per_category = summary.get(key_name, {})
    if not per_category:
        logger.warning("%s block is empty", key_name)
        return None

    mae_rows = []
    prf_rows = []

    has_pct_mae = any(
        stats.get("points_mae_pct") is not None for stats in per_category.values()
    )
    mae_label = "MAE (% pts)" if has_pct_mae else "MAE (pts)"
    mae_key = "points_mae_pct" if has_pct_mae else "points_mae"
    mae_y_label = "Score (%)" if has_pct_mae else "Score (pts)"

    mae_metrics = {mae_label: mae_key}
    prf_metrics = {
        "Precision": "macro_precision",
        "Recall": "macro_recall",
        "F1": "macro_f1",
    }

    is_model_category = "model" in category_label.lower()

    for cat_val, stats in per_category.items():
        fmt_cat = _format_model_name(cat_val) if is_model_category else cat_val
        for label, key in mae_metrics.items():
            val = stats.get(key)
            if val is not None:
                mae_rows.append(
                    {category_label: fmt_cat, "Metric": label, "Value": val}
                )
        for label, key in prf_metrics.items():
            val = stats.get(key)
            if val is not None:
                prf_rows.append(
                    {category_label: fmt_cat, "Metric": label, "Value": val}
                )

    df_mae = pd.DataFrame(mae_rows)
    df_prf = pd.DataFrame(prf_rows)

    fig, axes = plt.subplots(1, 2, figsize=(_FIG_W * 1.5, _FIG_H), layout="constrained")
    ax1, ax2 = axes[0], axes[1]

    if palette is None:
        mae_palette = "pastel"
        prf_palette = "deep"
    else:
        mae_palette = palette
        prf_palette = palette

    if not df_mae.empty:
        sns.barplot(
            data=df_mae,
            x="Metric" if palette is not None else category_label,
            y="Value",
            hue=category_label if palette is not None else "Metric",
            palette=mae_palette,
            ax=ax1,
        )
        ax1.set_xlabel("")
        ax1.set_ylabel(mae_y_label)
        ax1.set_title("Mean Absolute Error (MAE)")
        if palette is None:
            ax1.tick_params(axis="x", rotation=0)
    else:
        ax1.set_title("No MAE Data")

    if not df_prf.empty:
        sns.barplot(
            data=df_prf,
            x="Metric" if palette is not None else category_label,
            y="Value",
            hue=category_label if palette is not None else "Metric",
            palette=prf_palette,
            ax=ax2,
        )
        ax2.set_ylim(0, 1.05)
        if palette is None:
            ax2.tick_params(axis="x", rotation=0)

    format_facet_grid(
        axes,
        xlabel=["", ""],
        ylabel=[mae_y_label, "Score (%)"],
        titles=[
            "Mean Absolute Error (MAE)" if not df_mae.empty else "No MAE Data",
            (
                "Performance Metrics"
                if not df_prf.empty
                else "No Precision/Recall/F1 Data"
            ),
        ],
        y_pct=[False, not df_prf.empty],
    )

    if palette is None:
        sns.despine()

    fig.suptitle(f"Evaluation Metrics by {category_label.title()}")
    _save_or_show(fig, save_path)
    return ax1, ax2


def _plot_distribution(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    hue_col: str,
    title: str,
    palette,
    save_path: Path | None = None,
    order=None,
) -> Axes | None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.boxplot(
        data=df,
        x=x_col,
        y=y_col,
        hue=hue_col,
        palette=palette,
        fill=False,
        showfliers=False,
        ax=ax,
        order=order,
        legend=False,
    )
    sns.stripplot(
        data=df,
        x=x_col,
        y=y_col,
        hue=hue_col,
        palette=palette,
        jitter=True,
        alpha=0.6,
        ax=ax,
        size=4 if palette is None else 7,
        order=order,
        legend=False,
    )
    ax.set_title(title)
    if palette is None:
        ax.tick_params(axis="x", rotation=0)
    _save_or_show(fig, save_path)
    return ax


def _plot_scatter_with_trendlines(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    x_label: str,
    y_label: str,
    save_path: Path | None = None,
    hue_col: str = "generator_models",
) -> Axes | None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.scatterplot(data=df, x=x_col, y=y_col, hue=hue_col, s=80, alpha=0.6, ax=ax)
    for model_name in df[hue_col].unique():
        subset = df[df[hue_col] == model_name]
        if len(subset) > 1:
            sns.regplot(
                data=subset,
                x=x_col,
                y=y_col,
                scatter=False,
                ci=None,
                ax=ax,
                line_kws={"alpha": 0.5, "linewidth": 1.0},
            )
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    move_legend_if_present(ax, title="Vision Model + Content Model")
    _save_or_show(fig, save_path)
    return ax


def visualise_per_generator_model_metrics(
    summary: dict, save_path: Path | None = None
) -> tuple[Axes, Axes] | None:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for generator models."""
    axes = _plot_performance_metrics(
        summary, "per_generator_model", "Vision Model + Content Model", None, save_path
    )
    return axes


def visualise_per_judge_model_metrics(
    summary: dict, save_path: Path | None = None
) -> tuple[Axes, Axes] | None:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for judge models."""
    axes = _plot_performance_metrics(
        summary, "per_judge_model", "Judge Model", None, save_path
    )
    return axes

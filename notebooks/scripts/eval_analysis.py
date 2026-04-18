"""Gold evaluation visualisation and analysis."""

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
    FORMAT_PALETTE,
    LANGUAGE_PALETTE,
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
    set_integer_count_ticks,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes

logger = logging.getLogger(__name__)

_MODEL_NAME_MAP: dict[str, str] = {
    "ft:gpt-4.1-2025-04-14:personal:baduml-classifier-gold:DU8txcxh": "FT Vision",
    "gpt-5.4-nano-2026-03-17": "GPT 5.4 Nano",
    "gpt-5.4-mini-2026-03-17": "GPT 5.4 Mini",
    "gpt-5.4-2026-03-05": "GPT 5.4",
}

# ,- DEFAULTS,-

_DEFAULT_EVAL_DIR = Path(__file__).parent.parent.parent / "outputs" / "gold_eval"
_DEFAULT_SAMPLE_DIR = (
    Path(__file__).parent.parent.parent / "outputs" / "gold_eval_sample"
)

# ,- DATA LOADING,-


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

    if "generator_models" in df.columns:
        df["generator_models"] = df["generator_models"].apply(
            lambda value: _format_model_name(value) if pd.notna(value) else value
        )

    summary: dict = {}
    if json_path.exists():
        with json_path.open(encoding="utf-8") as fh:
            summary = json.load(fh)

    return df, summary


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


def visualise_score_scatter(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Scatter plot of gold doc_points vs tool-estimated points, coloured by variant."""
    df = per_student_df.dropna(subset=["doc_points", "tool_raw_points"])
    all_pts = pd.concat([df["doc_points"], df["tool_raw_points"]])
    lo, hi = all_pts.min() - 5, all_pts.max() + 5

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.scatterplot(
        data=df,
        x="doc_points",
        y="tool_raw_points",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        s=80,
        zorder=3,
        ax=ax,
    )
    add_identity_reference_line(ax, lo, hi)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Gold Score")
    ax.set_ylabel("Tool Score")
    ax.set_title("Gold Vs Tool Score Comparison")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="Task variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_points_delta_distribution(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Histogram of per-student points delta (tool - gold), split by bonus status."""
    df = per_student_df.dropna(subset=["points_delta"])

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(
        data=df,
        x="points_delta",
        hue="has_gold_bonus",
        bins=20,
        multiple="layer",
        element="step",
        alpha=0.5,
        ax=ax,
    )
    add_vertical_reference_line(ax, x=0, label="Reference: Zero Score Delta")
    ax.set_xlabel("Score Delta (Tool - Gold)")
    ax.set_ylabel("Number of Students (count)")
    set_integer_count_ticks(ax, axis="y")
    ax.set_title("Distribution of Tool-Gold Score Delta")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="Has Gold Bonus")
    _save_or_show(fig, save_path)
    return ax


def visualise_impact_delta_scatter(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Scatter of normalised gold impact vs tool impact with identity line."""
    df = per_student_df.dropna(subset=["gold_impact_sum", "tool_impact_sum"])
    all_vals = pd.concat([df["gold_impact_sum"], df["tool_impact_sum"]])
    lo, hi = all_vals.min() - 0.02, all_vals.max() + 0.02

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.scatterplot(
        data=df,
        x="gold_impact_sum",
        y="tool_impact_sum",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        s=80,
        zorder=3,
        ax=ax,
    )
    add_identity_reference_line(ax, lo, hi)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_xlabel("Gold Impact Score (%)")
    ax.set_ylabel("Tool Impact Score (%)")
    ax.set_title("Gold Vs Tool Impact Score Comparison")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="Task variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_per_code_agreement(
    summary: dict, save_path: Path | None = None
) -> Axes | None:
    """
    Diverging stacked horizontal bar chart:
    overlap / missed / added per code, sorted by gold count.
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
    ax.set_title("Per-Code Agreement Sorted by Diagnostic Priority")
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


def visualise_per_code_agreement_bias(
    summary: dict, save_path: Path | None = None
) -> Axes | None:
    """
    Diverging stacked horizontal bar chart sorted by net bias:
    added_by_tool - missed_by_tool.
    """
    df = _per_code_df(summary)
    if df.empty:
        logger.warning(
            "per_code block is empty, skipping visualise_per_code_agreement_bias"
        )
        return None

    df = df.assign(
        total_gold=df["total_in_gold"],
        total_tool=df["total_in_tool"],
        missed_neg=-df["missed_by_tool"],
        total_disagreement=df["missed_by_tool"] + df["added_by_tool"],
        net_bias=df["added_by_tool"] - df["missed_by_tool"],
    ).sort_values(["net_bias", "total_disagreement"], ascending=True)

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
    add_vertical_reference_line(ax, x=0, label="Reference: Zero Bias")
    ax.set_xlabel("Number of Students (count; Negative = Missed by Tool)")
    ax.set_ylabel("Code")
    set_integer_count_ticks(ax, axis="x")
    ax.set_title("Per-Code Agreement Sorted by Net Bias (Added - Missed)")
    ax.legend(
        handles=[
            Patch(facecolor=AGREEMENT_PALETTE["missed"], label="Missed"),
            Patch(facecolor=AGREEMENT_PALETTE["overlap"], label="Overlap"),
            Patch(facecolor=AGREEMENT_PALETTE["added"], label="Added"),
            Line2D(
                [0],
                [0],
                label="Reference: Zero Bias",
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
    """Bubble chart of per-code precision vs recall, sized by gold occurrence count."""
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
    ax.set_title("Per-Code Precision Vs Recall (Bubble Size = Gold Occurrence Count)")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="Reference")
    _save_or_show(fig, save_path)
    return ax


def visualise_code_frequency_comparison(
    summary: dict, save_path: Path | None = None
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
    combined = combined.sort_values("total_in_gold", ascending=True)
    order = combined["code"].tolist()

    melted = combined.melt(
        id_vars="code",
        value_vars=["total_in_gold", "total_in_tool", "raw_count"],
        var_name="source",
        value_name="count",
    ).assign(
        source=lambda d: d["source"].map(
            {
                "total_in_gold": "gold",
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
    if detail_melted.empty:
        detail_melted = melted.copy()
        outlier_code = ""

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(_FIG_W * 1.9, max(_FIG_H, len(order) * _FIG_H_PER_ITEM)),
        sharey=True,
        layout="constrained",
    )
    ax_full, ax_detail = axes[0], axes[1]

    sns.barplot(
        data=melted,
        y="code",
        x="count",
        hue="source",
        hue_order=["gold", "tool (final)", "tool (raw)"],
        orient="h",
        ax=ax_full,
    )
    sns.barplot(
        data=detail_melted,
        y="code",
        x="count",
        hue="source",
        hue_order=["gold", "tool (final)", "tool (raw)"],
        orient="h",
        ax=ax_detail,
    )

    ax_full.set_xlabel("Occurrence Count (Students)")
    ax_full.set_ylabel("Code")
    set_integer_count_ticks(ax_full, axis="x")
    ax_full.set_title("Code Frequency: Full Scale")

    ax_detail.set_xlabel("Occurrence Count (Students)")
    ax_detail.set_ylabel("")
    detail_max = detail_melted["count"].max() if not detail_melted.empty else 0
    ax_detail.set_xlim(0, max(1, detail_max * 1.1))
    set_integer_count_ticks(ax_detail, axis="x")
    if outlier_code:
        ax_detail.set_title(f"Detail View (Excluding Outlier: {outlier_code})")
    else:
        ax_detail.set_title("Detail View")

    ax_full.legend(title="Source")
    legend_detail = ax_detail.get_legend()
    if legend_detail is not None:
        legend_detail.remove()

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

    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, len(order) * _FIG_H_PER_ITEM)),
        layout="constrained",
    )
    plot_df.plot(kind="barh", stacked=True, color=colors, ax=ax, width=0.8)

    ax.set_xlabel("Number of Findings (count; Total = Raw Count)")
    ax.set_ylabel("Code")
    set_integer_count_ticks(ax, axis="x")
    ax.set_title("Pipeline Attrition: Final / Adjusted / Dismissed per Code")
    ax.legend(["Final", "Adjusted", "Dismissed"], title="Stage")
    _save_or_show(fig, save_path)
    return ax


def visualise_judge_survival_rate(
    summary: dict, save_path: Path | None = None
) -> Axes | None:
    """Horizontal bar chart of judge survival rate per code, sorted ascending."""
    df = _pipeline_stats_df(summary).dropna(subset=["survival_rate"])
    if df.empty:
        logger.warning("pipeline_stats block is empty, skipping survival rate chart")
        return None

    df = df.sort_values("survival_rate", ascending=True)

    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, len(df) * _FIG_H_PER_ITEM)), layout="constrained"
    )
    sns.barplot(
        data=df,
        y="code",
        x="survival_rate",
        orient="h",
        color=STAGE_PALETTE["final"],
        ax=ax,
    )
    add_vertical_reference_line(ax, x=0.5, label="Threshold: 50% Survival")
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_xlabel("Survival Rate (Final / Raw)")
    ax.set_ylabel("Code")
    ax.set_title("Judge Survival Rate per Code")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=labels, title="Reference")
    _save_or_show(fig, save_path)
    return ax


def visualise_code_set_sizes(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Distribution of per-student code set sizes for gold vs tool, split by variant."""
    melted = per_student_df.melt(
        id_vars=["task_variant"],
        value_vars=["gold_code_count", "tool_code_count"],
        var_name="source",
        value_name="n_codes",
    ).assign(
        source=lambda d: d["source"].map(
            {"gold_code_count": "gold", "tool_code_count": "tool (final)"}
        )
    )

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.boxplot(
        data=melted,
        x="task_variant",
        y="n_codes",
        hue="source",
        ax=ax,
        fill=False,
        flierprops={"alpha": 0.5},
    )
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Number of Distinct Codes (count)")
    set_integer_count_ticks(ax, axis="y")
    ax.set_title("Code Set Size per Student: Gold Vs Tool")
    ax.legend(title="Source")
    _save_or_show(fig, save_path)
    return ax


def visualise_raw_vs_final_code_count(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """2D density of raw code count vs final code count, with integer ticks."""
    df = per_student_df.dropna(subset=["raw_code_count", "tool_code_count"]).copy()
    if df.empty:
        logger.warning(
            "No rows with raw_code_count/tool_code_count, skipping density chart"
        )
        return None

    df["raw_code_count"] = pd.to_numeric(df["raw_code_count"], errors="coerce")
    df["tool_code_count"] = pd.to_numeric(df["tool_code_count"], errors="coerce")
    df = df.dropna(subset=["raw_code_count", "tool_code_count"])
    if df.empty:
        logger.warning("No numeric rows for raw/final code counts, skipping")
        return None

    df["raw_code_count"] = df["raw_code_count"].astype(int)
    df["tool_code_count"] = df["tool_code_count"].astype(int)

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(
        data=df,
        x="raw_code_count",
        y="tool_code_count",
        discrete=True,
        cbar=True,
        cmap="Blues",
        ax=ax,
    )

    max_raw = int(df["raw_code_count"].max())
    max_final = int(df["tool_code_count"].max())
    hi = max(max_raw, max_final)

    lo = 0
    identity_line = add_identity_reference_line(ax, lo, hi)
    ax.set_xlim(-0.5, max_raw + 0.5)
    ax.set_ylim(-0.5, max_final + 0.5)
    set_integer_count_ticks(ax, axis="x")
    set_integer_count_ticks(ax, axis="y")

    if ax.collections:
        colorbar = ax.collections[0].colorbar
        if colorbar is not None:
            colorbar.set_label("Number of Students (count)")

    ax.set_xlabel("Raw Code Count (Pre-Judge)")
    ax.set_ylabel("Final Code Count (Post-Judge)")
    ax.set_title("Judge Filtering Density: Raw Vs Final Code Count per Student")
    ax.legend(
        handles=[identity_line],
        labels=[identity_line.get_label()],
        title="Reference",
    )
    _save_or_show(fig, save_path)
    return ax


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


def visualise_cost_by_generator_model(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Strip and box plot of cost per document by generator model."""
    df = _validate_data(
        per_student_df,
        ["generator_cost_eur", "generator_models"],
        "visualise_cost_by_generator_model",
    )
    if df is None:
        return None
    ax = _plot_distribution(
        df,
        "generator_models",
        "generator_cost_eur",
        "task_variant",
        "Cost per Document by Vision Model + Content Model",
        TASK_VARIANT_PALETTE,
        save_path,
    )
    if ax is None:
        return None
    ax.set_xlabel("Vision Model + Content Model")
    ax.set_ylabel("Cost (EUR)")
    return ax


def visualise_latency_by_generator_model(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Strip and box plot of execution time by generator model."""
    df = _validate_data(
        per_student_df,
        ["analyser_time", "generator_models"],
        "visualise_latency_by_generator_model",
    )
    if df is None:
        return None
    ax = _plot_distribution(
        df,
        "generator_models",
        "analyser_time",
        "task_variant",
        "Pipeline Latency by Vision Model + Content Model",
        TASK_VARIANT_PALETTE,
        save_path,
    )
    if ax is None:
        return None
    ax.set_xlabel("Vision Model + Content Model")
    ax.set_ylabel("Latency (s)")
    return ax


def visualise_cost_vs_doc_points(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Scatter of gold doc_points vs cost per document."""
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
        "Pipeline Cost Vs Student Score (With Trendlines)",
        "Gold Score",
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


def visualise_token_breakdown(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Stacked bar of mean prompt vs completion tokens per variant."""
    df = _validate_data(
        per_student_df,
        ["prompt_tokens", "completion_tokens"],
        "visualise_token_breakdown",
    )
    if df is None:
        return None

    df = df[df["task_variant"] == "int"].copy()
    if hasattr(df["task_variant"], "cat"):
        df["task_variant"] = df["task_variant"].cat.remove_unused_categories()

    agg = (
        df.groupby("task_variant", observed=True)[
            ["prompt_tokens", "completion_tokens"]
        ]
        .mean()
        .reset_index()
    )
    melted = agg.melt(
        id_vars="task_variant",
        value_vars=["prompt_tokens", "completion_tokens"],
        var_name="token_type",
        value_name="mean_tokens",
    ).assign(
        token_type=lambda d: d["token_type"].map(
            {"prompt_tokens": "prompt", "completion_tokens": "completion"}
        )
    )

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.barplot(
        data=melted,
        x="task_variant",
        y="mean_tokens",
        hue="token_type",
        hue_order=["prompt", "completion"],
        ax=ax,
        order=["int"],
    )
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Mean Tokens (count)")
    ax.set_title("Mean Token Usage per Document by Task Variant")
    ax.legend(title="Token Type")
    _save_or_show(fig, save_path)
    return ax


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
    """Box plot of absolute points delta grouped by gold score quartile."""
    df = per_student_df.dropna(subset=["doc_points", "points_delta"]).copy()
    df["abs_delta"] = df["points_delta"].abs()
    df["score_quartile"] = pd.qcut(
        df["doc_points"], q=4, labels=["Q1 (low)", "Q2", "Q3", "Q4 (high)"]
    )

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.boxplot(
        data=df,
        x="score_quartile",
        y="abs_delta",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        ax=ax,
        fill=False,
        flierprops={"alpha": 0.5},
    )
    ax.set_xlabel("Gold Score Quartile")
    ax.set_ylabel("Absolute Score Delta")
    ax.set_title("Tool Error (|Score Delta|) by Gold Score Quartile")
    ax.legend(title="Task variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_format_comparison(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Side-by-side strip+box plots comparing PDF vs Markdown on three metrics."""
    df = _validate_data(per_student_df, ["doc_type"], "visualise_format_comparison")
    if df is None:
        return None

    metrics: list[tuple[str, str]] = []
    if "cost_eur" in df.columns and df["cost_eur"].notna().any():
        metrics.append(("cost_eur", "Cost (EUR)"))
    if "elapsed_seconds" in df.columns and df["elapsed_seconds"].notna().any():
        metrics.append(("elapsed_seconds", "Latency (s)"))
    metrics.append(("overlap_count", "Overlap Count"))

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
        ax.set_xlabel("Format")
        ax.set_ylabel(label)
        ax.set_title(label)
        if col == "overlap_count":
            set_integer_count_ticks(ax, axis="y")

    fig.suptitle("PDF Vs Markdown: Cost, Latency, and Overlap")
    _save_or_show(fig, save_path)
    return axes[0]


def visualise_stage_times(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """
    Density plot showing the distribution of
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

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.kdeplot(
        data=melted,
        x="seconds",
        hue="stage",
        hue_order=["parse", "analysers", "judge"],
        palette={
            "parse": STAGE_PALETTE["raw"],
            "analysers": STAGE_PALETTE["adjusted"],
            "judge": STAGE_PALETTE["dismissed"],
        },
        multiple="layer",
        fill=True,
        alpha=0.5,
        ax=ax,
    )
    ax.set_xlabel("Latency (s)")
    ax.set_ylabel("Density")
    ax.set_title("Distribution of Pipeline Stage Latencies")
    _save_or_show(fig, save_path)
    return ax


def visualise_cost_vs_words(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes | None:
    """Scatter of total_words vs cost_eur, coloured by task variant."""
    df = _validate_data(
        per_student_df,
        ["total_words", "generator_cost_eur", "generator_models"],
        "visualise_cost_vs_words",
    )
    if df is None:
        return None
    return _plot_scatter_with_trendlines(
        df,
        "total_words",
        "generator_cost_eur",
        "Pipeline Cost Vs Document Word Count (With Trendlines)",
        "Document Word Count",
        "Cost (EUR)",
        save_path,
    )


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
        logger.warning(f"{key_name} block is empty")
        return None

    mae_rows = []
    prf_rows = []

    mae_metrics = {"MAE (pts)": "points_mae"}
    prf_metrics = {
        "Precision": "macro_precision",
        "Recall": "macro_recall",
        "F1": "macro_f1",
    }

    for cat_val, stats in per_category.items():
        fmt_cat = (
            _format_model_name(cat_val)
            if category_label in ["Vision Model + Content Model", "Model"]
            else cat_val
        )
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
        ax1.set_ylabel("Score")
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
        ax2.set_xlabel("")
        ax2.set_ylabel("Score (%)")
        ax2.set_ylim(0, 1.05)
        ax2.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        ax2.set_title("Performance Metrics")
        if palette is None:
            ax2.tick_params(axis="x", rotation=0)
    else:
        ax2.set_title("No Precision/Recall/F1 Data")

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
    ax.legend(title="Vision Model + Content Model")
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
        summary, "per_judge_model", "Model", None, save_path
    )
    return axes


def plot_all(
    per_student_df: pd.DataFrame,
    summary: dict,
    save_dir: Path | None = None,
) -> None:
    """Generate all available diagrams, optionally saving to save_dir."""

    def _path(name: str) -> Path | None:
        return (save_dir / name) if save_dir is not None else None

    visualise_score_scatter(per_student_df, _path("score_scatter.png"))
    visualise_points_delta_distribution(
        per_student_df, _path("points_delta_distribution.png")
    )
    visualise_impact_delta_scatter(per_student_df, _path("impact_delta_scatter.png"))
    visualise_per_code_agreement(summary, _path("per_code_agreement.png"))
    visualise_per_code_agreement_bias(summary, _path("per_code_agreement_bias.png"))
    visualise_precision_recall_bubble(summary, _path("precision_recall_bubble.png"))
    visualise_code_frequency_comparison(summary, _path("code_frequency_comparison.png"))
    visualise_pipeline_waterfall(summary, _path("pipeline_waterfall.png"))
    visualise_judge_survival_rate(summary, _path("judge_survival_rate.png"))
    visualise_code_set_sizes(per_student_df, _path("code_set_sizes.png"))
    visualise_raw_vs_final_code_count(
        per_student_df, _path("raw_vs_final_code_count.png")
    )
    visualise_per_variant_metrics(summary, _path("per_variant_metrics.png"))
    visualise_per_format_metrics(summary, _path("per_format_metrics.png"))
    visualise_per_language_metrics(summary, _path("per_language_metrics.png"))
    visualise_mae_by_score_quartile(per_student_df, _path("mae_by_score_quartile.png"))
    visualise_format_comparison(per_student_df, _path("format_comparison.png"))
    visualise_cost_by_variant(per_student_df, _path("cost_by_variant.png"))
    visualise_cost_vs_doc_points(per_student_df, _path("cost_vs_doc_points.png"))
    visualise_cost_vs_words(per_student_df, _path("cost_vs_words.png"))
    visualise_cost_by_generator_model(
        per_student_df, _path("cost_by_generator_model.png")
    )
    visualise_latency_by_variant(per_student_df, _path("latency_by_variant.png"))
    visualise_latency_by_generator_model(
        per_student_df, _path("latency_by_generator_model.png")
    )
    visualise_token_breakdown(per_student_df, _path("token_breakdown.png"))
    visualise_stage_times(per_student_df, _path("stage_times.png"))

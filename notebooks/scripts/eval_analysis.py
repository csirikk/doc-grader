"""Gold evaluation visualisation and analysis."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import PercentFormatter

from .visual_utils import (
    _FIG_H,
    _FIG_H_PER_ITEM,
    _FIG_W,
    AGREEMENT_PALETTE,
    FORMAT_PALETTE,
    LANGUAGE_PALETTE,
    STAGE_PALETTE,
    TASK_VARIANT_PALETTE,
    _save_or_show,
    _validate_data,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes

logger = logging.getLogger(__name__)

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
) -> Axes:
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
    ax.plot([lo, hi], [lo, hi], color="gray", linestyle="--", linewidth=1, zorder=1)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Gold documentation points")
    ax.set_ylabel("Tool-estimated points")
    ax.set_title("Gold vs Tool Score Comparison")
    ax.legend(title="Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_points_delta_distribution(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
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
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=1)
    ax.set_xlabel("Points delta (tool - gold)")
    ax.set_ylabel("Number of students")
    ax.set_title("Distribution of Tool--Gold Points Delta")
    legend = ax.get_legend()
    if legend is not None:
        legend.set_title("Has gold bonus")
    _save_or_show(fig, save_path)
    return ax


def visualise_impact_delta_scatter(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
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
    ax.plot([lo, hi], [lo, hi], color="gray", linestyle="--", linewidth=1, zorder=1)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_xlabel("Gold normalised impact sum")
    ax.set_ylabel("Tool normalised impact sum")
    ax.set_title("Gold vs Tool Normalised Impact Comparison")
    ax.legend(title="Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_per_code_agreement(summary: dict, save_path: Path | None = None) -> Axes:
    """
    Diverging stacked horizontal bar chart:
    overlap / missed / added per code, sorted by gold count.
    """
    df = _per_code_df(summary)
    if df.empty:
        logger.warning("per_code block is empty, skipping visualise_per_code_agreement")
        return plt.subplots()[1]

    df = df.assign(
        total_gold=df["total_in_gold"],
        total_tool=df["total_in_tool"],
        missed_neg=-df["missed_by_tool"],
    ).sort_values("total_in_gold", ascending=True)

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

    ax.axvline(0, color="black", linewidth=1.2)

    ax.set_xlabel("Student count (Negative = Missed via Tool)")
    ax.set_ylabel("Code")
    ax.set_title("Per-Code Agreement: Diverging Overlap / Missed / Added")
    ax.legend(["Missed", "Overlap", "Added"], title="Category")
    _save_or_show(fig, save_path)
    return ax


def visualise_precision_recall_bubble(
    summary: dict, save_path: Path | None = None
) -> Axes:
    """Bubble chart of per-code precision vs recall, sized by gold occurrence count."""
    df = _per_code_df(summary).dropna(subset=["precision", "recall"])
    if df.empty:
        logger.warning("No codes with both precision and recall, skipping bubble chart")
        return plt.subplots()[1]

    df = df.assign(size=df["total_in_gold"].clip(lower=1))

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    ax.scatter(
        df["recall"],
        df["precision"],
        s=df["size"] * 60,
        alpha=0.7,
        color=sns.color_palette("deep")[0],
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
    ax.axhline(y=0.5, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.axvline(x=0.5, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Recall (vs gold)")
    ax.set_ylabel("Precision")
    ax.set_title("Per-Code Precision vs Recall\n(bubble size = gold occurrence count)")
    _save_or_show(fig, save_path)
    return ax


def visualise_code_frequency_comparison(
    summary: dict, save_path: Path | None = None
) -> Axes:
    """Three-way bar chart: gold, tool-final, and tool-raw occurrence counts."""
    df = _per_code_df(summary)
    pipeline = _pipeline_stats_df(summary)

    if df.empty:
        logger.warning("per_code block is empty, skipping frequency comparison")
        return plt.subplots()[1]

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

    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, len(order) * _FIG_H_PER_ITEM)),
        layout="constrained",
    )
    sns.barplot(
        data=melted,
        y="code",
        x="count",
        hue="source",
        hue_order=["gold", "tool (final)", "tool (raw)"],
        orient="h",
        ax=ax,
    )
    ax.set_xlabel("Occurrence count (students)")
    ax.set_ylabel("Code")
    ax.set_title("Code Frequency: Gold vs Tool Final vs Tool Raw")
    ax.legend(title="Source")
    _save_or_show(fig, save_path)
    return ax


def visualise_pipeline_waterfall(summary: dict, save_path: Path | None = None) -> Axes:
    """
    Stacked horizontal bar chart of raw findings composition:
    final / adjusted / dismissed.
    """
    df = _pipeline_stats_df(summary)
    if df.empty:
        logger.warning("pipeline_stats block is empty, skipping waterfall")
        return plt.subplots()[1]

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

    ax.set_xlabel("Number of findings (Total = Raw count)")
    ax.set_ylabel("Code")
    ax.set_title("Pipeline Attrition: Final / Adjusted / Dismissed per Code")
    ax.legend(["Final", "Adjusted", "Dismissed"], title="Stage")
    _save_or_show(fig, save_path)
    return ax


def visualise_judge_survival_rate(summary: dict, save_path: Path | None = None) -> Axes:
    """Horizontal bar chart of judge survival rate per code, sorted ascending."""
    df = _pipeline_stats_df(summary).dropna(subset=["survival_rate"])
    if df.empty:
        logger.warning("pipeline_stats block is empty, skipping survival rate chart")
        return plt.subplots()[1]

    df = df.sort_values("survival_rate", ascending=True)

    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, len(df) * _FIG_H_PER_ITEM)), layout="constrained"
    )
    sns.barplot(
        data=df,
        y="code",
        x="survival_rate",
        orient="h",
        color=sns.color_palette("deep")[0],
        ax=ax,
    )
    ax.axvline(x=0.5, color="gray", linestyle="--", linewidth=1)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_xlabel("Survival rate (final / raw)")
    ax.set_ylabel("Code")
    ax.set_title("Judge Survival Rate per Code")
    _save_or_show(fig, save_path)
    return ax


def visualise_code_set_sizes(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
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
    ax.set_ylabel("Number of distinct codes")
    ax.set_title("Code Set Size per Student: Gold vs Tool")
    ax.legend(title="Source")
    _save_or_show(fig, save_path)
    return ax


def visualise_raw_vs_final_code_count(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Scatter of raw code count vs final code count, showing judge filtering effect."""
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.scatterplot(
        data=per_student_df,
        x="raw_code_count",
        y="tool_code_count",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        s=70,
        zorder=3,
        ax=ax,
    )
    lo = 0
    hi = per_student_df["raw_code_count"].max() + 1
    ax.plot([lo, hi], [lo, hi], color="gray", linestyle="--", linewidth=1, zorder=1)
    ax.set_xlabel("Raw code count (pre-judge)")
    ax.set_ylabel("Final code count (post-judge)")
    ax.set_title("Judge Filtering: Raw vs Final Code Count per Student")
    ax.legend(title="Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_cost_by_variant(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Strip and box plot of cost per document by variant."""
    df = _validate_data(per_student_df, ["cost_eur"], "visualise_cost_by_variant")
    if df is None:
        return plt.subplots()[1]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.boxplot(
        data=df,
        x="task_variant",
        y="cost_eur",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        legend=False,
        ax=ax,
        fill=False,
        flierprops={"alpha": 0},
        order=["par", "int"],
    )
    sns.stripplot(
        data=df,
        x="task_variant",
        y="cost_eur",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        legend=False,
        order=["par", "int"],
        alpha=0.7,
        size=7,
        jitter=True,
        ax=ax,
    )
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Cost (EUR)")
    ax.set_title("Pipeline Cost per Document by Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_cost_vs_doc_points(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Scatter of gold doc_points vs cost per document."""
    df = _validate_data(
        per_student_df, ["doc_points", "cost_eur"], "visualise_cost_vs_doc_points"
    )
    if df is None:
        return plt.subplots()[1]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.scatterplot(
        data=df,
        x="doc_points",
        y="cost_eur",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        s=80,
        ax=ax,
    )
    ax.set_xlabel("Gold documentation points")
    ax.set_ylabel("Cost (EUR)")
    ax.set_title("Pipeline Cost vs Student Documentation Score")
    ax.legend(title="Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_latency_by_variant(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Strip and box plot of elapsed_seconds per document by variant."""
    df = _validate_data(
        per_student_df, ["elapsed_seconds"], "visualise_latency_by_variant"
    )
    if df is None:
        return plt.subplots()[1]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.boxplot(
        data=df,
        x="task_variant",
        y="elapsed_seconds",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        legend=False,
        ax=ax,
        fill=False,
        flierprops={"alpha": 0},
        order=["par", "int"],
    )
    sns.stripplot(
        data=df,
        x="task_variant",
        y="elapsed_seconds",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        legend=False,
        order=["par", "int"],
        alpha=0.7,
        size=7,
        jitter=True,
        ax=ax,
    )
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Elapsed time (seconds)")
    ax.set_title("Pipeline Latency per Document by Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_token_breakdown(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Stacked bar of mean prompt vs completion tokens per variant."""
    df = _validate_data(
        per_student_df,
        ["prompt_tokens", "completion_tokens"],
        "visualise_token_breakdown",
    )
    if df is None:
        return plt.subplots()[1]

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
    )
    ax.set_xlabel("Task variant")
    ax.set_ylabel("Mean tokens")
    ax.set_title("Mean Token Usage per Document by Variant")
    ax.legend(title="Token type")
    _save_or_show(fig, save_path)
    return ax


def visualise_per_variant_metrics(summary: dict, save_path: Path | None = None) -> Axes:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for par vs int."""
    per_variant = summary.get("per_variant", {})
    if not per_variant:
        logger.warning("per_variant block is empty, skipping per_variant_metrics")
        return plt.subplots()[1]

    mae_rows = []
    prf_rows = []

    mae_metrics = {"MAE (pts)": "points_mae"}
    prf_metrics = {
        "Precision": "macro_precision",
        "Recall": "macro_recall",
        "F1": "macro_f1",
    }

    for variant, stats in per_variant.items():
        for label, key in mae_metrics.items():
            val = stats.get(key)
            if val is not None:
                mae_rows.append({"Variant": variant, "Metric": label, "Value": val})
        for label, key in prf_metrics.items():
            val = stats.get(key)
            if val is not None:
                prf_rows.append({"Variant": variant, "Metric": label, "Value": val})

    df_mae = pd.DataFrame(mae_rows)
    df_prf = pd.DataFrame(prf_rows)

    fig, axes = plt.subplots(1, 2, figsize=(_FIG_W * 1.5, _FIG_H), layout="constrained")

    if not df_mae.empty:
        sns.barplot(
            data=df_mae,
            x="Metric",
            y="Value",
            hue="Variant",
            palette=TASK_VARIANT_PALETTE,
            ax=axes[0],
        )
        axes[0].set_xlabel("")
        axes[0].set_ylabel("Points")
        axes[0].set_title("Mean Absolute Error (MAE)")
        axes[0].legend(title="Variant")
    else:
        axes[0].set_title("No MAE Data")

    if not df_prf.empty:
        sns.barplot(
            data=df_prf,
            x="Metric",
            y="Value",
            hue="Variant",
            palette=TASK_VARIANT_PALETTE,
            ax=axes[1],
        )
        axes[1].set_xlabel("")
        axes[1].set_ylabel("Value")
        axes[1].set_ylim(0, 1.05)
        axes[1].set_title("Performance Metrics")
        axes[1].legend(title="Variant")
    else:
        axes[1].set_title("No P/R/F1 Data")

    fig.suptitle("Evaluation Metrics by Task Variant")
    _save_or_show(fig, save_path)
    return axes[0]


def visualise_per_language_metrics(
    summary: dict, save_path: Path | None = None
) -> Axes:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for document language."""
    per_language = summary.get("per_language", {})
    if not per_language:
        logger.warning(
            "per_language block is empty, skipping visualise_per_language_metrics"
        )
        return plt.subplots()[1]

    mae_rows = []
    prf_rows = []

    mae_metrics = {"MAE (pts)": "points_mae"}
    prf_metrics = {
        "Precision": "macro_precision",
        "Recall": "macro_recall",
        "F1": "macro_f1",
    }

    for lang, stats in per_language.items():
        for label, key in mae_metrics.items():
            val = stats.get(key)
            if val is not None:
                mae_rows.append({"Language": lang, "Metric": label, "Value": val})
        for label, key in prf_metrics.items():
            val = stats.get(key)
            if val is not None:
                prf_rows.append({"Language": lang, "Metric": label, "Value": val})

    df_mae = pd.DataFrame(mae_rows)
    df_prf = pd.DataFrame(prf_rows)

    fig, axes = plt.subplots(1, 2, figsize=(_FIG_W * 1.5, _FIG_H), layout="constrained")

    if not df_mae.empty:
        sns.barplot(
            data=df_mae,
            x="Metric",
            y="Value",
            hue="Language",
            palette=LANGUAGE_PALETTE,
            ax=axes[0],
        )
        axes[0].set_xlabel("")
        axes[0].set_ylabel("Points")
        axes[0].set_title("Mean Absolute Error (MAE)")
        axes[0].legend(title="Language")
    else:
        axes[0].set_title("No MAE Data")

    if not df_prf.empty:
        sns.barplot(
            data=df_prf,
            x="Metric",
            y="Value",
            hue="Language",
            palette=LANGUAGE_PALETTE,
            ax=axes[1],
        )
        axes[1].set_xlabel("")
        axes[1].set_ylabel("Value")
        axes[1].set_ylim(0, 1.05)
        axes[1].set_title("Performance Metrics")
        axes[1].legend(title="Language")
    else:
        axes[1].set_title("No P/R/F1 Data")

    fig.suptitle("Evaluation Metrics by Document Language")
    _save_or_show(fig, save_path)
    return axes[0]


def visualise_per_format_metrics(summary: dict, save_path: Path | None = None) -> Axes:
    """Grouped bar chart of MAE, macro-P, macro-R and macro-F1 for PDF vs MD."""
    per_format = summary.get("per_format", {})
    if not per_format:
        logger.warning(
            "per_format block is empty, skipping visualise_per_format_metrics"
        )
        return plt.subplots()[1]

    mae_rows = []
    prf_rows = []

    mae_metrics = {"MAE (pts)": "points_mae"}
    prf_metrics = {
        "Precision": "macro_precision",
        "Recall": "macro_recall",
        "F1": "macro_f1",
    }

    for fmt, stats in per_format.items():
        for label, key in mae_metrics.items():
            val = stats.get(key)
            if val is not None:
                mae_rows.append({"Format": fmt, "Metric": label, "Value": val})
        for label, key in prf_metrics.items():
            val = stats.get(key)
            if val is not None:
                prf_rows.append({"Format": fmt, "Metric": label, "Value": val})

    df_mae = pd.DataFrame(mae_rows)
    df_prf = pd.DataFrame(prf_rows)

    fig, axes = plt.subplots(1, 2, figsize=(_FIG_W * 1.5, _FIG_H), layout="constrained")

    if not df_mae.empty:
        sns.barplot(
            data=df_mae,
            x="Metric",
            y="Value",
            hue="Format",
            palette=FORMAT_PALETTE,
            ax=axes[0],
        )
        axes[0].set_xlabel("")
        axes[0].set_ylabel("Points")
        axes[0].set_title("Mean Absolute Error (MAE)")
        axes[0].legend(title="Format")
    else:
        axes[0].set_title("No MAE Data")

    if not df_prf.empty:
        sns.barplot(
            data=df_prf,
            x="Metric",
            y="Value",
            hue="Format",
            palette=FORMAT_PALETTE,
            ax=axes[1],
        )
        axes[1].set_xlabel("")
        axes[1].set_ylabel("Value")
        axes[1].set_ylim(0, 1.05)
        axes[1].set_title("Performance Metrics")
        axes[1].legend(title="Format")
    else:
        axes[1].set_title("No P/R/F1 Data")

    fig.suptitle("Evaluation Metrics by Document Format")
    _save_or_show(fig, save_path)
    return axes[0]


def visualise_mae_by_score_quartile(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
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
    ax.set_xlabel("Gold score quartile")
    ax.set_ylabel("Absolute points delta")
    ax.set_title("Tool Error (|Delta|) by Gold Score Quartile")
    ax.legend(title="Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_format_comparison(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Side-by-side strip+box plots comparing PDF vs Markdown on three metrics."""
    df = _validate_data(per_student_df, ["doc_type"], "visualise_format_comparison")
    if df is None:
        return plt.subplots()[1]

    metrics: list[tuple[str, str]] = []
    if "cost_eur" in df.columns and df["cost_eur"].notna().any():
        metrics.append(("cost_eur", "Cost (EUR)"))
    if "elapsed_seconds" in df.columns and df["elapsed_seconds"].notna().any():
        metrics.append(("elapsed_seconds", "Latency (s)"))
    metrics.append(("overlap_count", "Overlap count"))

    if not metrics:
        logger.warning("No suitable columns for format_comparison")
        return plt.subplots()[1]

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
            flierprops={"alpha": 0},
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

    fig.suptitle("PDF vs Markdown: Cost / Latency / Overlap")
    _save_or_show(fig, save_path)
    return axes[0]


def visualise_stage_times(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
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
        return plt.subplots()[1]

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
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Density")
    ax.set_title("Distribution of Pipeline Stage Times")
    _save_or_show(fig, save_path)
    return ax


def visualise_cost_vs_words(
    per_student_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Scatter of total_words vs cost_eur, coloured by task variant."""
    df = _validate_data(
        per_student_df, ["total_words", "cost_eur"], "visualise_cost_vs_words"
    )
    if df is None:
        return plt.subplots()[1]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.scatterplot(
        data=df,
        x="total_words",
        y="cost_eur",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        s=80,
        ax=ax,
    )
    ax.set_xlabel("Document word count")
    ax.set_ylabel("Cost (EUR)")
    ax.set_title("Pipeline Cost vs Document Word Count")
    ax.legend(title="Variant")
    _save_or_show(fig, save_path)
    return ax


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
    visualise_latency_by_variant(per_student_df, _path("latency_by_variant.png"))
    visualise_token_breakdown(per_student_df, _path("token_breakdown.png"))
    visualise_stage_times(per_student_df, _path("stage_times.png"))

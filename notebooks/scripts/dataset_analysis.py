"""IPP assessment analysis and visualisation.

Author: Matúš Csirik
"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from langdetect import LangDetectException, detect
from matplotlib.ticker import PercentFormatter

from .assessment_data.constants import MAX_DOC_POINTS
from .assessment_data.dataset_parser import DOC_CODES
from .visual_utils import (
    _FIG_H,
    _FIG_H_PER_ITEM,
    _FIG_W,
    CODE_TYPE_PALETTE,
    FORMAT_PALETTE,
    LANGUAGE_PALETTE,
    TASK_VARIANT_PALETTE,
    _save_or_show,
    _validate_data,
    add_horizontal_reference_line,
    add_vertical_reference_line,
    format_facet_grid,
    move_legend_if_present,
    render_plot,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes

logger = logging.getLogger(__name__)

_WARNING_TYPE_PALETTE: dict[str, str] = {
    "Warning (0)": "#1f77b4",
    "Bonus (>0)": "#2ca02c",
    "Penalty (<0)": "#d62728",
    "Unknown": "#7f7f7f",
}


def _code_category_labels(values: pd.Series) -> pd.Series:
    """Map codes to shared plotting categories for consistent hue labelling."""
    return values.isin(DOC_CODES).map({True: "Doc code", False: "Other code"})


def _normalise_year_token(value: str) -> str:
    """
    Normalise academic-year tokens,
    (for example 2021, meaning 20/21) to start year (2020).
    """
    token = value.strip()
    if not re.fullmatch(r"\d{4}", token):
        return token

    start_yy = int(token[:2])
    end_yy = int(token[2:])
    if end_yy == (start_yy + 1) % 100:
        return f"20{start_yy:02d}"

    return token


def load_clean_data(path: Path | None = None) -> pd.DataFrame:
    """
    Load the cleaned IPP event data from CSV.
    Also adds max_doc_points (from MAX_DOC_POINTS lookup) and
    impact_normalised (impact / max_doc_points) to every row.
    Rows for years/variants not in MAX_DOC_POINTS get NaN for both columns.
    """
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "clean_ipp_data.csv"

    df = pd.read_csv(path)

    df["year"] = df["year"].astype(str).map(_normalise_year_token)
    df["task_variant"] = df["task_variant"].astype(str)

    years = sorted(df["year"].unique())

    return df.assign(
        year=pd.Categorical(df["year"], categories=years, ordered=True),
        impact=pd.to_numeric(df["impact"], errors="coerce"),
        doc_points=pd.to_numeric(df["doc_points"], errors="coerce"),
        bonus_points=pd.to_numeric(df["bonus_points"], errors="coerce"),
        impact_has_sign=df["impact_has_sign"].astype("boolean"),
        impact_shared=df["impact_shared"].astype("boolean"),
        max_doc_points=df.set_index(["year", "task_variant"]).index.map(MAX_DOC_POINTS),
    ).assign(impact_normalised=lambda d: d["impact"] / d["max_doc_points"])


def build_project_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate event data to one row per project.

    Returns DataFrame with columns: id, year, task_variant, doc_points, doc_score_pct,
    doc_type, bonus_points, n_events, n_unique_codes, codes_list, total_impact,
    has_any_comment, source_file.
    """
    df_temp = df.assign(
        individual_impact=df["impact"].where(~df["impact_shared"].fillna(False)),
        has_comment=df["comment"].notna(),
    )
    return (
        df_temp.groupby(["id", "year", "task_variant"], sort=False, observed=True)
        .agg(
            doc_points=("doc_points", "first"),
            max_doc_points=("max_doc_points", "first"),
            doc_type=("doc_type", "first"),
            bonus_points=("bonus_points", "first"),
            n_events=("code", "size"),
            n_unique_codes=("code", "nunique"),
            codes_list=("code", lambda x: list(x.unique())),
            total_impact=("individual_impact", lambda x: x.sum(min_count=1)),
            has_any_comment=("has_comment", "any"),
            source_file=("source_file", "first"),
        )
        .reset_index()
        .assign(doc_score_pct=lambda d: (d["doc_points"] / d["max_doc_points"]) * 100)
    )


def filter_for_impact_stats(
    df: pd.DataFrame, exclude_shared: bool = True
) -> pd.DataFrame:
    """
    Filter to rows that have a given impact value.
    If exclude_shared=True, also exclude impact_shared=True rows.
    """
    mask = df["impact"].notna()
    if exclude_shared:
        mask = mask & ~df["impact_shared"]
    return df[mask]


def filter_to_normalised_years(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows where the year/variant has a known documentation point maximum."""
    return df.dropna(subset=["max_doc_points"])


def analyse_volume(df: pd.DataFrame, proj: pd.DataFrame) -> None:
    """Print key volume statistics."""
    logger.info("Total projects: %d", len(proj))
    logger.info("Total files: %d", df["source_file"].nunique())
    logger.info("Total unique codes used: %d", df["code"].nunique())
    logger.info("Year range: %s", (df["year"].min(), df["year"].max()))
    logger.info("Task Variants: %s", sorted(df["task_variant"].unique()))
    logger.info("Total grading events: %d", len(df))
    logger.info("Total grading events with impacts: %d", df["impact"].notna().sum())


def summarise_score_imbalance(proj: pd.DataFrame) -> None:
    """Print statistics about projects with zero documentation deductions."""
    perfect_docs = (proj["total_impact"] >= 0).sum()
    total_docs = len(proj)
    perfect_ratio = (perfect_docs / total_docs) * 100
    logger.info(
        "Projects with 0 deductions: %s / %s (%.1f%%)",
        perfect_docs,
        total_docs,
        perfect_ratio,
    )


def visualise_total_impact_distribution(
    proj: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Plot the distribution of total impact per project."""
    plot_data = proj.assign(
        total_impact_normalised=lambda d: d["total_impact"] / d["max_doc_points"]
    ).dropna(subset=["total_impact_normalised"])

    return render_plot(
        sns.histplot,
        data=plot_data,
        title="Distribution of Total Documentation Deductions per Project",
        xlabel="Total Deduction Score (% of Maximum)",
        ylabel="Number of Projects (count)",
        save_path=save_path,
        x="total_impact_normalised",
        bins=30,
        x_pct=True,
        y_int=True,
    )


def analyse_impact_statistics(
    df: pd.DataFrame, exclude_shared: bool = True
) -> pd.DataFrame:
    """
    Code impact statistics: count, mean, median, std, min, max, pct_no_impact.
    Returns DataFrame sorted by mean impact ascending.
    """
    df = filter_to_normalised_years(df)

    is_warning = df["impact"].isna()
    valid_for_math = df["impact"].notna()
    if exclude_shared:
        valid_for_math = valid_for_math & ~df["impact_shared"].fillna(False)

    return (
        df.assign(
            is_warning=is_warning,
            math_impact=df["impact_normalised"].where(valid_for_math),
        )
        .groupby("code")
        .agg(
            total=("code", "count"),
            pct_no_impact=("is_warning", "mean"),
            count=("math_impact", "count"),
            mean=("math_impact", "mean"),
            median=("math_impact", "median"),
            std=("math_impact", "std"),
            min=("math_impact", "min"),
            max=("math_impact", "max"),
        )
        .reset_index()
        .sort_values("mean")
    )


def analyse_format_impact(proj: pd.DataFrame) -> pd.DataFrame:
    """Build per-project data for document format comparison."""
    return proj.dropna(subset=["doc_type", "doc_score_pct"])


def summarise_format_impact(format_impact_df: pd.DataFrame) -> pd.DataFrame:
    """Return summary statistics for the analysed format impact data."""
    return (
        format_impact_df.groupby("doc_type")["doc_score_pct"]
        .agg(["count", "mean", "median"])
        .round(2)
        .sort_values("mean")
    )


def visualise_format_impact(
    format_impact_df: pd.DataFrame,
    save_path: Path | None = None,
) -> Axes | None:
    """
    Plot cumulative score distributions of Markdown vs PDF submissions.
    Expects the output of `analyse_format_impact`.
    """
    valid_df = _validate_data(
        format_impact_df, ["doc_score_pct", "doc_type"], "visualise_format_impact"
    )
    if valid_df is None:
        return None

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.ecdfplot(
        data=valid_df,
        y="doc_score_pct",
        hue="doc_type",
        palette=FORMAT_PALETTE,
        legend=False,
        linewidth=2.5,
        ax=ax,
    )
    add_vertical_reference_line(ax, x=0.5, label="Reference: Median Student")
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_xlabel("Students (%)")
    ax.set_ylabel("Score (% of Maximum)")
    ax.set_title("Cumulative Score Distribution by Document Format")
    ax.text(
        x=0.51,
        y=valid_df["doc_score_pct"].min() + 5,
        s="Median Student",
        color="gray",
        fontsize=10,
    )
    _save_or_show(fig, save_path)
    return ax


def analyse_zero_impact_warnings(df: pd.DataFrame, n_codes: int = 20) -> pd.DataFrame:
    """Prepare warning vs penalty events for top codes."""
    events = df[(df["code"] != "OK") & df["impact"].notna()]
    codes = events["code"].value_counts().head(n_codes).index.tolist()

    return events[events["code"].isin(codes)].assign(
        penalty_type=lambda d: np.select(
            [d["impact"] == 0, d["impact"] > 0, d["impact"] < 0],
            ["Warning (0)", "Bonus (>0)", "Penalty (<0)"],
            default="Unknown",
        )
    )


def summarise_zero_impact_warnings(warnings_df: pd.DataFrame) -> pd.DataFrame:
    """Summarise warning vs penalty ratios by code."""
    summary = warnings_df.groupby(["code", "penalty_type"]).size().unstack(fill_value=0)
    summary["total"] = summary.sum(axis=1)
    if "Warning (0)" in summary.columns:
        summary["warning_pct"] = (
            summary["Warning (0)"] / summary["total"] * 100
        ).round(1)
    return summary.sort_values("total", ascending=False)


def visualise_zero_impact_warnings(
    warnings_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """
    Plot the ratio of zero-impact warnings vs actual penalties per code.
    Expects the pre-computed output of `analyse_zero_impact_warnings`.
    """
    warning_props = (
        warnings_df.assign(is_warning=(warnings_df["penalty_type"] == "Warning (0)"))
        .groupby("code")["is_warning"]
        .mean()
        .sort_values(ascending=False)
    )
    order = warning_props.index.tolist()
    plot_data = warnings_df.assign(
        code=pd.Categorical(warnings_df["code"], categories=order, ordered=True)
    )

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(
        data=plot_data,
        y="code",
        hue="penalty_type",
        hue_order=["Penalty (<0)", "Warning (0)", "Bonus (>0)", "Unknown"],
        palette=_WARNING_TYPE_PALETTE,
        multiple="fill",
        discrete=True,
        shrink=0.8,
        ax=ax,
    )
    ax.set_xlabel("Proportion (%)")
    ax.set_ylabel("Code")
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_title("Warning Vs Penalty Vs Bonus Rate per Code")
    move_legend_if_present(ax, title="Type", loc="lower right")
    _save_or_show(fig, save_path)
    return ax


def visualise_doc_type_distribution(
    proj: pd.DataFrame,
    save_path: Path | None = None,
) -> Axes | None:
    """Plot proportional PDF vs MD submission distribution per year."""
    data = _validate_data(proj, ["doc_type", "year"], "visualise_doc_type_distribution")
    if data is None:
        return None
    data = data.sort_values("year")

    def _plot_doc_type_distribution(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.histplot(data=data, ax=ax, **kwargs)
        ax.tick_params(axis="x", rotation=45)

    return render_plot(
        _plot_doc_type_distribution,
        data=data,
        title="Document Format Distribution by Year",
        xlabel="Year",
        ylabel="Proportion (%)",
        save_path=save_path,
        x="year",
        hue="doc_type",
        hue_order=list(FORMAT_PALETTE),
        palette=FORMAT_PALETTE,
        multiple="fill",
        discrete=True,
        shrink=0.8,
        y_pct=True,
    )


def visualise_task_variant_distribution(
    proj: pd.DataFrame,
    save_path: Path | None = None,
) -> Axes | None:
    """Plot project counts per task variant per year."""
    data = _validate_data(
        proj, ["year", "task_variant"], "visualise_task_variant_distribution"
    )
    if data is None:
        return None
    data = data.sort_values("year")

    def _plot_task_variant_distribution(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.countplot(data=data, ax=ax, **kwargs)
        move_legend_if_present(ax, title="Task variant", loc="lower right")

    return render_plot(
        _plot_task_variant_distribution,
        data=data,
        title="Projects per Task Variant by Year",
        xlabel="Year",
        ylabel="Number of Projects (count)",
        save_path=save_path,
        x="year",
        hue="task_variant",
        palette=TASK_VARIANT_PALETTE,
        y_int=True,
    )


def visualise_score_trend_by_year_variant(
    proj: pd.DataFrame,
    save_path: Path | None = None,
) -> Axes | None:
    """Plot mean documentation score by year and task variant."""

    data = _validate_data(
        proj,
        ["year", "task_variant", "doc_score_pct"],
        "visualise_score_trend_by_year_variant",
    )
    if data is None:
        return None

    variant_order = [
        variant
        for variant in TASK_VARIANT_PALETTE
        if variant in data["task_variant"].unique()
    ]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.lineplot(
        data=data,
        x="year",
        y="doc_score_pct",
        hue="task_variant",
        hue_order=variant_order,
        palette=TASK_VARIANT_PALETTE,
        marker="o",
        errorbar=("ci", 95),
        ax=ax,
    )
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_title("Mean Documentation Score by Year and Task Variant")
    ax.set_xlabel("Year")
    ax.set_ylabel("Documentation Score (% of Maximum)")
    move_legend_if_present(ax, title="Task Variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_score_distribution_by_variant(
    proj: pd.DataFrame,
    save_path: Path | None = None,
) -> Axes | None:
    """Plot documentation score distribution by task variant."""

    data = _validate_data(
        proj,
        ["task_variant", "doc_score_pct"],
        "visualise_score_distribution_by_variant",
    )
    if data is None:
        return None

    variant_order = [
        variant
        for variant in TASK_VARIANT_PALETTE
        if variant in data["task_variant"].unique()
    ]

    def _plot_score_distribution_by_variant(
        data: pd.DataFrame, ax: Axes, **kwargs
    ) -> None:
        sns.boxplot(data=data, ax=ax, **kwargs)
        add_horizontal_reference_line(ax, y=100, label="Reference: Max score")
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))

    return render_plot(
        _plot_score_distribution_by_variant,
        data=data,
        title="Documentation Score Distribution by Task Variant",
        xlabel="Task Variant",
        ylabel="Documentation Score (% of Maximum)",
        save_path=save_path,
        x="task_variant",
        y="doc_score_pct",
        hue="task_variant",
        order=variant_order,
        hue_order=variant_order,
        palette=TASK_VARIANT_PALETTE,
        legend=False,
        whis=(5, 95),
    )


def visualise_code_frequency(
    df: pd.DataFrame, n_codes: int = 20, save_path: Path | None = None
) -> Axes:
    """Plot the n_codes most frequently used codes by occurrence count."""
    codes = df["code"].value_counts().head(n_codes).index.tolist()[::-1]
    plot_data = df[df["code"].isin(codes)].assign(
        code_category=lambda d: _code_category_labels(d["code"])
    )

    def _plot_code_frequency(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.countplot(data=data, ax=ax, **kwargs)
        move_legend_if_present(ax, title="Category")

    return render_plot(
        _plot_code_frequency,
        data=plot_data,
        title=f"Top {n_codes} IPP Codes by Occurrence Count",
        xlabel="Number of Events (count)",
        ylabel="Code",
        save_path=save_path,
        figsize=(_FIG_W, max(_FIG_H, n_codes * _FIG_H_PER_ITEM)),
        y="code",
        order=codes,
        hue="code_category",
        palette=CODE_TYPE_PALETTE,
        dodge=False,
        x_int=True,
    )


def visualise_impact_boxplots(
    df: pd.DataFrame,
    codes: list[str] | None = None,
    n_codes: int = 15,
    exclude_shared: bool = True,
    save_path: Path | None = None,
) -> Axes:
    """Plot impact distribution per code as overlaid strip and boxplots."""
    df = filter_to_normalised_years(df)
    filtered = filter_for_impact_stats(df, exclude_shared=exclude_shared)
    has_explicit_codes = codes is not None
    codes = codes or filtered["code"].value_counts().head(n_codes).index.tolist()
    subset = filtered[filtered["code"].isin(codes)].assign(
        code_category=lambda d: _code_category_labels(d["code"])
    )
    order = (
        subset.groupby("code")["impact_normalised"]
        .median()
        .sort_values()
        .index.tolist()
    )
    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, len(order) * _FIG_H_PER_ITEM)),
        layout="constrained",
    )
    sns.boxplot(
        data=subset,
        y="code",
        x="impact_normalised",
        order=order,
        hue="code_category",
        dodge=False,
        palette=CODE_TYPE_PALETTE,
        ax=ax,
        orient="h",
        fill=False,
        flierprops={"alpha": 0},
        legend=False,
    )
    sns.stripplot(
        data=subset,
        y="code",
        x="impact_normalised",
        order=order,
        hue="code_category",
        dodge=False,
        palette=CODE_TYPE_PALETTE,
        ax=ax,
        orient="h",
        alpha=0.5,
        size=4,
        jitter=True,
        legend=True,
    )
    format_facet_grid(
        ax,
        xlabel="Impact Score (% of Maximum)",
        ylabel="Code",
        titles="Impact Score Distribution per Code",
        x_pct=True,
    )
    legend_loc = "upper right" if has_explicit_codes else "lower left"
    move_legend_if_present(ax, title="Category", loc=legend_loc)
    _save_or_show(fig, save_path)
    return ax


def visualise_shared_vs_individual_impact(
    df: pd.DataFrame,
    n_codes: int = 15,
    save_path: Path | None = None,
) -> Axes:
    """Dumbbell chart comparing mean impact with vs without shared penalties."""
    df = filter_to_normalised_years(df)

    mean_excl = (
        filter_for_impact_stats(df)
        .groupby("code")["impact_normalised"]
        .mean()
        .rename("excl_shared")
    )
    mean_incl = (
        filter_for_impact_stats(df, exclude_shared=False)
        .groupby("code")["impact_normalised"]
        .mean()
        .rename("incl_shared")
    )
    combined = pd.concat([mean_excl, mean_incl], axis=1).dropna()
    combined["diff"] = (combined["incl_shared"] - combined["excl_shared"]).abs()
    # keep only codes where shared penalties actually shift the mean the most
    combined = combined.nlargest(n_codes, "diff")

    melted = (
        combined.reset_index()
        .melt(
            id_vars="code",
            value_vars=["excl_shared", "incl_shared"],
            var_name="Penalty scope",
            value_name="impact_normalised",
        )
        .assign(
            penalty_scope_label=lambda d: d["Penalty scope"].map(
                {"excl_shared": "Excluding shared", "incl_shared": "Including shared"}
            )
        )
    )
    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, len(combined) * _FIG_H_PER_ITEM)),
        layout="constrained",
    )
    sns.lineplot(
        data=melted,
        x="impact_normalised",
        y="code",
        units="code",
        estimator=None,
        color="gray",
        linewidth=1.5,
        zorder=1,
        ax=ax,
    )
    sns.scatterplot(
        data=melted,
        x="impact_normalised",
        y="code",
        hue="penalty_scope_label",
        s=60,
        zorder=3,
        ax=ax,
    )
    format_facet_grid(
        ax,
        xlabel="Mean Impact Score (% of Maximum)",
        ylabel="Code",
        titles="Shared Vs Individual Impact Comparison",
        x_pct=True,
    )
    move_legend_if_present(ax, title="Penalty Scope")
    _save_or_show(fig, save_path)
    return ax


def visualise_code_usage_trends(
    proj: pd.DataFrame,
    codes: list[str] | None = None,
    n_codes: int = 8,
    save_path: Path | None = None,
) -> sns.FacetGrid | None:
    """
    Plot the fraction of projects that received each code per year.
    The shaded area around each line shows the 95% confidence interval.
    """
    valid_proj = _validate_data(
        proj, ["id", "year", "codes_list"], "visualise_code_usage_trends"
    )
    if valid_proj is None:
        return None

    exploded = valid_proj[["id", "year", "codes_list"]].explode("codes_list")

    if codes is None:
        code_counts = exploded["codes_list"].value_counts()
        codes = code_counts.nlargest(n_codes).index.tolist()

    binary = (
        pd.crosstab([exploded["id"], exploded["year"]], exploded["codes_list"])
        .reindex(columns=codes, fill_value=0)
        .reset_index()
    )
    binary[codes] = binary[codes].astype(bool)

    melted = binary.melt(
        id_vars=["id", "year"],
        value_vars=codes,
        var_name="code",
        value_name="has_code",
    ).assign(code_category=lambda d: _code_category_labels(d["code"]))
    g = sns.relplot(
        data=melted,
        x="year",
        y="has_code",
        col="code",
        hue="code_category",
        palette=CODE_TYPE_PALETTE,
        col_wrap=4,
        kind="line",
        errorbar=("ci", 95),
        marker="o",
        height=3,
        aspect=1.3,
    )
    format_facet_grid(
        g,
        xlabel="Year",
        ylabel="Projects (%)",
        titles="{col_name}",
        y_pct=True,
        x_rotation=45,
        suptitle=(
            "Code Usage Over Time\n(Shaded Area Shows the 95% Confidence Interval)"
        ),
        suptitle_y=1.05,
    )
    _save_or_show(g.figure, save_path)
    return g


def visualise_code_impact_trends(
    df: pd.DataFrame,
    codes: list[str] | None = None,
    n_codes: int = 8,
    save_path: Path | None = None,
) -> sns.FacetGrid:
    """
    Plot mean penalty per code per year, expressed as a fraction of the maximum score.
    The shaded area around each line shows the 95% confidence interval.
    """
    df = filter_to_normalised_years(df)
    filtered = filter_for_impact_stats(df)
    codes = codes or filtered["code"].value_counts().head(n_codes).index.tolist()
    subset = filtered[filtered["code"].isin(codes)].assign(
        code_category=lambda d: _code_category_labels(d["code"])
    )

    g = sns.relplot(
        data=subset,
        x="year",
        y="impact_normalised",
        col="code",
        hue="code_category",
        palette=CODE_TYPE_PALETTE,
        col_wrap=4,
        kind="line",
        errorbar=("ci", 95),
        marker="o",
        height=3,
        aspect=1.3,
    )
    format_facet_grid(
        g,
        xlabel="Year",
        ylabel="Mean Impact Score (% of Maximum)",
        y_pct=True,
        x_rotation=45,
        suptitle=(
            "Code Impact Over Time\n(Shaded Area Shows the 95% Confidence Interval)"
        ),
        suptitle_y=1.05,
    )
    _save_or_show(g.figure, save_path)
    return g


def visualise_code_cooccurrence(
    proj: pd.DataFrame,
    n_codes: int = 15,
    save_path: Path | None = None,
) -> sns.matrix.ClusterGrid | None:
    """Hierarchical clustering to group similar codes."""
    valid_proj = _validate_data(
        proj, ["id", "codes_list"], "visualise_code_cooccurrence"
    )
    if valid_proj is None:
        return None

    exploded = valid_proj[["id", "codes_list"]].explode("codes_list")
    codes = exploded["codes_list"].value_counts().head(n_codes).index.tolist()

    binary = pd.crosstab(exploded["id"], exploded["codes_list"])[codes].astype(bool)

    corr_matrix = binary.corr()

    g = sns.clustermap(
        corr_matrix,
        cmap="mako",
        annot=True,
        center=0,
        fmt=".2f",
        figsize=(_FIG_W, _FIG_W),
        cbar_pos=(1.02, 0.15, 0.05, 0.65),
    )
    g.ax_row_dendrogram.set_visible(False)
    g.ax_col_dendrogram.set_visible(False)
    g.figure.suptitle("Code Co-occurrence Correlation", y=0.86)
    _save_or_show(g.figure, save_path)
    return g


def visualise_code_points_correlation(
    proj: pd.DataFrame,
    n_codes: int = 20,
    save_path: Path | None = None,
) -> Axes | None:
    """
    Correlation between code presence and documentation score (% of the maximum),
    normalised to remove cross year/variant max point differences.
    """
    valid_proj = _validate_data(
        proj, ["id", "doc_score_pct", "codes_list"], "visualise_code_points_correlation"
    )
    if valid_proj is None:
        return None

    exploded = valid_proj[["id", "codes_list"]].explode("codes_list")
    codes = exploded["codes_list"].value_counts().head(n_codes).index.tolist()

    binary = pd.crosstab(exploded["id"], exploded["codes_list"])[codes].astype(bool)

    correlations = binary.corrwith(
        valid_proj.set_index("id")["doc_score_pct"]
    ).sort_values(key=abs, ascending=True)

    plot_data = pd.DataFrame(
        {
            "correlation": correlations.values,
            "code": correlations.index,
            "code_category": _code_category_labels(pd.Series(correlations.index)),
        }
    )

    def _plot_code_points_correlation(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.barplot(data=data, ax=ax, **kwargs)
        move_legend_if_present(ax, title="Category", loc="upper right")

    return render_plot(
        _plot_code_points_correlation,
        data=plot_data,
        title="Code Correlation with Documentation Score",
        xlabel="Correlation with Documentation Score",
        ylabel="Code",
        save_path=save_path,
        figsize=(_FIG_W, _FIG_W),
        x="correlation",
        y="code",
        hue="code_category",
        palette=CODE_TYPE_PALETTE,
        dodge=False,
    )


_STOPWORDS = {
    "a",
    "i",
    "je",
    "se",
    "v",
    "na",
    "pro",
    "k",
    "do",
    "za",
    "s",
    "o",
    "z",
    "u",
    "od",
    "po",
    "jak",
    "co",
    "to",
    "ten",
    "ta",
    "ale",
    "nebo",
    "tak",
    "by",
    "si",
    "ne",
    "jen",
    "ve",
    "ze",
    "není",
    "být",
    "také",
    "bez",
    "atp",
    "např",
}


def detect_comment_language(text: str) -> str:
    """Detect the language of a comment string using langdetect."""
    stripped = text.strip() if text else ""
    if len(stripped) < 5 or not re.search(r"[A-Za-zÀ-ž]", stripped):
        return "unknown"
    try:
        lang = detect(text)
        return lang if lang in ("cs", "sk", "en") else "unknown"
    except LangDetectException:
        return "unknown"


def analyse_comment_presence(df: pd.DataFrame) -> pd.DataFrame:
    """
    What fraction of grading events have a non-null comment per code.
    Returns DataFrame: code, total_events, with_comment, pct_commented.
    """
    return (
        df.assign(has_comment=df["comment"].notna())
        .groupby("code")["has_comment"]
        .agg(total_events="count", with_comment="sum", pct_commented="mean")
        .reset_index()
        .assign(with_comment=lambda d: d["with_comment"].astype(int))
        .sort_values("pct_commented", ascending=False)
        .reset_index(drop=True)
    )


def analyse_comment_length(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare comment rows with computed comment lengths."""
    return df.dropna(subset=["comment"]).assign(
        comment_len=lambda d: d["comment"].str.len()
    )


def summarise_comment_length(comment_length_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate comment length statistics per code."""
    return (
        comment_length_df.groupby("code")["comment_len"]
        .agg(["count", "mean", "median", "max"])
        .sort_values("mean", ascending=False)
        .reset_index()
    )


def visualise_comment_length(
    comment_length_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """
    Plot the distribution of comment lengths.
    Expects the pre-computed output of `analyse_comment_length`.
    """

    def _plot_comment_length(data: pd.DataFrame, ax: Axes, **kwargs) -> None:
        sns.histplot(data=data, ax=ax, **kwargs)
        ax.set_xlim(0, data["comment_len"].quantile(0.99))

    return render_plot(
        _plot_comment_length,
        data=comment_length_df,
        title="Distribution of Comment Lengths",
        xlabel="Comment Length (characters)",
        ylabel="Number of Comments (count)",
        save_path=save_path,
        x="comment_len",
        binwidth=5,
        y_int=True,
    )


def analyse_language_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare comment rows with detected language labels."""
    return df.dropna(subset=["comment"]).assign(
        language=lambda d: d["comment"].map(detect_comment_language)
    )


def summarise_language_distribution(language_df: pd.DataFrame) -> pd.Series:
    """Return overall language counts for analysed comment language data."""
    return language_df["language"].value_counts()


def visualise_language_distribution_overall(
    language_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Bar chart of comment language totals."""
    return render_plot(
        sns.countplot,
        data=language_df,
        title="Comment Language (Overall)",
        xlabel="Language",
        ylabel="Number of Comments (count)",
        save_path=save_path,
        x="language",
        hue="language",
        hue_order=list(LANGUAGE_PALETTE),
        palette=LANGUAGE_PALETTE,
        legend=False,
        y_int=True,
    )


def visualise_language_distribution_by_year(
    language_df: pd.DataFrame, save_path: Path | None = None
) -> Axes:
    """Stacked proportion chart of comment language per year."""
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(
        data=language_df,
        x="year",
        hue="language",
        hue_order=list(LANGUAGE_PALETTE),
        palette=LANGUAGE_PALETTE,
        multiple="fill",
        discrete=True,
        shrink=0.8,
        ax=ax,
    )
    format_facet_grid(
        ax,
        xlabel="Year",
        ylabel="Proportion (%)",
        titles="Comment Language (By Year)",
        y_pct=True,
        x_rotation=45,
    )
    _save_or_show(fig, save_path)
    return ax


def analyse_comment_keywords(df: pd.DataFrame, n_keywords: int = 30) -> pd.DataFrame:
    """
    Top keywords from comment text after stopword removal.
    Returns a DataFrame with columns: keyword, count, top_codes.
    """
    comments = df.dropna(subset=["comment"])[["code", "comment"]]
    if comments.empty:
        return pd.DataFrame(columns=["keyword", "count", "top_codes"])

    # Explode to one (code, keyword) row per token
    pairs = (
        comments.assign(
            keyword=comments["comment"].str.lower().str.findall(r"[^\W\d_]{3,}")
        )
        .explode("keyword")
        .dropna(subset=["keyword"])
    )
    pairs = pairs[~pairs["keyword"].isin(_STOPWORDS)]

    counts = pairs["keyword"].value_counts().head(n_keywords)
    top_codes = pairs.groupby("keyword")["code"].apply(
        lambda s: ", ".join(s.value_counts().head(3).index)
    )

    return (
        counts.rename("count")
        .reset_index()
        .rename(columns={"index": "keyword"})
        .assign(top_codes=lambda d: d["keyword"].map(top_codes))
    )

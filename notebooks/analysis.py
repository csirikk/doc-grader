"""IPP assessment analysis and visualisation."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from dataset_parser import DOC_CODES
from langdetect import LangDetectException, detect
from matplotlib.ticker import PercentFormatter

# --- DATA ---

# Maximum documentation points per (year, task_variant), in milibody (mb).
# 100 mb = 1 b
MAX_DOC_POINTS: dict[tuple[str, str], int] = {
    ("2013", "php"): 200,
    ("2013", "py"): 200,
    ("2014", "php"): 200,
    ("2014", "py"): 200,
    ("2015", "php"): 200,
    ("2015", "py"): 200,
    ("2016", "php"): 200,
    ("2016", "py"): 200,
    ("2017", "int"): 300,
    ("2018", "par"): 100,
    ("2018", "int"): 200,
    ("2019", "par"): 100,
    ("2019", "int"): 200,
    ("2020", "par"): 100,
    ("2020", "int"): 200,
    ("2021", "par"): 100,
    ("2021", "int"): 200,
    ("2022", "par"): 100,
    ("2022", "int"): 300,
    ("2023", "par"): 100,
    ("2023", "int"): 400,
    ("2024", "par"): 100,
    ("2024", "int"): 400,
}


def load_clean_data(path: Path | None = None) -> pd.DataFrame:
    """
    Load the cleaned IPP event data from CSV.
    Also adds max_doc_points (from MAX_DOC_POINTS lookup) and
    impact_normalised (impact / max_doc_points) to every row.
    Rows for years/variants not in MAX_DOC_POINTS get NaN for both columns.
    """
    if path is None:
        path = Path(__file__).parent.parent / "data" / "clean_ipp_data.csv"

    df = pd.read_csv(path)

    df["year"] = df["year"].astype(str)
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
        df_temp.groupby(["id", "year", "task_variant"], sort=False)
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


# --- UTILITIES ---


def _ensure_proj(df: pd.DataFrame, proj: pd.DataFrame | None) -> pd.DataFrame:
    """Return proj if already computed, otherwise build it from df."""
    return proj if proj is not None else build_project_df(df)


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


# --- VISUALISATION UTILITIES ---

CODE_TYPE_PALETTE: dict[str, tuple] = {
    "Doc code": sns.color_palette("deep")[2],  # green
    "Other code": sns.color_palette("deep")[4],  # purple
}
TASK_VARIANT_PALETTE: dict[str, tuple] = {
    "php": sns.color_palette("deep")[0],  # blue
    "py": sns.color_palette("deep")[1],  # orange
    "par": sns.color_palette("deep")[2],  # green
    "int": sns.color_palette("deep")[3],  # red
}
FORMAT_PALETTE: dict[str, tuple] = {
    "md": sns.color_palette("deep")[0],  # blue
    "pdf": sns.color_palette("deep")[1],  # orange
}
LANGUAGE_PALETTE: dict[str, tuple] = {
    "cs": sns.color_palette("deep")[0],  # blue
    "sk": sns.color_palette("deep")[1],  # orange
    "en": sns.color_palette("deep")[2],  # green
    "unknown": sns.color_palette("deep")[7],  # gray
}

# Figure size constants
_FIG_W: int = 10  # standard width
_FIG_H: int = 6  # standard height
_FIG_H_PER_ITEM: float = 0.4  # height per row for list charts


def _save_or_show(fig: plt.Figure, save_path: Path | None) -> None:
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        print(f"Saved figure to {save_path}")
        plt.close(fig)
    else:
        plt.show()


def configure_plot_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook", palette="deep")


# --- OVERVIEW ---


def analyse_volume(df: pd.DataFrame, proj: pd.DataFrame | None = None) -> None:
    """Print key volume statistics."""
    proj = _ensure_proj(df, proj)
    print(f"Total projects: {len(proj)}")
    print(f"Total files: {df['source_file'].nunique()}")
    print(f"Total unique codes used: {df['code'].nunique()}")
    print(f"Year range: {(df['year'].min(), df['year'].max())}")
    print(f"Task Variants: {sorted(df['task_variant'].unique())}")
    print(f"Total grading events: {len(df)}")
    print(f"Total grading events with impacts: {df['impact'].notna().sum()}")


def summarise_score_imbalance(proj: pd.DataFrame) -> None:
    """Print statistics about projects with zero documentation deductions."""
    perfect_docs = (proj["total_impact"] >= 0).sum()
    total_docs = len(proj)
    perfect_ratio = (perfect_docs / total_docs) * 100
    print(
        f"Projects with 0 deductions: {perfect_docs} / {total_docs} ({perfect_ratio:.1f}%)"
    )


def visualise_total_impact_distribution(
    proj: pd.DataFrame, save_path: Path | None = None
) -> plt.Axes:
    """Plot the distribution of total impact per project."""
    plot_data = proj.assign(
        total_impact_normalised=lambda d: d["total_impact"] / d["max_doc_points"]
    ).dropna(subset=["total_impact_normalised"])

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(
        data=plot_data,
        x="total_impact_normalised",
        bins=30,
        ax=ax,
    )
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_title("Distribution of Total Documentation Deductions per Project")
    ax.set_xlabel("Total Deduction (% of Total Grade)")
    ax.set_ylabel("Number of Projects")
    _save_or_show(fig, save_path)
    return ax


# --- CODE IMPACT ---


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


# --- FORMAT ANALYSIS ---


def analyse_format_impact(
    df: pd.DataFrame, proj: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Build per-project data for document format comparison."""
    return _ensure_proj(df, proj).dropna(subset=["doc_type", "doc_score_pct"])


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
) -> plt.Axes:
    """
    Plot cumulative score distributions of Markdown vs PDF submissions.
    Expects the output of `analyse_format_impact`.
    """
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.ecdfplot(
        data=format_impact_df,
        y="doc_score_pct",
        hue="doc_type",
        palette=FORMAT_PALETTE,
        linewidth=2.5,
        ax=ax,
    )
    ax.set_xlabel("Fraction of Students")
    ax.set_ylabel("Documentation Score (% of Maximum)")
    ax.set_title("Cumulative Documentation Score Distribution by Document Format")
    ax.axvline(x=0.5, color="gray", linestyle="--", alpha=0.5, zorder=1)
    ax.text(
        x=0.51,
        y=format_impact_df["doc_score_pct"].min() + 5,
        s="Median Student",
        color="gray",
        fontsize=10,
    )
    _save_or_show(fig, save_path)
    return ax


# --- CODE WARNINGS ---


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
) -> plt.Axes:
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
        multiple="fill",
        discrete=True,
        shrink=0.8,
        ax=ax,
    )
    ax.set_xlabel("Proportion")
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.set_title("Warning vs Penalty vs Bonus Rate per Code")
    sns.move_legend(ax, loc="lower right", title="Type")
    _save_or_show(fig, save_path)
    return ax


# --- VISUALISATIONS ---


def visualise_doc_type_distribution(
    df: pd.DataFrame,
    proj: pd.DataFrame | None = None,
    save_path: Path | None = None,
) -> plt.Axes:
    """Plot proportional PDF vs MD submission distribution per year."""
    data = _ensure_proj(df, proj).dropna(subset=["doc_type"]).sort_values("year")

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(
        data=data,
        x="year",
        hue="doc_type",
        hue_order=list(FORMAT_PALETTE),
        palette=FORMAT_PALETTE,
        multiple="fill",
        discrete=True,
        shrink=0.8,
        ax=ax,
    )
    ax.set_ylabel("Proportion")
    ax.set_title("Document Format Distribution by Year")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.tick_params(axis="x", rotation=45)
    _save_or_show(fig, save_path)
    return ax


def visualise_task_variant_distribution(
    df: pd.DataFrame,
    proj: pd.DataFrame | None = None,
    save_path: Path | None = None,
) -> plt.Axes:
    """Plot project counts per task variant per year."""
    data = _ensure_proj(df, proj).sort_values("year")

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.countplot(
        data=data, x="year", hue="task_variant", palette=TASK_VARIANT_PALETTE, ax=ax
    )
    ax.set_ylabel("Number of Projects")
    ax.set_title("Projects per Task Variant by Year")
    ax.legend(title="Task variant")
    _save_or_show(fig, save_path)
    return ax


def visualise_code_frequency(
    df: pd.DataFrame, n_codes: int = 20, save_path: Path | None = None
) -> plt.Axes:
    """Plot the n_codes most frequently used codes by occurrence count."""
    codes = df["code"].value_counts().head(n_codes).index.tolist()[::-1]
    plot_data = df[df["code"].isin(codes)]

    fig, ax = plt.subplots(
        figsize=(_FIG_W, max(_FIG_H, n_codes * _FIG_H_PER_ITEM)), layout="constrained"
    )
    sns.countplot(
        data=plot_data,
        y="code",
        order=codes,
        hue=plot_data["code"]
        .isin(DOC_CODES)
        .map({True: "Doc code", False: "Other code"}),
        palette=CODE_TYPE_PALETTE,
        dodge=False,
        ax=ax,
    )

    ax.set_title(f"Top {n_codes} IPP Codes")
    ax.legend(title="Category")
    _save_or_show(fig, save_path)
    return ax


def visualise_impact_boxplots(
    df: pd.DataFrame,
    codes: list[str] | None = None,
    n_codes: int = 15,
    exclude_shared: bool = True,
    save_path: Path | None = None,
) -> plt.Axes:
    """Plot impact distribution per code as overlaid strip and boxplots."""
    df = filter_to_normalised_years(df)
    filtered = filter_for_impact_stats(df, exclude_shared=exclude_shared)
    codes = codes or filtered["code"].value_counts().head(n_codes).index.tolist()
    subset = filtered[filtered["code"].isin(codes)]
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
    code_hue = (
        subset["code"].isin(DOC_CODES).map({True: "Doc code", False: "Other code"})
    )
    sns.boxplot(
        data=subset,
        y="code",
        x="impact_normalised",
        order=order,
        hue=code_hue,
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
        hue=code_hue,
        dodge=False,
        palette=CODE_TYPE_PALETTE,
        ax=ax,
        orient="h",
        alpha=0.5,
        size=4,
        jitter=True,
        legend=True,
    )
    ax.set_xlabel("Impact")
    ax.set_title("Impact Distribution per Code")
    ax.legend(title="Category")
    _save_or_show(fig, save_path)
    return ax


def visualise_shared_vs_individual_impact(
    df: pd.DataFrame,
    n_codes: int = 15,
    save_path: Path | None = None,
) -> plt.Axes:
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

    melted = combined.reset_index().melt(
        id_vars="code",
        value_vars=["excl_shared", "incl_shared"],
        var_name="Penalty scope",
        value_name="impact_normalised",
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
        hue=melted["Penalty scope"].map(
            {"excl_shared": "Excluding shared", "incl_shared": "Including shared"}
        ),
        s=60,
        zorder=3,
        ax=ax,
    )
    ax.set_xlabel("Mean Impact")
    ax.set_title("Shared vs Individual Impact Comparison")
    ax.legend(title="Penalty scope")
    _save_or_show(fig, save_path)
    return ax


# --- CODE TRENDS ---


def visualise_code_usage_trends(
    df: pd.DataFrame,
    codes: list[str] | None = None,
    n_codes: int = 8,
    proj: pd.DataFrame | None = None,
    save_path: Path | None = None,
) -> sns.FacetGrid:
    """
    Plot the fraction of projects that received each code per year.
    The shaded area around each line shows the 95% confidence interval.
    """
    proj = _ensure_proj(df, proj)
    codes = codes or df["code"].value_counts().head(n_codes).index.tolist()

    # one binary column per code, then melt to long form for relplot
    binary = pd.DataFrame(
        {code: proj["codes_list"].map(lambda cl: code in cl) for code in codes}
    )
    binary["year"] = proj["year"]
    binary["id"] = proj["id"]

    melted = binary.melt(
        id_vars=["id", "year"],
        value_vars=codes,
        var_name="code",
        value_name="has_code",
    )
    g = sns.relplot(
        data=melted,
        x="year",
        y="has_code",
        col="code",
        hue=melted["code"].isin(DOC_CODES).map({True: "Doc code", False: "Other code"}),
        palette=CODE_TYPE_PALETTE,
        col_wrap=4,
        kind="line",
        errorbar=("ci", 95),
        marker="o",
        height=3,
        aspect=1.3,
    )
    g.set_titles("{col_name}")
    g.set_axis_labels("Year", "Fraction of projects")
    g.tick_params(axis="x", rotation=45)
    g.figure.suptitle(
        "Code usage over time\n(shaded area shows the 95% confidence interval)",
        y=1.05,
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
    subset = filtered[filtered["code"].isin(codes)]

    g = sns.relplot(
        data=subset,
        x="year",
        y="impact_normalised",
        col="code",
        hue=subset["code"].isin(DOC_CODES).map({True: "Doc code", False: "Other code"}),
        palette=CODE_TYPE_PALETTE,
        col_wrap=4,
        kind="line",
        errorbar=("ci", 95),
        marker="o",
        height=3,
        aspect=1.3,
    )
    g.set_titles("{col_name}")
    g.set_axis_labels("Year", "Mean penalty")
    g.tick_params(axis="x", rotation=45)
    g.figure.suptitle(
        "Penalty severity over time\n(shaded area shows the 95% confidence interval)",
        y=1.05,
    )
    _save_or_show(g.figure, save_path)
    return g


# --- CODE RELATIONSHIPS ---


def visualise_code_cooccurrence(
    df: pd.DataFrame,
    n_codes: int = 15,
    proj: pd.DataFrame | None = None,
    save_path: Path | None = None,
) -> sns.matrix.ClusterGrid:
    """Hierarchical clustering to group similar codes."""
    proj = _ensure_proj(df, proj)
    codes = df["code"].value_counts().head(n_codes).index.tolist()

    binary = pd.DataFrame(
        {code: proj["codes_list"].map(lambda cl: code in cl) for code in codes}
    )

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
    df: pd.DataFrame,
    n_codes: int = 20,
    proj: pd.DataFrame | None = None,
    save_path: Path | None = None,
) -> plt.Axes:
    """
    Correlation between code presence and documentation score (% of the maximum),
    normalised to remove cross year/variant max point differences.
    """
    proj = _ensure_proj(df, proj).dropna(subset=["doc_score_pct"])
    codes = df["code"].value_counts().head(n_codes).index.tolist()

    binary = pd.DataFrame(
        {code: proj["codes_list"].map(lambda cl: code in cl) for code in codes}
    )

    correlations = binary.corrwith(proj["doc_score_pct"]).sort_values(
        key=abs, ascending=True
    )

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_W), layout="constrained")
    sns.barplot(
        x=correlations.values,
        y=correlations.index,
        hue=pd.Series(correlations.index)
        .isin(DOC_CODES)
        .map({True: "Doc code", False: "Other code"}),
        palette=CODE_TYPE_PALETTE,
        dodge=False,
        ax=ax,
    )

    ax.set_xlabel("Correlation with Documentation Score")
    ax.set_ylabel("Codes")
    ax.set_title("Impact on Documentation Score")
    ax.legend(title="Category", loc="upper right")
    _save_or_show(fig, save_path)
    return ax


# --- COMMENT ANALYSIS ---


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
) -> plt.Axes:
    """
    Plot the distribution of comment lengths.
    Expects the pre-computed output of `analyse_comment_length`.
    """
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(data=comment_length_df, x="comment_len", binwidth=5, ax=ax)
    ax.set_xlim(0, comment_length_df["comment_len"].quantile(0.99))
    ax.set_xlabel("Comment Length (characters)")
    ax.set_title("Distribution of Comment Lengths")
    _save_or_show(fig, save_path)
    return ax


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
) -> plt.Axes:
    """Bar chart of comment language totals."""
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.countplot(
        data=language_df,
        x="language",
        hue="language",
        hue_order=list(LANGUAGE_PALETTE),
        palette=LANGUAGE_PALETTE,
        legend=False,
        ax=ax,
    )
    ax.set_title("Comment Language (Overall)")
    _save_or_show(fig, save_path)
    return ax


def visualise_language_distribution_by_year(
    language_df: pd.DataFrame, save_path: Path | None = None
) -> plt.Axes:
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
    ax.set_title("Comment Language (by Year)")
    ax.set_ylabel("Proportion")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.tick_params(axis="x", rotation=45)
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


# --- INPUT DATA ---


def summarise_token_limits(token_df: pd.DataFrame) -> None:
    """Print statistics about token length distribution."""
    if token_df.empty:
        print("No tokens processed. Please check if the datasets exist.")
        return

    p95 = token_df["tokens"].quantile(0.95)
    print(f"95th Percentile Token Length: {int(p95)} tokens")
    print(f"Max Token Length: {token_df['tokens'].max()}")
    print("Llama3 Context Limit: 4096 tokens")
    print("GPT-4 Context Limit: 8192 tokens")


def visualise_token_limits(
    token_df: pd.DataFrame, save_path: Path | None = None
) -> plt.Axes:
    """Plot the distribution of document token lengths."""
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H), layout="constrained")
    sns.histplot(
        data=token_df,
        x="tokens",
        hue="format",
        multiple="stack",
        bins=30,
        ax=ax,
    )

    llama3_limit = 4096
    gpt4_limit = 8192
    palette = sns.color_palette("deep")

    ax.axvline(
        llama3_limit,
        color=palette[3],
        linestyle="--",
        label=f"LLaMA3 Limit ({llama3_limit})",
    )
    ax.axvline(
        gpt4_limit,
        color=palette[2],
        linestyle="--",
        label=f"GPT-4 Limit ({gpt4_limit})",
    )

    ax.set_title("Token Length Distribution for Sampled Documents")
    ax.set_xlabel("Token Count (cl100k_base)")
    ax.set_ylabel("Number of Documents")

    _seaborn_legend = ax.get_legend()
    _seaborn_legend.remove()

    format_handles = _seaborn_legend.legend_handles
    format_labels = [t.get_text() for t in _seaborn_legend.get_texts()]

    line_handles, line_labels = ax.get_legend_handles_labels()
    ax.legend(
        handles=format_handles + line_handles,
        labels=format_labels + line_labels,
        title="Format & Limits",
    )

    _save_or_show(fig, save_path)
    return ax

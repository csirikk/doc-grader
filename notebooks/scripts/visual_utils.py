"""Shared visualisation utilities for notebook scripts.

Author: Matúš Csirik
"""

import logging
from pathlib import Path
from textwrap import fill
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.ticker import MaxNLocator, PercentFormatter

if TYPE_CHECKING:
    import pandas as pd
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

_FIG_W: int = 10  # Default width for notebook charts.
_FIG_H: int = 6  # Default height for notebook charts.
_FIG_H_PER_ITEM: float = 0.4  # Scale list-chart height with category count.

_DEEP_PALETTE = sns.color_palette("deep")

REFERENCE_LINE_COLOR = "gray"
REFERENCE_LINE_STYLE = "--"
REFERENCE_LINE_WIDTH = 1.0
REFERENCE_LINE_ALPHA = 0.5

CODE_TYPE_PALETTE: dict[str, tuple] = {
    "Doc code": _DEEP_PALETTE[2],  # green
    "Other code": _DEEP_PALETTE[7],  # gray
}
TASK_VARIANT_PALETTE: dict[str, tuple] = {
    "php": _DEEP_PALETTE[0],  # blue
    "py": _DEEP_PALETTE[1],  # orange
    "par": sns.color_palette(["#2A9D8F"])[0],  # teal
    "int": sns.color_palette(["#6C5CE7"])[0],  # indigo
}
FORMAT_PALETTE: dict[str, tuple] = {
    "md": _DEEP_PALETTE[0],  # blue
    "pdf": _DEEP_PALETTE[1],  # orange
}
LANGUAGE_PALETTE: dict[str, tuple] = {
    "cs": _DEEP_PALETTE[0],  # blue
    "sk": _DEEP_PALETTE[1],  # orange
    "en": _DEEP_PALETTE[2],  # green
    "unknown": _DEEP_PALETTE[7],  # gray
}
AGREEMENT_PALETTE: dict[str, tuple] = {
    "overlap": _DEEP_PALETTE[2],  # green
    "missed": _DEEP_PALETTE[3],  # red
    "added": _DEEP_PALETTE[0],  # blue
}
METRIC_PALETTE: dict[str, tuple] = {
    "Precision": _DEEP_PALETTE[0],  # blue
    "Recall": _DEEP_PALETTE[1],  # orange
    "Normalised MAE": _DEEP_PALETTE[3],  # red
    "precision": _DEEP_PALETTE[0],  # blue
    "recall": _DEEP_PALETTE[1],  # orange
    "normalised_mae": _DEEP_PALETTE[3],  # red
}
STAGE_PALETTE: dict[str, tuple] = {
    "raw": _DEEP_PALETTE[0],  # blue
    "dismissed": _DEEP_PALETTE[3],  # red
    "adjusted": _DEEP_PALETTE[1],  # orange
    "final": _DEEP_PALETTE[2],  # green
}
EXECUTION_STAGE_PALETTE: dict[str, tuple] = {
    "parse": sns.color_palette(["#4C6A92"])[0],  # blueish
    "analysers": sns.color_palette(["#2F8F6B"])[0],  # greenish
    "judge": sns.color_palette(["#C46A4A"])[0],  # reddish
}
OPERATIONAL_METRIC_PALETTE: dict[str, tuple] = {
    "generator_cost": _DEEP_PALETTE[0],  # blue
    "judge_cost": _DEEP_PALETTE[1],  # orange
    "latency": _DEEP_PALETTE[2],  # green
}


def configure_plot_style() -> None:
    """Set a consistent plotting style for notebook visualisations.

    Uses a whitegrid theme and the deep colour palette to keep charts
    visually consistent across scripts.
    """

    sns.set_theme(style="whitegrid", context="notebook", palette="deep")
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["savefig.bbox"] = "tight"
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["savefig.transparent"] = False


def _save_or_show(
    fig: Figure,
    save_path: Path | list[Path] | tuple[Path, ...] | None,
) -> None:
    """Save the figure and manage display/memory automatically."""
    paths = [save_path] if isinstance(save_path, Path) else (save_path or [])

    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path)
        logger.info("Saved figure to %s", path)

    if not paths or plt.isinteractive():
        plt.show()

    plt.close(fig)


def build_figure_path(stem: str, out_dir: Path) -> Path:
    return out_dir / f"{stem}.pdf"


def _validate_data(
    df: pd.DataFrame, required_cols: list[str], func_name: str
) -> pd.DataFrame | None:
    """Validate that the DataFrame contains the required columns and is not empty."""
    missing = set(required_cols) - set(df.columns)
    if missing:
        logger.warning("Columns %s absent, skipping %s", missing, func_name)
        return None

    valid_df = df.dropna(subset=required_cols)
    if valid_df.empty:
        logger.warning("No valid data for %s, skipping %s", required_cols, func_name)
        return None

    return valid_df


def render_plot(
    plot_func,
    data: pd.DataFrame,
    title: str,
    xlabel: str,
    ylabel: str,
    save_path: Path | None = None,
    figsize: tuple = (_FIG_W, _FIG_H),
    x_pct: bool = False,
    y_pct: bool = False,
    x_int: bool = False,
    y_int: bool = False,
    **sns_kwargs,
) -> Axes:
    """Render a seaborn plot with consistent formatting and optional saving."""
    fig, ax = plt.subplots(figsize=figsize, layout="constrained")

    plot_func(data=data, ax=ax, **sns_kwargs)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    if x_pct:
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    if y_pct:
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    if x_int:
        set_integer_count_ticks(ax, axis="x")
    if y_int:
        set_integer_count_ticks(ax, axis="y")

    _save_or_show(fig, save_path)
    return ax


def _expand_per_axis(value, count: int) -> list:
    """Repeat a scalar value or validate per-axis sequences."""
    if isinstance(value, (list, tuple)):
        if len(value) != count:
            raise ValueError(f"Expected {count} values, got {len(value)}")
        return list(value)
    return [value] * count


def format_facet_grid(
    grid_or_axes,
    xlabel: str | list[str] | tuple[str, ...] | None = None,
    ylabel: str | list[str] | tuple[str, ...] | None = None,
    titles: str | list[str] | tuple[str, ...] | None = None,
    suptitle: str | None = None,
    suptitle_y: float | None = None,
    x_pct: bool | list[bool] | tuple[bool, ...] = False,
    y_pct: bool | list[bool] | tuple[bool, ...] = False,
    x_int: bool | list[bool] | tuple[bool, ...] = False,
    y_int: bool | list[bool] | tuple[bool, ...] = False,
    x_rotation: float | None = None,
    y_rotation: float | None = None,
) -> None:
    """Apply shared formatting to a FacetGrid or a collection of axes."""
    axes_source = getattr(grid_or_axes, "axes", grid_or_axes)
    axes = np.atleast_1d(axes_source).flatten()
    axes = np.array([ax for ax in axes if ax is not None], dtype=object)
    if axes.size == 0:
        return

    is_grid = hasattr(grid_or_axes, "set_axis_labels") and hasattr(
        grid_or_axes, "set_titles"
    )

    if is_grid and isinstance(xlabel, str) and isinstance(ylabel, str):
        grid_or_axes.set_axis_labels(xlabel, ylabel)
    else:
        for ax, x_label, y_label in zip(
            axes,
            _expand_per_axis(xlabel, len(axes)),
            _expand_per_axis(ylabel, len(axes)),
        ):
            if x_label is not None:
                ax.set_xlabel(x_label)
            if y_label is not None:
                ax.set_ylabel(y_label)

    if is_grid and isinstance(titles, str):
        grid_or_axes.set_titles(titles)
    elif titles is not None:
        for ax, title in zip(axes, _expand_per_axis(titles, len(axes))):
            if title is not None:
                ax.set_title(title)

    for ax, use_x_pct, use_y_pct, use_x_int, use_y_int in zip(
        axes,
        _expand_per_axis(x_pct, len(axes)),
        _expand_per_axis(y_pct, len(axes)),
        _expand_per_axis(x_int, len(axes)),
        _expand_per_axis(y_int, len(axes)),
    ):
        if use_x_pct:
            ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        if use_y_pct:
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        if use_x_int:
            set_integer_count_ticks(ax, axis="x")
        if use_y_int:
            set_integer_count_ticks(ax, axis="y")
        if x_rotation is not None:
            ax.tick_params(axis="x", rotation=x_rotation)
        if y_rotation is not None:
            ax.tick_params(axis="y", rotation=y_rotation)

    if suptitle is not None:
        figure = getattr(grid_or_axes, "figure", axes[0].figure)
        if suptitle_y is None:
            figure.suptitle(suptitle)
        else:
            figure.suptitle(suptitle, y=suptitle_y)


def add_identity_reference_line(
    ax: Axes,
    label: str = "Identity (y = x)",
):
    return ax.axline(
        (0, 0),
        slope=1,
        color=REFERENCE_LINE_COLOR,
        linestyle=REFERENCE_LINE_STYLE,
        linewidth=REFERENCE_LINE_WIDTH,
        alpha=REFERENCE_LINE_ALPHA,
        label=label,
        zorder=1,
    )


def add_vertical_reference_line(ax: Axes, x: float, label: str, zorder: int = 1):
    return ax.axvline(
        x=x,
        color=REFERENCE_LINE_COLOR,
        linestyle=REFERENCE_LINE_STYLE,
        linewidth=REFERENCE_LINE_WIDTH,
        alpha=REFERENCE_LINE_ALPHA,
        label=label,
        zorder=zorder,
    )


def add_horizontal_reference_line(ax: Axes, y: float, label: str, zorder: int = 1):
    return ax.axhline(
        y=y,
        color=REFERENCE_LINE_COLOR,
        linestyle=REFERENCE_LINE_STYLE,
        linewidth=REFERENCE_LINE_WIDTH,
        alpha=REFERENCE_LINE_ALPHA,
        label=label,
        zorder=zorder,
    )


def set_integer_count_ticks(
    ax: Axes,
    axis: str,
    nbins: int = 10,
) -> None:
    """Configure the axis to show integer ticks suitable for count data."""
    if axis not in {"x", "y"}:
        raise ValueError("axis must be 'x' or 'y'")

    axis_obj = ax.xaxis if axis == "x" else ax.yaxis
    axis_obj.set_major_locator(
        MaxNLocator(nbins=nbins, integer=True, steps=[1, 2, 5, 10])
    )


def _wrap_category_label(label: str, width: int) -> str:
    """Wrap long categorical labels."""
    clean_label = " ".join(str(label).split())
    if not clean_label:
        return clean_label
    if " + " in clean_label:
        return clean_label.replace(" + ", "\n+ ")
    return fill(
        clean_label,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )


def wrap_category_tick_labels(
    ax: Axes,
    axis: str = "x",
    width: int = 16,
    rotation: float = 0.0,
    ha: str | None = None,
) -> None:
    """Wrap categorical tick labels for dense charts with long names."""
    if axis not in {"x", "y"}:
        raise ValueError("axis must be 'x' or 'y'")

    if ha is None:
        ha = "center" if axis == "x" else "right"

    if axis == "x":
        ticks = ax.get_xticks()
        labels = [
            _wrap_category_label(tick.get_text(), width)
            for tick in ax.get_xticklabels()
        ]
        ax.set_xticks(ticks, labels=labels, rotation=rotation, ha=ha)
    else:
        ticks = ax.get_yticks()
        labels = [
            _wrap_category_label(tick.get_text(), width)
            for tick in ax.get_yticklabels()
        ]
        ax.set_yticks(ticks, labels=labels, rotation=rotation, ha=ha)


def move_legend_if_present(ax: Axes, title: str, loc: str = "best") -> None:
    """Reposition an existing seaborn legend while preserving semantic entries."""
    if ax.get_legend() is not None:
        sns.move_legend(ax, loc, title=title)

"""Shared visualisation utilities for notebook scripts."""

import logging
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import MaxNLocator, MultipleLocator

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

_FIG_W: int = 10  # standard width
_FIG_H: int = 6  # standard height
_FIG_H_PER_ITEM: float = 0.4  # height per row for list charts

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
STAGE_PALETTE: dict[str, tuple] = {
    "raw": _DEEP_PALETTE[0],  # blue
    "dismissed": _DEEP_PALETTE[3],  # red
    "adjusted": _DEEP_PALETTE[1],  # orange
    "final": _DEEP_PALETTE[2],  # green
}


def configure_plot_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook", palette="deep")


def _save_or_show(fig: Figure, save_path: Path | None) -> None:
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        logger.info("Saved figure to %s", save_path)
        plt.close(fig)
    else:
        plt.show()


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


def add_identity_reference_line(
    ax: Axes,
    lo: float,
    hi: float,
    label: str = "Identity (y = x)",
):
    return ax.plot(
        [lo, hi],
        [lo, hi],
        color=REFERENCE_LINE_COLOR,
        linestyle=REFERENCE_LINE_STYLE,
        linewidth=REFERENCE_LINE_WIDTH,
        alpha=REFERENCE_LINE_ALPHA,
        label=label,
        zorder=1,
    )[0]


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
    unit_step_max_span: float = 20.0,
    nbins: int = 10,
) -> None:
    """Keep count axes integer while avoiding dense one-step tick striping."""
    if axis not in {"x", "y"}:
        raise ValueError("axis must be 'x' or 'y'")

    axis_obj = ax.xaxis if axis == "x" else ax.yaxis
    lo, hi = ax.get_xlim() if axis == "x" else ax.get_ylim()
    span = abs(hi - lo)

    if span <= unit_step_max_span:
        axis_obj.set_major_locator(MultipleLocator(1))
    else:
        axis_obj.set_major_locator(MaxNLocator(nbins=nbins, integer=True))

"""Shared visualisation utilities for notebook scripts."""

import logging
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import seaborn as sns

if TYPE_CHECKING:
    from pathlib import Path

    from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

_FIG_W: int = 10  # standard width
_FIG_H: int = 6  # standard height
_FIG_H_PER_ITEM: float = 0.4  # height per row for list charts

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
AGREEMENT_PALETTE: dict[str, tuple] = {
    "overlap": sns.color_palette("deep")[2],  # green
    "missed": sns.color_palette("deep")[3],  # red
    "added": sns.color_palette("deep")[0],  # blue
}
STAGE_PALETTE: dict[str, tuple] = {
    "raw": sns.color_palette("deep")[0],  # blue
    "dismissed": sns.color_palette("deep")[3],  # red
    "adjusted": sns.color_palette("deep")[1],  # orange
    "final": sns.color_palette("deep")[2],  # green
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

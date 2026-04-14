"""Compute per-code severity weights from the historical IPP assessment dataset.

Reads data/clean_ipp_data.csv, applies the same impact normalisation used by
analysis.py, and calculates the absolute median normalised impact for each code.
The function `compute_weights` returns a mapping of ac_code to weight where
1.0 corresponds to losing the full documentation budget.

This module is intended to be imported and used from a notebook; it no longer
provides a CLI entrypoint.
"""

from pathlib import Path

import numpy as np

from .analysis import (
    filter_for_impact_stats,
    filter_to_normalised_years,
    load_clean_data,
)


def compute_weights(data_path: Path) -> dict[str, float]:
    """Return a dict mapping ac_code to abs(median normalised impact).

    Only rows that:
    - belong to a year/variant with a known documentation point maximum
    - have a non-null numeric impact value
    - are not shared across multiple codes (exclude_shared=True)
    are used.  The result is clamped to [0.0, 1.0].
    """
    df = load_clean_data(data_path)
    df = filter_to_normalised_years(df)
    df = filter_for_impact_stats(df, exclude_shared=True)

    medians = df.groupby("code")["impact_normalised"].median().dropna()

    weights: dict[str, float] = {}
    for code, med in medians.items():
        w = float(np.abs(med))
        weights[str(code)] = round(min(max(w, 0.0), 1.0), 6)

    return dict(sorted(weights.items(), key=lambda kv: kv[1], reverse=True))

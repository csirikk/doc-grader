"""Compute per-code severity weights from the IPP dataset.

Author: Matúš Csirik
"""

import json
import logging
from pathlib import Path

from doc_grader.utils import log_json, write_json

from .constants import DOC_CODES, LEGACY_TO_CANONICAL
from .dataset_analysis import (
    filter_for_impact_stats,
    filter_to_normalised_years,
    load_clean_data,
)
from .dataset_parser import normalise_code_alias


def compute_weights(
    data_path: Path | None = None,
    write_path: Path | None = None,
    rulebook_path: Path | None = None,
) -> dict[str, float]:
    """Compute canonical severity weights from historical dataset.

    Args:
        data_path: Optional path to the cleaned dataset CSV. If omitted a
            default location is used.
        write_path: Optional path to write the computed JSON weights.
        rulebook_path: Optional path to the rulebook JSON used to filter codes.

    Returns:
        Mapping of canonical AC codes to inferred severity weights.
    """
    logger = logging.getLogger(__name__)

    df = load_clean_data(data_path)
    df = filter_to_normalised_years(df)
    df = filter_for_impact_stats(df, exclude_shared=True)

    df["code"] = df["code"].astype(str).apply(lambda s: normalise_code_alias(s.strip()))
    legacy_codes = {str(c) for c in DOC_CODES}
    df = df[df["code"].isin(legacy_codes)]

    if rulebook_path is None:
        rulebook_path = (
            Path(__file__).resolve().parent.parent.parent / "config" / "rulebook.json"
        )
    try:
        with rulebook_path.open(encoding="utf-8") as fh:
            rulebook = json.load(fh)
    except Exception:
        rulebook = {"rules": []}

    allowed_rulebook_codes = set()
    for r in rulebook.get("rules", []):
        if r.get("course") == "ifj":
            continue
        for c in [r.get("ac_code")] if r.get("ac_code") else []:
            allowed_rulebook_codes.add(str(c))

    # Map each event to its canonical code and compute canonical medians from
    # event-level absolute normalised impacts.
    df = df.assign(impact_normalised_abs=lambda d: d["impact_normalised"].abs())
    df["canon"] = df["code"].apply(lambda c: LEGACY_TO_CANONICAL.get(str(c), str(c)))
    df_mapped = df[df["canon"].isin(allowed_rulebook_codes)]

    canonical_medians = (
        df_mapped.groupby("canon")["impact_normalised_abs"].median().dropna()
    )

    weights: dict[str, float] = {}
    for canon, med in canonical_medians.items():
        w = float(med)
        weights[str(canon)] = round(min(max(w, 0.0), 1.0), 6)

    # Infer reasonable values for non-legacy canonical codes when possible.
    non_legacy_codes = set()
    try:
        for r in rulebook.get("rules", []):
            if r.get("is_legacy", False):
                continue
            for c in [r.get("ac_code")] if r.get("ac_code") else []:
                if str(c) in allowed_rulebook_codes:
                    non_legacy_codes.add(str(c))
    except Exception:
        logger.debug(
            "Could not derive non-legacy codes from rulebook: %s", rulebook_path
        )
    missing_non_legacy = sorted([c for c in non_legacy_codes if c not in weights])
    SIMILARITY_MAP = {  # manually curated based on code descriptions
        "AI": ["CITE", "JAK", "CONTENT"],
        "CITE": ["COPY", "CONTENT"],
        "COVER": ["FORMAT", "SAZBA", "MISSING"],
        "DS": ["JAK", "IR", "DP"],
        "FLUFF": ["SHORT", "STYLE"],
        "NOSRP": ["OOP", "STRUCT", "DP"],
        "SEMUML": ["NOUML", "BADUML"],
    }

    for code in missing_non_legacy:
        candidates = SIMILARITY_MAP.get(code, [])
        candidate_vals = [weights[c] for c in candidates if c in weights]
        if not candidate_vals:
            logger.info("No candidate weights for %s; skipping inference", code)
            continue
        inferred = float(sum(candidate_vals) / len(candidate_vals))
        logger.info("Inferred weight for %s from %s to %s", code, candidates, inferred)
        weights[str(code)] = round(min(max(float(inferred), 0.0), 1.0), 6)

    # Final safety: keep only codes present in the rulebook (allowed canonical codes).
    weights = {k: v for k, v in weights.items() if k in allowed_rulebook_codes}

    ordered = dict(sorted(weights.items(), key=lambda kv: kv[1], reverse=True))

    if write_path is not None:
        try:
            p = Path(write_path)
            write_json(p, ordered)
            log_json(logger, "severity_weights", ordered)
            logger.info("Wrote computed severity weights to %s", p)
        except Exception:
            logger.exception("Failed to write weights to %s", write_path)

    return ordered

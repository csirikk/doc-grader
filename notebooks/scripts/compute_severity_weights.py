"""Compute per-code severity weights from the IPP dataset."""

import json
import logging
from pathlib import Path

from doc_grader.utils import log_json, write_json
from notebooks.scripts.analysis import (
    filter_for_impact_stats,
    filter_to_normalised_years,
    load_clean_data,
)
from notebooks.scripts.dataset_parser import DOC_CODES


def compute_weights(
    data_path: Path | None = None,
    write_path: Path | None = None,
) -> dict[str, float]:
    """Compute canonical severity weights."""
    logger = logging.getLogger(__name__)

    df = load_clean_data(data_path)
    df = filter_to_normalised_years(df)
    df = filter_for_impact_stats(df, exclude_shared=True)

    medians = df.groupby("code")["impact_normalised"].median().dropna()
    medians = medians[medians.index.isin(map(str, DOC_CODES))]

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
        for c in r.get("ac_codes") or []:
            allowed_rulebook_codes.add(str(c))

    LEGACY_TO_CANONICAL = {
        "BLOK": "SAZBA",
        "DOCTYPE": "SAZBA",
        "DP": "BADDP",
        "EX": "EXT",
        "FORM": "SAZBA",
        "FORMAT": "SAZBA",
        "HOW": "HOV",
        "MDLINES": "SAZBA",
        "MEZ": "SAZBA",
        "MISSING": "STRUCT",
        "NV": "BADDP",
        "NVPDOC": "EXT",
        "OK": "ICH",
        "OOP": "NOOOP",
        "PRED": "SAZBA",
        "SINGLETON": "NOSRP",
        "SPACETAB": "SAZBA",
        "UML": "NOUML",
        "WHY": "JAK",
    }

    # Aggregate medians from legacy codes into canonical codes.
    aggregated: dict[str, list[float]] = {}
    for code, med in medians.items():
        code_str = str(code)
        canon = LEGACY_TO_CANONICAL.get(code_str, code_str)
        if canon not in allowed_rulebook_codes:
            continue
        aggregated.setdefault(canon, []).append(float(abs(med)))

    # Compute weights as the mean of aggregated absolute medians.
    weights: dict[str, float] = {}
    for canon, vals in aggregated.items():
        if not vals:
            continue
        w = float(sum(vals) / len(vals))
        weights[str(canon)] = round(min(max(w, 0.0), 1.0), 6)

    # Infer reasonable values for non-legacy canonical codes when possible.
    non_legacy_codes = set()
    try:
        for r in rulebook.get("rules", []):
            if r.get("is_legacy", False):
                continue
            for c in r.get("ac_codes", []) or []:
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

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas.finding import Finding

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_THRESHOLD: float = 0.80


class RuleEngine:
    def __init__(self, *, high_confidence_threshold: float | None = None):
        self.high_confidence_threshold = (
            high_confidence_threshold
            if high_confidence_threshold is not None
            else HIGH_CONFIDENCE_THRESHOLD
        )

    def process(self, findings: list[Finding]) -> tuple[list[Finding], dict]:
        """Filter and normalise findings. Returns (final_findings, summary_dict).

        - dismissed: dropped (judge vetoed).
        - approved: kept unconditionally (judge validated).
        - proposed: kept only if confidence >= high_confidence_threshold.
        - duplicates: de-duplicated by finding_id.
        """
        final: list[Finding] = []
        seen_ids: set[str] = set()
        dropped_dismissed = 0
        dropped_low_conf = 0
        dropped_dupe = 0

        for f in findings:
            if f.status == "dismissed":
                dropped_dismissed += 1
                logger.debug("RuleEngine: dropped dismissed finding '%s'", f.finding_id)
                continue

            if (
                f.status == "proposed"
                and f.confidence is not None
                and f.confidence < self.high_confidence_threshold
            ):
                dropped_low_conf += 1
                logger.debug(
                    "Dropped low-confidence proposed finding '%s' (%.2f)",
                    f.finding_id,
                    f.confidence,
                )
                continue

            if f.finding_id in seen_ids:
                dropped_dupe += 1
                logger.debug("Dropped duplicate finding '%s'", f.finding_id)
                continue

            seen_ids.add(f.finding_id)
            final.append(f)

        summary = {
            "rule_engine": {
                "high_conf_threshold": self.high_confidence_threshold,
                "dropped": {
                    "dismissed_by_judge": dropped_dismissed,
                    "low_confidence_proposed": dropped_low_conf,
                    "duplicates": dropped_dupe,
                },
                "final_count": len(final),
            }
        }

        logger.info(
            "RuleEngine: %d findings in %d final (dismissed=%d, low-conf=%d, dupes=%d)",
            len(findings),
            len(final),
            dropped_dismissed,
            dropped_low_conf,
            dropped_dupe,
        )

        return final, summary

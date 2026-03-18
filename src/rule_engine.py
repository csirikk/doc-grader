"""Rule engine for post-processing analyser findings.

1. Aggregate findings from multiple analysers.
2. Apply normalization / filtering rules:
    - Drop findings with status == 'dismissed' (Judge vetoed them).
    - For 'approved' findings, keep unconditionally (Judge already validated).
    - For 'proposed' findings (never reached the Judge), threshold by confidence score.
    - De-duplicate by finding_id.

Future extensions?
    - Severity normalization
    - Tag-based grouping and merging
    - Impact score computation & grade suggestion
    - Configurable rule sets loaded from JSON / YAML
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .schemas.finding import Finding

HIGH_CONFIDENCE_THRESHOLD: float = 0.80


class RuleEngine:
    def __init__(self, *, high_confidence_threshold: float | None = None):
        self.high_confidence_threshold = (
            high_confidence_threshold
            if high_confidence_threshold is not None
            else HIGH_CONFIDENCE_THRESHOLD
        )

    def process(self, batches: Iterable[list[Finding]]) -> tuple[list[Finding], dict]:
        """
        Aggregate and normalize findings. Returns (filtered_findings, summary_dict).
        """
        aggregated: list[Finding] = []
        seen_ids: set[str] = set()
        dropped_dismissed: int = 0
        dropped_low_conf: int = 0
        dropped_dupe: int = 0

        for seq in batches:
            for f in seq:
                if f.status == "dismissed":
                    dropped_dismissed += 1
                    continue

                if (
                    f.status == "proposed"
                    and f.confidence is not None
                    and f.confidence < self.high_confidence_threshold
                ):
                    dropped_low_conf += 1
                    continue

                # De-duplication by finding_id
                if f.finding_id in seen_ids:
                    dropped_dupe += 1
                    continue
                seen_ids.add(f.finding_id)
                aggregated.append(f)

        summary = {
            "rule_engine": {
                "high_conf_threshold": self.high_confidence_threshold,
                "dropped": {
                    "dismissed_by_judge": dropped_dismissed,
                    "low_confidence_proposed": dropped_low_conf,
                    "duplicates": dropped_dupe,
                },
                "final_count": len(aggregated),
            }
        }

        return aggregated, summary

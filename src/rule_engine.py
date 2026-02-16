"""Rule engine for post-processing analyser findings.

1. Aggregate findings from multiple analysers.
2. Apply simple normalization / filtering rules.
   - Keep only findings with confidence >= HIGH_CONFIDENCE_THRESHOLD when a confidence value is present.
   - If a finding has no confidence specified, keep it for now
3. De-duplicate identical finding_ids

Future extensions?
 - Severity normalization
 - Tag-based grouping and merging
 - Impact score computation & grade suggestion
 - Configurable rule sets loaded from JSON / YAML
"""

from typing import Dict, Iterable, List, Set

from .schemas.finding import Finding

HIGH_CONFIDENCE_THRESHOLD: float = 0.80


class RuleEngine:
    def __init__(self, *, high_confidence_threshold: float | None = None):
        self.high_confidence_threshold = (
            high_confidence_threshold
            if high_confidence_threshold is not None
            else HIGH_CONFIDENCE_THRESHOLD
        )

    def process(self, batches: Iterable[List[Finding]]) -> tuple[List[Finding], Dict]:
        """Aggregate and normalize findings. Returns (filtered_findings, summary_dict)."""
        aggregated: List[Finding] = []
        seen_ids: Set[str] = set()
        dropped_low_conf: int = 0
        dropped_dupe: int = 0

        for seq in batches:
            for f in seq:
                # Confidence filter
                if (
                    f.confidence is not None
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
                    "low_confidence": dropped_low_conf,
                    "duplicates": dropped_dupe,
                },
                "final_count": len(aggregated),
            }
        }

        return aggregated, summary

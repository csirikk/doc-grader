from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas.finding import Finding
    from .schemas.llm import JudgeModelResponse

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_THRESHOLD: float = 0.80
JUDGE_MIN_CONFIDENCE: float = 0.10


class RuleEngine:
    def __init__(self, *, high_confidence_threshold: float | None = None):
        self.high_confidence_threshold = (
            high_confidence_threshold
            if high_confidence_threshold is not None
            else HIGH_CONFIDENCE_THRESHOLD
        )

    def prepare_judge_batch(self, findings: list[Finding]) -> list[Finding]:
        """Select findings that should be sent to the judge model."""
        to_judge: list[Finding] = []

        for finding in findings:
            if finding.status == "approved":
                continue

            if finding.confidence is None:
                finding.status = "approved"
                continue

            if not finding.anchors:
                logger.warning(
                    "Dismissing finding '%s' (%s): no anchors",
                    finding.finding_id,
                    finding.ac_code,
                )
                finding.status = "dismissed"
                continue

            if finding.confidence < JUDGE_MIN_CONFIDENCE:
                logger.debug(
                    ("Dismissing finding '%s' (%s): confidence %.2f below threshold"),
                    finding.finding_id,
                    finding.ac_code,
                    finding.confidence,
                )
                finding.status = "dismissed"
                continue

            to_judge.append(finding)

        if not to_judge:
            logger.info("No findings passed pre-judge validation.")

        return to_judge

    def apply_judge_response(
        self, findings: list[Finding], response: JudgeModelResponse
    ) -> None:
        """Apply judge verdicts to findings in-place."""
        verdict_map = {verdict.finding_id: verdict for verdict in response.verdicts}

        for finding in findings:
            verdict = verdict_map.get(finding.finding_id)
            if verdict is None:
                logger.warning(
                    ("Judge returned no verdict for '%s', leaving as 'proposed'"),
                    finding.finding_id,
                )
                continue

            if verdict.decision == "dismissed":
                finding.status = "dismissed"
            elif verdict.decision == "approved":
                finding.status = "approved"
            elif verdict.decision == "adjusted":
                finding.status = "approved"
                if verdict.adjusted_severity is not None:
                    finding.severity = verdict.adjusted_severity
                if verdict.adjusted_confidence is not None:
                    finding.confidence = verdict.adjusted_confidence

            logger.debug(
                "RuleEngine: judge verdict for '%s': %s - %s",
                finding.finding_id,
                verdict.decision,
                verdict.rationale,
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

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas.finding import Finding
    from .schemas.llm import JudgeModelResponse

logger = logging.getLogger(__name__)


class RuleEngine:
    def prepare_judge_batch(self, findings: list[Finding]) -> list[Finding]:
        """Select findings that should be sent to the judge model."""
        to_judge: list[Finding] = []

        for finding in findings:
            if finding.judge_status != "to_be_judged":
                continue

            has_anchors = bool(finding.anchors)
            has_stats = bool(finding.stats)
            has_model_evals = bool(finding.model_evals)
            if not has_anchors and not has_stats and not has_model_evals:
                logger.warning(
                    ("Skipping finding '%s' (%s): no anchors, stats, or model_evals"),
                    finding.finding_id,
                    finding.ac_code,
                )
                finding.judge_status = "not_to_be_judged"
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
                    ("Judge returned no verdict for '%s', leaving as 'to_be_judged'"),
                    finding.finding_id,
                )
                continue

            before_state = {
                "summary": finding.summary,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "snippet": finding.anchors[0].snippet if finding.anchors else None,
            }

            if verdict.decision == "dismissed":
                finding.judge_status = "judged_dismissed"
            elif verdict.decision == "approved":
                finding.judge_status = "judged_approved"
            elif verdict.decision == "adjusted":
                finding.judge_status = "judged_adjusted"
                if verdict.adjusted_severity is not None:
                    finding.severity = verdict.adjusted_severity
                if verdict.adjusted_confidence is not None:
                    finding.confidence = verdict.adjusted_confidence

            after_state = {
                "summary": finding.summary,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "snippet": finding.anchors[0].snippet if finding.anchors else None,
            }
            changed_fields = [
                key for key in before_state if before_state[key] != after_state[key]
            ]

            judge_meta: dict = {
                "decision": verdict.decision,
                "rationale": verdict.rationale,
                "reasoning_chain": response.reasoning_chain,
            }
            if changed_fields:
                judge_meta["change"] = {
                    "fields": changed_fields,
                    "before": before_state,
                    "after": after_state,
                }
            finding.meta = {**(finding.meta or {}), "judge": judge_meta}

            if verdict.decision in {"approved", "dismissed"} and not changed_fields:
                logger.info(
                    "Judge confirmed finding '%s' without content changes.",
                    finding.finding_id,
                )

            logger.debug(
                "RuleEngine: judge verdict for '%s': %s - %s",
                finding.finding_id,
                verdict.decision,
                verdict.rationale,
            )

    def process(self, findings: list[Finding]) -> tuple[list[Finding], dict]:
        """Filter and normalise findings. Returns (final_findings, summary_dict).

        - judged_dismissed: dropped (judge vetoed).
        - all other judge states: kept.
        - duplicates: de-duplicated by finding_id.
        """
        final: list[Finding] = []
        seen_ids: set[str] = set()
        dropped_dismissed = 0
        dropped_dupe = 0

        for f in findings:
            if f.judge_status == "judged_dismissed":
                dropped_dismissed += 1
                logger.debug("RuleEngine: dropped dismissed finding '%s'", f.finding_id)
                continue

            if f.finding_id in seen_ids:
                dropped_dupe += 1
                logger.debug("Dropped duplicate finding '%s'", f.finding_id)
                continue

            seen_ids.add(f.finding_id)
            final.append(f)

        summary = {
            "rule_engine": {
                "dropped": {
                    "dismissed_by_judge": dropped_dismissed,
                    "duplicates": dropped_dupe,
                },
                "final_count": len(final),
            }
        }

        logger.info(
            "RuleEngine: %d findings in %d final (dismissed=%d, dupes=%d)",
            len(findings),
            len(final),
            dropped_dismissed,
            dropped_dupe,
        )

        return final, summary

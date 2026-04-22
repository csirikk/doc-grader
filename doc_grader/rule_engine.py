"""Rule engine for post-processing findings.

Author: Matúš Csirik

This module contains the class `RuleEngine` which prepares findings for a
separate judge model, applies judge verdicts and performs final filtering
and normalisation of findings produced by analysers.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas.finding import Finding
    from .schemas.llm import JudgeModelResponse

logger = logging.getLogger(__name__)


class RuleEngine:
    """Provide utilities to prepare, apply and finalise judge decisions.

    The class methods are stateless and operate on lists of ``Finding``
    objects produced by analysers.
    """

    def prepare_judge_batch(self, findings: list[Finding]) -> list[Finding]:
        """Select findings that should be sent to the judge model.

        The method filters out findings that are not marked for judgement or
        that lack anchors, stats and model evaluations because the judge
        requires some evidence to make a reliable decision.

        Args:
            findings: Sequence of findings to evaluate.

        Returns:
            A list of findings that are valid inputs for the judge model.
        """
        to_judge: list[Finding] = []

        for finding in findings:
            if finding.judge_status != "to_be_judged":
                continue

            if not (finding.anchors or finding.stats or finding.model_evals):
                logger.info(
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
        """Apply judge verdicts to findings in-place.

        Updates each finding's ``judge_status`` and, when present, applies any
        adjusted severity, confidence, summary or snippet supplied by the
        judge response. The method also records judge metadata under
        ``finding.meta['judge']``.

        Args:
            findings: List of findings to update. Findings are mutated in place.
            response: Judge model response containing verdicts keyed by finding id.

        Returns:
            None
        """
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
                if verdict.adjusted_summary is not None:
                    finding.summary = verdict.adjusted_summary
                if verdict.adjusted_snippet is not None and finding.anchors:
                    finding.anchors[0].snippet = verdict.adjusted_snippet

            finding.judge_model = response.model_name

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

    def process(self, findings: list[Finding]) -> tuple[list[Finding], dict]:
        """Filter and normalise findings.

        The method drops findings vetoed by the judge, removes duplicate
        finding ids and returns a summary structure.

        Args:
            findings: Input list of findings to process.

        Returns:
            A tuple ``(final_findings, summary_dict)`` where ``final_findings``
            is the filtered list of findings and ``summary_dict`` contains
            counts of dropped items and the final count.
        """
        final: list[Finding] = []
        seen_ids: set[str] = set()
        dropped_dismissed = 0
        dropped_dupe = 0

        for f in findings:
            if f.judge_status == "judged_dismissed":
                dropped_dismissed += 1
                continue

            if f.finding_id in seen_ids:
                dropped_dupe += 1
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

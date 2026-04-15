"""Calibrated severity scoring for doc-grader findings.

impact = -(severity_weight * severity * max_doc_points)

- ``severity_weight`` is stored on each LLMRule in the rulebook
- ``severity`` is the violation intensity [0.0, 1.0] set by the analyser
- ``max_doc_points`` is the maximum documentation score for this run

"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas.finding import Finding
    from .schemas.llm import Rulebook

logger = logging.getLogger(__name__)


class Scorer:
    """Post-processes final findings to compute calibrated impact scores."""

    def score(
        self,
        findings: list[Finding],
        rulebook: Rulebook,
        max_doc_points: int | None = None,
    ) -> None:
        """Compute impact for each finding in-place using per-rule severity weights."""
        for finding in findings:
            rule = rulebook.rules_by_code.get(finding.ac_code)
            if rule is None:
                logger.warning(
                    "No rule for %s (%s), impact left as None.",
                    finding.finding_id,
                    finding.ac_code,
                )
                continue

            if rule.severity_weight == 0.0:
                finding.impact = 0.0
                continue

            severity = finding.severity if finding.severity is not None else 1.0
            if max_doc_points is not None:
                finding.impact = round(
                    -rule.severity_weight * severity * max_doc_points, 4
                )
            else:
                finding.impact = round(-rule.severity_weight * severity, 6)

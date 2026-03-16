"""Style analyser for checks related to writing style."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from ..schemas.llm import LLMRule
from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMEvaluation


class StyleAnalyser(BaseLLMAnalyser):
    """
    LLM checks for writing style and tone, with heuristic pre-filters.

    Implemented AC codes:
    - STYLE: Unclear or poor writing style.
    - FILO: Missing or insufficient design philosophy description (IPP only).
    - HOV: Informal, conversational, or slang language.
    """

    analyser_id: ClassVar[str] = "style_analyser"
    name: ClassVar[str] = "Style Analyser"

    def get_rules(self) -> list[LLMRule]:
        return [
            LLMRule(
                ac_code="STYLE",
                prompt_instruction="unclear or poor writing style, repetitive, or unacademic phrasing",
                analyser_id=self.analyser_id,
            ),
            LLMRule(
                ac_code="FILO",
                prompt_instruction="missing or insufficient explanation of design philosophy or architectural decisions",
                analyser_id=self.analyser_id,
            ),
            LLMRule(
                ac_code="HOV",
                prompt_instruction="informal, conversational, or slang language",
                analyser_id=self.analyser_id,
            ),
        ]

    def process_evaluations(
        self,
        doc: Document,
        evals: list[LLMEvaluation],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []

        for ev in evals:
            item = doc.text_items.get(ev.item_cref)

            findings.append(
                self._make_finding(
                    doc=doc,
                    ac_code=ev.ac_code,
                    title=f"Style issue: {ev.ac_code}",
                    summary=ev.reason,
                    evidence_item=item,
                    snippet_override=ev.snippet,
                    severity=ev.severity,
                    confidence=ev.confidence,
                )
            )

        return findings

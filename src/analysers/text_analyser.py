"""LLM-based text analyser."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from ..schemas.llm import LLMRule
from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMEvaluation

logger = logging.getLogger(__name__)


class TextAnalyser(BaseLLMAnalyser):
    analyser_id: ClassVar[str] = "text_analyser"
    name: ClassVar[str] = "Text Analyser"

    def get_rules(self) -> list[LLMRule]:
        return [
            LLMRule(
                ac_code="CH",
                prompt_instruction="spelling or grammar mistakes",
                analyser_id=self.analyser_id,
            ),
            LLMRule(
                ac_code="gram.",
                prompt_instruction="grammar mistakes in IFJ project",
                analyser_id=self.analyser_id,
            ),
            LLMRule(
                ac_code="ICH",
                prompt_instruction="first-person singular usage (e.g. 'implementoval jsem', 'popisuji', 'mine')",
                analyser_id=self.analyser_id,
            ),
            LLMRule(
                ac_code="TERM",
                prompt_instruction="incorrect or imprecise technical terminology",
                analyser_id=self.analyser_id,
            ),
            LLMRule(
                ac_code="LANG",
                prompt_instruction="language mixing (mixing Czech, Slovak, or English in the same sentence or paragraph)",
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
                    title=f"Text issue: {ev.ac_code}",
                    summary=ev.reason,
                    evidence_item=item,
                    snippet_override=ev.snippet,
                    severity=ev.severity,
                    confidence=ev.confidence,
                )
            )

        return findings

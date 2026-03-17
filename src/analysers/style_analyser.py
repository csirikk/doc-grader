"""LLM-based writing style analyser. Nuanced, subjective aim, editorial.

Responsible for AC:
- 'STYLE': Unclear or poor writing style.
- 'HOV': Informal, conversational, or slang language.

Future AC codes to consider:
- 'REPET': repetitive or redundant phrasing
  - "The algorithm is efficient. It runs in O(n) time, which is efficient."
- 'TUTORIAL': tutorial-like tone, excessive hand-holding, or over-explaining
  - "First, we will initialize the variables. Then, ..."
  - "Now, let's look at how we can implement the parser..."
- 'FLUFF': unnecessary filler that does not add meaning
- 'VUL': vulgar language
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from ..schemas.llm import LLMRule
from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMEvaluation


class StyleAnalyser(BaseLLMAnalyser):
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

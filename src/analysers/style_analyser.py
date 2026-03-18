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

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.llm import LLMRule, Rulebook


class StyleAnalyser(BaseLLMAnalyser):
    analyser_id: ClassVar[str] = "style_analyser"
    name: ClassVar[str] = "Style Analyser"

    def get_rules(
        self, rulebook: Rulebook, params: dict[str, Any] | None = None
    ) -> list[LLMRule]:
        course = params.get("course") if params else None
        return [
            r
            for r in rulebook.rules
            if r.analyser_id == self.analyser_id
            and (r.course is None or r.course == course)
        ]

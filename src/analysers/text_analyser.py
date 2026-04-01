"""LLM-based text analyser. Deterministic, objective aim, proofreading.

Responsible for AC codes:
- 'CH': Spelling or grammar mistakes in Czech text.
- 'ICH': First-person singular usage.
- 'TERM': Incorrect or imprecise technical terminology.
- 'LANG': Language mixing.

Future AC codes to consider:
- 'TODO': unresolved placeholders, todos lorem ipsum, etc.
- 'ACRO': unexplained acronyms or abbreviations
- 'CODE': unformatted code snippets

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.llm import LLMRule, Rulebook


class TextAnalyser(BaseLLMAnalyser):
    analyser_id: ClassVar[str] = "text_analyser"
    name: ClassVar[str] = "Text Analyser"

    def get_rules(
        self, rulebook: Rulebook, params: dict[str, Any] | None = None
    ) -> list[LLMRule]:
        rules = super().get_rules(rulebook, params=params)
        language = params.get("language") if params else None
        if language == "cs":
            return rules
        return [rule for rule in rules if "CH" not in rule.ac_codes]

"""LLM-based content analyser. All prose-based LLM grading.

Author: Matúš Csirik

Responsible for AC:
- 'CH': Combined spelling or grammar mistakes when the rulebook does not split them.
- 'SPELLING': Spelling mistakes in Czech or Slovak text.
- 'GRAMMAR': Grammar or punctuation mistakes in Czech or Slovak text.
- 'ICH': First-person singular usage.
- 'TERM': Incorrect or imprecise technical terminology.
- 'LANG': Language mixing.
- 'STYLE': Unclear or poor writing style.
- 'HOV': Informal, conversational, or slang language.
- 'CONTENT': Sections off-topic, such as subjective feelings or time spent.
- 'SA': Insufficient syntax analysis description.
- 'SAV': Insufficient syntax analysis of expressions description.
- 'SeA': Insufficient semantic analysis description.
- 'PSA': Insufficient precedence syntax analysis description.
- 'TS': Insufficient symbol table description.
- 'GK': Insufficient code generation description.
- 'IR': Insufficient internal representation description.
- 'JAK': Insufficient implementation description.
- 'RP': Insufficient division of work section.
- 'NVPDOC': Missing or insufficient NVP extension document.
- 'OOP': Meaningful and well-described object-oriented programming usage.
- 'NOOOP': Code ignores OOP principles and merely wraps functions in classes.
- 'NOSRP': Violation of the Single Responsibility Principle.
- 'DP': Good and well-justified design pattern usage.
- 'BADDP': Inappropriate use or bad implementation of a design pattern.
- 'SINGLETON': Use of the Singleton pattern, explicitly disallowed for NVP.
- 'EXT': Insufficient extensibility or modularity description.
- 'EX': Particularly clean exception usage and error handling.
- 'FILO': Missing or insufficient design philosophy description.
"""

from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.llm import LLMRule, Rulebook


class ContentAnalyser(BaseLLMAnalyser):
    """LLM-based analyser for content- and prose-based rubric criteria."""

    analyser_id: ClassVar[str] = "content_analyser"
    name: ClassVar[str] = "Content Analyser"

    def get_rules(
        self, rulebook: Rulebook, params: dict[str, Any] | None = None
    ) -> list[LLMRule]:
        params = params or {}
        rules = super().get_rules(rulebook, params=params)
        language = params.get("language")
        grammar_codes = {"CH", "SPELLING", "GRAMMAR"}
        if language not in {"cs", "sk"}:
            # English grammar and spelling are handled by grammar_analyser.
            return [rule for rule in rules if rule.ac_code not in grammar_codes]
        return rules

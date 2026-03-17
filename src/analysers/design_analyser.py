"""LLM-based design analyser. Architecture, OOP principles.
Quality of what is written from a design perspective.

Responsible for AC:
- 'OOP': Meaningful and well-described object-oriented programming usage.
- 'NOOOP': Code ignores OOP principles and merely wraps functions in classes.
- 'NOSRP': Violation of the Single Responsibility Principle.
- 'DP': Good and well-justified design pattern usage.
- 'BADDP': Inappropriate use or bad implementation of a design pattern.
- 'SINGLETON': Use of the Singleton pattern, explicitly disallowed for NVP.
- 'EXT': Insufficient extensibility or modularity description.
- 'EX': Particularly clean exception usage and error handling.
- 'FILO': Missing or insufficient design philosophy description.

Future AC codes to consider:
- 'GODCLASS': Document describes a single class handling entirely unrelated responsibilities.
- 'OVERENG': Over-engineering or using complex patterns for trivial problems.
- 'DRY': WET architecture implying heavy code duplication.
"""

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


class DesignAnalyser(BaseLLMAnalyser):
    """
    Evaluates object-oriented design quality based on the student's text.
    Checks for inappropriate use of design patterns.
    """

    analyser_id: ClassVar[str] = "design_analyser"
    name: ClassVar[str] = "Design Analyser"

    def get_rules(self) -> list[LLMRule]:
        return [
            LLMRule(
                ac_code="FILO",
                prompt_instruction="missing or insufficient explanation of design philosophy or architectural decisions",
                analyser_id=self.analyser_id,
            ),
        ]

    def process_evaluations(
        self,
        doc: Document,
        evals: list[LLMEvaluation],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        return []

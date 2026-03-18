"""LLM-based text analyser. Deterministic, objective aim, proofreading.

Responsible for AC codes:
- 'CH': Spelling or grammar mistakes.
- 'ICH': First-person singular usage.
- 'TERM': Incorrect or imprecise technical terminology.
- 'LANG': Language mixing.

Future AC codes to consider:
- 'TODO': unresolved placeholders, todos lorem ipsum, etc.
- 'ACRO': unexplained acronyms or abbreviations
- 'CODE': unformatted code snippets
Grammar subtypes, instead of CH:
- 'TENSE': inconsistent or incorrect verb tense
- 'AGREE': subject-verb agreement errors
- 'PUNCT': punctuation errors
- 'SPELL': spelling mistakes

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMFinding, LLMRule, Rulebook

logger = logging.getLogger(__name__)


class TextAnalyser(BaseLLMAnalyser):
    analyser_id: ClassVar[str] = "text_analyser"
    name: ClassVar[str] = "Text Analyser"

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

    def process_llm_findings(
        self,
        doc: Document,
        llm_findings: list[LLMFinding],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        return [self._convert_llm_finding_to_finding(doc, f) for f in llm_findings]

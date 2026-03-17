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

from ..schemas.llm import LLMRule
from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMFinding, Rulebook

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
        findings: list[Finding] = []

        for f in llm_findings:
            item = doc.text_items.get(f.item_cref)

            findings.append(
                self._make_finding(
                    doc=doc,
                    ac_code=f.ac_code,
                    title=f"Text issue: {f.ac_code}",
                    summary=f.reason,
                    evidence_item=item,
                    snippet_override=f.snippet,
                    severity=f.severity,
                    confidence=f.confidence,
                )
            )

        return findings

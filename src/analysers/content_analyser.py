"""LLM-based content analyser. Technical adequacy and topical relevance of sections.
Required domain topics presence and their content.

Responsible for AC:
- 'CONTENT': Sections off-topic, such as subjective feelings or time spent.
- 'SA': Insufficient syntax analysis description.
- 'SAV': Insufficient syntax analysis of expressions description.
- 'SéA': Insufficient semantic analysis description.
- 'PSA': Insufficient precedence syntax analysis description.
- 'TS': Insufficient symbol table description.
- 'GK': Insufficient code generation description.
- 'IR': Insufficient internal representation description.
- 'JAK': Insufficient implementation description.
- 'RP': Insufficient division of work section.
- 'NVPDOC': Missing or insufficient NVP extension document.

Future AC codes to consider:
- 'NOTEST': Missing testing methodology or validation description.
- 'EDGE': Document only covers the happy path and ignores error or edge cases.
- 'MEM': Missing explanation of memory management.
- 'LIMIT': Explicitly documenting known limitations, functional bugs.
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


class ContentAnalyser(BaseLLMAnalyser):
    """
    Analyses section-level content adequacy and topical relevance.
    Verifies if specific concepts are described accurately and efficiently.
    """

    analyser_id: ClassVar[str] = "content_analyser"
    name: ClassVar[str] = "Content Analyser"

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
                    title=f"Content issue: {f.ac_code}",
                    summary=f.reason,
                    evidence_item=item,
                    snippet_override=f.snippet,
                    severity=f.severity,
                    confidence=f.confidence,
                )
            )

        return findings

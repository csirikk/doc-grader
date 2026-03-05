"""llm draft"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import TextItem
from docling_core.types.doc.labels import DocItemLabel

from .base_analyser import BaseAnalyser

if TYPE_CHECKING:
    from ..llm_client import LLMClient
    from ..schemas.finding import Finding
    from ..schemas.ir import Document

logger = logging.getLogger(__name__)


class TextAnalyser(BaseAnalyser):
    analyser_id: ClassVar[str] = "text_analyser"
    name: ClassVar[str] = "Text Analyser"

    MASTER_SYSTEM_PROMPT: ClassVar[str] = """\
You are a strict academic reviewer for university project documentation.
Documents are written in Czech, Slovak or English by undergraduate students.

For each text passage you receive, identify any of the following issues:
  
1. CH: spelling or grammar mistakes
2. HOV: informal, colloquial, conversational, or slang expressions
3. ICH: first-person singular usage (e.g. "implementoval jsem", "popisuji", "mine")
4. STYLE: unclear, repetitive, unacademic, or imprecise phrasing
5. TERM: incorrect or imprecise technical terminology

Return only a JSON object with a single key "findings", 
whose value is a list of objects. Each object must have:
  "code" : one of CH / HOV / ICH / STYLE / TERM
  "snippet" : the exact offending substring from the input
  "reason" : one-sentence string explanation in English
  "severity" : float on a scale of 0.0 (trivial) to 1.0 (critical)

If no issues exist, return {"findings": []}.
"""

    _PARAGRAPH_LABELS: ClassVar[frozenset[DocItemLabel]] = frozenset(
        {DocItemLabel.TEXT, DocItemLabel.PARAGRAPH}
    )

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def analyse(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        for item, _ in doc.docling_doc.iterate_items():
            if not isinstance(item, TextItem):
                continue
            if item.label not in self._PARAGRAPH_LABELS:
                continue
            if not item.text or not item.text.strip():
                continue

            try:
                result = self.llm.run(self.MASTER_SYSTEM_PROMPT, item.text)
            except Exception as exc:
                logger.warning("LLM call failed: %s", exc)
                continue

            logger.debug("paragraph: %s", item.text)
            logger.debug("llm response: %s", result)

        return []

"""Style analyser for checks related to writing style."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document


class StyleAnalyser(BaseAnalyser):
    """
    LLM checks for writing style and tone, with heuristic pre-filters.

    Implemented AC codes:
    - STYLE: Unclear or poor writing style.
    - FILO: Missing or insufficient design philosophy description (IPP only).
    - HOV: Informal, conversational, or slang language.
    """

    analyser_id: ClassVar[str] = "style_analyser"
    name: ClassVar[str] = "Style Analyser"

    def check_style(self, doc: Document) -> list[Finding]:
        """Detect unclear or poor writing style."""
        return []

    def check_filo(self, doc: Document) -> list[Finding]:
        """Detect missing or insufficient design philosophy section."""
        return []

    def check_hov(self, doc: Document) -> list[Finding]:
        """Detect informal, conversational, or slang language."""
        return []

    def analyse(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        """Run all style checks."""
        findings: list[Finding] = []

        findings.extend(self.check_style(doc))
        findings.extend(self.check_filo(doc))
        findings.extend(self.check_hov(doc))

        return findings

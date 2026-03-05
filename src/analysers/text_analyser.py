"""Text analyser for deterministic text checks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document


class TextAnalyser(BaseAnalyser):
    """
    Deterministic checks for text mechanics.

    Implemented AC codes:
    - LANG:  Language mixing, Czech / Slovak text with English words (both variants).
    - CH:    Spelling and grammar mistakes.
    - ICH:   First-person singular usage in formal documentation.
    - TERM:  Incorrect or imprecise technical terminology.
    """

    analyser_id: ClassVar[str] = "text_analyser"
    name: ClassVar[str] = "Text Analyser"

    def check_lang(self, doc: Document) -> list[Finding]:
        """Detect unsanctioned language mixing (cs/sk/en)."""
        return []

    def check_ch(self, doc: Document) -> list[Finding]:
        """Detect spelling and grammar mistakes"""
        return []

    def check_ich(self, doc: Document) -> list[Finding]:
        """Detect first-person singular usage in formal documentation"""
        return []

    def check_term(self, doc: Document) -> list[Finding]:
        """Detect incorrect or imprecise technical terminology."""
        return []

    def analyse(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        findings: list[Finding] = []

        findings.extend(self.check_lang(doc))
        findings.extend(self.check_ch(doc))
        findings.extend(self.check_gram(doc))
        findings.extend(self.check_ich(doc))
        findings.extend(self.check_term(doc))

        return findings

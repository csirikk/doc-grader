"""Structure analyser for deterministic document structure checks.
TODO: add guard in judge show context around"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import SectionHeaderItem, TextItem
from docling_core.types.doc.labels import DocItemLabel

from ..schemas.finding import Stat
from .base_analyser import BaseAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document

logger = logging.getLogger(__name__)

SHORT_MIN_WORDS: int = 486  # Accounts for ~90% of recorded SHORT docs
SHORT_MIN_CHARS: int = 3422  # Accounts for ~90% of recorded SHORT docs
SHORT_MIN_STRUCT: int = 7  # Accounts for ~75% of recorded SHORT docs


class StructureAnalyser(BaseAnalyser):
    """
    Deterministic checks for document structure and completeness.

    Implemented AC codes:
    - SHORT: Document is too short based on word/char/paragraph counts.
    - KAPTXT: Consecutive headings without intervening content.
    """

    analyser_id: ClassVar[str] = "structure_analyser"
    name: ClassVar[str] = "Structure Analyser"

    @staticmethod
    def _page_confidence(item: SectionHeaderItem) -> float:
        """Return reduced confidence for headings on early pages (ToC / cover)."""
        prov = item.prov
        page_no = prov[0].page_no if prov else None
        return 0.5 if page_no is not None and page_no <= 2 else 1.0

    def _check_kaptxt_severity(
        self, prev_level: int, curr_level: int
    ) -> tuple[float, str]:
        """
        Determine severity of empty section based on the heading levels involved.

        Args:
            prev_level: The semantic level of the empty heading (1 is top).
            curr_level: The semantic level of the following heading, or
                        prev_level when called for an end-of-document heading.
        """

        # H(N) -> H(N): sibling follows immediately with no content between
        if curr_level == prev_level:
            return 0.8, "Empty section (sibling heading follows with no content)"

        # H(N) -> H(>N): section jumps straight to children, no intro text
        if curr_level > prev_level:
            return 0.6, "Section has no introductory text before its subsections"

        # H(N) -> H(<N): section is completely empty before the block closes
        return 0.9, "Empty subsection at end of its block"

    def check_kaptxt(self, doc: Document) -> list[Finding]:
        """Detect headings that have no content before the next heading."""
        findings: list[Finding] = []

        last_was_heading = False
        last_heading_item: SectionHeaderItem | None = None
        last_heading_level = 0

        for item, _iter_level in doc.docling_doc.iterate_items():
            if not isinstance(item, TextItem):
                continue

            label = item.label

            if label == DocItemLabel.SECTION_HEADER and isinstance(
                item, SectionHeaderItem
            ):
                header_level = item.level

                if last_was_heading and last_heading_item is not None:
                    severity, reason = self._check_kaptxt_severity(
                        last_heading_level, header_level
                    )
                    confidence = self._page_confidence(last_heading_item)

                    findings.append(
                        self._make_finding(
                            doc=doc,
                            ac_code="KAPTXT",
                            title="Empty section detected",
                            summary=f"{reason}: '{last_heading_item.text}'.",
                            judge_status="to_be_judged",
                            human_status="proposed",
                            evidence_item=last_heading_item,
                            severity=severity,
                            confidence=confidence,
                        )
                    )

                last_was_heading = True
                last_heading_item = item
                last_heading_level = header_level

            else:
                is_noise = label in {
                    DocItemLabel.PAGE_HEADER,
                    DocItemLabel.PAGE_FOOTER,
                    DocItemLabel.FOOTNOTE,
                }
                is_empty_text = isinstance(item, TextItem) and not (
                    item.text and item.text.strip()
                )
                if not is_noise and not is_empty_text:
                    last_was_heading = False
                    last_heading_item = None
                    last_heading_level = 0

        # Trailing heading with no content after it
        if last_was_heading and last_heading_item is not None:
            severity, reason = self._check_kaptxt_severity(
                last_heading_level, last_heading_level
            )
            confidence = self._page_confidence(last_heading_item)

            findings.append(
                self._make_finding(
                    doc=doc,
                    ac_code="KAPTXT",
                    title="Empty section at end of document",
                    summary=f"{reason}: '{last_heading_item.text}'.",
                    judge_status="to_be_judged",
                    human_status="proposed",
                    evidence_item=last_heading_item,
                    severity=severity,
                    confidence=confidence,
                )
            )

        return findings

    def check_short(
        self,
        doc: Document,
        min_words: int = SHORT_MIN_WORDS,
        min_chars: int = SHORT_MIN_CHARS,
        min_struct: int = SHORT_MIN_STRUCT,
    ) -> list[Finding]:
        """Detect documents that are not detailed enough based on length and structure.

        Args:
            doc: Parsed document.
            min_words: Minimum acceptable word count.
            min_chars: Minimum acceptable character count.
            min_struct: Minimum acceptable structural blocks (paragraphs).
        """
        w = doc.total_words
        c = doc.total_chars
        s = doc.total_paragraphs

        # If any of the metrics exceed the threshold, arguably not a 'short' doc
        if w >= min_words and c >= min_chars and s >= min_struct:
            return []

        word_ratio = w / min_words if min_words > 0 else 1.0
        char_ratio = c / min_chars if min_chars > 0 else 1.0
        struct_ratio = s / min_struct if min_struct > 0 else 1.0

        # Use the lowest ratio to determine the severity penalty
        lowest_ratio = min(word_ratio, char_ratio, struct_ratio)

        if lowest_ratio < 0.5:
            severity = 0.9
        elif lowest_ratio < 0.75:
            severity = 0.7
        else:
            severity = 0.5

        finding = self._make_finding(
            doc=doc,
            ac_code="SHORT",
            title="Document is too short",
            summary=(f"Content is insufficient ({w} words, {c} chars, {s} blocks)."),
            judge_status="to_be_judged",
            human_status="proposed",
            evidence_item=None,
            severity=severity,
            confidence=0.8,
        )

        finding.stats = [
            Stat(name="word_count", value=w, unit="words"),
            Stat(name="char_count", value=c, unit="chars"),
            Stat(name="structure_count", value=s, unit="blocks"),
        ]

        return [finding]

    def check_struct(self, doc: Document) -> list[Finding]:
        """Detect missing required section headings (STRUCT / strukt.)."""
        return []

    def check_first_page(self, doc: Document) -> list[Finding]:
        """Detect missing mandatory information on the cover page (1. strana)."""
        return []

    def analyse(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        """Run all structure checks."""
        findings: list[Finding] = []

        findings.extend(self.check_kaptxt(doc))
        findings.extend(self.check_struct(doc))
        findings.extend(self.check_first_page(doc))

        p = params or {}
        findings.extend(
            self.check_short(
                doc,
                min_words=int(p.get("min_words", SHORT_MIN_WORDS)),
                min_chars=int(p.get("min_chars", SHORT_MIN_CHARS)),
                min_struct=int(p.get("min_struct", SHORT_MIN_STRUCT)),
            )
        )

        return findings

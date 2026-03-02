"""Section analyser for structure and content checks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import TextItem
from docling_core.types.doc.labels import DocItemLabel

from .base_analyser import BaseAnalyser

if TYPE_CHECKING:
    from docling_core.types.doc.document import SectionHeaderItem

    from ..schemas.finding import Finding
    from ..schemas.ir import Document

logger = logging.getLogger(__name__)


class SectionAnalyser(BaseAnalyser):
    """
    Analyses document structure and completeness.

    Currently implemented AC codes:
    - KAPTXT: Consecutive headings without content.
    """

    analyser_id: ClassVar[str] = "section_analyser"
    name: ClassVar[str] = "Section Analyser"

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
            label = item.label

            if label == DocItemLabel.SECTION_HEADER:
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
                    evidence_item=last_heading_item,
                    severity=severity,
                    confidence=confidence,
                )
            )

        return findings

    def analyse(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        """Run all section checks."""
        findings: list[Finding] = []
        findings.extend(self.check_kaptxt(doc))
        return findings

"""Section analyser for structure and content checks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import DOCUMENT_TOKENS_EXPORT_LABELS, TextItem
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

    def _check_kaptxt_severity(
        self, prev_level: int, curr_level: int
    ) -> tuple[float, str]:
        """
        Determine severity of empty section.

        Args:
            prev_level: The semantic level of the empty heading (1 is top).
            curr_level: The semantic level of the following heading.
        """

        # 1. H(N) -> H(N)
        if curr_level == prev_level:
            return 0.8, "Empty section content (sibling heading follows)"

        # 2. H(N) -> H(>N)
        if curr_level > prev_level:
            return 0.3, "Section container has no introductory text"

        # 3. H(N) -> H(<N)
        if curr_level < prev_level:
            return 0.9, "Empty subsection at end of block"

        return 0.5, "Empty section structure detected"

    def check_kaptxt(self, doc: Document) -> list[Finding]:
        """Detect consecutive headings without content."""
        findings: list[Finding] = []

        last_was_heading = False
        last_heading_item: SectionHeaderItem | None = None
        last_heading_level = 0

        content_labels = set(DOCUMENT_TOKENS_EXPORT_LABELS) - {
            DocItemLabel.SECTION_HEADER
        }

        for item, _iter_level in doc.docling_doc.iterate_items():
            label = item.label

            if label == DocItemLabel.SECTION_HEADER:
                header_level = item.level

                if last_was_heading and last_heading_item is not None:
                    # Previous heading was empty because we hit another heading now
                    severity, reason = self._check_kaptxt_severity(
                        last_heading_level, header_level
                    )

                    findings.append(
                        self._make_finding(
                            doc=doc,
                            ac_code="KAPTXT",
                            title="Empty Section detected",
                            summary=f"{reason}. Heading '{last_heading_item.text}' has no content.",
                            evidence_item=last_heading_item,
                            severity=severity,
                        )
                    )

                last_was_heading = True
                last_heading_item = item
                last_heading_level = header_level

            elif label in content_labels:
                if isinstance(item, TextItem):
                    if item.text and item.text.strip():
                        last_was_heading = False
                        last_heading_item = None
                        last_heading_level = 0
                else:
                    # Non-text Docling items are content
                    last_was_heading = False
                    last_heading_item = None
                    last_heading_level = 0

        # If loop finishes and last_was_heading is True, the last section is empty
        if last_was_heading and last_heading_item is not None:
            findings.append(
                self._make_finding(
                    doc=doc,
                    ac_code="KAPTXT",
                    title="Empty Section at end of document",
                    summary="Document ends with a heading.",
                    evidence_item=last_heading_item,
                    severity=0.8,
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

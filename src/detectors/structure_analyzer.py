"""Structure Analyzer.

Analyzes document structure including heading hierarchy, section organization,
and detects structural issues like empty sections or heading chains.
"""

from typing import List, Optional

from .base_detector import BaseDetector
from ..schemas.ir import Document, Heading, SectionBoundary
from ..schemas.finding import Finding, Stat
from ..logger import debug

DEFAULTS = dict(
    min_content_blocks_per_section=1,
    max_heading_level_jump=1,
)


class StructureAnalyzer(BaseDetector):
    code = "STRUCT"
    name = "StructureAnalyzer"
    version = "0.2"
    param_spec = {
        "min_content_blocks_per_section": "Minimum content blocks required per section",
        "max_heading_level_jump": "Maximum allowed jump in heading levels",
    }

    def __init__(self, *, run_id: Optional[str] = None, params: Optional[dict] = None):
        updated_params = DEFAULTS.copy()
        if params:
            updated_params.update(
                {key: value for key, value in params.items() if key in DEFAULTS}
            )
        super().__init__(run_id=run_id, params=updated_params)
        self.cfg = updated_params

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        findings: List[Finding] = []

        # Get section boundaries (uses cached version if available, computes if not)
        sections = self.get_section_boundaries(doc)

        if not sections:
            confidence = 0.95
            try:
                src = (doc.source_path or "").lower()
            except Exception:
                src = ""

            block_count = len(getattr(doc, "blocks", []))
            if src.endswith(".pdf") or block_count > 30:
                confidence = 0.6

            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="poor_hierarchy",
                    title="No document structure",
                    message="Document has no headings or sections",
                    severity_rank=1,
                    confidence=confidence,
                    tags=["structure", "hierarchy"],
                    extra_evidence=[
                        Stat(name="heading_count", value=0),
                        Stat(name="block_count", value=block_count),
                    ],
                )
            )
            return findings

        # Get headings for additional checks
        headings = self.get_blocks(doc, "Heading")

        # Extract TOC text to identify sections mentioned in TOC
        toc_text = self._extract_toc_text(doc, sections)

        # Check heading chain (consecutive headings without content)
        findings.extend(self._detect_heading_chains(doc, doc_hash, sections, toc_text))

        # Check empty sections
        findings.extend(self._detect_empty_sections(doc, doc_hash, sections, toc_text))

        # Check hierarchy issues (level jumps)
        # Exclude headings that belong to TOC sections
        toc_heading_ids = {s.heading_id for s in sections if s.is_toc}
        filtered_headings = [h for h in headings if h.id not in toc_heading_ids]
        findings.extend(self._detect_hierarchy_issues(doc, doc_hash, filtered_headings))

        return findings

    def _extract_toc_text(self, doc: Document, sections: List[SectionBoundary]) -> str:
        """Extract all text from TOC section for pattern matching."""
        for section in sections:
            if section.is_toc:
                text_parts = []
                for block_idx in range(section.start_idx, section.end_idx):
                    block = doc.blocks[block_idx]
                    if hasattr(block, "text") and block.text:
                        text_parts.append(block.text.lower())
                return " ".join(text_parts)
        return ""

    def _is_section_in_toc(self, heading_text: str, toc_text: str) -> bool:
        """Check if a heading text appears in the TOC text."""
        if not toc_text:
            return False
        return heading_text.lower() in toc_text

    def _detect_heading_chains(
        self,
        doc: Document,
        doc_hash: str,
        sections: List[SectionBoundary],
        toc_text: str = "",
    ) -> List[Finding]:
        """Detect consecutive headings without content between them.

        Skip sections whose headings appear in the TOC, as these are expected
        to have no content before their actual section heading appears.
        """
        findings: List[Finding] = []

        for i in range(len(sections) - 1):
            current_section = sections[i]
            next_section = sections[i + 1]

            # Skip TOC sections entirely
            if current_section.is_toc:
                debug(
                    f"Skipping TOC section '{current_section.heading_text}' in heading chain check."
                )
                continue

            # Skip sections that are listed in the TOC (expected to have no content)
            if self._is_section_in_toc(current_section.heading_text, toc_text):
                debug(
                    f"Skipping section '{current_section.heading_text}' listed in TOC in heading chain check."
                )
                continue

            # Check if current section has any content blocks
            if current_section.content_block_count == 0:
                # Get the actual heading blocks for better error messages
                current_heading = doc.blocks[current_section.start_idx]

                findings.append(
                    self.emit(
                        doc=doc,
                        doc_hash=doc_hash,
                        slug="heading_chain",
                        title="Consecutive headings without content",
                        message=f"Heading '{current_section.heading_text}' is immediately followed by '{next_section.heading_text}' with no content in between",
                        severity_rank=2,
                        confidence=0.90,
                        anchor_block=current_heading,
                        tags=["structure", "heading_chain"],
                        extra_evidence=[
                            Stat(name="heading_1", value=current_section.heading_text),
                            Stat(name="heading_2", value=next_section.heading_text),
                        ],
                    )
                )

        return findings

    def _detect_empty_sections(
        self,
        doc: Document,
        doc_hash: str,
        sections: List[SectionBoundary],
        toc_text: str = "",
    ) -> List[Finding]:
        """Detect sections with no or very little content.

        Skip sections whose headings appear in the TOC, as these are expected
        to be just listing entries without content.
        """
        findings: List[Finding] = []

        for section in sections:
            # Skip TOC sections entirely
            if section.is_toc:
                continue

            # Skip sections that are listed in the TOC (expected to be empty)
            if self._is_section_in_toc(section.heading_text, toc_text):
                continue

            if section.content_block_count < self.cfg["min_content_blocks_per_section"]:
                # Get the heading block for anchor
                heading = doc.blocks[section.start_idx]

                findings.append(
                    self.emit(
                        doc=doc,
                        doc_hash=doc_hash,
                        slug="empty_section",
                        title="Section has insufficient content",
                        message=f"Section '{section.heading_text}' has only {section.content_block_count} content blocks",
                        severity_rank=2,
                        confidence=0.85,
                        anchor_block=heading,
                        tags=["structure", "empty_section"],
                        extra_evidence=[
                            Stat(name="section_heading", value=section.heading_text),
                            Stat(
                                name="content_blocks", value=section.content_block_count
                            ),
                            Stat(
                                name="min_expected",
                                value=self.cfg["min_content_blocks_per_section"],
                            ),
                        ],
                    )
                )

        return findings

    def _detect_hierarchy_issues(
        self, doc: Document, doc_hash: str, headings: List[Heading]
    ) -> List[Finding]:
        """Detect improper heading level jumps."""
        findings: List[Finding] = []

        for i in range(len(headings) - 1):
            current = headings[i]
            next_heading = headings[i + 1]

            level_jump = next_heading.level - current.level

            # Check for skipping levels (e.g., h1 to h4)
            if level_jump > self.cfg["max_heading_level_jump"]:
                findings.append(
                    self.emit(
                        doc=doc,
                        doc_hash=doc_hash,
                        slug="poor_hierarchy",
                        title="Heading level skipped",
                        message=f"Heading '{current.text}' (level {current.level}) jumps to '{next_heading.text}' (level {next_heading.level}), skipping intermediate levels",
                        severity_rank=3,
                        confidence=0.80,
                        anchor_block=next_heading,
                        tags=["structure", "hierarchy"],
                        extra_evidence=[
                            Stat(name="from_level", value=current.level),
                            Stat(name="to_level", value=next_heading.level),
                            Stat(name="level_jump", value=level_jump),
                        ],
                    )
                )

        return findings

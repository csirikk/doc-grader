"""Section Analyzer.

Detects missing or misaligned required sections based on course-specific requirements.
Emits findings for missing critical sections.
"""

import re
from typing import List, Optional

from .base_detector import BaseDetector
from ..schemas.ir import Document, SectionBoundary
from ..schemas.finding import Finding, Stat
from ..logger import debug


DEFAULTS = dict(
    course=None,  # "ifj" or "ipp" - if None, skips section checks
)


class SectionAnalyzer(BaseDetector):
    code = "SECTION"
    name = "SectionAnalyzer"
    version = "0.2"
    param_spec = {
        "course": "Course identifier (ifj/ipp).",
    }

    REQUIRED_SECTIONS = {
        "ifj": {
            "lexer": [
                "lexikální analýza",
                "scanner",
                "lexer",
                "tokenizace",
                "lexikální analyzátor",
            ],
            "syntax_analysis": [
                "syntaktická analýza",
                "syntax analysis",
                "parser",
                "syntaktick",
            ],
            "precedence_analysis": [
                "precedenční analýza",
                "precedence",
                "precedenč",
                "precedenční",
            ],
            "error_handling": ["zpracování chyb", "error handling", "chyb", "error"],
            "team_work": [
                "rozdělení",
                "division of labor",
                "prace",
                "práce",
                "division of work",
                "práce v týmu",
                "teamwork",
            ],
        },
        "ipp": {
            "internal_representation": [
                "vnitřní reprezentace",
                "internal representation",
                "ir ",
                "reprezentace",
            ],
            "implementation": [
                "implementace",
                "implementation",
                "jak to funguje",
                "popis implementace",
            ],
        },
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

        course = self.cfg["course"]

        if not course:
            debug("SectionAnalyzer: No course specified, skipping section checks.")
            return findings

        if course not in self.REQUIRED_SECTIONS:
            debug("SectionAnalyzer: Unknown course, skipping section checks.")
            return findings

        # Get section boundaries (reuses cached if StructureAnalyzer ran first)
        sections = self.get_section_boundaries(doc)

        # Extract section info
        total_headings = len(sections)

        # If there are no headings, don't emit missing-section findings here.
        # StructureAnalyzer will already have reported structural issues.
        if total_headings == 0:
            debug(
                "SectionAnalyzer: No headings found, skipping section existence checks."
            )
            return findings

        # Check for each required section
        required = self.REQUIRED_SECTIONS[course]
        for section_key, section_patterns in required.items():
            if not self._section_exists(sections, section_patterns):
                # Lower confidence when document is very short (few headings)
                confidence = 0.80
                if total_headings < 3:
                    confidence = 0.50

                findings.append(
                    self.emit(
                        doc=doc,
                        doc_hash=doc_hash,
                        slug=f"section_missing:{section_key}",
                        title=f"Missing required section: {section_key}",
                        message=f"Document appears to be missing the '{section_key}' section (expected patterns: {', '.join(section_patterns[:2])})",
                        severity_rank=1,
                        confidence=confidence,
                        tags=["section", "missing", course, section_key],
                        extra_evidence=[
                            Stat(name="course", value=course),
                            Stat(name="section_key", value=section_key),
                            Stat(name="total_headings", value=total_headings),
                        ],
                    )
                )

        return findings

    def _section_exists(
        self, sections: List[SectionBoundary], patterns: List[str]
    ) -> bool:
        """Check if any pattern matches section headings using word boundaries."""
        for section in sections:
            # Skip TOC sections - they are not authoritative for content
            if getattr(section, "is_toc", False):
                continue

            heading_text_lower = section.heading_text.lower()
            for pattern in patterns:
                if pattern.lower().strip() in heading_text_lower:
                    debug(
                        "SectionAnalyzer: Found match for pattern '%s' in heading '%s'",
                        pattern,
                        section.heading_text,
                    )
                    return True

        return False

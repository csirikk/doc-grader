"""Length analyzer.

Flags documents that appear too short or too long.
Emits at most one finding per condition (too-short or too-long) with supporting `Stat` evidence objects.
"""

from typing import List, Optional

from .base_detector import BaseDetector
from ..schemas.ir import Document, Paragraph, Heading, ListBlock, Block
from ..schemas.finding import Finding, Stat
from ..util import count_words

# TODO: improve/add more heuristics
# TODO: tweak thresholds based on dataset
# TODO: add page count
DEFAULTS = dict(
    min_words=300,  # ~P15, catch severely short docs
    min_paragraphs=6,  # ~P12, reasonable minimum structure
    min_avg_words_per_paragraph=10.0,  # ~P12, very terse paragraphs
    min_paragraphs_per_heading=1.0,  # ~P15, at least some content per section
    max_words=4000,  # ~P92, catch overly verbose docs
    max_paragraphs=200,  # ~P92, excessive verbosity
    max_avg_words_per_paragraph=50.0,  # ~P92, wall-of-text paragraphs
    # require at least this many individual short/long flags to raise a finding
    min_flags_short=2,
    min_flags_long=2,
)


class LengthAnalyzer(BaseDetector):
    code = "LENGTH"
    name = "LengthAnalyzer"
    version = "0.2"
    param_spec = {
        "min_words": "Minimum total words before flagging short",
        "min_paragraphs": "Minimum paragraphs before flagging short",
        "min_avg_words_per_paragraph": "Minimum average words per paragraph",
        "min_paragraphs_per_heading": "Minimum paragraphs per heading",
        "max_words": "Maximum total words before flagging long",
        "max_paragraphs": "Maximum paragraphs before flagging long",
        "max_avg_words_per_paragraph": "Maximum average words per paragraph",
        "min_flags_short": "Minimum number of short condition breaches required",
        "min_flags_long": "Minimum number of long condition breaches required",
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
        metrics, stats_evidence = self._collect_stats(doc)
        findings: List[Finding] = []
        findings.extend(
            self._compute_short_findings(doc, doc_hash, metrics, stats_evidence)
        )
        findings.extend(
            self._compute_long_findings(doc, doc_hash, metrics, stats_evidence)
        )
        return findings

    def _collect_stats(self, doc: Document):
        # Use base detector utilities for counting
        paragraph_count = self.count_blocks(doc, "Paragraph")
        heading_count = self.count_blocks(doc, "Heading")
        block_count = self.count_blocks(doc)

        # Extract text and count words using base utilities
        paragraph_text = self.extract_text(doc, "Paragraph")
        list_text = self.extract_text(doc, "List")

        # Count words using base method
        paragraph_words = self.count_words(paragraph_text)
        list_words = self.count_words(list_text)
        total_words = paragraph_words + list_words

        avg_words_per_paragraph = (
            (paragraph_words / paragraph_count) if paragraph_count else 0.0
        )
        paragraphs_per_heading = (
            (paragraph_count / heading_count) if heading_count else None
        )

        stats_evidence: List[Stat] = [
            Stat(name="total_words", value=total_words),
            Stat(name="paragraph_count", value=paragraph_count),
            Stat(name="heading_count", value=heading_count),
            Stat(name="block_count", value=block_count),
            Stat(
                name="avg_words_per_paragraph", value=round(avg_words_per_paragraph, 2)
            ),
            Stat(
                name="paragraphs_per_heading",
                value=(
                    round(paragraphs_per_heading, 2)
                    if paragraphs_per_heading is not None
                    else None
                ),
            ),
        ]

        metrics = dict(
            total_words=total_words,
            paragraph_count=paragraph_count,
            heading_count=heading_count,
            block_count=block_count,
            avg_words_per_paragraph=avg_words_per_paragraph,
            paragraphs_per_heading=paragraphs_per_heading,
        )
        return metrics, stats_evidence

    def _compute_short_findings(
        self, doc: Document, doc_hash: str, metrics: dict, stats_evidence: List[Stat]
    ) -> List[Finding]:
        total_words = metrics["total_words"]
        paragraph_count = metrics["paragraph_count"]
        paragraphs_per_heading = metrics["paragraphs_per_heading"]
        avg_words_per_paragraph = metrics["avg_words_per_paragraph"]

        short_flags = 0
        if total_words < self.cfg["min_words"]:
            short_flags += 1
        if paragraph_count < self.cfg["min_paragraphs"]:
            short_flags += 1
        if (paragraphs_per_heading is not None) and (
            paragraphs_per_heading < self.cfg["min_paragraphs_per_heading"]
        ):
            short_flags += 1
        if (
            avg_words_per_paragraph < self.cfg["min_avg_words_per_paragraph"]
            and paragraph_count >= 3
        ):
            short_flags += 1

        findings: List[Finding] = []
        if short_flags >= self.cfg["min_flags_short"]:
            deviations: List[float] = []
            if total_words < self.cfg["min_words"]:
                deviations.append(1 - (total_words / max(self.cfg["min_words"], 1)))
            if paragraph_count < self.cfg["min_paragraphs"]:
                deviations.append(
                    1 - (paragraph_count / max(self.cfg["min_paragraphs"], 1))
                )
            if (paragraphs_per_heading is not None) and (
                paragraphs_per_heading < self.cfg["min_paragraphs_per_heading"]
            ):
                deviations.append(
                    1
                    - (paragraphs_per_heading / self.cfg["min_paragraphs_per_heading"])
                )
            if (
                avg_words_per_paragraph < self.cfg["min_avg_words_per_paragraph"]
                and paragraph_count >= 3
            ):
                deviations.append(
                    1
                    - (
                        avg_words_per_paragraph
                        / self.cfg["min_avg_words_per_paragraph"]
                    )
                )
            confidence = max(0.3, min(0.97, max(deviations) if deviations else 0.5))

            reasons = []
            if total_words < self.cfg["min_words"]:
                reasons.append(f"word_count {total_words} < {self.cfg['min_words']}")
            if paragraph_count < self.cfg["min_paragraphs"]:
                reasons.append(
                    f"paragraphs {paragraph_count} < {self.cfg['min_paragraphs']}"
                )
            if (paragraphs_per_heading is not None) and (
                paragraphs_per_heading < self.cfg["min_paragraphs_per_heading"]
            ):
                reasons.append(
                    f"paragraphs/heading {paragraphs_per_heading:.2f} < {self.cfg['min_paragraphs_per_heading']}"
                )
            if (
                avg_words_per_paragraph < self.cfg["min_avg_words_per_paragraph"]
                and paragraph_count >= 3
            ):
                reasons.append(
                    f"avg_words/para {avg_words_per_paragraph:.1f} < {self.cfg['min_avg_words_per_paragraph']}"
                )

            message = "Document appears too short: " + ", ".join(reasons) + ". "
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="too-short",
                    title="Likely too short",
                    message=message,
                    severity_rank=2,
                    confidence=confidence,
                    tags=["length", "short"],
                    extra_evidence=stats_evidence,
                )
            )
        return findings

    def _compute_long_findings(
        self, doc: Document, doc_hash: str, metrics: dict, stats_evidence: List[Stat]
    ) -> List[Finding]:
        total_words = metrics["total_words"]
        paragraph_count = metrics["paragraph_count"]
        avg_words_per_paragraph = metrics["avg_words_per_paragraph"]

        long_flags = 0
        if total_words > self.cfg["max_words"]:
            long_flags += 1
        if paragraph_count > self.cfg["max_paragraphs"]:
            long_flags += 1
        if avg_words_per_paragraph > self.cfg["max_avg_words_per_paragraph"]:
            long_flags += 1

        findings: List[Finding] = []
        if long_flags >= self.cfg["min_flags_long"]:
            deviations: List[float] = []
            if total_words > self.cfg["max_words"]:
                deviations.append(
                    (total_words - self.cfg["max_words"]) / self.cfg["max_words"]
                )
            if paragraph_count > self.cfg["max_paragraphs"]:
                deviations.append(
                    (paragraph_count - self.cfg["max_paragraphs"])
                    / self.cfg["max_paragraphs"]
                )
            if avg_words_per_paragraph > self.cfg["max_avg_words_per_paragraph"]:
                deviations.append(
                    (avg_words_per_paragraph - self.cfg["max_avg_words_per_paragraph"])
                    / self.cfg["max_avg_words_per_paragraph"]
                )
            confidence = max(0.3, min(0.95, max(deviations) if deviations else 0.5))

            reasons = []
            if total_words > self.cfg["max_words"]:
                reasons.append(f"word_count {total_words} > {self.cfg['max_words']}")
            if paragraph_count > self.cfg["max_paragraphs"]:
                reasons.append(
                    f"paragraphs {paragraph_count} > {self.cfg['max_paragraphs']}"
                )
            if avg_words_per_paragraph > self.cfg["max_avg_words_per_paragraph"]:
                reasons.append(
                    f"avg_words/para {avg_words_per_paragraph:.1f} > {self.cfg['max_avg_words_per_paragraph']}"
                )

            message = (
                "Document appears overly long/verbose: " + ", ".join(reasons) + ". "
            )
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="too-long",
                    title="Likely too long or verbose",
                    message=message,
                    severity_rank=2,
                    confidence=confidence,
                    tags=["length", "long"],
                    extra_evidence=stats_evidence,
                )
            )

        return findings

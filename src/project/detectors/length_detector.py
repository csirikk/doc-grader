# detectors/length_detector.py

from typing import List, Optional

from .base_detector import BaseDetector
from ..schemas.ir import Document, Paragraph, Heading, ListBlock, Block
from ..schemas.finding import Finding, Stat

# TODO: improve/add more heuristics
# TODO: tweak thresholds based on dataset
# under -> likely too short
MIN_WORDS = 500
MIN_PARAGRAPHS = 8
MIN_AVG_WORDS_PER_PARAGRAPH = 15
MIN_PARAGRAPHS_PER_HEADING = 2.0  # paragraphs per heading

# over -> likely too long
MAX_WORDS = 8000
MAX_PARAGRAPHS = 120
MAX_AVG_WORDS_PER_PARAGRAPH = 120

"""
LENGTH detector

Flags documents that appear too short or too long.
Uses multiple heuristics (word count, paragraph count, average words per paragraph) 
to emit a single finding per condition (too-short or too-long).

Finding codes emitted:
  LENGTH:too-short
  LENGTH:too-long

Evidence: Stat objects for the computed metrics.
"""
class LengthDetector(BaseDetector):
    code = "LENGTH"
    name = "LengthDetector"
    version = "0.1.0"

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        blocks: List[Block] = doc.blocks
        paragraphs: List[Paragraph] = [b for b in blocks if isinstance(b, Paragraph)]
        headings: List[Heading] = [b for b in blocks if isinstance(b, Heading)]
        lists: List[ListBlock] = [b for b in blocks if isinstance(b, ListBlock)]

        # Word counts (only paragraphs & list items' text)
        def _count_words(text: Optional[str]) -> int:
            return len([w for w in (text or "").split() if w])

        para_word_counts = [_count_words(p.text) for p in paragraphs]
        list_word_counts: List[int] = []
        for lb in lists:
            for it in lb.items:
                list_word_counts.append(_count_words(it.text))
        total_words = sum(para_word_counts) + sum(list_word_counts)

        paragraph_count = len(paragraphs)
        heading_count = len(headings)
        block_count = len(blocks)

        avg_words_per_paragraph = (sum(para_word_counts) / paragraph_count) if paragraph_count else 0.0
        paragraphs_per_heading = (paragraph_count / heading_count) if heading_count else float('inf')

        stats_evidence: List[Stat] = [
            Stat(name="total_words", value=total_words),
            Stat(name="paragraph_count", value=paragraph_count),
            Stat(name="heading_count", value=heading_count),
            Stat(name="avg_words_per_paragraph", value=round(avg_words_per_paragraph, 2)),
            Stat(name="paragraphs_per_heading", value=(round(paragraphs_per_heading, 2) if paragraphs_per_heading != float('inf') else "inf")),
        ]

        findings: List[Finding] = []

        # too-short heuristics -------------------------------------------------
        short_flags = 0
        if total_words < MIN_WORDS: short_flags += 1
        if paragraph_count < MIN_PARAGRAPHS: short_flags += 1
        if paragraphs_per_heading < MIN_PARAGRAPHS_PER_HEADING: short_flags += 1
        if avg_words_per_paragraph < MIN_AVG_WORDS_PER_PARAGRAPH and paragraph_count >= 3: short_flags += 1

        if short_flags >= 2:  # require at least two signals
            # Confidence - strongest deviation
            deviations: List[float] = []
            if total_words < MIN_WORDS:
                deviations.append(1 - (total_words / max(MIN_WORDS, 1)))
            if paragraph_count < MIN_PARAGRAPHS:
                deviations.append(1 - (paragraph_count / max(MIN_PARAGRAPHS, 1)))
            if paragraphs_per_heading < MIN_PARAGRAPHS_PER_HEADING:
                deviations.append(1 - (paragraphs_per_heading / MIN_PARAGRAPHS_PER_HEADING))
            if avg_words_per_paragraph < MIN_AVG_WORDS_PER_PARAGRAPH and paragraph_count >= 3:
                deviations.append(1 - (avg_words_per_paragraph / MIN_AVG_WORDS_PER_PARAGRAPH))
            confidence = max(0.3, min(0.97, max(deviations) if deviations else 0.5))

            reasons = []
            if total_words < MIN_WORDS:
                reasons.append(f"word_count {total_words} < {MIN_WORDS}")
            if paragraph_count < MIN_PARAGRAPHS:
                reasons.append(f"paragraphs {paragraph_count} < {MIN_PARAGRAPHS}")
            if paragraphs_per_heading < MIN_PARAGRAPHS_PER_HEADING:
                reasons.append(f"paragraphs/heading {paragraphs_per_heading:.2f} < {MIN_PARAGRAPHS_PER_HEADING}")
            if avg_words_per_paragraph < MIN_AVG_WORDS_PER_PARAGRAPH and paragraph_count >= 3:
                reasons.append(f"avg_words/para {avg_words_per_paragraph:.1f} < {MIN_AVG_WORDS_PER_PARAGRAPH}")

            message = "Document appears too short: " + ", ".join(reasons) + ". "
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="too-short",
                    title="Likely too short",
                    message=message,
                    severity="warning",
                    confidence=confidence,
                    tags=["length", "short"],
                    extra_evidence=stats_evidence,
                )
            )

        # too-long heuristics --------------------------------------------------
        long_flags = 0
        if total_words > MAX_WORDS: long_flags += 1
        if paragraph_count > MAX_PARAGRAPHS: long_flags += 1
        if avg_words_per_paragraph > MAX_AVG_WORDS_PER_PARAGRAPH: long_flags += 1

        if long_flags >= 2:
            deviations: List[float] = []
            if total_words > MAX_WORDS:
                deviations.append((total_words - MAX_WORDS) / MAX_WORDS)
            if paragraph_count > MAX_PARAGRAPHS:
                deviations.append((paragraph_count - MAX_PARAGRAPHS) / MAX_PARAGRAPHS)
            if avg_words_per_paragraph > MAX_AVG_WORDS_PER_PARAGRAPH:
                deviations.append((avg_words_per_paragraph - MAX_AVG_WORDS_PER_PARAGRAPH) / MAX_AVG_WORDS_PER_PARAGRAPH)
            confidence = max(0.3, min(0.95, max(deviations) if deviations else 0.5))

            reasons = []
            if total_words > MAX_WORDS:
                reasons.append(f"word_count {total_words} > {MAX_WORDS}")
            if paragraph_count > MAX_PARAGRAPHS:
                reasons.append(f"paragraphs {paragraph_count} > {MAX_PARAGRAPHS}")
            if avg_words_per_paragraph > MAX_AVG_WORDS_PER_PARAGRAPH:
                reasons.append(f"avg_words/para {avg_words_per_paragraph:.1f} > {MAX_AVG_WORDS_PER_PARAGRAPH}")

            message = "Document appears overly long/verbose: " + ", ".join(reasons) + ". "
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="too-long",
                    title="Likely too long or verbose",
                    message=message,
                    severity="info",
                    confidence=confidence,
                    tags=["length", "long"],
                    extra_evidence=stats_evidence,
                )
            )

        return findings

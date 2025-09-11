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
MIN_AVG_WORDS_PER_PARA = 15
MIN_HEADING_CONTENT_RATIO = 2.0  # paragraphs per heading

# over -> likely too long
MAX_WORDS = 8000
MAX_PARAGRAPHS = 120
MAX_AVG_WORDS_PER_PARA = 120

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

    def detect_on_ir(self, doc: Document, doc_hash_value: str) -> List[Finding]:
        blocks: List[Block] = doc.blocks
        paragraphs: List[Paragraph] = [b for b in blocks if isinstance(b, Paragraph)]
        headings: List[Heading] = [b for b in blocks if isinstance(b, Heading)]
        lists: List[ListBlock] = [b for b in blocks if isinstance(b, ListBlock)]

        # Word counts (only paragraphs & list items' text)
        def _get_word_counts(text: Optional[str]) -> int:
            return len([w for w in (text or "").split() if w])

        para_word_counts = [_get_word_counts(p.text) for p in paragraphs]
        list_word_counts: List[int] = []
        for lb in lists:
            for it in lb.items:
                list_word_counts.append(_get_word_counts(it.text))
        total_words = sum(para_word_counts) + sum(list_word_counts)

        paragraph_count = len(paragraphs)
        heading_count = len(headings)
        block_count = len(blocks)

        avg_words_per_para = (sum(para_word_counts) / paragraph_count) if paragraph_count else 0.0
        paragraphs_per_heading = (paragraph_count / heading_count) if heading_count else float('inf')

        stats_evidence: List[Stat] = [
            Stat(name="total_words", value=total_words),
            Stat(name="paragraph_count", value=paragraph_count),
            Stat(name="heading_count", value=heading_count),
            Stat(name="avg_words_per_paragraph", value=round(avg_words_per_para, 2)),
            Stat(name="paragraphs_per_heading", value=(round(paragraphs_per_heading, 2) if paragraphs_per_heading != float('inf') else "inf")),
        ]

        findings: List[Finding] = []

        # too-short heuristics -------------------------------------------------
        short_flags = 0
        if total_words < MIN_WORDS: short_flags += 1
        if paragraph_count < MIN_PARAGRAPHS: short_flags += 1
        if paragraphs_per_heading < MIN_HEADING_CONTENT_RATIO: short_flags += 1
        if avg_words_per_para < MIN_AVG_WORDS_PER_PARA and paragraph_count >= 3: short_flags += 1

        if short_flags >= 2:  # require at least two signals
            # Confidence - strongest deviation
            deviations: List[float] = []
            if total_words < MIN_WORDS:
                deviations.append(1 - (total_words / max(MIN_WORDS, 1)))
            if paragraph_count < MIN_PARAGRAPHS:
                deviations.append(1 - (paragraph_count / max(MIN_PARAGRAPHS, 1)))
            if paragraphs_per_heading < MIN_HEADING_CONTENT_RATIO:
                deviations.append(1 - (paragraphs_per_heading / MIN_HEADING_CONTENT_RATIO))
            if avg_words_per_para < MIN_AVG_WORDS_PER_PARA and paragraph_count >= 3:
                deviations.append(1 - (avg_words_per_para / MIN_AVG_WORDS_PER_PARA))
            confidence = max(0.3, min(0.97, max(deviations) if deviations else 0.5))

            reasons = []
            if total_words < MIN_WORDS:
                reasons.append(f"word_count {total_words} < {MIN_WORDS}")
            if paragraph_count < MIN_PARAGRAPHS:
                reasons.append(f"paragraphs {paragraph_count} < {MIN_PARAGRAPHS}")
            if paragraphs_per_heading < MIN_HEADING_CONTENT_RATIO:
                reasons.append(f"paragraphs/heading {paragraphs_per_heading:.2f} < {MIN_HEADING_CONTENT_RATIO}")
            if avg_words_per_para < MIN_AVG_WORDS_PER_PARA and paragraph_count >= 3:
                reasons.append(f"avg_words/para {avg_words_per_para:.1f} < {MIN_AVG_WORDS_PER_PARA}")

            message = "Document appears too short: " + ", ".join(reasons) + ". "
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash_value=doc_hash_value,
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
        if avg_words_per_para > MAX_AVG_WORDS_PER_PARA: long_flags += 1

        if long_flags >= 2:
            deviations: List[float] = []
            if total_words > MAX_WORDS:
                deviations.append((total_words - MAX_WORDS) / MAX_WORDS)
            if paragraph_count > MAX_PARAGRAPHS:
                deviations.append((paragraph_count - MAX_PARAGRAPHS) / MAX_PARAGRAPHS)
            if avg_words_per_para > MAX_AVG_WORDS_PER_PARA:
                deviations.append((avg_words_per_para - MAX_AVG_WORDS_PER_PARA) / MAX_AVG_WORDS_PER_PARA)
            confidence = max(0.3, min(0.95, max(deviations) if deviations else 0.5))

            reasons = []
            if total_words > MAX_WORDS:
                reasons.append(f"word_count {total_words} > {MAX_WORDS}")
            if paragraph_count > MAX_PARAGRAPHS:
                reasons.append(f"paragraphs {paragraph_count} > {MAX_PARAGRAPHS}")
            if avg_words_per_para > MAX_AVG_WORDS_PER_PARA:
                reasons.append(f"avg_words/para {avg_words_per_para:.1f} > {MAX_AVG_WORDS_PER_PARA}")

            message = "Document appears overly long/verbose: " + ", ".join(reasons) + ". "
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash_value=doc_hash_value,
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

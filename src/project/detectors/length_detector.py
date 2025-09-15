"""Length detector.

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
# Thresholds (under -> likely too short)
MIN_WORDS = 500
MIN_PARAGRAPHS = 8
MIN_AVG_WORDS_PER_PARAGRAPH = 15
MIN_PARAGRAPHS_PER_HEADING = 2.0  # paragraphs per heading

# Thresholds (over -> likely too long)
MAX_WORDS = 8000
MAX_PARAGRAPHS = 120
MAX_AVG_WORDS_PER_PARAGRAPH = 120

class LengthDetector(BaseDetector):
    code = "LENGTH"
    name = "LengthDetector"
    version = "0.2"

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        metrics, stats_evidence = self._collect_stats(doc)
        findings: List[Finding] = []
        findings.extend(self._compute_short_findings(doc, doc_hash, metrics, stats_evidence))
        findings.extend(self._compute_long_findings(doc, doc_hash, metrics, stats_evidence))
        return findings

    def _collect_stats(self, doc: Document):
        blocks: List[Block] = doc.blocks
        paragraphs: List[Paragraph] = [b for b in blocks if isinstance(b, Paragraph)]
        headings: List[Heading] = [b for b in blocks if isinstance(b, Heading)]
        lists: List[ListBlock] = [b for b in blocks if isinstance(b, ListBlock)]

        paragraph_word_counts = [count_words(p.text) for p in paragraphs]
        list_word_counts: List[int] = []
        for lb in lists:
            for it in lb.items:
                list_word_counts.append(count_words(it.text))
        total_words = sum(paragraph_word_counts) + sum(list_word_counts)

        paragraph_count = len(paragraphs)
        heading_count = len(headings)
        block_count = len(blocks)

        avg_words_per_paragraph = (sum(paragraph_word_counts) / paragraph_count) if paragraph_count else 0.0
        paragraphs_per_heading = (paragraph_count / heading_count) if heading_count else None

        stats_evidence: List[Stat] = [
            Stat(name="total_words", value=total_words),
            Stat(name="paragraph_count", value=paragraph_count),
            Stat(name="heading_count", value=heading_count),
            Stat(name="block_count", value=block_count),
            Stat(name="avg_words_per_paragraph", value=round(avg_words_per_paragraph, 2)),
            Stat(name="paragraphs_per_heading", value=(round(paragraphs_per_heading, 2) if paragraphs_per_heading is not None else None)),
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

    def _compute_short_findings(self, doc: Document, doc_hash: str, metrics: dict, stats_evidence: List[Stat]) -> List[Finding]:
        total_words = metrics["total_words"]
        paragraph_count = metrics["paragraph_count"]
        paragraphs_per_heading = metrics["paragraphs_per_heading"]
        avg_words_per_paragraph = metrics["avg_words_per_paragraph"]

        short_flags = 0
        if total_words < MIN_WORDS: short_flags += 1
        if paragraph_count < MIN_PARAGRAPHS: short_flags += 1
        if (paragraphs_per_heading is not None) and (paragraphs_per_heading < MIN_PARAGRAPHS_PER_HEADING): short_flags += 1
        if avg_words_per_paragraph < MIN_AVG_WORDS_PER_PARAGRAPH and paragraph_count >= 3: short_flags += 1

        findings: List[Finding] = []
        if short_flags >= 2:
            deviations: List[float] = []
            if total_words < MIN_WORDS:
                deviations.append(1 - (total_words / max(MIN_WORDS, 1)))
            if paragraph_count < MIN_PARAGRAPHS:
                deviations.append(1 - (paragraph_count / max(MIN_PARAGRAPHS, 1)))
            if (paragraphs_per_heading is not None) and (paragraphs_per_heading < MIN_PARAGRAPHS_PER_HEADING):
                deviations.append(1 - (paragraphs_per_heading / MIN_PARAGRAPHS_PER_HEADING))
            if avg_words_per_paragraph < MIN_AVG_WORDS_PER_PARAGRAPH and paragraph_count >= 3:
                deviations.append(1 - (avg_words_per_paragraph / MIN_AVG_WORDS_PER_PARAGRAPH))
            confidence = max(0.3, min(0.97, max(deviations) if deviations else 0.5))

            reasons = []
            if total_words < MIN_WORDS:
                reasons.append(f"word_count {total_words} < {MIN_WORDS}")
            if paragraph_count < MIN_PARAGRAPHS:
                reasons.append(f"paragraphs {paragraph_count} < {MIN_PARAGRAPHS}")
            if (paragraphs_per_heading is not None) and (paragraphs_per_heading < MIN_PARAGRAPHS_PER_HEADING):
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
        return findings

    def _compute_long_findings(self, doc: Document, doc_hash: str, metrics: dict, stats_evidence: List[Stat]) -> List[Finding]:
        total_words = metrics["total_words"]
        paragraph_count = metrics["paragraph_count"]
        avg_words_per_paragraph = metrics["avg_words_per_paragraph"]

        long_flags = 0
        if total_words > MAX_WORDS: long_flags += 1
        if paragraph_count > MAX_PARAGRAPHS: long_flags += 1
        if avg_words_per_paragraph > MAX_AVG_WORDS_PER_PARAGRAPH: long_flags += 1

        findings: List[Finding] = []
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
                    severity="warning",
                    confidence=confidence,
                    tags=["length", "long"],
                    extra_evidence=stats_evidence,
                )
            )

        return findings

"""Language Analyzer.

Detects undesired languages (anything outside cs/sk/en) and flags mixed-language usage within a single document.
"""

from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

from langdetect import DetectorFactory, LangDetectException, detect_langs

from .base_detector import BaseDetector
from ..schemas.ir import Block, Document
from ..schemas.finding import Finding, Stat

DetectorFactory.seed = 0  # deterministic predictions


@dataclass
class LanguageSample:
    block: Block
    lang: str
    prob: float
    char_len: int


DEFAULTS = dict(
    allowed_languages=("cs", "sk", "en"),
    # sampling parameters
    min_chars_per_sample=60,
    min_lang_prob=0.85,
    max_samples=200,
    # mixing detection parameters
    mixing_ratio_threshold=0.10,
    switch_threshold=10,
    min_mix_samples=4,
    min_mix_total_chars=400,
    min_offending_ratio=0.05,
)


class LanguageAnalyzer(BaseDetector):
    code = "LANG"
    name = "LanguageAnalyzer"
    version = "0.1"

    # Private constants for low-level heuristics
    _MIN_CANDIDATES_FOR_RELIABILITY = 30
    _MIN_ALPHA_CHARS = 25
    _MIN_ALPHA_RATIO = 0.35
    _MIN_MIX_CHAR_SHARE = 250
    _LONG_SEGMENT_RATIO_THRESHOLD = 0.12
    _LONG_SEGMENT_MIN_CHARS = 280

    param_spec = {
        "allowed_languages": "Iterable of ISO language codes that are allowed",
        "min_chars_per_sample": "Discard blocks shorter than this many characters",
        "min_lang_prob": "Minimum langdetect probability to accept a prediction",
        "max_samples": "Maximum number of blocks to sample per document",
        "mixing_ratio_threshold": "Share of non-dominant language required to flag mixing",
        "switch_threshold": "Maximum allowed language switches between consecutive blocks",
        "min_mix_samples": "Minimum number of samples required to flag mixing",
        "min_mix_total_chars": "Minimum total character count required to flag mixing",
        "min_offending_ratio": "Minimum unsupported-language share before flagging",
    }

    def __init__(self, *, run_id: Optional[str] = None, params: Optional[dict] = None):
        updated_params = DEFAULTS.copy()
        if params:
            updated_params.update(
                {key: value for key, value in params.items() if key in DEFAULTS}
            )
        updated_params["allowed_languages"] = tuple(updated_params["allowed_languages"])
        super().__init__(run_id=run_id, params=updated_params)
        self.cfg = updated_params

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        samples, skipped = self._collect_samples(doc)
        stats = self._analyze_samples(samples)

        # Store analysis for debugging/testing
        self.last_analysis = dict(stats)
        self.last_analysis["skipped"] = skipped

        findings: List[Finding] = []

        total_candidates = len(samples) + skipped
        if (
            total_candidates >= self._MIN_CANDIDATES_FOR_RELIABILITY
            and len(samples) / total_candidates < 0.4
        ):
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="language_unreliable",
                    title="Language detection unreliable",
                    message=(
                        "Most blocks were too short or ambiguous for reliable language detection."
                    ),
                    severity_rank=1,
                    confidence=0.45,
                    tags=["language", "analysis"],
                    extra_evidence=[
                        Stat(name="samples_used", value=len(samples)),
                        Stat(name="samples_skipped", value=skipped),
                    ],
                )
            )

        if not samples:
            return findings

        findings.extend(self._detect_wrong_language(doc, doc_hash, stats))
        findings.extend(self._detect_mixed_languages(doc, doc_hash, stats))

        return findings

    # --- helpers -----------------------------------------------------------------

    def _collect_samples(self, doc: Document) -> Tuple[List[LanguageSample], int]:
        """Collect language samples from text-heavy blocks."""
        samples: List[LanguageSample] = []
        skipped = 0
        candidate_types = {"Paragraph", "Heading", "Quote", "List"}

        for block in doc.blocks:
            if block.type not in candidate_types:
                continue

            text = self._extract_text_from_block(block).strip()
            if len(text) < self.cfg["min_chars_per_sample"]:
                skipped += 1
                continue

            alpha_chars = sum(ch.isalpha() for ch in text)
            if alpha_chars < self._MIN_ALPHA_CHARS:
                skipped += 1
                continue
            if alpha_chars / max(1, len(text)) < self._MIN_ALPHA_RATIO:
                skipped += 1
                continue

            try:
                predictions = detect_langs(text)
            except LangDetectException:
                skipped += 1
                continue
            if not predictions:
                skipped += 1
                continue

            top = None
            for pred in predictions:
                if top is None or pred.prob > top.prob:
                    top = pred

            if top.prob < self.cfg["min_lang_prob"]:
                skipped += 1
                continue

            lang = top.lang

            samples.append(
                LanguageSample(
                    block=block,
                    lang=lang,
                    prob=float(top.prob),
                    char_len=alpha_chars,
                )
            )
            if len(samples) >= self.cfg["max_samples"]:
                break

        return samples, skipped

    def _analyze_samples(self, samples: List[LanguageSample]) -> Dict[str, Any]:
        """Compute aggregated language statistics from samples."""
        counts = self._aggregate_weights(samples)
        total_chars = int(sum(counts.values()))
        primary_lang = counts.most_common(1)[0][0] if counts else None
        switch_count = self._count_switches(samples)
        runs = self._segment_language_runs(samples)

        longest_alt_run = None
        if primary_lang is not None:
            best_len = -1
            for run in runs:
                if run["lang"] == primary_lang:
                    continue
                if run["char_len"] > best_len:
                    best_len = run["char_len"]
                    longest_alt_run = run

        return {
            "samples": samples,
            "counts": counts,
            "total_chars": total_chars,
            "primary_lang": primary_lang,
            "switch_count": switch_count,
            "longest_alt_run": longest_alt_run,
        }

    def _detect_wrong_language(
        self, doc: Document, doc_hash: str, stats: Dict[str, Any]
    ) -> List[Finding]:
        allowed = set(self.cfg["allowed_languages"])
        counts: Counter = stats["counts"]
        total: int = stats["total_chars"]

        offending = {}
        for lang, weight in counts.items():
            if lang not in allowed:
                offending[lang] = weight

        if not offending:
            return []

        offending_ratio = sum(offending.values()) / total
        if offending_ratio < self.cfg["min_offending_ratio"]:
            return []

        confidence = min(0.99, 0.55 + offending_ratio)
        details = []
        for lang, cnt in offending.items():
            details.append(lang + " (" + str(cnt) + ")")
        details_str = ", ".join(details)

        allowed_list = []
        for lang in self.cfg["allowed_languages"]:
            allowed_list.append(lang)
        allowed_str = ", ".join(allowed_list)

        msg = (
            "Detected unsupported languages: "
            + details_str
            + ". Allowed languages: "
            + allowed_str
            + "."
        )

        return [
            self.emit(
                doc=doc,
                doc_hash=doc_hash,
                slug="wrong_language",
                title="Document uses unsupported language",
                message=msg,
                severity_rank=2,
                confidence=confidence,
                tags=["language", "policy"],
                extra_evidence=[
                    Stat(name="sampled_chars", value=total),
                    Stat(name="unsupported_ratio", value=round(offending_ratio, 2)),
                    Stat(name="lang_weights", value=str(dict(counts))),
                ],
            )
        ]

    def _detect_mixed_languages(
        self, doc: Document, doc_hash: str, stats: Dict[str, Any]
    ) -> List[Finding]:
        counts: Counter = stats["counts"]
        if len(counts) <= 1:
            return []

        total: int = stats["total_chars"]
        primary_lang: Optional[str] = stats["primary_lang"]
        samples: List[LanguageSample] = stats["samples"]

        primary_weight = counts.get(primary_lang, 0)
        non_primary_weight = total - primary_weight
        non_primary_ratio = non_primary_weight / total if total else 0.0

        if len(samples) < self.cfg["min_mix_samples"]:
            return []
        if total < self.cfg["min_mix_total_chars"]:
            return []

        longest_alt_run = stats["longest_alt_run"]
        longest_alt_ratio = (
            longest_alt_run["char_len"] / total if longest_alt_run and total else 0.0
        )

        switch_count: int = stats["switch_count"]
        switch_ratio = (
            switch_count / max(1, len(samples) - 1) if len(samples) > 1 else 0.0
        )

        distribution_trigger = non_primary_weight >= self._MIN_MIX_CHAR_SHARE and (
            non_primary_ratio >= self.cfg["mixing_ratio_threshold"]
            or switch_count >= self.cfg["switch_threshold"]
        )

        segment_trigger = (
            bool(longest_alt_run)
            and longest_alt_run["char_len"] >= self._LONG_SEGMENT_MIN_CHARS
            and longest_alt_ratio >= self._LONG_SEGMENT_RATIO_THRESHOLD
        )

        if not (distribution_trigger or segment_trigger):
            return []

        confidence = 0.5
        if distribution_trigger:
            confidence = max(
                confidence, 0.5 + 0.45 * max(non_primary_ratio, switch_ratio)
            )
        if segment_trigger:
            confidence = max(confidence, 0.5 + 0.45 * longest_alt_ratio)
        confidence = min(0.95, confidence)

        message_parts = [
            f"Primary language {primary_lang.upper()} covers {primary_weight}/{total} chars."
        ]
        if distribution_trigger:
            message_parts.append(
                f"Other languages contribute {non_primary_weight}/{total} chars (~{non_primary_ratio:.0%}) with {switch_count} language switches."
            )
        if segment_trigger and longest_alt_run:
            message_parts.append(
                f"Detected a contiguous {longest_alt_run['lang'].upper()} run of ~{longest_alt_run['char_len']} chars (~{longest_alt_ratio:.0%}) across {longest_alt_run['blocks']} blocks."
            )

        return [
            self.emit(
                doc=doc,
                doc_hash=doc_hash,
                slug="mixed_languages",
                title="Document mixes multiple languages",
                message=" ".join(message_parts),
                severity_rank=2,
                confidence=confidence,
                tags=["language", "consistency"],
                extra_evidence=[
                    Stat(name="sampled_chars", value=total),
                    Stat(name="primary_language", value=primary_lang),
                    Stat(name="non_primary_ratio", value=round(non_primary_ratio, 2)),
                    Stat(name="language_switches", value=switch_count),
                    Stat(name="lang_counts", value=str(dict(counts))),
                    Stat(
                        name="longest_alt_run_chars",
                        value=(longest_alt_run["char_len"] if longest_alt_run else 0),
                    ),
                    Stat(
                        name="longest_alt_run_ratio",
                        value=round(longest_alt_ratio, 2),
                    ),
                ],
            )
        ]

    @staticmethod
    def _count_switches(samples: List[LanguageSample]) -> int:
        switches = 0
        previous_lang: Optional[str] = None
        for sample in samples:
            if previous_lang is None:
                previous_lang = sample.lang
                continue
            if sample.lang != previous_lang:
                switches += 1
            previous_lang = sample.lang
        return switches

    def _aggregate_weights(self, samples: List[LanguageSample]) -> Counter:
        counts = Counter()
        for sample in samples:
            counts[sample.lang] += sample.char_len
        return counts

    @staticmethod
    def _segment_language_runs(samples: List[LanguageSample]) -> List[Dict[str, Any]]:
        runs: List[Dict[str, Any]] = []
        current_lang: Optional[str] = None
        current_chars = 0
        current_blocks = 0

        for sample in samples:
            if sample.lang == current_lang:
                current_chars += sample.char_len
                current_blocks += 1
            else:
                if current_lang is not None:
                    runs.append(
                        {
                            "lang": current_lang,
                            "char_len": current_chars,
                            "blocks": current_blocks,
                        }
                    )
                current_lang = sample.lang
                current_chars = sample.char_len
                current_blocks = 1

        if current_lang is not None:
            runs.append(
                {
                    "lang": current_lang,
                    "char_len": current_chars,
                    "blocks": current_blocks,
                }
            )

        return runs

"""Integrity analyser: detect spec-copied text via sentence embeddings.

Author: Matúš Csirik

Responsible for AC:
- 'COPY': Significant overlap with the official assignment specification,
  indicating text was copied or closely paraphrased rather than written
  independently.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field

from ..schemas.base import StrictModel
from ..schemas.finding import Anchor, FineRef, ModelEval, Stat
from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from ..schemas.document import Document
    from ..schemas.finding import Finding
    from ..schemas.llm import LLMRule, Rulebook

logger = logging.getLogger(__name__)

# -- Embedding model --------------------------------------------------------
EMBEDDING_MODEL: str = "BAAI/bge-m3"

# -- Similarity thresholds --------------------------------------------------
CHUNK_SIM_THRESHOLD: float = 0.80
DOC_COPY_THRESHOLD: float = 0.25
SPEC_COVERAGE_THRESHOLD: float = 0.65
SPEC_COVERAGE_DOC_THRESHOLD: float = 0.24

SOFT_SENTENCE_THRESHOLD: float = 0.75
HARD_SENTENCE_THRESHOLD: float = 0.90

LETHAL_CHUNK_THRESHOLD: float = 0.95
LETHAL_SENTENCE_THRESHOLD: float = 0.95

# -- Structural constants ---------------------------------------------------
MIN_USABLE_CHUNKS: int = 3
MIN_OUTPUT_CONFIDENCE: float = 0.20
TOP_K_ANCHORS: int = 5
MIN_SENTENCE_LEN: int = 20

# -- Filtering patterns -----------------------------------------------------
TITLE_RE = re.compile(
    r"^(implementa[cv]n[iy]|dokumentace|student|login|jmeno|xlogin|zadani)",
    re.IGNORECASE,
)
TOC_RE = re.compile(r"^\s*(\d+\.)+\s*$")
YEAR_RE = re.compile(r"(20\d{2}\s*/\s*20\d{2}|IPP\s*20\d{2})", re.IGNORECASE)


# -- Data containers --------------------------------------------------------


@dataclass
class TextUnit:
    """A segment of text with a reference to its source DocItem."""

    text: str
    cref: str | None = None


@dataclass
class SpecIndex:
    """Pre-computed spec embeddings and text units."""

    chunk_units: list[TextUnit] = field(default_factory=list)
    sentence_units: list[TextUnit] = field(default_factory=list)
    chunk_vecs: Any = None  # NDArray[np.float32]
    sentence_vecs: Any = None  # NDArray[np.float32]


class ScoredResult(StrictModel):
    """All intermediate scores for one student-vs-spec comparison."""

    # Chunk-level
    contamination_score: float = 0.0
    cont_triggered: bool = False
    spec_coverage_score: float = 0.0
    cov_triggered: bool = False
    n_flagged: int = 0
    n_total: int = 0
    max_student_sim: float = 0.0

    # Sentence-level
    n_soft_candidates: int = 0
    max_sentence_sim: float = 0.0
    n_sentences_above_soft: int = 0

    # Corroboration
    n_corroborated: int = 0

    # Aggregate
    has_similarity_evidence: bool = False

    # Per-unit detail for anchor building
    flagged_chunks: list[dict[str, Any]] = Field(default_factory=list)
    hard_sentences: list[dict[str, Any]] = Field(default_factory=list)


# -- Module-level singletons ----------------------------------------
_model: Any = None
_stanza_pipeline: Any = None
_spec_cache: dict[str, SpecIndex] = {}
_tok_cache: dict[str, Any] = {}


def _get_model() -> Any:
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model %s ...", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Embedding model loaded")
    return _model


def _get_stanza() -> Any:
    """Lazy-load the stanza tokeniser for sentence boundary detection."""
    global _stanza_pipeline
    if _stanza_pipeline is None:
        import stanza

        logger.info("Loading stanza multilingual tokeniser ...")
        _stanza_pipeline = stanza.Pipeline(
            "multilingual",
            processors="langid",
            download_method=stanza.DownloadMethod.REUSE_RESOURCES,
            verbose=False,
        )
        logger.info("Stanza pipeline loaded")
    return _stanza_pipeline


def _encode(texts: list[str]) -> NDArray[np.float32]:
    """Encode texts into normalised dense vectors."""
    import numpy as np

    if not texts:
        return np.empty((0, 1024), dtype=np.float32)
    vecs = _get_model().encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vecs, dtype=np.float32)


# -- Text filtering ---------------------------------------------------------


def _is_boilerplate(text: str) -> bool:
    """Return True if text looks like a title, ToC line or identity block."""
    stripped = text.strip()
    return (
        not stripped
        or bool(TITLE_RE.search(stripped))
        or bool(TOC_RE.match(stripped))
        or (bool(YEAR_RE.match(stripped)) and len(stripped) < 80)
    )


def _clean_and_filter(text: str, min_len: int) -> str | None:
    """Return cleaned text or ``None`` if it should be skipped."""
    from ..document_parser import clean_pdf_text

    cleaned = clean_pdf_text(text).strip()
    if len(cleaned) < min_len or _is_boilerplate(cleaned):
        return None
    return cleaned


# -- Sentence splitting -----------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using stanza multilingual langid."""
    import stanza

    langid_doc = _get_stanza()(text)
    lang = langid_doc.lang or "cs"

    if lang not in _tok_cache:
        try:
            _tok_cache[lang] = stanza.Pipeline(
                lang,
                processors="tokenize",
                download_method=stanza.DownloadMethod.REUSE_RESOURCES,
                verbose=False,
            )
        except Exception:
            logger.debug(
                "Stanza model for '%s' unavailable, falling back to 'cs'",
                lang,
            )
            if "cs" not in _tok_cache:
                _tok_cache["cs"] = stanza.Pipeline(
                    "cs",
                    processors="tokenize",
                    download_method=stanza.DownloadMethod.REUSE_RESOURCES,
                    verbose=False,
                )
            _tok_cache[lang] = _tok_cache["cs"]

    doc = _tok_cache[lang](text)
    return [sent.text for sent in doc.sentences]


# -- Spec caching -----------------------------------------------------------


def _spec_cache_path(spec_path: Path) -> Path:
    """Return the path for the cached spec embeddings."""
    content_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()[:16]
    model_tag = EMBEDDING_MODEL.replace("/", "_")
    return spec_path.parent / f".integrity_cache_{model_tag}_{content_hash}.npz"


def _build_spec_index(spec_path: Path, min_chunk_len: int) -> SpecIndex:
    """Parse, chunk, sentence-split and embed the specification."""
    from ..document_parser import DocumentParser

    cache_key = str(spec_path.resolve())
    if cache_key in _spec_cache:
        return _spec_cache[cache_key]

    npz_path = _spec_cache_path(spec_path)
    spec_index = _try_load_spec_cache(npz_path)
    if spec_index is not None:
        _spec_cache[cache_key] = spec_index
        return spec_index

    logger.info("Parsing spec: %s", spec_path)
    parse_output = DocumentParser().parse(spec_path)
    if parse_output.ir is None:
        logger.warning("Failed to parse spec: %s", spec_path)
        empty = SpecIndex()
        _spec_cache[cache_key] = empty
        return empty

    chunk_units = _extract_chunks(parse_output.ir, min_chunk_len)
    sentence_units = _extract_sentences(parse_output.ir, min_chunk_len)
    logger.info(
        "Spec: %d chunks, %d sentences after filtering",
        len(chunk_units),
        len(sentence_units),
    )

    chunk_vecs = _encode([u.text for u in chunk_units])
    sentence_vecs = _encode([u.text for u in sentence_units])

    spec_index = SpecIndex(
        chunk_units=chunk_units,
        sentence_units=sentence_units,
        chunk_vecs=chunk_vecs,
        sentence_vecs=sentence_vecs,
    )
    _save_spec_cache(npz_path, spec_index)
    _spec_cache[cache_key] = spec_index
    return spec_index


def _try_load_spec_cache(npz_path: Path) -> SpecIndex | None:
    """Attempt to load cached spec embeddings from disk."""
    import numpy as np

    if not npz_path.exists():
        return None
    try:
        data = np.load(npz_path, allow_pickle=True)
        chunk_units = [
            TextUnit(text=t, cref=c)
            for t, c in zip(data["chunk_texts"], data["chunk_crefs"])
        ]
        sentence_units = [
            TextUnit(text=t, cref=c)
            for t, c in zip(data["sentence_texts"], data["sentence_crefs"])
        ]
        logger.info("Loaded spec cache from %s", npz_path)
        return SpecIndex(
            chunk_units=chunk_units,
            sentence_units=sentence_units,
            chunk_vecs=data["chunk_vecs"],
            sentence_vecs=data["sentence_vecs"],
        )
    except Exception:
        logger.debug("Failed to load spec cache %s, will recompute", npz_path)
        return None


def _save_spec_cache(npz_path: Path, index: SpecIndex) -> None:
    """Save spec embeddings to an .npz file."""
    import numpy as np

    try:
        np.savez_compressed(
            npz_path,
            chunk_texts=[u.text for u in index.chunk_units],
            chunk_crefs=[u.cref or "" for u in index.chunk_units],
            sentence_texts=[u.text for u in index.sentence_units],
            sentence_crefs=[u.cref or "" for u in index.sentence_units],
            chunk_vecs=index.chunk_vecs,
            sentence_vecs=index.sentence_vecs,
        )
        logger.info("Saved spec cache to %s", npz_path)
    except Exception:
        logger.debug("Failed to save spec cache to %s", npz_path, exc_info=True)


# -- Text extraction ---------------------------------------------------


def _extract_chunks(doc: Document, min_chunk_len: int) -> list[TextUnit]:
    """Extract chunks from a parsed document using Docling HybridChunker."""
    from docling_core.transforms.chunker.hybrid_chunker import HybridChunker

    units: list[TextUnit] = []
    for chunk in HybridChunker(merge_peers=True).chunk(doc.docling_doc):
        cleaned = _clean_and_filter(chunk.text, min_chunk_len)
        if cleaned is None:
            continue
        cref = None
        doc_items = getattr(chunk.meta, "doc_items", None)
        if doc_items:
            cref = doc_items[0].get_ref().cref
        units.append(TextUnit(text=cleaned, cref=cref))
    return units


def _extract_sentences(doc: Document, min_len: int) -> list[TextUnit]:
    """Extract sentences from all text items using stanza SBD."""
    from docling_core.types.doc.document import TextItem

    units: list[TextUnit] = []
    effective_min = max(min_len, MIN_SENTENCE_LEN)
    for item, _ in doc.docling_doc.iterate_items():
        if not isinstance(item, TextItem):
            continue
        if not item.text or not item.text.strip():
            continue
        cref = item.get_ref().cref
        for sent in _split_sentences(item.text):
            cleaned = _clean_and_filter(sent, effective_min)
            if cleaned is not None:
                units.append(TextUnit(text=cleaned, cref=cref))
    return units


# -- Similarity computation -------------------------------------------------


def _compute_scores(
    student_chunk_units: list[TextUnit],
    student_sentence_units: list[TextUnit],
    spec_index: SpecIndex,
) -> ScoredResult:
    """Compute all similarity signals from student vs spec embeddings."""
    from sklearn.metrics.pairwise import cosine_similarity

    n_chunks = len(student_chunk_units)
    if n_chunks == 0 or spec_index.chunk_vecs.shape[0] == 0:
        return ScoredResult(n_total=n_chunks)

    student_chunk_vecs = _encode([u.text for u in student_chunk_units])
    student_sent_vecs = _encode([u.text for u in student_sentence_units])

    # Chunk-level similarity
    chunk_sim = cosine_similarity(student_chunk_vecs, spec_index.chunk_vecs)
    max_sim_student = chunk_sim.max(axis=1)

    flagged_mask = max_sim_student > CHUNK_SIM_THRESHOLD
    n_flagged = int(flagged_mask.sum())
    contamination_score = float(flagged_mask.mean())
    cont_triggered = contamination_score >= DOC_COPY_THRESHOLD
    max_student_sim = float(max_sim_student.max())

    # Spec coverage
    max_sim_spec = chunk_sim.max(axis=0)
    cov_mask = max_sim_spec > SPEC_COVERAGE_THRESHOLD
    spec_coverage_score = float(cov_mask.mean())
    cov_triggered = spec_coverage_score >= SPEC_COVERAGE_DOC_THRESHOLD

    flagged_chunks: list[dict[str, Any]] = sorted(
        [
            {
                "student_idx": i,
                "student_text": student_chunk_units[i].text,
                "student_cref": student_chunk_units[i].cref,
                "sim": float(max_sim_student[i]),
                "spec_text": spec_index.chunk_units[int(chunk_sim[i].argmax())].text,
            }
            for i in range(n_chunks)
            if flagged_mask[i]
        ],
        key=lambda x: x["sim"],
        reverse=True,
    )

    # Sentence-level similarity
    n_soft = 0
    max_sentence_sim = 0.0
    hard_sentences: list[dict[str, Any]] = []
    n_sents = len(student_sentence_units)

    if n_sents > 0 and spec_index.sentence_vecs.shape[0] > 0:
        sent_sim = cosine_similarity(student_sent_vecs, spec_index.sentence_vecs)
        max_sim_sents = sent_sim.max(axis=1)
        max_sentence_sim = float(max_sim_sents.max())
        n_soft = int((max_sim_sents > SOFT_SENTENCE_THRESHOLD).sum())
        hard_mask = max_sim_sents > HARD_SENTENCE_THRESHOLD

        hard_sentences = sorted(
            [
                {
                    "student_idx": i,
                    "student_text": student_sentence_units[i].text,
                    "student_cref": student_sentence_units[i].cref,
                    "sim": float(max_sim_sents[i]),
                    "spec_text": spec_index.sentence_units[
                        int(sent_sim[i].argmax())
                    ].text,
                }
                for i in range(n_sents)
                if hard_mask[i]
            ],
            key=lambda x: x["sim"],
            reverse=True,
        )

    # Sentence within chunk
    hard_sent_crefs = {s["student_cref"] for s in hard_sentences if s["student_cref"]}
    n_corroborated = sum(
        1 for fc in flagged_chunks if fc.get("student_cref") in hard_sent_crefs
    )

    return ScoredResult(
        contamination_score=contamination_score,
        cont_triggered=cont_triggered,
        spec_coverage_score=spec_coverage_score,
        cov_triggered=cov_triggered,
        n_flagged=n_flagged,
        n_total=n_chunks,
        max_student_sim=max_student_sim,
        n_soft_candidates=n_soft,
        max_sentence_sim=max_sentence_sim,
        n_sentences_above_soft=len(hard_sentences),
        n_corroborated=n_corroborated,
        has_similarity_evidence=n_flagged > 0 or n_soft > 0,
        flagged_chunks=flagged_chunks,
        hard_sentences=hard_sentences,
    )


# -- IntegrityAnalyser ------------------------------------------------------


class IntegrityAnalyser(BaseLLMAnalyser):
    """Detect text copied from the official spec using sentence embeddings.

    AC code: COPY
    """

    analyser_id: ClassVar[str] = "integrity_analyser"
    name: ClassVar[str] = "Integrity Analyser"

    def build_system_prompt(
        self,
        rules: list[LLMRule],
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Extend the grader prompt with the assignment spec text for COPY checks."""
        system_prompt = super().build_system_prompt(rules, rulebook, params)

        has_copy_rule = any(r.ac_code == "COPY" for r in rules)
        if has_copy_rule and (params or {}).get("spec_path"):
            from ..document_parser import DocumentParser

            spec_path = Path(params["spec_path"])  # type: ignore
            try:
                spec_parse = DocumentParser().parse(spec_path)
                if spec_parse.ir is not None:
                    from docling_core.types.doc.document import (
                        TextItem,
                    )

                    spec_text = "".join(
                        item.text + "\n"
                        for item, _ in spec_parse.ir.docling_doc.iterate_items()
                        if isinstance(item, TextItem) and item.text
                    )
                    system_prompt += (
                        "\n\n### ASSIGNMENT SPECIFICATION"
                        " (For COPY rule comparison)\n" + spec_text
                    )
                    logger.debug(
                        "Appended spec text (%d chars) to grader prompt",
                        len(spec_text),
                    )
            except Exception as exc:
                logger.warning("Could not load spec for COPY rule comparison: %s", exc)

        return system_prompt

    def get_rules(
        self,
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> list[LLMRule]:
        rules = super().get_rules(rulebook, params)
        if (params or {}).get("copy_engine", "local") == "local":
            rules = [r for r in rules if r.ac_code != "COPY"]
        return rules

    def analyse(
        self,
        doc: Document,
        rulebook: Rulebook | None = None,
        params: dict[str, Any] | None = None,
        llm_client: Any | None = None,
    ) -> list[Finding]:
        findings = list(super().analyse(doc, rulebook, params, llm_client))
        if (params or {}).get("copy_engine", "local") == "local":
            findings.extend(self._run_local_analysis(doc, params))
        return findings

    def _run_local_analysis(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        """Run the integrity pipeline and return COPY findings if warranted."""
        scored = self.score_document(doc, params)
        if scored is None:
            return []

        confidence = self._calculate_confidence(scored)
        if not scored.has_similarity_evidence or confidence < MIN_OUTPUT_CONFIDENCE:
            return []

        return self._build_findings(doc, scored, confidence)

    def score_document(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> ScoredResult | None:
        """Score a document against the spec and return the raw result."""
        params = params or {}
        spec_path_str = params.get("spec_path")
        if not spec_path_str:
            logger.warning("No spec_path provided in params, skipping integrity check")
            return None

        spec_path = Path(spec_path_str)
        if not spec_path.exists():
            logger.warning("Spec file does not exist: %s", spec_path)
            return None

        min_chunk_len: int = params.get("min_chunk_len", 40)
        spec_index = _build_spec_index(spec_path, min_chunk_len)
        if not spec_index.chunk_units:
            logger.warning("Spec produced no usable chunks")
            return None

        student_chunks = _extract_chunks(doc, min_chunk_len)
        student_sentences = _extract_sentences(doc, min_chunk_len)

        if len(student_chunks) < MIN_USABLE_CHUNKS:
            logger.info(
                "Student has only %d usable chunks (min %d), skipping",
                len(student_chunks),
                MIN_USABLE_CHUNKS,
            )
            return ScoredResult(n_total=len(student_chunks))

        return _compute_scores(student_chunks, student_sentences, spec_index)

    # -- Confidence calculation ---------------------------------------------

    def _calculate_confidence(self, scored: ScoredResult) -> float:
        """Derive a single confidence score from the multi-signal scored result."""
        confidence = 0.0
        has_chunk_evidence = scored.n_flagged > 0 or scored.cont_triggered

        # Any near-verbatim chunk
        if scored.max_student_sim >= LETHAL_CHUNK_THRESHOLD:
            confidence = max(confidence, 0.80)

        # Contamination contribution (0.25..1.0 -> 0.30..0.70)
        if scored.cont_triggered:
            ratio = min(scored.contamination_score, 1.0)
            confidence = max(confidence, 0.30 + 0.40 * ratio)

        # Single-chunk base (below contamination threshold)
        if scored.n_flagged > 0 and not scored.cont_triggered:
            confidence = max(
                confidence,
                0.05 + (scored.max_student_sim - CHUNK_SIM_THRESHOLD) * 1.0,
            )

        # Hard sentence contribution (gated on chunk evidence or lethal sim)
        if scored.n_sentences_above_soft > 0:
            sent_boost = min(scored.n_sentences_above_soft * 0.08, 0.30)
            if has_chunk_evidence:
                confidence += 0.10 + sent_boost
            elif scored.max_sentence_sim >= LETHAL_SENTENCE_THRESHOLD:
                confidence = max(confidence, 0.20 + sent_boost)

        # Localised flagged chunk backed by soft sentences
        localised = scored.n_flagged > 0 and scored.n_soft_candidates >= 1
        if localised:
            extra = min((scored.n_soft_candidates - 1) * 0.05, 0.20)
            confidence = max(confidence, 0.15 + extra)

        # Soft-sentence cluster (gated on chunk evidence or high count)
        if scored.n_soft_candidates >= 3:
            soft_base = 0.12 + min((scored.n_soft_candidates - 3) * 0.04, 0.18)
            if has_chunk_evidence or scored.n_soft_candidates >= 6:
                confidence = max(confidence, soft_base)

        # Corroboration boost (requires strong base)
        if scored.n_corroborated > 0 and (
            scored.cont_triggered or scored.n_flagged >= 2
        ):
            confidence += min(scored.n_corroborated * 0.10, 0.25)

        # Coverage additive boost
        if scored.cov_triggered:
            confidence += 0.05

        # Multi-trigger multiplier
        triggers_fired = sum(
            [
                scored.cont_triggered,
                scored.n_sentences_above_soft > 0 and has_chunk_evidence,
                scored.n_corroborated > 0,
                scored.max_student_sim >= LETHAL_CHUNK_THRESHOLD,
                localised,
                scored.n_soft_candidates >= 3 and has_chunk_evidence,
            ]
        )
        if triggers_fired >= 2:
            confidence *= 1.10
        if triggers_fired >= 3:
            confidence *= 1.10

        return min(confidence, 1.0)

    # -- Finding construction -----------------------------------------------

    def _build_findings(
        self,
        doc: Document,
        scored: ScoredResult,
        confidence: float,
    ) -> list[Finding]:
        """Build COPY finding(s) from the scored result."""
        severity = self._calculate_severity(scored)
        notes = self._build_trigger_notes(scored)

        summary = (
            f"Detected similarity with the official specification: "
            f"contamination={scored.contamination_score:.2f}, "
            f"coverage={scored.spec_coverage_score:.2f}, "
            f"{scored.n_flagged}/{scored.n_total} chunks flagged, "
            f"{scored.n_sentences_above_soft} hard sentence matches"
        )

        anchor_sources = self._pick_anchor_sources(scored, doc)
        finding = self._make_finding(
            doc=doc,
            ac_code="COPY",
            title="Specification text detected",
            summary=summary,
            judge_status="to_be_judged",
            human_status="proposed",
            evidence_item=anchor_sources[0]["item"] if anchor_sources else None,
            snippet_override=anchor_sources[0]["student_text"][:300]
            if anchor_sources
            else None,
            severity=severity,
            confidence=confidence,
        )

        for src in anchor_sources[1:TOP_K_ANCHORS]:
            item = src["item"]
            if item is None:
                continue
            cref = item.get_ref().cref
            finding.anchors.append(
                Anchor(
                    target=FineRef.model_validate({"$ref": cref}),
                    snippet=src["student_text"][:300],
                    prov=list(item.prov),
                    section_path=doc.section_paths.get(cref),
                )
            )

        finding.model_evals = [
            ModelEval(
                model_name=EMBEDDING_MODEL,
                label=src["label"],
                score=round(src["sim"], 4),
                raw={"spec_text": src["spec_text"]},
            )
            for src in anchor_sources
        ]

        finding.stats = [
            Stat(
                name="contamination_score",
                value=round(scored.contamination_score, 4),
            ),
            Stat(
                name="spec_coverage_score",
                value=round(scored.spec_coverage_score, 4),
            ),
            Stat(name="n_flagged_chunks", value=scored.n_flagged),
            Stat(name="n_total_chunks", value=scored.n_total),
            Stat(name="max_chunk_sim", value=round(scored.max_student_sim, 4)),
            Stat(name="n_hard_sentences", value=scored.n_sentences_above_soft),
            Stat(name="n_corroborated", value=scored.n_corroborated),
            Stat(name="max_sentence_sim", value=round(scored.max_sentence_sim, 4)),
        ]

        finding.notes = notes
        return [finding]

    def _calculate_severity(self, scored: ScoredResult) -> float:
        """Derive severity from how much and how closely text was copied."""
        if scored.max_student_sim >= LETHAL_CHUNK_THRESHOLD:
            return min(0.85 + scored.contamination_score * 0.15, 1.0)
        if scored.cont_triggered and scored.n_corroborated > 0:
            return min(0.60 + scored.contamination_score * 0.30, 0.90)
        if scored.cont_triggered:
            return min(0.40 + scored.contamination_score * 0.30, 0.75)
        if scored.n_sentences_above_soft > 0:
            return min(0.30 + scored.n_sentences_above_soft * 0.05, 0.60)
        return 0.20

    def _build_trigger_notes(self, scored: ScoredResult) -> list[str]:
        """Build human-readable notes about which triggers fired."""
        notes: list[str] = []

        if scored.max_student_sim >= LETHAL_CHUNK_THRESHOLD:
            notes.append(
                f"Near-verbatim chunk detected (sim={scored.max_student_sim:.3f})"
            )

        if scored.cont_triggered:
            notes.append(
                f"Contamination triggered: {scored.contamination_score:.3f} "
                f">= {DOC_COPY_THRESHOLD}"
            )

        if scored.n_sentences_above_soft > 0:
            notes.append(
                f"{scored.n_sentences_above_soft} hard sentence match(es) "
                f"(max_sim={scored.max_sentence_sim:.3f})"
            )

        if scored.n_flagged > 0 and scored.n_soft_candidates >= 2:
            notes.append(
                f"Localised trigger: {scored.n_flagged} flagged chunk(s) "
                f"+ {scored.n_soft_candidates} soft sentence(s)"
            )

        if scored.n_soft_candidates >= 3:
            notes.append(
                f"Soft-sentence cluster: {scored.n_soft_candidates} "
                f"sentence(s) above {SOFT_SENTENCE_THRESHOLD}"
            )

        if scored.n_corroborated > 0:
            notes.append(
                f"{scored.n_corroborated} chunk(s) corroborated "
                f"by sentence-level evidence"
            )

        if scored.cov_triggered:
            notes.append(
                f"Spec coverage triggered: {scored.spec_coverage_score:.3f} "
                f">= {SPEC_COVERAGE_DOC_THRESHOLD}"
            )

        return notes

    def _pick_anchor_sources(
        self,
        scored: ScoredResult,
        doc: Document,
    ) -> list[dict[str, Any]]:
        """Select the top evidence items as anchors for the finding."""
        sources: list[dict[str, Any]] = []
        seen_crefs: set[str] = set()

        for entries, label in (
            (scored.flagged_chunks, "sim"),
            (scored.hard_sentences, "sent_sim"),
        ):
            for entry in entries:
                cref = entry.get("student_cref")
                if not cref or cref in seen_crefs:
                    continue
                from docling_core.types.doc.document import RefItem

                try:
                    item = RefItem.model_validate({"$ref": cref}).resolve(
                        doc=doc.docling_doc
                    )
                except Exception:
                    item = None
                if item is None:
                    continue
                seen_crefs.add(cref)
                sources.append(
                    {
                        "item": item,
                        "student_text": entry["student_text"],
                        "sim": entry["sim"],
                        "label": label,
                        "spec_text": entry["spec_text"],
                    }
                )
                if len(sources) >= TOP_K_ANCHORS:
                    return sources

        return sources

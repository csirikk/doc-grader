# Research Q4: Handling multiple languages in documentation

**Research question:** How do different languages (cz/sk/en) affect the evaluation process?

## 1. Introduction

The community of students at FIT is diverse, so IFJ and IPP allow submitting project documentation in Czech, Slovak or English. An effective automated evaluation tool must be robust across these languages.

## 2. Main points

- **General model language support:** Large models differ in quality across Czech, Slovak and English. English performance is usually strongest, Czech and Slovak may perform worse.
- **Prompting language mismatch:** Assignments and grading criteria are usually in Czech, but English prompts often yield better LLM performance.
- **Mixing languages:** Students frequently mix English technical terms inside Czech and Slovak documents. The tool must tolerate necessary technical terms while flagging unnecessary language switches.
- **Fairness and consistency:** A chosen approach must not systematically perform different across different languages.
- **Cost and latency:** Translation and heavyweight model calls add latency and API cost. Local light-weight steps should filter or batch work.
- **Error propagation risk:** Full-document translation introduces the risk that one mistranslation cascades into incorrect deductions.

## 3. Possible approaches

### Approach A: Language-agnostic multilingual model

A single powerful multilingual LLM processes all documents directly.

- **Process:**
    1. Send original text (cz/sk/en) with one English (or mixed) prompt.
    2. Collect detector outputs (sections present, possible copied spec text, style flags).
- **Pros:** One prompt set, fastest to prototype.
- **Cons:** Hidden performance gaps across languages, harder to calibrate fairness. Requires extensive manual validation of Czech and Slovak outputs due to risk of bias.

### Approach B: Language detector and language-specific prompts

Detect primary document language then use a prompt (and optionally few-shot examples) tailored to that language.

- **Process:**
    1. Lightweight language identification (fastText / langdetect) on text portions.
    2. Select prompt variant (cz/sk/en) for detectors needing natural language reasoning.
    3. Run detectors.
- **Pros:** Better alignment with source language. Clearer grading criteria phrasing. Potentially higher accuracy for nuances.
- **Cons:** Prompt set maintenance triples. Risk of drift between versions, still depends on multilingual model quality. Language bias.

### Approach C: Translate-to-english pipeline

Translate non-English documents to English, then run an English-optimized pipeline.

- **Process:**
    1. Language identification.
    2. If not English, machine translate full text (DeepL api, ...) retaining mapping to original spans (store offsets or parallel list of paragraphs).
    3. Run all detectors (mostly English-focused) on translated text, reference original for evidence snippets.
- **Pros:** Allows usage of only the strongest English models. Single detector implementation simplifies prompt tuning. Consistent grading logic.
- **Cons:** Translation errors can mislead detectors. Extra cost and latency. May lose formality or subtle style cues, requires alignment layer to cite original evidence reliably (which doesn't necessarily have to be too big of a problem if the format of the document is kept simple and restricted to specific sections).

### Approach D: Cross-lingual embeddings baseline (deterministic layer)

Use multilingual sentence/document embeddings (e.g., LaBSE, Distiluse multilingual, Instructor-xl multilingual) for language-agnostic similarity tasks before any LLM reasoning.

- **Process:**
    1. Pre-chunk spec into canonical segments (cz, sk, en) and embed once.
    2. Embed student document paragraphs with the same model.
    3. Perform cosine similarity to detect: required section presence, potential copied spec text (high overlap), semantic coverage of mandatory topics.
    4. Output structured findings with confidence scores; only ambiguous or missing items escalated to an LLM.
- **Pros:** Fast, inexpensive, language-agnostic. Fairness guaranteed. Reduced number of LLM calls. Reproducible scoring for structural checks.
- **Cons:** Limited to similarity-type detectors. Embeddings may conflate superficially related content. Requires threshold calibration per detector.

### Approach E: Selective translate-on-demand pipeline

Translate only the parts that actually require high-quality English reasoning (e.g., ambiguous sections, style analysis), leaving the rest processed via multilingual or embedding-based methods.

- **Process:**
    1. Run language identification + cross-lingual embedding checks (Approach D) over entire document.
    2. Flag paragraphs requiring nuanced evaluation (style, clarity, justification of design decisions) or with low similarity confidence.
    3. Translate only those flagged paragraphs and run English LLM detectors.
    4. Combine results with embedding-based structural findings.
- **Pros:** Reduces translation cost and error surface, preserves original language for most content; focuses expensive reasoning where needed; easier audit (only a subset translated).
- **Cons:** Requires routing logic and confidence thresholds; potential inconsistency if translated and non-translated segments are judged differently.

## 4. AI generated comparison summary

| Approach | Added engineering complexity           | Cost efficiency                | Fairness / reproducibility               | Primary risk           |
|----------|----------------------------------------|--------------------------------|------------------------------------------|------------------------|
| A        | Very low                               | Medium (LLM for all)           | Medium (opaque variance)                 | Silent quality gaps    |
| B        | Medium (multiple prompts)              | Medium                         | Medium (needs parity tests)              | Maintenance overhead   |
| C        | Medium (translation + mapping)         | Low/Medium (extra translation) | High (single logic)                      | Translation distortion |
| D        | Low (embedding pipeline)               | High (cheap)                   | High (deterministic)                     | Threshold tuning       |
| E        | Medium (routing + partial translation) | High (minimized API use)       | High (deterministic core + targeted LLM) | Routing errors         |

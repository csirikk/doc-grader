# Tool overview

Grading assistant for IFJ/IPP student project documentation.

## 1. Motivation

Manual grading of student documentation is slow and inconsistent across years and graders. This tool analyses submitted PDFs or Markdown files against a set of assessment criteria (AC codes) and produces machine-readable findings with evidence anchors that graders can review, confirm, or dismiss.

## 2. Inputs and Outputs

Inputs:

| Item        | Format                      | Notes                                              |
|-------------|-----------------------------|----------------------------------------------------|
| Student doc | `.pdf` or `.md` or a folder | -                                                  |
| App config  | `config/default.json`       | Enabled analysers, model overrides, course.        |
| Rulebook    | `config/rulebook.json`      | LLM prompt templates and per-AC rule instructions. |
| Course tag  | `"ipp"` or `"ifj"`          | Filters which AC rules and thresholds apply.       |

Outputs:

Per student, written to `out/<student_id>/`

| File                   | Contents                                                        |
|------------------------|-----------------------------------------------------------------|
| `ir.json`              | IR document (stats, metadata, `doc_ref`)                        |
| `docling.json`         | Raw Docling `DoclingDocument`                                   |
| `parser_findings.json` | Findings from parsing (missing file, unsupported format, ...)   |
| `raw_findings.json`    | All analyser findings before judge pass                         |
| `judged_findings.json` | Findings after judge approval/dismissal                         |
| `findings.json`        | Final findings after `RuleEngine` filtering                     |
| `info.json`            | Run metadata and `RuleEngine` summary statistics                |
| CSV (optional)         | Findings in the same schema as ground-truth assessment datasets |

## 3. Pipeline

```txt
Input (.pdf / .md)
       |
       v
DocumentParser [Docling]
       |  ParseOutput { ir: Document, parser_findings }
       v
Analysers
  - StructureAnalyser, ...                                 [heuristics]
  - LLM Analysers ----------> LLMClient.analyse_document() [grader model]
       |  (AssetAnalyser) --> LLMClient.analyse_assets()   [vision model]
       |
       v  raw findings (judge_status = "to_be_judged" | "not_to_be_judged")
RuleEngine.prepare_judge_batch()
       |
       v  judgeable findings
LLMClient.judge_findings()                              [judge model]
       |
       v
RuleEngine.apply_judge_response()
       |  updates judge_status: "judged_approved" | "judged_adjusted" | "judged_dismissed"
       v
RuleEngine.process()
       |  drops judged_dismissed, deduplicates
       v
Final findings -> JSON + optional CSV
```

## 4. Modules

### 4.1 Parser (`doc_grader/parsers/parser.py`)

`DocumentParser` wraps Docling's `DocumentConverter`. It accepts `.pdf` and `.md` and returns a `ParseOutput`:

- `ir: Document` - the converted document plus stats.
- `parser_findings` - problems found during parsing (missing file, unsupported type, empty content).

PDF pipeline options: OCR (`ces`/`eng`/`slk`), table structure extraction with cell matching, picture image generation, and full page image generation. Page images are sent alongside diagrams to the vision model for layout context.

The parser builds a section-path map and collects Markdown image URIs. Text items remain accessible via the embedded `DoclingDocument`:

- `section_paths: dict[cref, str]` - heading-path string for every text item (e.g. "Introduction > Lexical Analysis"), injected into the LLM prompt as `[Section: ...]` prefixes.
- `md_image_uris: list[str]` - ordered image URIs extracted when the source is Markdown (used to resolve local images).

### 4.2 Intermediate Representation (`doc_grader/schemas/ir.py`)

`Document` is a Pydantic `StrictModel` wrapping a `DoclingDocument` with additional metadata:

```txt
Document
+ doc_ref: DocumentRef (source path, binary_hash, Docling origin)
+ docling_doc: DoclingDocument
+ total_words / total_chars / total_paragraphs / total_headings
+ total_pictures: int
+ md_image_uris: list[str]
+ section_paths: dict[cref -> str]
```

`DoclingDocument` preserves the full typed-block structure (`SectionHeaderItem`, `TextItem`, `TableItem`, `PictureItem`) with provenance (page number, bounding box) on every node.

### 4.3 Analysers (`doc_grader/analysers/`)

All analysers implement `BaseAnalyser.analyse(doc, params) -> list[Finding]`.

#### Deterministic

| Analyser            | AC codes          | Method                                                             |
| ------------------- | ----------------- | ------------------------------------------------------------------ |
| `StructureAnalyser` | `SHORT`, `KAPTXT` | Heuristic thresholds calibrated on historical data; heading scan   |

- `SHORT`: flagged when word count < 486, char count < 3422, or heading count < 7 (covers ~90% of historically short submissions).
- `KAPTXT`: iterates all `SectionHeaderItem` nodes, severity depends on the relationship between adjacent heading levels (sibling, parent->child, child->parent).

Deterministic findings set `judge_status = "to_be_judged"` when they are meant to be reviewed by the judge, and `judge_status = "not_to_be_judged"` when they should bypass the judge.

#### LLM-based

These analysers declare which rules they own via `get_rules(rulebook, params)` and post-process findings returned by `LLMClient`. Orchestration is in `_run_analysers()` in `__main__.py`.

| Analyser             | AC codes (representative)                                      | Notes                                    |
|----------------------|----------------------------------------------------------------|------------------------------------------|
| `content_analyser`   | `CH`, `ICH`, `TERM`, `LANG`, `STYLE`, `CONTENT`, `OOP`, `FILO` | Prose, content and design ACs            |
| `grammar_analyser`   | `CH`                                                           | LanguageTool local checks / LLM fallback |
| `integrity_analyser` | `COPY`                                                         | Spec-similarity via embeddings           |
| `asset_analyser`     | `BADUML`, `SEMUML`, `OWNDIF`, `BW`, `NOUML`                    | Vision + fine-tuned classifier           |

`AssetAnalyser` uses a separate vision path: page context images and each `PictureItem` are encoded and sent to the vision/classifier calls on `LLMClient`. Vision findings produced by the analyser are emitted as standard `Finding` objects (by default `judge_status = "to_be_judged"`) so they can be included in judge batches when a judge client is available.

### 4.4 LLM Client (`doc_grader/llm_client.py`)

`LLMClient` wraps the OpenAI Python client and uses structured response parsing into the Pydantic models defined in `doc_grader/schemas/llm.py`. When an `LLMClient` instance is available (the current CLI constructs it in `__main__.py` when `config.judge` is true) up to three distinct model interactions may occur per document:

#### Grader model (`analyse_document`)

Document text is serialised as a flat string with `[Ref: cref]` and `[Section: path]` prefixes per text item. The system prompt comes from `rulebook.grader_model_prompt_template` with active rules injected at the `{rules}` placeholder. Returns `GraderModelResponse { reasoning_chain, findings: list[LLMFinding] }`.

`LLMFinding` fields: `ac_code`, `item_cref` (pointer into the IR), `snippet`, `reason`, `severity`, `confidence`.

#### Vision model (`analyse_assets`)

Each picture and its page context are sent as multipart image messages. Prompt comes from `rulebook.vision_model_prompt_template`. Returns `VisionModelResponse { reasoning_chain, findings: list[VisionFinding] }`.

#### Judge model (`judge_findings`)

Receives the judgeable batch selected by `RuleEngine.prepare_judge_batch()`. Re-evaluates each finding against the source document and returns a structured judge response. The API client only handles the OpenAI call and response parsing; `RuleEngine` applies validation and verdicts.

### 4.5 Rule Engine (`doc_grader/rule_engine.py`)

`RuleEngine` handles finding validation and filtering:

1. `prepare_judge_batch()` keeps explicit judge states and only returns findings marked `to_be_judged` that still have evidence.
2. `apply_judge_response()` mutates findings in-place using judge verdicts.
3. `process(findings)` applies final filters in order:

- **Judge-dismissed** - drop (judge vetoed).
- **Deduplication** - drop if `finding_id` already seen in this run.

Returns `(final_findings, summary_dict)`. The summary (counts per drop reason, final count) is written to `info.json`.

### 4.6 Finding Schema (`doc_grader/schemas/finding.py`)

Every analyser produces `Finding` objects with the same schema:

```txt
Finding
+-- finding_id: str           # e.g. "STRUCTURE_ANALYSER:KAPTXT-1"
+-- ac_code: str              # assessment criterion code (e.g. "KAPTXT")
+-- title / summary: str
+-- severity: float [0-1]     # how serious the issue is
+-- confidence: float | None  # model certainty; None = deterministic
+-- judge_status: ...         # explicit judge lifecycle state
+-- human_status: ...         # explicit human review lifecycle state
+-- analyser: AnalyserInfo    # analyser_id, name, run_id, config_hash
+-- document: DocumentRef     # source file identity
+-- anchors: list[Anchor]     # cref + snippet + page/bbox provenance
+-- stats: list[Stat]         # numeric evidence (word counts, etc.)
+-- model_evals: list[ModelEval]
```

`Anchor.target` is a Docling `FineRef` (`$ref` cref string), pointing back into the `DoclingDocument`.

### 4.7 Config and Rulebook

**`AppConfig`** (`config/default.json`):

```json
{
  "course": "ipp",
  "judge": true,
  "judge_model": "gpt-5.4",
  "judge_temperature": 0.0,
  "analysers": [
    {
       "analyser_id": "structure_analyser",
       "enabled": true,
       "params": {
              "min_words": 486,
              "min_chars": 3422,
              "min_struct": 7
       }
    },
    {
       "analyser_id": "content_analyser",
       "enabled": true,
       "model": "gpt-5.4-nano",
       "temperature": 0.0,
       "params": {}
    },
    {
       "analyser_id": "asset_analyser",
       "enabled": true,
       "model": "gpt-5.4-nano",
       "temperature": 0.0,
       "params": {
              "classifier_model": "ft:gpt-4.1-2025-04-14:personal:baduml-classifier-gold:DU8txcxh"
       }
    },
    {
       "analyser_id": "integrity_analyser",
       "enabled": true,
       "params": {
              "spec_path": "data/ipp/spec/ipp2425spec.pdf",
              "min_chunk_len": 40,
              "copy_engine": "local"
       }
    },
    {
       "analyser_id": "grammar_analyser",
       "enabled": true,
       "params": {
              "grammar_engine": "local"
       }
    }
  ]
}
```

Each analyser entry can override the OpenAI model and pass arbitrary `params`. The `"course"` field filters rulebook rules: each `LLMRule` declares its `course` scope (`null` = both courses).

#### Rulebook (`config/rulebook.json`)

- `grader_model_prompt_template` - system prompt with a `{rules}` placeholder.
- `vision_model_prompt_template` - system prompt for the vision model.
- `judge_model_prompt` - judge system prompt.
- `rules: list[LLMRule]` - one entry per AC code group, each with `ac_codes`, `prompt_instruction`, `analyser_id`, `course`, and optional language scope.

## 5. CLI

```txt
doc-grader [options] <input> [<input> ...]

Options:
  -d, --debug         Enable debug logging
  -o, --out PATH      Output directory  (default: out/default/)
  -c, --config PATH   JSON config file  (default: config/default.json)
  --csv-out PATH      Write findings as CSV, compatible with ground-truth datasets
```

Multiple input files can be passed in one invocation. Each is processed independently with a shared parser and LLM client. Finding ID counters reset per document.

## 6. Dataset

Historical graded documentation for IPP and IFJ courses (2013-2024) is stored under `data/`. Assessment CSVs record per-document AC code deductions and serve as ground truth. The `--csv-out` flag produces findings in the same schema for direct comparison with human deductions.

# Tool overview

Grading assistant for IFJ/IPP student project documentation.

## 1. Motivation

Manual grading of student documentation is slow and inconsistent across years and graders. This tool analyses submitted PDFs or Markdown files against a set of assessment criteria (AC codes) and produces machine-readable findings with evidence anchors that graders can review, confirm, or dismiss.

## 2. Inputs and Outputs

Inputs:

| Item            | Format                 | Notes                                              |
| --------------- | ---------------------- | -------------------------------------------------- |
| Student doc     | `.pdf` or `.md`        | One or more files per invocation.                  |
| App config      | `config/default.json`  | Enabled analysers, model overrides, course.        |
| Rulebook        | `config/rulebook.json` | LLM prompt templates and per-AC rule instructions. |
| Course tag      | `"ipp"` or `"ifj"`     | Filters which AC rules and thresholds apply.       |

Outputs:

Per document, written to `out/<stem>/`

| File                   | Contents                                                           |
| ---------------------- | ------------------------------------------------------------------ |
| `ir.json`              | IR document (stats, metadata, `doc_ref`)                           |
| `docling.json`         | Raw Docling `DoclingDocument`                                      |
| `parser_findings.json` | Findings from parsing (missing file, unsupported format, ...)      |
| `raw_findings.json`    | All analyser findings before judge pass                            |
| `judged_findings.json` | Findings after judge approval/dismissal                            |
| `findings.json`        | Final findings after `RuleEngine` filtering                        |
| `info.json`            | Run metadata and `RuleEngine` summary statistics                   |
| CSV (optional)         | Findings in the same schema as ground-truth assessment datasets    |

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
       v  raw findings (status = "proposed" | "approved")
RuleEngine.prepare_judge_batch()
       |
       v  judgeable findings
LLMClient.judge_findings()                              [judge model]
       |
       v
RuleEngine.apply_judge_response()
       |  updates status: "approved" | "dismissed"
       v
RuleEngine.process()
       |  drops dismissed, low confidence, deduplicates
       v
Final findings -> JSON + optional CSV
```

## 4. Modules

### 4.1 Parser (`src/parsers/parser.py`)

`DocumentParser` wraps Docling's `DocumentConverter`. It accepts `.pdf` and `.md` and returns a `ParseOutput`:

- `ir: Document` - the converted document plus stats.
- `parser_findings` - problems found during parsing (missing file, unsupported type, empty content).

PDF pipeline options: OCR (`ces`/`eng`/`slk`), table structure extraction with cell matching, picture image generation, and full page image generation. Page images are sent alongside diagrams to the vision model for layout context.

The parser builds two index maps over all text items:

- `text_items: dict[cref, TextItem]` - used to anchor findings to exact document nodes.
- `section_paths: dict[cref, str]` - heading-path string for every text item (e.g. `"Introduction > Lexical Analysis"`), injected into the LLM prompt as `[Section: ...]` prefixes.

### 4.2 Intermediate Representation (`src/schemas/ir.py`)

`Document` is a Pydantic `StrictModel` wrapping a `DoclingDocument` with additional metadata:

```txt
Document
+ doc_ref: DocumentRef (source path, binary_hash, Docling origin)
+ docling_doc: DoclingDocument
+ total_words / total_chars / total_paragraphs / total_headings
+ text_items: dict[cref -> TextItem]
+ section_paths: dict[cref -> str]
```

`DoclingDocument` preserves the full typed-block structure (`SectionHeaderItem`, `TextItem`, `TableItem`, `PictureItem`) with provenance (page number, bounding box) on every node.

### 4.3 Analysers (`src/analysers/`)

All analysers implement `BaseAnalyser.analyse(doc, params) -> list[Finding]`.

#### Deterministic

| Analyser            | AC codes          | Method                                                             |
| ------------------- | ----------------- | ------------------------------------------------------------------ |
| `StructureAnalyser` | `SHORT`, `KAPTXT` | Heuristic thresholds calibrated on historical data; heading scan   |

- `SHORT`: flagged when word count < 486, char count < 3422, or heading count < 7 (covers ~90% of historically short submissions).
- `KAPTXT`: iterates all `SectionHeaderItem` nodes, severity depends on the relationship between adjacent heading levels (sibling, parent->child, child->parent).

Deterministic findings have `confidence = None` and are unconditionally approved, bypassing the judge.

#### LLM-based

These analysers declare which rules they own via `get_rules(rulebook, params)` and post-process findings returned by `LLMClient`. Orchestration is in `_run_analysers()` in `__main__.py`.

| Analyser          | AC codes (representative)                                                     | Notes                    |
|-------------------|-------------------------------------------------------------------------------|--------------------------|
| `TextAnalyser`    | `CH`, `ICH`, `TERM`, `LANG`                                                   | Proofreading, objective  |
| `StyleAnalyser`   | `STYLE`, `HOV`                                                                | Editorial, subjective    |
| `ContentAnalyser` | `CONTENT`, `SA`, `SAV`, `SeA`, `PSA`, `TS`, `GK`, `IR`, `JAK`, `NVPDOC`, `RP` | Section-level quality    |
| `DesignAnalyser`  | `OOP`, `NOOOP`, `NOSRP`, `DP`, `BADDP`, `SINGLETON`, `EXT`, `EX`, `FILO`      | OOP/architecture quality |
| `AssetAnalyser`   | `BADUML`, `OWNDIF`, `BW`                                                      | Vision model             |

`AssetAnalyser` uses a separate vision path, every `PictureItem` and its surrounding page image are base64-encoded and sent to `LLMClient.analyse_assets()`. Vision findings bypass the judge and are immediately `"approved"`.

### 4.4 LLM Client (`src/llm_client.py`)

`LLMClient` wraps OpenAI via `instructor`, which enforces structured Pydantic-validated responses. Three model calls are made per document:

#### Grader model (`analyse_document`)

Document text is serialised as a flat string with `[Ref: cref]` and `[Section: path]` prefixes per text item. The system prompt comes from `rulebook.grader_model_prompt_template` with active rules injected at the `{rules}` placeholder. Returns `GraderModelResponse { reasoning_chain, findings: list[LLMFinding] }`.

`LLMFinding` fields: `ac_code`, `item_cref` (pointer into the IR), `snippet`, `reason`, `severity`, `confidence`.

#### Vision model (`analyse_assets`)

Each picture and its page context are sent as multipart image messages. Prompt comes from `rulebook.vision_model_prompt_template`. Returns `VisionModelResponse { reasoning_chain, findings: list[VisionFinding] }`.

#### Judge model (`judge_findings`)

Receives the judgeable batch selected by `RuleEngine.prepare_judge_batch()`. Re-evaluates each finding against the source document and returns a structured judge response. The API client only handles the OpenAI call and response parsing; `RuleEngine` applies validation and verdicts.

### 4.5 Rule Engine (`src/rule_engine.py`)

`RuleEngine` handles finding validation and filtering:

1. `normalise_findings()` promotes deterministic findings with no confidence to `approved`.
2. `prepare_judge_batch()` auto-dismisses findings without anchors or below the judge threshold.
3. `apply_judge_response()` mutates findings in-place using judge verdicts.
4. `process(findings)` applies final filters in order:

- **Dismissed** - drop (judge vetoed).
- **Low-confidence proposed** - drop if `confidence < N`.
- **Deduplication** - drop if `finding_id` already seen in this run.

Returns `(final_findings, summary_dict)`. The summary (counts per drop reason, final count) is written to `info.json`.

### 4.6 Finding Schema (`src/schemas/finding.py`)

Every analyser produces `Finding` objects with the same schema:

```txt
Finding
+-- finding_id: str           # e.g. "STRUCTURE_ANALYSER:KAPTXT-1"
+-- ac_code: str              # assessment criterion code (e.g. "KAPTXT")
+-- title / summary: str
+-- severity: float [0-1]     # how serious the issue is
+-- confidence: float | None  # model certainty; None = deterministic
+-- status: "proposed" | "approved" | "dismissed"
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
  "analysers": [
    { "analyser_id": "structure_analyser", "enabled": true, "params": { "min_words": 486 } },
    { "analyser_id": "asset_analyser",     "enabled": true, "model": "gpt-4o" }
  ]
}
```

Each analyser entry can override the OpenAI model and pass arbitrary `params`. The `"course"` field filters rulebook rules: each `LLMRule` declares its `course` scope (`null` = both courses).

#### Rulebook (`config/rulebook.json`)

- `grader_model_prompt_template` - system prompt with a `{rules}` placeholder.
- `vision_model_prompt_template` - system prompt for the vision model.
- `judge_model_prompt` - judge system prompt.
- `rules: list[LLMRule]` - one entry per AC code group, each with `ac_codes`, `prompt_instruction`, `analyser_id`, `course`, and `is_bonus`.

## 5. CLI

```txt
python -m src [options] <input> [<input> ...]

Options:
  -d, --debug         Enable debug logging
  -o, --out PATH      Output directory  (default: out/default/)
  -c, --config PATH   JSON config file  (default: config/default.json)
  --csv-out PATH      Write findings as CSV, compatible with ground-truth datasets
```

Multiple input files can be passed in one invocation. Each is processed independently with a shared parser and LLM client. Finding ID counters reset per document.

## 6. Dataset

Historical graded documentation for IPP and IFJ courses (2013-2024) is stored under `data/`. Assessment CSVs record per-document AC code deductions and serve as ground truth. The `--csv-out` flag produces findings in the same schema for direct comparison with human deductions.

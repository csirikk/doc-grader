# Project Overview

This document is an architecture and operations overview of the repository. It explains how the main parts work together, how model routing is resolved, and which output artefacts are expected from routine runs.

The repository has two working areas:

- `doc_grader/`: production runtime of the tool itself
- `notebooks/`: exploratory and evaluation workflow used for analysis, and miscellaneous supporting workflows

## doc_grader

The runtime flow is:

1. Parse input into a shared IR
2. Run enabled analysers
3. Optionally run judge review
4. Aggregate, score, and write outputs

Core modules:

- `doc_grader/document_parser.py`: input discovery and IR creation
- `doc_grader/analysers/`: analyser implementations
- `doc_grader/llm_client.py`: model and usage handling
- `doc_grader/rule_engine.py`: merge, filter, deduplicate
- `doc_grader/scorer.py`: impact scoring
- `doc_grader/ui/`: read-only Streamlit review app

### Config

Configuration lives under `config/`.

- `config/default.json`: compatibility default profile
- `config/presets/`: standard per-course presets
- `config/experiments/`: non-default research presets
- `config/rulebooks/`: canonical rulebook files
- `config/rulebook.json`: compatibility default rulebook

A preset controls which analysers run and how they run.
A rulebook defines criteria, prompt instructions, and severity weights.

### Model Routing and Access Limits

The asset pipeline supports three execution backends, selected per rule:

- `vision`: Generic vision-model path for diagram and page interpretation.
- `classifier`: BADUML-style binary UML quality path using a classifier model.
- `deterministic`: In-code checks that do not require model calls.

Classifier rules are routed through `asset_analyser.params.classifier_model`.
In shipped defaults and presets, this setting points to a private fine-tuned OpenAI model tied to the owner account/project.

Because of this access boundary, external API keys may not be able to call the same classifier model. When classifier calls fail, the pipeline continues and other analysers still run, but classifier-dependent UML findings can be reduced or missing.

Fallback profiles for external users:

- `config/experiments/generic_classifier_fallback.json`: Keeps OpenAI-backed grading paths but swaps the private classifier for a generic accessible model.
- `config/experiments/local_only.json`: Uses local/deterministic paths and avoids LLM calls for maximum portability.

Reproducibility boundary:

- Local and deterministic checks are generally reproducible after setup.
- Generic OpenAI-backed checks are reproducible when equivalent model/version access exists.
- Classifier-backed BADUML results are conditionally reproducible unless an equivalent accessible fine-tuned classifier is provided.

### Runtime outputs

Each processed student gets an individual output directory, for example `out/<student_id>/`.

Per-student artefacts:

- `info.json`: run and config metadata, stage timings, usage summary, and counts.
- `ir.json`: parsed intermediate representation used by analysers.
- `docling.json`: raw Docling extraction output.
- `parser_findings.json`: parser-stage findings.
- `raw_findings.json`: analyser findings before judge and rule-engine post-processing.
- `judged_findings.json`: findings after judge stage when judge is enabled.
- `findings.json`: final filtered findings used for review/export.

Run-level artefact:

- `run_summary.json`: aggregate counts, stage timings, and usage/cost summary across all processed documents in the run.

Optional exports:

- Run-level CSV export through `--csv-out`.

### Operational caveats

During routine operation, the following caveats are the most important:

- If no matching document is discovered, the parser emits a missing-document finding so the case remains visible in outputs.
- If parsing fails, parser artefacts are still written, but later analyser stages do not execute for that document.
- The reviewer workspace should consume `findings.json` as the final reviewer-facing result.

## Notebooks

The `notebooks/` folder is the analysis workspace. It contains experiment notebooks, evaluation notebooks, and exported reports.

The `notebooks/scripts/` folder contains reusable Python modules used by notebooks. These scripts hold shared parsing, constants, and evaluation logic so notebooks stay focused on analysis.

Typical responsibilities in `notebooks/scripts/` include:

- Dataset parsing and normalisation helpers
- Shared constants and cohort mappings
- Evaluation metric and aggregation utilities
- Utilities for training and related data preparation tasks

## Supporting directories

- `data/`: bundled samples, specs, and supporting reference material
- `docs/`: written documentation for architecture, plans, and findings

Notebook analysis workflow:

1. Load data from `data/`, `out/`, or notebook-specific `outputs/`
2. Reuse helpers from `notebooks/scripts/`
3. Save derived results to `out/` or `outputs/` (for notebook evaluation exports)

## Extensibility

Add a new analyser:

- Implement under `doc_grader/analysers/`
- Register it in runtime wiring
- Add config support in presets
- Add rule coverage in relevant rulebook

Add notebook analysis capability:

- Add reusable logic in `notebooks/scripts/`
- Keep notebooks focused on interpretation and visualisation
- Save final artefacts to `out/` or notebook-specific `outputs/`

# Project Overview

This document explains how the repository is organised and how the main parts work together.

The repository has two working areas:

- `doc_grader/`: production runtime of the tool itself
- `notebooks/`: exploratory and evaluation workflow used for analysis, and miscellaneous supporting workflows

## doc_grader

The CLI entry point is `doc-grader <path_or_folder>`.
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

### Runtime outputs

Each processed student gets an individual output directory, e.g. `out/<id>/`. Key files:

- `info.json`: run metadata, stage timings, and counts
- `ir.json`: parsed intermediate representation
- `docling.json`: raw Docling extraction
- `parser_findings.json`: parser-level issues
- `raw_findings.json`: analyser output before judge
- `judged_findings.json`: judge output when enabled
- `findings.json`: final filtered findings

Optional run-level CSV export is available through `--csv-out`.

## Notebooks

The `notebooks/` folder is the analysis workspace. It contains experiment notebooks, evaluation notebooks, and exported reports.

The `notebooks/scripts/` folder contains reusable Python modules used by notebooks. These scripts hold shared parsing, constants, and evaluation logic so notebooks stay focused on analysis.

Typical responsibilities in `notebooks/scripts/` include:

- Dataset parsing and normalisation helpers
- Shared constants and cohort mappings
- Evaluation metric and aggregation utilities
- Utilities for training and related data preparation tasks

## Supporting directories

- `data/`: source datasets, specs, and supporting material, not provided in the repository
- `docs/`: written documentation for architecture, plans, and findings

## Usage

Runtime grading run:

```bash
doc-grader <path_or_folder>
```

Open review UI locally only:

```bash
streamlit run doc_grader/ui/app.py --server.address 127.0.0.1
```

Notebook analysis workflow:

1. Load data from `data/` or `outputs/`
2. Reuse helpers from `notebooks/scripts/`
3. Save derived results to `outputs/`

## Extensibility

Add a new analyser:

- Implement under `doc_grader/analysers/`
- Register it in runtime wiring
- Add config support in presets
- Add rule coverage in relevant rulebook

Add notebook analysis capability:

- Add reusable logic in `notebooks/scripts/`
- Keep notebooks focused on interpretation and visualisation
- Save final artefacts to `outputs/`

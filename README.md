# IFJ & IPP documentation grader

Bachelor's thesis tool to assist with grading IPP & IFJ student project documentation.

## Repository layout

```txt
docs/                Reference documentation (codes, thesis specification, overview)
research/            Aggregated research
src/project/         Source code
    parsers/           Markdown and PDF parsers producing the IR models
    detectors/         Detectors (base_detector, length_detector)
    schemas/           Pydantic models (IR, findings, config)
    util.py            Helper utilities (ids, hashing, summary)
    logger.py          Simple debug logger
    rule_engine.py     Post-processing and aggregation
thesis/              Bachelor's thesis latex code 
test/                Playground, sample input markdown files, sample output folder, not included in repo
data/                Private data assets, not included in repo
```

## Installation

Create and activate a virtual environment, then install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Command line usage

Process one or more input files (markdown or PDF).

```bash
PYTHONPATH=src python -m project path/to/file1.md path/to/file2.md --out path/to/folder
```

Enable debug output to see full json dumps of the parsed document and findings, a token stream, as well as other internal debug prints.

```bash
PYTHONPATH=src python -m project -d path/to/file1.md
```

Use a config file to customize detector parameters.

```bash
PYTHONPATH=src python -m project -c test/config.example.json path/to/file1.md
```

The command prints:

1. File path and computed hash
2. A basic json summary of the internal representation (counts, words, structure)
3. Detector findings count
4. Aggregated findings after rule engine processing

Findings are written as json files in the chosen output directory. Each file name encodes the finding id (detector code and a document hash fragment).

## Length detector

Heuristics use simple thresholds (word count, paragraph count, average words per paragraph, paragraphs per heading) to emit at most one finding for a too short document and one finding for a too long document. Evidence includes numeric stats. Thresholds can be configured via config file or use defaults in `length_detector.py`.

## Rule engine

Post-processes and aggregates findings from all detectors. Filters findings by confidence threshold (default 0.80) and removes duplicates. Returns aggregated findings list with summary statistics.

## Internal representation (IR) data model

The markdown parser builds a list of typed blocks (`Heading`, `Paragraph`, `List`, `CodeBlock`, `Quote`, `Table`, `Figure`). Each block has an id and a span with line and byte offsets (when available). The PDF parser extracts text and image blocks with page numbers and bounding boxes, converting them to the same IR format. Findings reference blocks or spans and can attach statistics.

## Dependencies

Core dependencies from `requirements.txt`:

```txt
pydantic
markdown-it-py
PyMuPDF
```

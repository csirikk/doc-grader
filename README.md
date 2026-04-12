# doc-grader

Matúš Csirik, 2026

Intelligent tool for effective assessment of student project documentations within IFJ and IPP courses at FIT BUT. Developed as part of the author's bachelor thesis. The goal is to verify the suitability of various modern machine learning models and Python libraries within a grading process.

The tool parses Markdown or PDF student documentations into a normalised intermediate representaiton, which is then processed by various analyser models. The resulting findings are then validated by additional models and processed by a rule engine, producing concrete suggestions for the human grader using this tool.

## Pipeline

1. Parse: document(s) (``.md`` or ``.pdf``) are parsed into an intermediate representation.
2. Analyse: run analysers on the parsed document(s) and emit findings.
3. Judge (optional): an LLM-based judge verifies and adjusts findings.
4. Aggregate: the rule engine finalises findings and writes outputs for review.

## Installation

For exact installation steps, see [INSTALL.md](INSTALL.md).

## Usage

Run the pipeline:

```bash
python -m src <input_dir>
```

CLI options:

- `-h, --help` show help message and exit
- `-d, --debug` enable debug logging
- `-o, --out PATH` path to output directory (default: `out/default/`)
- `-c, --config PATH` path to a JSON config file (default: `config/default.json`)
- `--csv-out PATH` path where to write a combined CSV of all findings, mirroring the original csv grading workflow

### Inputs

Three input modes handled for convenience.

1. Single file: `python -m src path/to/doc.pdf ...` student id is derived from the filename.
2. Student folder: `python -m src path/to/student_folder ...` if the folder contains a document it is used and the folder name becomes the student id. Recommended for ``.md`` documents, which often carry references to other resources within the ``student_folder``.
3. Project variant folder: `python -m src path/to/project_variant_folder/* ...` if the provided folder contains student subfolders, each subfolder is scanned for a primary document and treated as a separate student.

### Outputs

Each analyzed student produces a per-student output folder (e.g. `out/<id>/`) with
files:

- `info.json` run metadata and counts
- `ir.json` intermediate representation used by analysers
  - `docling.json` docling extraction output
- `findings.json` finalised findings for review
  - `parser_findings.json` parser-level issues
  - `raw_findings.json` analyser-emitted findings before judge
  - `judged_findings.json` findings after optional model judge (if enabled)

Use `--csv-out` to produce a combined CSV of all final findings.

## Configuration

Configuration is ran by multiple main ``.json`` files.

1. App configuration [config/default.json](config/default.json). Specifying the course, configuring the analysers and judge.
2. Assessment rules and prompt templates in [config/rulebook.json](config/rulebook.json). Edit this file to add or adjust codes and rules.

## Review UI

The user inteface provided focuses on showcasing the outputs of the tool after running, it is not meant for adjusting or real time grading. Loads runs under `out/`.

Run the UI:

```bash
streamlit run src/ui/app.py
```

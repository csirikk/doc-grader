# doc-grader

`doc-grader` is a tool to aid both graders and students by producing evidence-linked suggestions for documentation scoring in IFJ and IPP at FIT BUT.

It parses PDF or Markdown submissions, runs configured analysers, and writes findings for human review.

The project was built to reduce repetitive grading work while keeping the final decision with the grader.

## Flow

- Parses each document into a shared intermediate representation
- Runs deterministic and machine learning based analysers
- Optionally runs a judge LLM pass on selected findings
- Aggregates and filters findings into final review artefacts
- Exports machine-readable outputs and optional assessment CSVs

Depending on the configured profile and rulebook, the tool analyses:

- **Structure:** Required sections, heading organisation, and basic formatting constraints.
- **Language:** Grammar, spelling, and typographic issues.
- **Diagrams:** UML diagram presence and quality checks via vision, classifier, and deterministic paths.
- **Content:** Technical coverage and language quality.
- **Integrity:** Overlap with assignment specification.

## Repository layout

- `doc_grader/`: runtime package and CLI
- `config/`: presets, experiments, and rulebooks
- `docs/`: project and architecture documentation
- `notebooks/`: analysis and evaluation notebooks
- `data/`: input datasets and reference material, not provided here
- `sample_data/`: small bundled IFJ and IPP submissions for quick local runs
- `outputs/`: generated evaluation outputs

## Installation

See [INSTALL.md](INSTALL.md).

## Usage

For routine runs, ensure your environment is activated (for example, `conda activate doc-grader` or `source .venv/bin/activate`), then use the command-line entry point:

```bash
doc-grader <path_or_folder>
```

General patterns:

```bash
# single file
doc-grader path/to/submission.pdf

# student folder
doc-grader path/to/student-folder

# cohort folder
doc-grader path/to/cohort-folder
```

### Example Runs

Quick checks on `sample_data/`:

```bash
# IPP 2024/2025 individual preset
doc-grader sample_data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/presets/ipp_2024_25_int.json -o outputs/sample_ipp_int

# IPP 2024/2025 parser preset
doc-grader sample_data/ipp/ipp2425/parser/parser_REDACTED_STUDENT -c config/presets/ipp_2024_25_par.json -o outputs/sample_ipp_par

# IFJ 2024/2025 preset
doc-grader sample_data/ifj/ifj2425/REDACTED_STUDENT -c config/presets/ifj_2024_25.json -o outputs/sample_ifj

# External-friendly fallback (no private classifier dependency)
doc-grader sample_data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/experiments/generic_classifier_fallback.json -o outputs/sample_fallback

# Parse-only smoke check
doc-grader sample_data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/experiments/parse_only.json -o outputs/sample_parse_only

# Local-only run (no LLM calls)
doc-grader sample_data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/experiments/local_only.json -o outputs/sample_local_only
```

### CLI options

| Option              | Description                         |
|---------------------|-------------------------------------|
| `-h, --help`        | Show help message                   |
| `-d, --debug`       | Enable debug logging                |
| `-o, --out PATH`    | Output directory                    |
| `-c, --config PATH` | Config file                         |
| `--csv-out PATH`    | Write merged CSV findings           |
| `--skip-existing`   | Skip students with existing outputs |

## Review UI

A read-only Streamlit interface is available for inspecting saved runs:

```bash
streamlit run doc_grader/ui/app.py
```

In the sidebar, load any run directory under `out/` that contains `findings.json`.

For immediate viewing, a pre-generated demo run output is available at `out/sample_par/` and `out/sample_int`

## Quick Links

- Architecture, model routing, and expected outputs: [docs/overview.md](docs/overview.md)
- Setup and fallback configurations: [INSTALL.md](INSTALL.md)
- Configuration profiles and presets: [config/configs.md](config/configs.md)

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See the [LICENSE](LICENSE) file for details.

Because `doc-grader` relies on the [`language-tool-python`](https://github.com/jxmorris12/language_tool_python) library, it adopts its GPL-3.0 license.

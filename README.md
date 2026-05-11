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
- `data/`: bundled IFJ/IPP samples, specs, and cleaned dataset
- `out/`: generated runtime outputs and bundled demo runs

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

Quick checks on bundled samples in `data/`:

```bash
# IPP 2024/2025 individual preset
doc-grader data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/presets/ipp_2024_25_int.json -o out/sample_ipp_int

# IPP 2024/2025 parser preset
doc-grader data/ipp/ipp2425/parser/parser_REDACTED_STUDENT -c config/presets/ipp_2024_25_par.json -o out/sample_ipp_par

# IFJ 2024/2025 preset
doc-grader data/ifj/ifj2425/REDACTED_STUDENT -c config/presets/ifj_2024_25.json -o out/sample_ifj

# External-friendly fallback (no private classifier dependency)
doc-grader data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/experiments/generic_classifier_fallback.json -o out/sample_fallback

# Parse-only smoke check
doc-grader data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/experiments/parse_only.json -o out/sample_parse_only

# Local-only run (no LLM calls)
doc-grader data/ipp/ipp2425/int/int_REDACTED_STUDENT -c config/experiments/local_only.json -o out/sample_local_only
```

Note: the bundled IPP sample filenames (`readme1.pdf`, `readme2.md`) are intentionally non-canonical, so parser finding `DOCTYPE` appears in sample outputs.

### CLI options

| Option                 | Description                             |
|------------------------|-----------------------------------------|
| `-h, --help`           | Show help message                       |
| `-d, --debug`          | Enable debug logging                    |
| `-o, --out PATH`       | Output directory                        |
| `-c, --config PATH`    | Config file                             |
| `--csv-out PATH`       | Write merged CSV findings               |
| `--clean-csv-out PATH` | Write all findings as dataset-style CSV |
| `--skip-existing`      | Skip students with existing outputs     |

## Review UI

A read-only Streamlit interface is available for inspecting saved runs:

```bash
streamlit run doc_grader/ui/app.py
```

In the sidebar, load any run directory under `out/` that contains `findings.json`.

For immediate viewing, bundled demo run outputs are available at `out/sample_par/` and `out/sample_int/`.

The sample commands above create their own output folders (`out/sample_ipp_int/`, `out/sample_ipp_par/`, `out/sample_ifj/`, `out/sample_fallback/`, `out/sample_parse_only/`, and `out/sample_local_only/`).

## Quick Links

- Architecture, model routing, and expected outputs: [docs/overview.md](docs/overview.md)
- Setup and fallback configurations: [INSTALL.md](INSTALL.md)
- Configuration profiles and presets: [config/configs.md](config/configs.md)

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See the [LICENSE](LICENSE) file for details.

Because `doc-grader` relies on the [`language-tool-python`](https://github.com/jxmorris12/language_tool_python) library, it adopts its GPL-3.0 license.

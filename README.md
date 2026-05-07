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
- `data/`: input datasets and reference material
- `outputs/`: generated evaluation outputs

## Installation

See [INSTALL.md](INSTALL.md).

## Usage

For routine runs, ensure your environment is activated (for example, `conda activate doc-grader` or `source .venv/bin/activate`), then use the command-line entry point:

```bash
doc-grader <path_or_folder>
```

Examples:

```bash
# single file
doc-grader data/ipp_docs/student1/student1.pdf

# student folder
doc-grader data/ipp_docs/student1

# cohort folder
doc-grader data/ipp_docs
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

## Quick Links

- Architecture, model routing, and expected outputs: [docs/overview.md](docs/overview.md)
- Setup and fallback configurations: [INSTALL.md](INSTALL.md)
- Configuration profiles and presets: [config/configs.md](config/configs.md)

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See the [LICENSE](LICENSE) file for details.

Because `doc-grader` relies on the [`language-tool-python`](https://github.com/jxmorris12/language_tool_python) library, it adopts its GPL-3.0 license.

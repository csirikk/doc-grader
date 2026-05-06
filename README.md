# doc-grader

`doc-grader` is a tool to aid both graders and students. It facilitates support by providing suggestions for scoring student documentations, specifically within IFJ and IPP at FIT BUT.

It parses PDF or Markdown submissions, runs configured analysers, and writes findings for human review.

The project was built to reduce repetitive grading work while keeping the final decision with the grader. The framework also ensures that these suggestions or findings carry evidence.

## Flow

- Parses each document into a shared intermediate representation
- Runs deterministic and machine learning based analysers
- Optionally runs a judge LLM pass on selected findings
- Aggregates and filters findings into final review artefacts
- Exports machine-readable outputs and optional assessment CSVs

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

## Outputs

Each processed student gets an output folder such as `out/<id>/`:

- `info.json`: run metadata, stage timings, and counts
- `ir.json`: parsed intermediate representation
- `docling.json`: raw Docling extraction
- `parser_findings.json`: parser-level issues
- `raw_findings.json`: analyser output before judge
- `judged_findings.json`: judge output when enabled
- `findings.json`: final filtered findings

## Review UI

A read-only Streamlit interface is available for inspecting saved runs:

```bash
streamlit run doc_grader/ui/app.py
```

## Documentation

- High-level tool overview: [docs/overview.md](docs/overview.md)
- Installation instructions: [INSTALL.md](INSTALL.md)
- Configuration descriptions: [config/configs.md](config/configs.md)

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See the [LICENSE](LICENSE) file for details.

Because `doc-grader` relies on the [`language-tool-python`](https://github.com/jxmorris12/language_tool_python) library, it adpts its GPL-3.0 license.

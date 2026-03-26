# IFJ & IPP Documentation Grader

A tool to assist with grading student project documentation for the IFJ & IPP courses at BUT FIT.

## Repository Layout

```txt
data/                Private dataset
deprecated/          Deprecated prototypes
docs/                Project documentation (specifications, criteria, overview)
notebooks/           Jupyter notebooks for data analysis
research/            Aggregated research, study materials and notes
src/                 Source code
    analysers/         Document analysers
    llm_client.py      LLM integration
    parsers/           Docling parsing
    rule_engine.py     Validation, post-processing, and finding aggregation
    schemas/           Pydantic models (IR, findings, config)
    ui/                Grading UI
    __main__.py        Entry point
    utils.py           Logging and helper utilities
```

## Installation

Conda:

```bash
# create and activate conda env
conda env create -f environment.yml
conda activate doc-grader

# install the project
python -m pip install -e '.[dev]'
```

venv:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Notebook Setup

Using Conda for notebook development:

```bash
conda env create -f environment.yml
conda activate doc-grader
python -m ipykernel install --user --name doc-grader
```

Open the notebooks in VS Code and select the **doc-grader** kernel.

## Review UI

Launch the Streamlit review UI:

```bash
streamlit run src/ui/app.py
```

## Command Line Usage

Process one or more input files (Markdown or PDF):

```bash
python -m src path/to/file.pdf path/to/other.md --out out/results/
```

### Options

- `-d, --debug`: Enable debug logging and JSON dumps of processed models.
- `-o, --out`: Specify the output directory (defaults to `out/default/`).
- `-c, --config`: Path to a JSON configuration file for analysers.
- `--csv-out PATH`: Write all findings as CSV to the given path.

The `doc-grader` command is installed from the project package; `python -m src` is
equivalent when running from the repository checkout.

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
    parsers/           Docling parsering
    schemas/           Pydantic models (IR, findings, config)
    __main__.py        Entry point
    logger.py          Logging and debugging utilities
    rule_engine.py     Post-processing and finding aggregation
    util.py            Helper utilities
```

## Installation

Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Notebook Setup

Using Conda for notebook development:

```bash
conda env create -f environment.yml
conda activate doc-grader
python -m ipykernel install --user --name doc-grader
```

Open the notebooks in VS Code and select the **doc-grader** kernel.

## Command Line Usage

Process one or more input files (Markdown or PDF):

```bash
python -m src path/to/file.pdf path/to/other.md --out out/results/
```

### Options

- `-d, --debug`: Enable debug logging and JSON dumps of processed models.
- `-o, --out`: Specify the output directory (defaults to `out/default/`).
- `-c, --config`: Path to a JSON configuration file for analysers.

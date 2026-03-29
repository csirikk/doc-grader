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

The CLI accepts one or more input paths. Each input may be:

- a single document file (`.pdf` or `.md`)
- a student folder containing one or more documents
- a folder containing multiple student subfolders

Outputs are written per-student to `out/<student_id>/` by default.

```bash
# single file
python -m src path/to/student123.pdf -o out/results/

# student folder
python -m src path/to/student123_folder -o out/results/

# variant folder (with student subfolders)
python -m src path/to/variantX -o out/results/
```

### Options

- `-d, --debug`: Enable debug logging and JSON dumps of processed models.
- `-o, --out`: Specify the output directory (defaults to `out/default/`). The tool will create a per-student subfolder under this path (for example `out/default/student123/`).
- `-c, --config`: Path to a JSON configuration file for analysers.
- `--csv-out PATH`: Write all findings as CSV to the given path.

The `doc-grader` command is installed from the project package; `python -m src` is
equivalent when running from the repository checkout.

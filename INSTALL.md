# Installation

This tool requires **Python 3.14** or newer.

## 1. Clone the Repository

Open your terminal and clone the project to your local machine and enter the root:

```bash
git clone https://github.com/csirikk/doc-grader
cd doc-grader
```

## 2. Package Managers

Choose one of the two installation methods below.

### A: Conda

Recommended. Conda will install the correct Python version and handle complex non-Python dependencies (like C++ components) inside the environment.

To ensure exact reproducibility, use the strictly locked environment file.
*(Note: The locked file is generated for Linux. If you are reviewing this on macOS or Windows, use the unpinned fallback command below to allow Conda to resolve the correct system binaries for your platform).*

Create the environment:

```bash
# For Linux (strict reproducibility)
conda env create -f environment-lock.yml

# For macOS / Windows (fallback)
conda env create -f environment.yml
```

Activate the environment:

```bash
conda activate doc-grader
```

After activating the environment, install the project in editable mode so local changes are picked up by notebooks and scripts, and the tool can properly locate the configuration directory in the repository root:

```bash
pip install -e .
```

### B: Pip

Recommended if you already have Python 3.14 and Java installed. This uses standard Python tools and is more lightweight, but requires you to manage system-level dependencies manually.

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

To ensure exact reproducibility, first install the strictly locked dependencies, then install the tool itself in editable mode (this is required for the tool to locate configuration files in the repository root):

```bash
pip install -r requirements-lock.txt
pip install -e .
```

## 3. External Dependencies

Some libraries used by this tool have requirements beyond Python packages:

- **Java:** `language-tool-python` requires a Java Runtime Environment (JRE). If not installed, you can usually get it via your package manager:

```bash
# For Ubuntu/Debian
sudo apt update && sudo apt install default-jre
```

- **NLP Models:** On the first run, `stanza` and `sentence-transformers` will attempt to download pre-trained models. Ensure you have an active internet connection.

## 4. Environment Configuration

The project uses `python-dotenv` to manage secrets. Create a `.env` file in the root directory to store your API keys and set the `OPENAI_API_KEY` variable to your OpenAI API key.

```bash
touch .env
```

## 5. Fallback Configurations

By default, the tool attempts to use a private fine-tuned model. If you are an external user without access, use one of these fallback configurations to run the tool:

```bash
doc-grader <path_or_folder> -c config/experiments/generic_classifier_fallback.json
```

For maximum portability without LLM calls, use the local-only preset:

```bash
doc-grader <path_or_folder> -c config/experiments/local_only.json
```

For details on model routing and reproducibility boundaries, see [docs/overview.md](docs/overview.md).

## 6. First-Run Operational Prerequisites

Before starting a batch run, ensure that:

- The selected profile in `config/` matches the assessed course variant.
- Java is installed whenever grammar analysis is enabled.
- `OPENAI_API_KEY` is set whenever the selected profile enables LLM-backed analysers or judge review.

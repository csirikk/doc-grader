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

Create the environment:

```bash
conda env create -f environment.yml
```

Activate the environment:

```bash
conda activate doc-grader
```

After activating the environment, install the project in editable mode so
local changes are picked up by notebooks and scripts:

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

Install the package and its dependencies:

```bash
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

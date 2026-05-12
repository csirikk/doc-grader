# Installation

This tool requires **Python 3.14** or newer, so it is not installable on FIT BUT CVT computers.

## External Dependencies

Some libraries used by this tool have requirements beyond Python packages:

- **Java:** `language-tool-python` requires a Java Runtime Environment (JRE):

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install default-jre
```

- **Cairo (pip path only):** `cairosvg` requires the system Cairo library. Conda installs this automatically; pip does not:

```bash
# Ubuntu/Debian
sudo apt install libcairo2-dev
```

- **NLP Models:** On first run, `stanza`, `sentence-transformers`, and `docling` will each download pre-trained models (~3–4 GB total). An active internet connection is required.

- **Disk space:** The full environment including CUDA packages and downloaded models requires approximately 10–15 GB.

- **GPU:** CUDA packages are included and will be used automatically on Linux with an NVIDIA GPU. On CPU-only machines or macOS, the tool falls back to CPU inference, which is significantly slower.

## Package Managers

Choose one of the two installation methods below.

### A: Conda

Recommended. Conda will install the correct Python version and handle complex non-Python dependencies (like C++ components) inside the environment.

To ensure exact reproducibility, use the strictly locked environment file.
*(Note: The locked file is generated for Linux. On macOS or Windows, use `environment.yml` instead — it carries the same version pins but without Linux-specific build hashes, so Conda can resolve the correct binaries for your platform.)*

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

## Environment Configuration

The project uses `python-dotenv` to manage secrets. Create a `.env` file in the root directory to store your API keys and set the `OPENAI_API_KEY` variable to your OpenAI API key.

```bash
touch .env
```

By default, the tool attempts to use a private fine-tuned model. If you are an external user without access, use one of these fallback configurations to run the tool:

```bash
doc-grader <path_or_folder> -c config/experiments/generic_classifier_fallback.json
```

For maximum portability without LLM calls, use the local-only preset:

```bash
doc-grader <path_or_folder> -c config/experiments/local_only.json
```

For details on model routing and reproducibility boundaries, see [docs/overview.md](docs/overview.md).

Before starting a run, ensure that:

- The selected profile in `config/` matches the assessed course variant.
- Java is installed whenever grammar analysis is enabled.
- `OPENAI_API_KEY` is set whenever the selected profile enables LLM-backed analysers or judge review.

For runnable sample commands and Streamlit review workflow, use [README.md](README.md).

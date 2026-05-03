# Config Directory Reference

This file briefly explains the purpose of each configuration file in the `config/` tree.

Defaults are placed at the root.

- **`default.json`**: A general IPP 2024/2025 profile that acts as the CLI
  default when no `-c` argument is supplied.
- **`rulebook.json`**: A compatibility rulebook for IPP 2024/2025. It also
  serves as the final fallback in runtime rulebook resolution and in the review
  UI.

## presets/

These are the main presets intended for real cohort runs.

- **`presets/ifj_2024_25.json`**: The standard IFJ configuration for the 2024/2025 academic year with the full analysis pipeline enabled.
- **`presets/ipp_2024_25_int.json`**: The standard IPP configuration for the 2024/2025 individual variant with the full analysis pipeline enabled.
- **`presets/ipp_2024_25_par.json`**: The standard IPP configuration for the 2024/2025 parser variant. It keeps the same general pipeline but uses milder
  structure expectations and a lower point scale.
- **`presets/ipp_2025_26.json`**: The standard IPP configuration for the 2025/2026 academic year. It reflects the newer rulebook, the expected file name `dokumentace`, and the revised point scale.

## rulebooks/

There is one rulebook for each main profile. These files define the rule set,
severity weights, routing metadata, and prompt templates used by the grading
pipeline.

- **`rulebooks/ifj_2024_25.json`**: IFJ 2024/2025 profile.
- **`rulebooks/ipp_2024_25_int.json`**: IPP 2024/2025 intepreter profile.
- **`rulebooks/ipp_2024_25_par.json`**: IPP 2024/2025 parser profile.
- **`rulebooks/ipp_2025_26.json`**: IPP 2025/2026 profile.

## experiments/

These are non-default presets used for testing and evaluation.

- **`experiments/smoke.json`**: A very small pre-flight configuration that
  checks the basic pipeline before a full run.
- **`experiments/parse_only.json`**: A parser-only configuration for checking
  input discovery and document parsing without further analysis.
- **`experiments/no_judge_baseline.json`**: A baseline configuration that keeps
  the analysers but omits the judge stage.
- **`experiments/local_only.json`**: A configuration that relies on local tools
  as much as possible and avoids LLM calls.
- **`experiments/grammar_only.json`**: A focused configuration for grammar and
  spelling checks.
- **`experiments/integrity.json`**: A focused configuration for plagiarism or
  copy-detection checks.

### evaluation/

These variants support thesis evaluation of quality, cost, and latency. All of
them target the IPP 2024/2025 individual rulebook.

- **`evaluation/normal_judge_mini_content.json`**: An evaluation setup with a
  stronger judge model and mid-tier content models.
- **`evaluation/mini_judge_nano_content.json`**: A lower-cost evaluation setup
  with smaller judge, content, and asset models.
- **`evaluation/mini_judge_nano_content_nolocal.json`**: A lower-cost
  evaluation setup that also replaces local grammar and integrity components
  with LLM-based ones.

## weights/

- **`weights/severity_weights.json`**: Calibrated severity weights derived from
  historical IPP assessment data. These values are used by the scorer when
  converting findings into point deductions.

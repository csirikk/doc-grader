"""Configuration schema for analysers and pipeline."""

from pathlib import Path  # noqa: TC003
from typing import Any

from pydantic import Field

from .base import StrictModel
from .llm import Rulebook


class AnalyserConfig(StrictModel):
    """Configuration for a single analyser."""

    analyser_id: str = Field(
        ...,
        description="Analyser implementation identifier used by analyser list",
    )
    enabled: bool = Field(default=True, description="Whether analyser is enabled")
    model: str | None = Field(
        default=None,
        description="Override the LLM model for this analyser.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Analyser-specific parameters"
    )


class AppConfig(StrictModel):
    """Configuration for the application."""

    version: str = Field(default="config/0.1", description="Configuration version")
    run_id: str | None = Field(default=None, description="Unique run identifier")
    course: str | None = Field(
        default=None,
        description="Course code: 'ifj' or 'ipp', None to auto-detect",
    )
    analysers: list[AnalyserConfig] = Field(
        default_factory=list, description="List of analyser configurations"
    )


def load_app_config(path: Path) -> AppConfig:
    """Load and validate configuration from JSON file."""
    return AppConfig.model_validate_json(path.read_text(encoding="utf-8"))


def load_rulebook(path: Path) -> Rulebook:
    """Load and validate the LLM rulebook from JSON file."""
    return Rulebook.model_validate_json(path.read_text(encoding="utf-8"))

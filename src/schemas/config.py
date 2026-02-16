"""Configuration schema for analysers and pipeline."""

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalyserConfig(BaseModel):
    """Configuration for a single analyser."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Analyser code identifier")
    enabled: bool = Field(default=True, description="Whether analyser is enabled")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Analyser-specific parameters"
    )


class AppConfig(BaseModel):
    """Configuration for the application."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="config/0.1", description="Configuration version")
    run_id: Optional[str] = Field(default=None, description="Unique run identifier")
    course: Optional[str] = Field(
        default=None, description="Course code: 'ifj' or 'ipp', None to auto-detect"
    )
    analysers: list[AnalyserConfig] = Field(
        default_factory=list, description="List of analyser configurations"
    )


def load_config(path: Path) -> AppConfig:
    """Load and validate configuration from JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)

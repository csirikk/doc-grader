"""Configuration schema for detectors and pipeline."""

from typing import List, Optional, Any, Dict
from pathlib import Path
import json
from pydantic import BaseModel, Field


class DetectorConfig(BaseModel):
    code: str
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)
    model_config = dict(extra="forbid")


class AppConfig(BaseModel):
    version: str = Field(default="config/0.1")
    run_id: Optional[str] = None
    detectors: List[DetectorConfig] = Field(default_factory=list)
    model_config = dict(extra="forbid")


def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)


def dump_config(cfg: AppConfig, path: Path) -> None:
    path.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")

"""Configuration schema for detectors and pipeline."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DetectorConfig(BaseModel):
    code: str
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)
    model_config = dict(extra="forbid")


class AppConfig(BaseModel):
    version: str = Field(default="config/0.1")
    run_id: Optional[str] = None
    course: Optional[str] = None  # "ifj" or "ipp", none tries to detect
    detectors: List[DetectorConfig] = Field(default_factory=list)
    model_config = dict(extra="forbid")


def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    logger.info(f"Loaded config from {path}")
    return AppConfig.model_validate(data)

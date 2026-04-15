"""Base Pydantic models and shared utilities."""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base model with no extra fields allowed"""

    model_config = ConfigDict(extra="forbid")

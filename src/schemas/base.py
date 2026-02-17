"""Base Pydantic models and shared utilities."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict


def utc_now() -> datetime:
    """Return current UTC datetime."""

    return datetime.now(UTC)


class StrictModel(BaseModel):
    """Base model with no extra fields allowed"""

    model_config = ConfigDict(extra="forbid")

from pydantic import Field

from .base import StrictModel


class LLMRule(StrictModel):
    ac_code: str
    prompt_instruction: str
    analyser_id: str


class LLMEvaluation(StrictModel):
    ac_code: str
    item_cref: str = Field(
        ..., description="The Docling canonical reference (cref) of the relevant item"
    )
    snippet: str | None = None
    reason: str
    severity: float
    confidence: float = 1.0

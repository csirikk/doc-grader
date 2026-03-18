from typing import Literal

from pydantic import Field

from .base import StrictModel


class LLMRule(StrictModel):
    ac_codes: list[str] = Field(..., description="The assessment criterion codes")
    prompt_instruction: str = Field(..., description="LLM prompt")
    analyser_id: str = Field(..., description="ID of the analyser this rule belongs to")
    course: Literal["ifj", "ipp", None] = Field(
        default=None, description="The course this rule applies to. None means both."
    )
    is_bonus: bool = Field(
        default=False,
        description="Whether this rule represents a bonus points criterion",
    )


class Rulebook(StrictModel):
    system_prompt_template: list[str] = Field(
        ...,
        description="The main system prompt containing a '{rules}' placeholder",
    )
    rules: list[LLMRule] = Field(
        default_factory=list, description="List of all available LLM rules"
    )


class LLMFinding(StrictModel):
    ac_code: str
    item_cref: str = Field(
        ..., description="The Docling canonical reference (cref) of the relevant item"
    )
    snippet: str | None = None
    reason: str
    severity: float
    confidence: float = 1.0


class LLMResponse(StrictModel):
    """The complete, raw response expected from the Base LLM."""

    reasoning_chain: str = Field(
        ...,
        description="The model's internal reasoning analysing the text before scoring.",
    )
    findings: list[LLMFinding] = Field(
        default_factory=list,
        description="The list of flagged assessment criteria violations.",
    )

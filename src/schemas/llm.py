from __future__ import annotations

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
    grader_model_prompt_template: list[str] = Field(
        ...,
        description=(
            "Grader model system prompt template containing a '{rules}' placeholder"
        ),
    )
    judge_model_prompt: list[str] = Field(
        ...,
        description="Judge model system prompt",
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


class GraderModelResponse(StrictModel):
    """The complete, raw response expected from the grader model."""

    reasoning_chain: str = Field(
        ...,
        description="The model's internal reasoning analysing the text before scoring.",
    )
    findings: list[LLMFinding] = Field(
        default_factory=list,
        description="The list of flagged assessment criteria violations.",
    )


class JudgeVerdict(StrictModel):
    """A single verdict from the judge model on one grader model finding."""

    finding_id: str = Field(
        ..., description="Exact finding_id of the finding being judged"
    )
    decision: Literal["approved", "dismissed", "adjusted"] = Field(
        ...,
        description=(
            "approved: violation confirmed; "
            "dismissed: false positive; "
            "adjusted: real issue but severity/confidence miscalibrated"
        ),
    )
    adjusted_severity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Corrected severity (only set when decision is 'adjusted')",
    )
    adjusted_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Corrected confidence (only set when decision is 'adjusted')",
    )
    rationale: str = Field(
        ..., description="One-sentence justification for the decision"
    )


class JudgeModelResponse(StrictModel):
    """Complete judge model response for a batch of findings."""

    reasoning_chain: str = Field(
        ...,
        description=(
            "2-3 sentence internal analysis of the finding batch "
            "before issuing verdicts."
        ),
    )
    verdicts: list[JudgeVerdict] = Field(
        default_factory=list,
        description="One verdict per finding in the submitted batch.",
    )

from typing import Literal

from pydantic import Field

from .base import StrictModel


class LLMRule(StrictModel):
    title: str = Field(..., description="Short rule title phrase")
    ac_codes: list[str] = Field(..., description="The assessment criterion codes")
    prompt_instruction: str = Field(
        ..., description="Analyser prompt: describes what to flag and when."
    )
    judge_instruction: str | None = Field(
        default=None,
        description=(
            "Judge prompt: describes when to approve, adjust, or dismiss a finding. "
            "When absent the judge falls back to prompt_instruction."
        ),
    )
    analyser_id: str = Field(..., description="ID of the analyser this rule belongs to")
    course: Literal["ifj", "ipp", None] = Field(
        default=None, description="The course this rule applies to. None means both."
    )
    language: str | None = Field(
        default=None,
        description="Language code this rule applies to. None means all languages.",
    )


class Rulebook(StrictModel):
    grader_model_prompt_template: list[str] = Field(
        ...,
        description=(
            "Grader model system prompt template containing a '{rules}' placeholder"
        ),
    )
    vision_model_prompt_template: list[str] = Field(
        ...,
        description=(
            "Vision model system prompt template with a '{rules}' placeholder"
        ),
    )
    judge_model_prompt_template: list[str] = Field(
        ...,
        description="Judge model system prompt template.",
    )
    rules: list[LLMRule] = Field(
        default_factory=list, description="List of all available LLM rules"
    )


class LLMFinding(StrictModel):
    ac_code: str = Field(
        ..., description="The AC code exactly as listed in the rules (e.g. 'ICH')."
    )
    item_cref: str = Field(
        ..., description="The Docling canonical reference (cref) of the relevant item"
    )
    snippet: str | None = None
    reason: str
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


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


class VisionFinding(StrictModel):
    """A single finding from the vision model."""

    ac_code: str = Field(
        ..., description="The AC code exactly as listed in the rules (e.g. 'BADUML')."
    )
    item_cref: str = Field(
        ...,
        description="Docling picture cref (e.g. '#/pictures/0')",
    )
    reason: str
    severity: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    model_name: str | None = Field(
        default=None,
        description="Name of the model that produced this finding, if known.",
    )


class VisionModelResponse(StrictModel):
    """Complete response expected from the vision grader model."""

    reasoning_chain: str = Field(
        ...,
        description="The model's internal reasoning before scoring.",
    )
    findings: list[VisionFinding] = Field(
        default_factory=list,
        description="Flagged assessment criteria violations for the diagram(s).",
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
            "adjusted: real issue but text, snippet, severity, or confidence need correcting"
        ),
    )
    adjusted_summary: str | None = Field(
        default=None,
        description="The rewritten, clearer explanation of the violation (only set if decision is 'adjusted').",
    )
    adjusted_snippet: str | None = Field(
        default=None,
        description="The corrected exact, unedited substring from the document (only set if decision is 'adjusted').",
    )
    adjusted_severity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Corrected severity (only set if decision is 'adjusted')",
    )
    adjusted_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Corrected confidence (only set if decision is 'adjusted')",
    )
    rationale: str = Field(
        ..., description="One-sentence justification for why this decision was made"
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

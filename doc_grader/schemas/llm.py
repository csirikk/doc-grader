from typing import Literal, Self

from pydantic import Field, model_validator

from .base import StrictModel


class LLMRule(StrictModel):
    title: str = Field(..., description="Short rule title phrase")
    ac_code: str = Field(..., description="The assessment criterion code")
    severity_weight: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Calibrated per-code weight: fraction of max_doc_points deducted at "
            "severity=1.0."
        ),
    )
    is_legacy: bool = Field(
        default=False,
        description="Whether this rule corresponds to a legacy assessment code.",
    )
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
    vision_page_context_header: str = Field(
        ..., description="Header injected before full-page context images."
    )
    vision_diagrams_header: str = Field(
        ..., description="Header injected before extracted diagram images."
    )
    vision_diagrams_footer: str = Field(
        ..., description="Footer appended after all diagram images."
    )
    vision_pages_only_footer: str = Field(
        ..., description="Footer appended in pages-only vision model calls."
    )
    classifier_system_prompt: str = Field(
        ..., description="System prompt for the fine-tuned BADUML binary classifier."
    )
    judge_findings_header: str = Field(
        ..., description="Header for the findings block in judge model user messages."
    )
    judge_doc_context_header: str = Field(
        ..., description="Header for the document context block in judge user messages."
    )
    judge_doc_context_pdf_note: str = Field(
        ...,
        description=(
            "Note appended to the doc context header when PDF page images are attached."
        ),
    )
    rules: list[LLMRule] = Field(
        default_factory=list, description="List of all available LLM rules"
    )
    rules_by_code: dict[str, LLMRule] = Field(
        default_factory=dict,
        exclude=True,
        description="Pre-built index for O(1) rule lookup by AC code.",
    )

    @model_validator(mode="after")
    def _build_index(self) -> Self:
        self.rules_by_code = {r.ac_code: r for r in self.rules}
        return self


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
    model_name: str | None = Field(
        default=None,
        description="Name of the model that generated this finding, if known.",
    )

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
    raw_response: str | None = Field(
        default=None,
        description="Raw model output.",
    )
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
            "adjusted: real issue but text, snippet, severity, "
            "or confidence need correcting"
        ),
    )
    adjusted_summary: str | None = Field(
        default=None,
        description=(
            "The rewritten, clearer explanation of the violation "
            "(only set if decision is 'adjusted')."
        ),
    )
    adjusted_snippet: str | None = Field(
        default=None,
        description=(
            "The corrected exact, unedited substring from the document "
            "(only set if decision is 'adjusted')."
        ),
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
    model_name: str | None = Field(
        default=None, description="The specific name of the judge model used."
    )

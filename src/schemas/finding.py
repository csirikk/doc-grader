from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from docling_core.types.doc.document import (
        FineRef,
        ProvenanceItem,
    )

    from .ir import DocumentRef


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    """Base model with no extra fields allowed."""

    model_config = ConfigDict(extra="forbid")


class AnalyserInfo(StrictModel):
    """Info about the analyser that generated a finding."""

    analyser_id: str = Field(
        ...,
        description="Analyser implementation identifier (e.g. 'section_analyser')",
    )
    name: str = Field(..., description="Human-readable analyser name")
    run_id: str | None = None
    config_hash: str | None = None
    params: dict[str, Any] | None = None


# TODO: add helper to transform to docling_item anchor
class Anchor(StrictModel):
    """Evidence: Canonical pointer into a DoclingDocument."""

    target: FineRef
    snippet: str | None = None
    prov: list[ProvenanceItem] = Field(default_factory=list)


class Stat(StrictModel):
    """Evidence: Measurable attribute."""

    name: str
    value: bool | int | float | str | None
    unit: str | None = None
    notes: str | None = None


class ModelEval(StrictModel):
    """Evidence: Output from an ML model evaluation."""

    model_name: str | None = None
    label: str | None = None
    score: float | None = None
    raw: Any | None = None


class Finding(StrictModel):
    """
    Represents a detected issue in a document, with context and evidence.
    Possibly becomes a concrete suggestion.
    """

    created_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp for when the finding was created",
    )

    # Context
    analyser: AnalyserInfo
    document: DocumentRef
    finding_id: str = Field(
        ..., description="Unique ID for this finding (e.g. 'PARSER:MISSING-1')"
    )
    ac_code: str = Field(..., description="Assessment Criteria code (e.g. 'STRUCT')")
    title: str
    summary: str

    severity: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # Evidence
    anchors: list[Anchor] = Field(default_factory=list)
    stats: list[Stat] = Field(default_factory=list)
    model_evals: list[ModelEval] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    status: Literal["proposed", "approved", "dismissed"] = "proposed"
    meta: dict[str, Any] | None = None

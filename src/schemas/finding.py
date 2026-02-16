from datetime import datetime, timezone
from typing import Any, List, Literal, Optional, Union

from docling_core.types.doc.document import (
    FineRef,
    ProvenanceItem,
)
from pydantic import BaseModel, ConfigDict, Field

from .ir import DocumentRef


class StrictModel(BaseModel):
    """Base model with no extra fields allowed."""

    model_config = ConfigDict(extra="forbid")


class AnalyserInfo(StrictModel):
    """Info about the analyser that generated a finding."""

    analyser_id: str = Field(
        ..., description="Analyser implementation identifier (e.g. 'section_analyser')"
    )
    name: str = Field(..., description="Human-readable analyser name")
    run_id: Optional[str] = None
    config_hash: Optional[str] = None
    params: Optional[dict[str, Any]] = None


# TODO: add helper to transform to docling_item anchor
class Anchor(StrictModel):
    """Evidence: Canonical pointer into a DoclingDocument."""

    target: FineRef
    snippet: Optional[str] = None
    prov: List[ProvenanceItem] = Field(default_factory=list)


class Stat(StrictModel):
    """Evidence: Measurable attribute."""

    name: str
    value: Union[bool, int, float, str, None]
    unit: Optional[str] = None
    notes: Optional[str] = None


class ModelEval(StrictModel):
    """Evidence: Output from an ML model evaluation."""

    model_name: Optional[str] = None
    label: Optional[str] = None
    score: Optional[float] = None
    raw: Optional[Any] = None


class Finding(StrictModel):
    """
    Represents a detected issue in a document, with context and evidence.
    Possibly becomes a concrete suggestion.
    """

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
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

    severity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Evidence
    anchors: List[Anchor] = Field(default_factory=list)
    stats: List[Stat] = Field(default_factory=list)
    model_evals: List[ModelEval] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    status: Literal["proposed", "approved", "dismissed"] = "proposed"
    meta: Optional[dict[str, Any]] = None

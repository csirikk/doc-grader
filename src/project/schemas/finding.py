from typing import Annotated, Literal, Optional, Union, List, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class SpanRef(BaseModel):
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    byte_start: Optional[int] = None
    byte_end: Optional[int] = None
    page: Optional[int] = None  # for PDFs


class Location(BaseModel):
    block_id: Optional[str] = None
    span: Optional[SpanRef] = None


class ImpactDelta(BaseModel):
    kind: Literal["penalty", "bonus", "neutral"] = "penalty" # default to penalty
    min: Optional[int] = None
    max: Optional[int] = None
    default: Optional[int] = None


class Impact(BaseModel):
    suggested_deduction: Optional[ImpactDelta] = None


class DetectorInfo(BaseModel):
    code: str
    name: str
    version: str
    run_id: Optional[str] = None
    config_hash: Optional[str] = None
    params: Optional[dict] = None


class DocumentRef(BaseModel):
    source_path: str
    hash: str  # TODO: choose and enforce format (sha256?)


# Evidence -------------------------------------------------------------------
class BlockRef(BaseModel):
    type: Literal["BlockRef"] = "BlockRef"
    block_ids: List[str]
    snippet: Optional[str] = None
    notes: Optional[str] = None


class TextSpan(BaseModel):
    type: Literal["TextSpan"] = "TextSpan"
    text: Optional[str] = None
    span: Optional[SpanRef] = None
    notes: Optional[str] = None


class Stat(BaseModel):
    type: Literal["Stat"] = "Stat"
    name: str
    value: Union[int, float, str]
    notes: Optional[str] = None


class ImageRef(BaseModel):
    type: Literal["ImageRef"] = "ImageRef"
    block_id: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class CodeRef(BaseModel):
    type: Literal["CodeRef"] = "CodeRef"
    symbol: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class ModelEval(BaseModel):
    type: Literal["ModelEval"] = "ModelEval"
    label: Optional[str] = None
    score: Optional[float] = None
    raw: Optional[Any] = None
    notes: Optional[str] = None


Evidence = Annotated[
    Union[BlockRef, TextSpan, Stat, ImageRef, CodeRef, ModelEval],
    Field(discriminator="type"),
]


# Finding -------------------------------------------------------------------
class Finding(BaseModel):
    schema_version: Literal["finding/0.1"] = "finding/0.1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Context
    detector: DetectorInfo
    document: DocumentRef
    finding_id: str
    doc_id: str  # TODO: doc hash 

    # Classification
    code: str
    title: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    confidence: Optional[float] = None

    impact: Optional[Impact] = None

    locations: Optional[List[Location]] = None
    evidence: List[Evidence] = Field(default_factory=list)

    tags: List[str] = Field(default_factory=list)
    status: Literal["proposed", "approved", "dismissed"] = "proposed"
    meta: Optional[dict] = None


# test ---------------------------------------------------------------
if __name__ == "__main__":
    demo_hash = "sha256:" + ("0" * 64)
    finding = Finding(
        document=DocumentRef(source_path="../docs/sample.md", hash=demo_hash),
        finding_id="STRUCT:00000000:missing-intro",
        doc_id=demo_hash,
        code="STRUCT",
        title="Missing introduction section",
        message="Top-level heading sequence is missing an introduction.",
        severity="warning",
        confidence=0.92,
        detector=DetectorInfo(
            code="STRUCT",
            name="StructureDetector",
            version="0.0.1",
            run_id="run_demo",
            config_hash="sha256:hello",
            params={"ahoj": "ahoj"},
        ),
        impact=Impact(
            suggested_deduction=ImpactDelta(kind="penalty", min=10, max=30, default=20)
        ),
        locations=[
            Location(
                block_id="h-1",
                span=SpanRef(line_start=1, line_end=1, byte_start=0, byte_end=24),
            )
        ],
        evidence=[
            BlockRef(block_ids=["h-1"], snippet="# Implementation Details"),
            Stat(name="heading_count", value=5),
        ],
        tags=["structure", "missing-section"],
        status="proposed",
        meta={"demo": True},
    )
    print(finding.model_dump_json(indent=2))

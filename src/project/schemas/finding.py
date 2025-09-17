"""Schemas for detector findings and related evidence objects."""

from typing import Annotated, Literal, Optional, Union, List, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, model_validator, field_validator

class BBox(BaseModel):
    """Bounding box in page coordinates for PDFs."""
    x0: float
    y0: float
    x1: float
    y1: float
    model_config = dict(extra="forbid")


class SpanRef(BaseModel):
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    byte_start: Optional[int] = None
    byte_end: Optional[int] = None
    page: Optional[int] = None
    bbox: Optional[BBox] = None
    model_config = dict(extra="forbid")

    @field_validator("line_end")
    @classmethod
    def _line_end_ge_start(cls, v, info):
        ls = info.data.get("line_start")
        if v is not None and ls is not None and v < ls:
            raise ValueError("line_end must be >= line_start")
        return v

    @field_validator("byte_end")
    @classmethod
    def _byte_end_ge_start(cls, v, info):
        bs = info.data.get("byte_start")
        if v is not None and bs is not None and v < bs:
            raise ValueError("byte_end must be >= byte_start")
        return v

    @field_validator("page")
    @classmethod
    def _page_nonneg(cls, v):
        if v is not None and v < 0:
            raise ValueError("page must be >= 0")
        return v

    @model_validator(mode="after")
    def _at_least_one_axis(self):
        has_lines = self.line_start is not None or self.line_end is not None
        has_bytes = self.byte_start is not None or self.byte_end is not None
        if not (has_lines or has_bytes):
            raise ValueError("SpanRef requires at least line_* or byte_* to be set")
        return self


class Location(BaseModel):
    block_id: Optional[str] = None
    span: Optional[SpanRef] = None
    model_config = dict(extra="forbid")

class ImpactDelta(BaseModel):
    kind: Literal["penalty", "bonus", "neutral"] = "penalty"  # default to penalty
    min: Optional[int] = Field(default=None, ge=0)
    max: Optional[int] = Field(default=None, ge=0)
    default: Optional[int] = Field(default=None, ge=0)
    model_config = dict(extra="forbid")

    @field_validator("max")
    @classmethod
    def _max_ge_min(cls, v, info):
        mn = info.data.get("min")
        if v is not None and mn is not None and v < mn:
            raise ValueError("max must be >= min")
        return v


class Impact(BaseModel):
    suggested_deduction: Optional[ImpactDelta] = None
    model_config = dict(extra="forbid")


class DetectorInfo(BaseModel):
    code: str
    name: str
    version: str
    run_id: Optional[str] = None
    config_hash: Optional[str] = None
    params: Optional[dict] = None
    model_config = dict(extra="forbid")


class DocumentRef(BaseModel):
    source_path: str
    hash: str  # sha256:<64hex>
    model_config = dict(extra="forbid")

    @field_validator("hash")
    @classmethod
    def _hash_sha256(cls, v: str):
        if not v.startswith("sha256:") or len(v) != len("sha256:") + 64:
            raise ValueError("hash must be 'sha256:' followed by 64 hex chars")
        hexpart = v.split(":", 1)[1]
        try:
            int(hexpart, 16)
        except ValueError:
            raise ValueError("hash hex part invalid")
        return v


# --- Evidence models
class BlockRef(BaseModel):
    type: Literal["BlockRef"] = "BlockRef"
    block_ids: List[str] = Field(min_length=1)
    snippet: Optional[str] = None
    notes: Optional[str] = None
    model_config = dict(extra="forbid")

    @field_validator("snippet")
    @classmethod
    def _limit_snippet(cls, v: Optional[str]):
        if v is not None and len(v) > 300:
            return v[:300] + "…"
        return v


class TextSpan(BaseModel):
    type: Literal["TextSpan"] = "TextSpan"
    text: Optional[str] = None
    span: Optional[SpanRef] = None
    notes: Optional[str] = None
    model_config = dict(extra="forbid")

    @model_validator(mode="after")
    def _text_or_span(self):
        if self.text is None and self.span is None:
            raise ValueError("TextSpan requires at least text or span")
        return self


class Stat(BaseModel):
    type: Literal["Stat"] = "Stat"
    name: str
    value: Union[int, float, str, None]
    notes: Optional[str] = None
    model_config = dict(extra="forbid")

    @field_validator("name")
    @classmethod
    def _nonempty_name(cls, v: str):
        if not v.strip():
            raise ValueError("stat name must be non-empty")
        return v


class ImageRef(BaseModel):
    type: Literal["ImageRef"] = "ImageRef"
    block_id: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    model_config = dict(extra="forbid")


class CodeRef(BaseModel):
    type: Literal["CodeRef"] = "CodeRef"
    symbol: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    model_config = dict(extra="forbid")


class ModelEval(BaseModel):
    type: Literal["ModelEval"] = "ModelEval"
    label: Optional[str] = None
    score: Optional[float] = None
    raw: Optional[Any] = None
    notes: Optional[str] = None
    model_config = dict(extra="forbid")


Evidence = Annotated[
    Union[BlockRef, TextSpan, Stat, ImageRef, CodeRef, ModelEval],
    Field(discriminator="type"),
]


# --- Finding model
class Finding(BaseModel):
    schema_version: Literal["finding/0.2"] = "finding/0.2"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Context
    detector: DetectorInfo
    document: DocumentRef
    finding_id: str
    doc_id: str  # document hash

    # Classification
    code: str
    title: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    impact: Optional[Impact] = None

    locations: Optional[List[Location]] = None
    evidence: List[Evidence] = Field(default_factory=list)

    tags: List[str] = Field(default_factory=list)
    status: Literal["proposed", "approved", "dismissed"] = "proposed"
    meta: Optional[dict] = None
    model_config = dict(extra="forbid")

    @field_validator("code")
    @classmethod
    def _code_upper(cls, v: str):
        return v.strip().upper()

    @field_validator("finding_id")
    @classmethod
    def _finding_id_nonempty(cls, v: str):
        if not v.strip():
            raise ValueError("finding_id must be non-empty")
        return v

    @model_validator(mode="after")
    def _at_least_one_anchor(self):
        no_locations = self.locations is None or len(self.locations) == 0
        no_evidence = self.evidence is None or len(self.evidence) == 0
        if no_locations and no_evidence:
            raise ValueError("finding must include at least one location or one evidence item")
        # locations if provided must not contain empty span-only placeholders
        if self.locations:
            for loc in self.locations:
                if loc.block_id is None and loc.span is None:
                    raise ValueError("location must define block_id or span")
        # if provided, locations must not be an empty list
        if self.locations is not None and len(self.locations) == 0:
            raise ValueError("locations, if provided, must be non-empty")
        # doc id consistency
        if self.doc_id != self.document.hash:
            raise ValueError("doc_id must equal document.hash")
        # detector code consistency
        if (self.code or "").strip().upper() != (self.detector.code or "").strip().upper():
            raise ValueError("code must equal detector.code (case-insensitive)")
        return self


# --- Self-test
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
            version="0.1",
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
            TextSpan(text="Example text", span=SpanRef(line_start=1, line_end=1, byte_start=0, byte_end=10)),
        ],
        tags=["structure", "missing-section"],
        status="proposed",
        meta={"demo": True},
    )
    print(finding.model_dump_json(indent=2))

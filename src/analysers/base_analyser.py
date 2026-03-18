"""Base analyser structure and registry."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import DocItem, TextItem

from ..schemas.finding import AnalyserInfo, Anchor, Finding, FineRef
from ..schemas.ir import Document
from ..utils import next_id

if TYPE_CHECKING:
    from docling_core.types.doc.document import DocItem

    from ..schemas.ir import Document
    from ..schemas.llm import LLMFinding, LLMRule, Rulebook

logger = logging.getLogger(__name__)


class BaseAnalyser(ABC):
    """Abstract base class for all analysers."""

    # Analyser implementation identifier
    analyser_id: ClassVar[str] = "base_analyser"

    # Human-readable analyser name
    name: ClassVar[str] = "Base Analyser"

    def _make_finding(
        self,
        doc: Document,
        ac_code: str,
        title: str,
        summary: str,
        evidence_item: DocItem | None = None,
        snippet_override: str | None = None,
        severity: float | None = None,
        confidence: float | None = None,
        run_id: str | None = None,
        config_hash: str | None = None,
    ) -> Finding:
        """Helper to create a unified Finding object."""

        anchors: list[Anchor] = []
        if evidence_item is not None:
            ref = evidence_item.get_ref().cref
            snippet = (
                snippet_override
                if snippet_override is not None
                else (
                    evidence_item.text if isinstance(evidence_item, TextItem) else None
                )
            )
            anchors.append(
                Anchor(
                    target=FineRef.model_validate({"$ref": ref}),
                    snippet=snippet,
                    prov=list(evidence_item.prov),
                )
            )

        prefix = f"{self.analyser_id.upper()}:{ac_code}"
        finding_id = next_id(prefix)

        return Finding(
            analyser=AnalyserInfo(
                analyser_id=self.analyser_id,
                name=self.name,
                run_id=run_id,
                config_hash=config_hash,
            ),
            document=doc.doc_ref,
            finding_id=finding_id,
            ac_code=ac_code,
            title=title,
            summary=summary,
            severity=severity,
            confidence=confidence,
            anchors=anchors,
        )

    @abstractmethod
    def analyse(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        """
        Perform analysis on the document.

        Args:
            doc: The intermediate representation of the document.
            params: Optional dictionary of configuration parameters.

        Returns:
            A list of detected Findings.
        """
        ...


class BaseLLMAnalyser(BaseAnalyser):
    """Base class for analysers that delegate logic to an LLM."""

    @abstractmethod
    def get_rules(
        self, rulebook: Rulebook, params: dict[str, Any] | None = None
    ) -> list[LLMRule]:
        """Return the rules this analyser wants the LLM to check."""
        ...

    @abstractmethod
    def process_llm_findings(
        self,
        doc: Document,
        llm_findings: list[LLMFinding],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        """Convert LLM findings back into standard Findings."""
        ...

    def analyse(self, doc: Document, params: dict | None = None) -> list[Finding]:
        raise NotImplementedError("LLM Analysers must be run via LLMClient.")

    def _convert_llm_finding_to_finding(
        self,
        doc: Document,
        f: LLMFinding,
    ) -> Finding:
        """Convert an LLMFinding to a Finding."""
        return self._make_finding(
            doc=doc,
            ac_code=f.ac_code,
            title=f.ac_code,
            summary=f.reason,
            evidence_item=doc.text_items.get(f.item_cref),
            snippet_override=f.snippet,
            severity=f.severity,
            confidence=f.confidence,
        )

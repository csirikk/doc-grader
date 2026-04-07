"""Base analyser structure and registry."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import TextItem

from ..schemas.finding import (
    AnalyserInfo,
    Anchor,
    Finding,
    FineRef,
    HumanStatus,
    JudgeStatus,
)
from ..utils import next_id

if TYPE_CHECKING:
    from docling_core.types.doc.document import DocItem

    from ..schemas.ir import Document
    from ..schemas.llm import LLMFinding, LLMRule, Rulebook, VisionFinding

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
        judge_status: JudgeStatus,
        human_status: HumanStatus,
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
                    section_path=doc.section_paths.get(ref),
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
            judge_status=judge_status,
            human_status=human_status,
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

    @staticmethod
    def _title_for_ac_code(rules: list[LLMRule], ac_code: str) -> str:
        ac_codes = ac_code.split("/")
        for rule in rules:
            if any(code in rule.ac_codes for code in ac_codes):
                return rule.title
        raise KeyError(f"No rule title found for AC code {ac_code!r}")

    def get_rules(
        self, rulebook: Rulebook, params: dict[str, Any] | None = None
    ) -> list[LLMRule]:
        """Return the rules this analyser owns, filtered by course and language.

        Subclasses may override for custom rule selection logic.
        """
        course = params.get("course") if params else None
        language = params.get("language") if params else None
        return [
            r
            for r in rulebook.rules
            if r.analyser_id == self.analyser_id
            and (r.course is None or r.course == course)
            and (r.language is None or r.language == language)
        ]

    def process_vision_findings(
        self,
        doc: Document,
        vision_findings: list[VisionFinding],
        rules: list[LLMRule],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        """Convert vision model findings into standard Findings."""
        known_codes: set[str] = {code for r in rules for code in r.ac_codes}
        findings: list[Finding] = []
        for f in vision_findings:
            if f.ac_code not in known_codes:
                logger.warning(
                    "Ignoring vision finding with unknown AC code %r", f.ac_code
                )
                continue
            finding = self._make_finding(
                doc=doc,
                ac_code=f.ac_code,
                title=self._title_for_ac_code(rules, f.ac_code),
                summary=f.reason,
                judge_status="to_be_judged",
                human_status="proposed",
                evidence_item=doc.picture_items.get(f.item_cref),
                snippet_override=None,
                severity=f.severity,
                confidence=f.confidence,
            )
            findings.append(finding)
        return findings

    def process_llm_findings(
        self,
        doc: Document,
        llm_findings: list[LLMFinding],
        rules: list[LLMRule],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        """Convert grader model findings into standard Findings.

        Subclasses may override for custom post-processing logic.
        """
        known_codes: set[str] = {code for r in rules for code in r.ac_codes}
        findings: list[Finding] = []
        for f in llm_findings:
            if f.ac_code not in known_codes:
                logger.warning(
                    "Ignoring LLM finding with unknown AC code %r", f.ac_code
                )
                continue
            findings.append(self._convert_llm_finding_to_finding(doc, f, rules))
        return findings

    def analyse(self, doc: Document, params: dict | None = None) -> list[Finding]:
        raise NotImplementedError("LLM analysers are orchestrated via _run_analysers.")

    def _convert_llm_finding_to_finding(
        self,
        doc: Document,
        f: LLMFinding,
        rules: list[LLMRule],
    ) -> Finding:
        """Convert an LLMFinding to a Finding."""
        return self._make_finding(
            doc=doc,
            ac_code=f.ac_code,
            title=self._title_for_ac_code(rules, f.ac_code),
            summary=f.reason,
            judge_status="to_be_judged",
            human_status="proposed",
            evidence_item=doc.text_items.get(f.item_cref),
            snippet_override=f.snippet,
            severity=f.severity,
            confidence=f.confidence,
        )

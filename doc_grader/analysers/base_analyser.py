"""Base analyser structure and registry.

Author: Matúš Csirik
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import PageItem, TextItem

from ..schemas.finding import (
    AnalyserInfo,
    Anchor,
    Finding,
    FineRef,
    HumanStatus,
    JudgeStatus,
    ModelEval,
)
from ..utils import next_id

if TYPE_CHECKING:
    from docling_core.types.doc.document import DocItem

    from ..schemas.document import Document
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
        generator_model: str | None = None,
    ) -> Finding:
        """Helper to create a unified Finding object."""

        anchors: list[Anchor] = []
        if evidence_item is not None:
            if isinstance(evidence_item, PageItem):
                # Pages dont have stable crefs
                ref = f"#/pages/{evidence_item.page_no}"
                snippet = snippet_override
            else:
                ref = evidence_item.get_ref().cref
                snippet = (
                    snippet_override
                    if snippet_override is not None
                    else (
                        evidence_item.text
                        if isinstance(evidence_item, TextItem)
                        else None
                    )
                )
            anchors.append(
                Anchor(
                    target=FineRef.model_validate({"$ref": ref}),
                    snippet=snippet,
                    prov=[]
                    if isinstance(evidence_item, PageItem)
                    else list(evidence_item.prov),
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
            generator_model=generator_model,
            anchors=anchors,
        )

    @abstractmethod
    def analyse(
        self,
        doc: Document,
        rulebook: Rulebook | None = None,
        params: dict[str, Any] | None = None,
        llm_client: Any | None = None,
    ) -> list[Finding]:
        """
        Perform analysis on the document.

        Args:
            doc: The intermediate representation of the document.
            rulebook: Rulebook for rule lookup. Required by LLM-backed analysers.
            params: Optional dictionary of configuration parameters.
            llm_client: Optional LLM client. Required by LLM-backed analysers.

        Returns:
            A list of detected Findings.
        """
        ...


class BaseLLMAnalyser(BaseAnalyser):
    """Base class for analysers that delegate logic to an LLM."""

    @staticmethod
    def _title_for_ac_code(rules: list[LLMRule], ac_code: str) -> str:
        titles = {r.ac_code: r.title for r in rules}
        title = titles.get(ac_code)
        if title is None:
            raise KeyError(f"No rule title found for AC code {ac_code!r}")
        return title

    def get_rules(
        self, rulebook: Rulebook, params: dict[str, Any] | None = None
    ) -> list[LLMRule]:
        """Return the rules this analyser owns, filtered by course, language, and
        any disabled_codes set in params.

        Subclasses may override for custom rule selection logic.
        """
        course = params.get("course") if params else None
        language = params.get("language") if params else None
        disabled: set[str] = set((params or {}).get("disabled_codes") or [])
        return [
            r
            for r in rulebook.rules
            if r.analyser_id == self.analyser_id
            and (r.course is None or r.course == course)
            and (r.language is None or r.language == language)
            and r.ac_code not in disabled
        ]

    def _output_vision_ac_code(self, ac_code: str) -> str:
        """Map internal vision-model labels to public rulebook AC codes."""
        return ac_code

    def _finalise_vision_finding(
        self,
        finding: Finding,
        vision_finding: VisionFinding,
        output_code: str,
    ) -> None:
        """Apply analyser-specific post-processing to a converted vision finding."""
        if vision_finding.model_name:
            finding.model_evals.append(
                ModelEval(
                    model_name=vision_finding.model_name,
                    label=vision_finding.ac_code,
                )
            )

    def _resolve_item_cref(
        self,
        doc: Document,
        item_cref: str,
        source_name: str,
    ) -> DocItem | None:
        """Resolve a Docling cref into an evidence item for a generated finding."""
        from docling_core.types.doc.document import RefItem

        try:
            return RefItem.model_validate({"$ref": item_cref}).resolve(
                doc=doc.docling_doc
            )
        except Exception:
            logger.warning("Failed to resolve %s item_cref %r", source_name, item_cref)
            return None

    def _make_generated_finding(
        self,
        doc: Document,
        rules: list[LLMRule],
        ac_code: str,
        item_cref: str,
        summary: str,
        snippet_override: str | None,
        severity: float | None,
        confidence: float | None,
        generator_model: str | None,
        source_name: str,
    ) -> Finding:
        """Build a Finding from a structured model output record."""
        evidence_item = self._resolve_item_cref(doc, item_cref, source_name)
        return self._make_finding(
            doc=doc,
            ac_code=ac_code,
            title=self._title_for_ac_code(rules, ac_code),
            summary=summary,
            judge_status="to_be_judged",
            human_status="proposed",
            evidence_item=evidence_item,
            snippet_override=snippet_override,
            severity=severity,
            confidence=confidence,
            generator_model=generator_model,
        )

    def process_vision_findings(
        self,
        doc: Document,
        vision_findings: list[VisionFinding],
        rules: list[LLMRule],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        """Convert vision model findings into standard Findings."""
        known_codes: set[str] = {r.ac_code for r in rules}
        findings: list[Finding] = []

        for f in vision_findings:
            output_code = self._output_vision_ac_code(f.ac_code)
            if output_code not in known_codes:
                if output_code == f.ac_code:
                    logger.warning(
                        "Ignoring vision finding with unknown AC code %r", output_code
                    )
                else:
                    logger.warning(
                        (
                            "Ignoring vision finding with unknown AC code %r "
                            "(mapped from %r)"
                        ),
                        output_code,
                        f.ac_code,
                    )
                continue
            finding = self._make_generated_finding(
                doc=doc,
                rules=rules,
                ac_code=output_code,
                item_cref=f.item_cref,
                summary=f.reason,
                snippet_override=f.reason,
                severity=f.severity,
                confidence=f.confidence,
                generator_model=f.model_name,
                source_name="vision finding",
            )
            self._finalise_vision_finding(finding, f, output_code)
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
        known_codes: set[str] = {r.ac_code for r in rules}
        model_name: str | None = (params or {}).get("model")
        findings: list[Finding] = []
        for f in llm_findings:
            if f.ac_code == "FIL0":
                logger.debug("Correcting hallucinated AC code 'FIL0' to 'FILO'")
                f = f.model_copy(update={"ac_code": "FILO"})
            if f.ac_code not in known_codes:
                logger.warning(
                    "Ignoring LLM finding with unknown AC code %r", f.ac_code
                )
                continue
            finding = self._convert_llm_finding_to_finding(doc, f, rules)
            if model_name:
                finding.model_evals.append(
                    ModelEval(model_name=model_name, label=f.ac_code)
                )
            findings.append(finding)
        return findings

    def build_system_prompt(
        self,
        rules: list[LLMRule],
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Build the grader system prompt from rules and the rulebook template.

        Subclasses may override to inject extra context (e.g. a spec document).
        """
        rules_text = ""
        for r in rules:
            rules_text += f"- {r.ac_code}: {r.prompt_instruction}\n"
        template = "\n".join(rulebook.grader_model_prompt_template)
        return template.replace("{rules}", rules_text)

    def execute_llm(
        self,
        llm_client: Any,
        doc: Document,
        rules: list[LLMRule],
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> tuple[list[Any], dict]:
        """Call the grader LLM and return (raw_findings, usage).

        Subclasses may override.
        """
        model = (params or {}).get("model")
        temperature = (params or {}).get("temperature")
        system_prompt = self.build_system_prompt(rules, rulebook, params)
        return llm_client.analyse_document(
            doc, system_prompt, model=model, temperature=temperature
        )

    def analyse(
        self,
        doc: Document,
        rulebook: Rulebook | None = None,
        params: dict[str, Any] | None = None,
        llm_client: Any | None = None,
    ) -> list[Finding]:
        self._accumulated_usage: dict = {}
        if rulebook is None or not llm_client:
            return []
        rules = self.get_rules(rulebook, params)
        if not rules:
            return []
        raw, usage = self.execute_llm(llm_client, doc, rules, rulebook, params)
        self._accumulated_usage = usage
        return self.process_llm_findings(doc, raw, rules, params)

    def _convert_llm_finding_to_finding(
        self,
        doc: Document,
        f: LLMFinding,
        rules: list[LLMRule],
    ) -> Finding:
        """Convert an LLMFinding to a Finding."""
        return self._make_generated_finding(
            doc=doc,
            rules=rules,
            ac_code=f.ac_code,
            item_cref=f.item_cref,
            summary=f.reason,
            snippet_override=f.snippet,
            severity=f.severity,
            confidence=f.confidence,
            generator_model=f.model_name,
            source_name="LLM finding",
        )

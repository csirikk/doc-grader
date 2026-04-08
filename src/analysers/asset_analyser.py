"""LLM-based asset analyser. Visual quality of diagrams and figures.

Responsible for AC:
- 'NOUML': No UML class diagram is present in the document.
- 'BADUML': UML class diagram has broken notation, uses the wrong type, was
  auto-generated without curation, or is so visually flawed it cannot be read.
  Detected by the Azure fine-tuned binary classifier.
- 'SEMUML': UML class diagram is semantically incomplete: missing significant
  classes or methods, or fails to convey class interactions.
  Detected by the OpenAI vision LLM.
- 'OWNDIF': Diagram does not visually distinguish custom (student) classes from
  framework/library classes (e.g. ipp-core).
- 'BW': Dark-background diagram pasted into a light-background document.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMRule, Rulebook

logger = logging.getLogger(__name__)

# Azure fine-tuned binary classifier defaults
_AZURE_BADUML_MODEL = "gpt-4-04-14"
_AZURE_BADUML_SYSTEM = (
    "You are an expert teaching assistant scoring student UML diagrams. "
    "Analyse the provided image and classify it as 'GOODUML' if it presents a "
    "readable, structurally valid diagram, or 'BADUML' if the diagram is poor, "
    "illegible, or incorrect."
)


class AssetAnalyser(BaseLLMAnalyser):
    """
    Analyses visual assets (diagrams, figures) using an OpenAI vision model.
    Each PictureItem in the document is sent as an image for evaluation.
    """

    analyser_id: ClassVar[str] = "asset_analyser"
    name: ClassVar[str] = "Asset Analyser"

    def build_vision_system_prompt(
        self,
        rules: list[LLMRule],
        rulebook: Rulebook,
        doc: Document,
    ) -> str:
        """Build the vision grader system prompt, excluding rules that cannot be
        evaluated from images alone.

        - NOUML: absence of a diagram cannot be seen in an image.
        - BADUML: handled by the Azure binary classifier, not the vision LLM.
        - BW: excluded for markdown docs as it requires document background context
        """
        excluded: set[str] = {"NOUML", "BADUML"}
        if not doc.docling_doc.pages:
            excluded.add("BW")
        rules_text = ""
        for r in rules:
            if any(code in excluded for code in r.ac_codes):
                continue
            codes_str = "/".join(r.ac_codes)
            rules_text += f"- {codes_str}: {r.prompt_instruction}\n"
        template = "\n".join(rulebook.vision_model_prompt_template)
        return template.replace("{rules}", rules_text)

    def execute_llm(
        self,
        llm_client: Any,
        doc: Document,
        rules: list[LLMRule],
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        from ..schemas.llm import VisionFinding

        model = (params or {}).get("model")
        temperature = (params or {}).get("temperature")
        azure_model = (params or {}).get("classifier_model") or _AZURE_BADUML_MODEL
        vision_system_prompt = self.build_vision_system_prompt(rules, rulebook, doc)

        # Azure binary classifier: returns raw label strings keyed by cref.
        raw_labels = llm_client.run_azure_vision_classifier(
            doc, _AZURE_BADUML_SYSTEM, azure_model
        )
        baduml_count = 0
        findings: list[VisionFinding] = []
        for cref, label in raw_labels.items():
            logger.info("Azure classified [%s] as %r", cref, label)
            if "BADUML" in label.upper():
                findings.append(
                    VisionFinding(
                        ac_code="BADUML",
                        item_cref=cref,
                        reason="Classified as BADUML by fine-tuned classifier.",
                        severity=1.0,
                        confidence=1.0,
                    )
                )
                baduml_count += 1
        logger.info(
            "%d/%d images classified as BADUML by Azure model.",
            baduml_count,
            len(raw_labels),
        )

        # OpenAI vision model: semantic and other visual findings.
        vision_findings = llm_client.analyse_assets(
            doc, vision_system_prompt, model=model, temperature=temperature
        )
        findings.extend(vision_findings)
        return findings

    def analyse(
        self,
        doc: Document,
        rulebook: Rulebook | None = None,
        params: dict[str, Any] | None = None,
        llm_client: Any | None = None,
    ) -> list[Finding]:
        if rulebook is None:
            return []
        rules = self.get_rules(rulebook, params)
        if not rules:
            return []
        if not doc.total_pictures:
            return [
                self._make_finding(
                    doc=doc,
                    ac_code="NOUML",
                    title=self._title_for_ac_code(rules, "NOUML"),
                    summary="No UML Class Diagram was found in the document.",
                    judge_status="to_be_judged",
                    human_status="proposed",
                    evidence_item=None,
                    severity=1.0,
                    confidence=1.0,
                )
            ]
        if not llm_client:
            return []
        raw = self.execute_llm(llm_client, doc, rules, rulebook, params)
        return self.process_vision_findings(doc, raw, rules, params)

"""LLM-based asset analyser. Visual quality of diagrams and figures.

Responsible for AC:
- 'NOUML': No UML class diagram is present in the document.
- 'BADUML': UML class diagram has broken notation, uses the wrong type, was
  auto-generated without curation, or is so visually flawed it cannot be read.
  Detected by the OpenAI fine-tuned binary classifier.
- 'SEMUML': UML class diagram is semantically incomplete: missing significant
  classes or methods, or fails to convey class interactions.
  Detected by a generic OpenAI vision LLM.
- 'OWNDIF': Diagram does not visually distinguish custom (student) classes from
  framework/library classes (e.g. ipp-core).
- 'BW': Dark-background diagram pasted into a light-background document.
"""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMRule, Rulebook

logger = logging.getLogger(__name__)

# OpenAI fine-tuned binary classifier defaults
_BADUML_MODEL = "ft:gpt-4.1-2025-04-14:personal:baduml-classifier-gold:DU8txcxh"
_BADUML_SYSTEM_PROMPT = (
    "Classify this UML class diagram. "
    "GOODUML: Correct, readable diagram with standard notation, "
    "attributes, methods, and clear relationships. "
    "BADUML: Missing details, unreadable, or uses non-standard notation."
)


class AssetAnalyser(BaseLLMAnalyser):
    """
    Analyses visual assets (diagrams, figures) using a generic OpenAI vision LLM.
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
        - BADUML: handled by the fine-tuned binary classifier, not the vision LLM.
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
        ft_model = (params or {}).get("classifier_model") or _BADUML_MODEL
        vision_system_prompt = self.build_vision_system_prompt(rules, rulebook, doc)
        raw_labels = llm_client.run_vision_classifier(
            doc, _BADUML_SYSTEM_PROMPT, ft_model
        )
        baduml_count = 0
        findings: list[VisionFinding] = []
        for cref, item in raw_labels.items():
            label = (item.get("label") or "").strip().upper()
            raw = (item.get("raw") or "").strip()

            if "BADUML" in label or "BADUML" in raw.upper():
                findings.append(
                    VisionFinding(
                        ac_code="BADUML",
                        item_cref=cref,
                        reason=(
                            "The UML Class Diagram is visually flawed and "
                            " its structure cannot easily be understood."
                        ),
                        raw_response=raw,
                        severity=1.0,
                        confidence=1.0,
                        model_name=ft_model,
                    )
                )
                baduml_count += 1
        logger.info(
            "%d/%d images classified as BADUML by fine-tuned model.",
            baduml_count,
            len(raw_labels),
        )

        # Generic OpenAI vision model: semantic and other visual findings.
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

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

from typing import TYPE_CHECKING, Any, ClassVar

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMRule, Rulebook


class AssetAnalyser(BaseLLMAnalyser):
    """
    Analyses visual assets (diagrams, figures) using an OpenAI vision model.
    Each PictureItem in the document is sent as an image for evaluation.
    """

    analyser_id: ClassVar[str] = "asset_analyser"
    name: ClassVar[str] = "Asset Analyser"

    def execute_llm(
        self,
        llm_client: Any,
        doc: Document,
        rules: list[LLMRule],
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        model = (params or {}).get("model")
        temperature = (params or {}).get("temperature")
        return llm_client.analyse_assets(
            doc, rules, rulebook, model=model, temperature=temperature, params=params
        )

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
        if not doc.picture_items:
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

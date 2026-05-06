"""LLM-based asset analyser. Visual quality of diagrams and figures.

Author: Matúš Csirik

Responsible for AC:
- 'UML_MISSING': No UML class diagram is present in the document.
- 'UML_BAD': UML class diagram has broken notation, uses the wrong type, was
    auto-generated without curation, or is so visually flawed it cannot be read.
    Detected by the OpenAI fine-tuned BADUML classifier and mapped from the
    internal BADUML label at output time.
- 'SEMUML': UML class diagram is semantically incomplete: missing significant
    classes or methods, or fails to convey class interactions.
    Detected by a generic OpenAI vision LLM.
- 'UML_OWNDIF': Diagram does not visually distinguish custom (student) classes from
    framework/library classes (e.g. ipp-core).
- 'UML_READ': Dark-background diagram pasted into a light-background document,
    low readability, or otherwise poor visual clarity.
- 'TYPESET': Typography and formatting violations (monospace identifiers, block
    justification, font consistency, spacing around brackets, etc.).
    PDF: evaluated by the generic vision LLM seeing all document pages.
    Markdown: evaluated deterministically via pymarkdownlnt and markdown-it-py.
"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..llm_client import merge_usage
from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.document import Document
    from ..schemas.finding import Finding
    from ..schemas.llm import LLMRule, Rulebook, VisionFinding

logger = logging.getLogger(__name__)

# OpenAI fine-tuned binary classifier default model ID
BADUML_MODEL = "ft:gpt-4.1-2025-04-14:personal:baduml-classifier-gold:DU8txcxh"

# Internal classifier labels mapped onto public rulebook AC codes.
CLASSIFIER_AC_CODE_MAP: dict[str, str] = {"BADUML": "UML_BAD"}

# pymarkdownlnt rules targeted by the MD SAZBA check
SAZBA_LINT_RULES: frozenset[str] = frozenset({"md009", "md010"})

# Regex for programming identifiers likely missing monospace formatting
IDENT_RE = re.compile(
    r"\b(?:"
    r"[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*"  # camelCase
    r"|[a-zA-Z_][a-zA-Z0-9]*_[a-zA-Z][a-zA-Z0-9]*"  # snake_case
    r"|[A-Z]{2,}(?:_[A-Z0-9]+)+"  # ALL_CAPS_CONST
    r"|[a-z][a-zA-Z0-9_]*\(\)"  # function()
    r")\b"
)

# Regex for incorrect spacing around brackets (MEZ)
MEZ_RE = re.compile(r"\( | \)")


class AssetAnalyser(BaseLLMAnalyser):
    """
    Analyses visual assets (diagrams, figures) using a generic OpenAI vision LLM.
    Each PictureItem in the document is sent as an image for evaluation.
    """

    analyser_id: ClassVar[str] = "asset_analyser"
    name: ClassVar[str] = "Asset Analyser"

    def _output_vision_ac_code(self, ac_code: str) -> str:
        return CLASSIFIER_AC_CODE_MAP.get(ac_code, ac_code)

    def build_vision_system_prompt(
        self,
        rules: list[LLMRule],
        rulebook: Rulebook,
        doc: Document,
    ) -> str:
        """Build the vision grader system prompt, excluding rules that are handled
        by dedicated sub-engines or require page context unavailable for this doc.

        Exclusion is data-driven via LLMRule.backend and LLMRule.requires_pages:
        - backend='classifier' or 'deterministic': handled outside the vision LLM.
        - requires_pages=True: needs full PDF page context; excluded for markdown.
        """
        excluded: set[str] = {
            r.ac_code for r in rules if r.backend in ("classifier", "deterministic")
        }
        if not doc.docling_doc.pages:
            excluded.update(r.ac_code for r in rules if r.requires_pages)
        rules_text = ""
        for r in rules:
            if r.ac_code in excluded:
                continue
            rules_text += f"- {r.ac_code}: {r.prompt_instruction}\n"
        template = "\n".join(rulebook.vision_model_prompt_template)
        return template.replace("{rules}", rules_text)

    def execute_llm(
        self,
        llm_client: Any,
        doc: Document,
        rules: list[LLMRule],
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> tuple[list[Any], dict, int]:
        """Dispatch all active rules to the appropriate sub-engine.

        - backend='classifier': fine-tuned vision classifier.
        - backend='deterministic': handled in analyse(), not here.
        - requires_pages=False, backend=None: vision LLM on extracted diagrams.
        - requires_pages=True, backend=None: vision LLM on full PDF page images.
        """
        from ..schemas.llm import VisionFinding

        model = (params or {}).get("model")
        temperature = (params or {}).get("temperature")
        ft_model = (params or {}).get("classifier_model") or BADUML_MODEL
        usage: dict = {}
        findings: list[VisionFinding] = []
        images_sent: int = 0

        raw_labels: dict = {}
        if any(r.backend == "classifier" for r in rules):
            raw_labels, classifier_usage, classifier_images = (
                llm_client.run_vision_classifier(
                    doc, rulebook.classifier_system_prompt, ft_model
                )
            )
            usage = merge_usage(usage, classifier_usage)
            images_sent += classifier_images
        for cref, item in raw_labels.items():
            label = (item.get("label") or "").strip().upper()
            raw = (item.get("raw") or "").strip()
            if "BADUML" in label or "BADUML" in raw.upper():
                findings.append(
                    VisionFinding(
                        ac_code="BADUML",
                        item_cref=cref,
                        reason=(
                            "The UML Class Diagram is visually flawed and"
                            " its structure cannot easily be understood."
                        ),
                        raw_response=raw,
                        severity=1.0,
                        confidence=1.0,
                        model_name=ft_model,
                    )
                )

        diagram_rules = [
            r
            for r in rules
            if not r.requires_pages and r.backend not in ("classifier", "deterministic")
        ]
        if diagram_rules:
            diagram_prompt = self.build_vision_system_prompt(
                diagram_rules, rulebook, doc
            )
            diagram_findings, diagram_usage, diagram_images = llm_client.analyse_assets(
                doc, diagram_prompt, rulebook, model=model, temperature=temperature
            )
            findings.extend(diagram_findings)
            usage = merge_usage(usage, diagram_usage)
            images_sent += diagram_images

        page_rules = [
            r
            for r in rules
            if r.requires_pages and r.backend not in ("classifier", "deterministic")
        ]
        if page_rules and doc.docling_doc.pages:
            page_prompt = self.build_vision_system_prompt(page_rules, rulebook, doc)
            page_findings, page_usage, page_images = llm_client.analyse_pages_only(
                doc, page_prompt, rulebook, model=model, temperature=temperature
            )
            findings.extend(page_findings)
            usage = merge_usage(usage, page_usage)
            images_sent += page_images

        return findings, usage, images_sent

    def _finalise_vision_finding(
        self,
        finding: Finding,
        vision_finding: VisionFinding,
        output_code: str,
    ) -> None:
        super()._finalise_vision_finding(finding, vision_finding, output_code)
        if finding.model_evals:
            existing = finding.model_evals[-1].raw or {}
            existing = {
                **existing,
                "classifier_raw_response": vision_finding.raw_response,
            }
            finding.model_evals[-1].raw = existing
        if vision_finding.ac_code != output_code:
            finding.meta = {
                **(finding.meta or {}),
                "internal_ac_code": vision_finding.ac_code,
            }

    def _has_resolvable_md_images(self, doc: Document) -> bool:
        """Return True when any Markdown image URI resolves to a local image file.

        This is a lightweight check used to decide whether the Markdown branch
        should invoke the vision/classifier path instead of emitting a
        deterministic "UML_MISSING" finding.
        """
        md_uris = getattr(doc, "md_image_uris", None) or []
        if not md_uris:
            return False

        source_path = getattr(doc.doc_ref, "source_path", None)
        if not source_path:
            return False

        base_resolved = Path(source_path).parent.resolve()
        for img_uri in md_uris:
            img_path_str = str(img_uri)
            if img_path_str.startswith("file://"):
                img_path_str = img_path_str[7:]
            try:
                img_path = (base_resolved / img_path_str).resolve()
            except Exception:
                continue
            # ensure the resolved path is inside the document folder
            try:
                if not img_path.is_relative_to(base_resolved):
                    continue
            except Exception:
                continue
            if not img_path.is_file():
                continue
            if img_path.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".svg",
                ".gif",
                ".bmp",
                ".webp",
                ".tif",
                ".tiff",
                ".ico",
            }:
                return True
        return False

    def _check_sazba_md(
        self,
        doc: Document,
        sazba_rules: list[LLMRule],
    ) -> list[Finding]:
        """Deterministic SAZBA typography check for Markdown source files.

        Runs pymarkdownlnt for MD009/MD010 lint rules and a markdown-it-py
        token walk for unformatted identifiers (SAZBA) and spacing around
        brackets (MEZ).  Emits at most one Finding aggregating all violations.
        """
        title = self._title_for_ac_code(sazba_rules, "TYPESET")
        source_path = doc.doc_ref.source_path
        if source_path is None:
            logger.warning("No source path available for MD SAZBA check; skipping.")
            return []

        try:
            content = Path(source_path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Could not read MD source for SAZBA check: %s", exc)
            return []

        violations: list[str] = []

        # --- pymarkdownlnt: MD009 (trailing spaces) and MD010 (hard tabs) ---
        try:
            from pymarkdown.api import PyMarkdownApi

            scan_result = PyMarkdownApi().scan_string(content)
            for failure in scan_result.scan_failures:
                if failure.rule_id.lower() in SAZBA_LINT_RULES:
                    violations.append(
                        f"Line {failure.line_number}: "
                        f"[{failure.rule_id.upper()}] {failure.rule_description}"
                    )
        except Exception as exc:
            logger.warning("pymarkdownlnt scan failed: %s", exc)

        # --- markdown-it-py: identifier backtick and MEZ checks ---
        try:
            from markdown_it import MarkdownIt

            md_parser = MarkdownIt("commonmark")
            tokens = md_parser.parse(content)
            for token in tokens:
                if token.type != "inline" or not token.children:
                    continue
                line_no = (token.map[0] + 1) if token.map else None
                for child in token.children:
                    if child.type == "code_inline":
                        continue
                    if child.type != "text":
                        continue
                    text = child.content
                    for m in IDENT_RE.finditer(text):
                        violations.append(
                            f"Line {line_no or '?'}: "
                            f"Identifier '{m.group()}' should use monospace formatting"
                        )
                    if MEZ_RE.search(text):
                        violations.append(
                            f"Line {line_no or '?'}: Incorrect spacing around bracket"
                        )
        except Exception as exc:
            logger.warning("markdown-it-py token walk failed: %s", exc)

        if not violations:
            return []

        severity = min(len(violations) / max(doc.total_words, 1) * 100, 1.0)
        severity = max(round(severity, 3), 0.1)

        formatted_violations = [" ".join(v.split()) for v in violations]
        max_items = 20
        items = formatted_violations[:max_items]
        summary = (
            f"{len(violations)} typography/formatting issue(s) found: "
            + "; ".join(items)
        )
        if len(violations) > max_items:
            summary += f"; ... and {len(violations) - max_items} more"

        return [
            self._make_finding(
                doc=doc,
                ac_code="TYPESET",
                title=title,
                summary=summary,
                judge_status="not_to_be_judged",
                human_status="proposed",
                evidence_item=None,
                snippet_override=summary,
                severity=severity,
                confidence=1.0,
            )
        ]

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

        self._accumulated_usage: dict = {}

        sazba_rules = [r for r in rules if r.ac_code == "TYPESET"]

        # Markdown uses deterministic TYPESET checks plus optional image vision checks.
        if not doc.docling_doc.pages:
            findings: list[Finding] = []
            if sazba_rules:
                findings.extend(self._check_sazba_md(doc, sazba_rules))

            has_md_images = self._has_resolvable_md_images(doc)
            if (doc.total_pictures or has_md_images) and llm_client:
                raw, usage, images_sent = self.execute_llm(
                    llm_client, doc, rules, rulebook, params
                )
                self._accumulated_usage = merge_usage(self._accumulated_usage, usage)
                findings.extend(self.process_vision_findings(doc, raw, rules, params))
                # If no images were encoded, emit deterministic UML_MISSING.
                if images_sent == 0:
                    nouml_active = any(r.ac_code == "UML_MISSING" for r in rules)
                    if nouml_active:
                        findings.append(
                            self._make_finding(
                                doc=doc,
                                ac_code="UML_MISSING",
                                title=self._title_for_ac_code(rules, "UML_MISSING"),
                                summary=(
                                    "No UML Class Diagram was found in the document."
                                ),
                                judge_status="to_be_judged",
                                human_status="proposed",
                                evidence_item=None,
                                severity=1.0,
                                confidence=1.0,
                            )
                        )
                return findings

            # No resolvable images found for Markdown, emit deterministic UML_MISSING
            nouml_active = any(r.ac_code == "UML_MISSING" for r in rules)
            if nouml_active:
                findings.append(
                    self._make_finding(
                        doc=doc,
                        ac_code="UML_MISSING",
                        title=self._title_for_ac_code(rules, "UML_MISSING"),
                        summary="No UML Class Diagram was found in the document.",
                        judge_status="to_be_judged",
                        human_status="proposed",
                        evidence_item=None,
                        severity=1.0,
                        confidence=1.0,
                    )
                )
            return findings

        # PDF routes all active asset rules through execute_llm for one dispatch path.
        findings = []

        if not doc.total_pictures:
            # No extracted diagrams: execute_llm will skip analyse_assets (no images)
            # and use analyse_pages_only for page-level rules.
            if llm_client:
                raw, usage, _images_sent = self.execute_llm(
                    llm_client, doc, rules, rulebook, params
                )
                self._accumulated_usage = merge_usage(self._accumulated_usage, usage)
                findings.extend(self.process_vision_findings(doc, raw, rules, params))
            nouml_active = any(r.ac_code == "UML_MISSING" for r in rules)
            if nouml_active:
                findings.append(
                    self._make_finding(
                        doc=doc,
                        ac_code="UML_MISSING",
                        title=self._title_for_ac_code(rules, "UML_MISSING"),
                        summary="No UML Class Diagram was found in the document.",
                        judge_status="to_be_judged",
                        human_status="proposed",
                        evidence_item=None,
                        severity=1.0,
                        confidence=1.0,
                    )
                )
            return findings

        if not llm_client:
            return []
        raw, usage, images_sent = self.execute_llm(
            llm_client, doc, rules, rulebook, params
        )
        self._accumulated_usage = merge_usage(self._accumulated_usage, usage)
        findings = self.process_vision_findings(doc, raw, rules, params)
        if images_sent == 0:
            nouml_active = any(r.ac_code == "UML_MISSING" for r in rules)
            if nouml_active:
                findings.append(
                    self._make_finding(
                        doc=doc,
                        ac_code="UML_MISSING",
                        title=self._title_for_ac_code(rules, "UML_MISSING"),
                        summary="No UML Class Diagram was found in the document.",
                        judge_status="to_be_judged",
                        human_status="proposed",
                        evidence_item=None,
                        severity=1.0,
                        confidence=1.0,
                    )
                )
        return findings

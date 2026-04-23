"""LLM-based asset analyser. Visual quality of diagrams and figures.

Author: Matúš Csirik

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
- 'SAZBA': Typography and formatting violations (monospace identifiers, block
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
    from ..schemas.llm import LLMRule, Rulebook

logger = logging.getLogger(__name__)

# OpenAI fine-tuned binary classifier default model ID
BADUML_MODEL = "ft:gpt-4.1-2025-04-14:personal:baduml-classifier-gold:DU8txcxh"

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
    ) -> tuple[list[Any], dict]:
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

        raw_labels: dict = {}
        if any(r.backend == "classifier" for r in rules):
            raw_labels, classifier_usage = llm_client.run_vision_classifier(
                doc, rulebook.classifier_system_prompt, ft_model
            )
            usage = merge_usage(usage, classifier_usage)
        baduml_count = 0
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
                baduml_count += 1
        logger.info(
            "%d/%d images classified as BADUML by fine-tuned model.",
            baduml_count,
            len(raw_labels),
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
            diagram_findings, diagram_usage = llm_client.analyse_assets(
                doc, diagram_prompt, rulebook, model=model, temperature=temperature
            )
            findings.extend(diagram_findings)
            usage = merge_usage(usage, diagram_usage)

        page_rules = [
            r
            for r in rules
            if r.requires_pages and r.backend not in ("classifier", "deterministic")
        ]
        if page_rules and doc.docling_doc.pages:
            page_prompt = self.build_vision_system_prompt(page_rules, rulebook, doc)
            page_findings, page_usage = llm_client.analyse_pages_only(
                doc, page_prompt, rulebook, model=model, temperature=temperature
            )
            findings.extend(page_findings)
            usage = merge_usage(usage, page_usage)

        return findings, usage

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
        title = self._title_for_ac_code(sazba_rules, "SAZBA")
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
                        continue  # already formatted with monospace
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

        summary_lines = "\n".join(f"  - {v}" for v in violations[:20])
        summary = (
            f"{len(violations)} typography/formatting issue(s) found:\n{summary_lines}"
        )
        if len(violations) > 20:
            summary += f"\n  ... and {len(violations) - 20} more"

        return [
            self._make_finding(
                doc=doc,
                ac_code="SAZBA",
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

        sazba_rules = [r for r in rules if r.ac_code == "SAZBA"]

        # Markdown branch: deterministic SAZBA linting + vision LLM for diagrams
        if not doc.docling_doc.pages:
            findings: list[Finding] = []
            if sazba_rules:
                findings.extend(self._check_sazba_md(doc, sazba_rules))
            if doc.total_pictures and llm_client:
                raw, usage = self.execute_llm(llm_client, doc, rules, rulebook, params)
                self._accumulated_usage = merge_usage(self._accumulated_usage, usage)
                findings.extend(self.process_vision_findings(doc, raw, rules, params))
            return findings

        # PDF branch: execute_llm dispatches diagram/page/classifier rules internally.
        findings = []

        if not doc.total_pictures:
            # No extracted diagrams: execute_llm will skip analyse_assets (no images)
            # and use analyse_pages_only for page-level rules.
            if llm_client:
                raw, usage = self.execute_llm(llm_client, doc, rules, rulebook, params)
                self._accumulated_usage = merge_usage(self._accumulated_usage, usage)
                findings.extend(self.process_vision_findings(doc, raw, rules, params))
            nouml_active = any(
                r.backend == "deterministic" and r.ac_code == "NOUML" for r in rules
            )
            if nouml_active:
                findings.append(
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
                )
            return findings

        if not llm_client:
            return []
        raw, usage = self.execute_llm(llm_client, doc, rules, rulebook, params)
        self._accumulated_usage = merge_usage(self._accumulated_usage, usage)
        return self.process_vision_findings(doc, raw, rules, params)

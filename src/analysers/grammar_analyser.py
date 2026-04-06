"""Grammar and spelling analyser using LanguageTool (English and Slovak)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import TextItem

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.finding import Finding
    from ..schemas.ir import Document
    from ..schemas.llm import LLMFinding, LLMRule, Rulebook

logger = logging.getLogger(__name__)

_MIN_SECTION_WORDS: int = 10
_MAX_FINDINGS: int = 100

_SK_CHARS: frozenset[str] = frozenset("áÁäÄčČďĎéÉěĚíÍĺĹľĽňŇóÓôÔŕŔřŘšŠťŤúÚůŮýÝžŽ")
_SK_THRESHOLD: float = 0.02


_LT_SEVERITY: dict[str, float] = {
    "grammar": 0.4,
    "misspelling": 0.4,
}
_CH_TITLE = "Grammar and Spelling"
_ISSUE_TITLES: dict[str, str] = {
    "grammar": "Grammar Error",
    "misspelling": "Spelling Error",
}


def _lt_lang(text: str) -> str | None:
    """Return the LanguageTool language tag for text, or ``None`` to skip."""
    if sum(1 for ch in text if ch in _SK_CHARS) / max(len(text), 1) >= _SK_THRESHOLD:
        return "sk"
    return "en-US"


def _make_message(issue_type: str, snippet: str, replacements: list[str]) -> str:
    title = _ISSUE_TITLES[issue_type]
    msg = f"{title}: {snippet!r}" if snippet else title
    if replacements:
        alt = ", ".join(f"{r!r}" for r in replacements[:3])
        msg += f". Maybe: {alt}"
    return msg


class GrammarAnalyser(BaseLLMAnalyser):
    """LanguageTool-based grammar and spelling analyser for English and Slovak.

    Text items are grouped by section path, concatenated, and checked
    as a unit. Each match offset is mapped back to the originating item
    for anchor placement.
    """

    analyser_id: ClassVar[str] = "grammar_analyser"
    name: ClassVar[str] = "Grammar Analyser"

    # Cache keyed by lt_lang so each server starts only once
    _lt: ClassVar[dict[str, Any]] = {}

    def get_rules(
        self,
        rulebook: Rulebook,
        params: dict[str, Any] | None = None,
    ) -> list[LLMRule]:
        params = params or {}
        if params.get("grammar_engine", "local") == "local":
            return []

        language = params.get("language")
        if language == "cs":
            # Czech CH is handled by language_analyser.
            return []

        course = params.get("course")
        return [
            rule
            for rule in rulebook.rules
            if "CH" in rule.ac_codes
            and (rule.course is None or rule.course == course)
            and (rule.language is None or rule.language == language)
        ]

    def process_llm_findings(
        self,
        doc: Document,
        llm_findings: list[LLMFinding],
        rules: list[LLMRule],
        params: dict[str, Any] | None = None,
    ) -> list[Finding]:
        if (params or {}).get("grammar_engine", "local") == "local":
            return self._run_local_analysis(doc)
        return super().process_llm_findings(doc, llm_findings, rules, params)

    def analyse(
        self, doc: Document, params: dict[str, Any] | None = None
    ) -> list[Finding]:
        if (params or {}).get("grammar_engine", "local") != "local":
            return []
        return self._run_local_analysis(doc)

    def _run_local_analysis(self, doc: Document) -> list[Finding]:
        if doc.language == "cs":
            logger.debug(
                "Skipping grammar check, czech is not supported by LanguageTool"
            )
            return []

        groups: dict[str, list[tuple[str, TextItem, str]]] = {}
        for cref, item in doc.text_items.items():
            if not isinstance(item, TextItem):
                continue
            text = (item.text or "").strip()
            if not text:
                continue
            groups.setdefault(doc.section_paths.get(cref, ""), []).append(
                (cref, item, text)
            )

        findings: list[Finding] = []

        for section, entries in groups.items():
            combined = " ".join(t for _, _, t in entries)
            if len(combined.split()) < _MIN_SECTION_WORDS:
                continue

            lt_lang = _lt_lang(combined)
            if lt_lang is None:
                continue

            issues = self._check(combined, lt_lang)
            logger.debug("section %r [%s]: %d issue(s)", section, lt_lang, len(issues))

            # Map each match offset back to its originating TextItem
            offset_map: list[tuple[int, int, TextItem]] = []
            pos = 0
            for _, item, t in entries:
                offset_map.append((pos, pos + len(t), item))
                pos += len(t) + 1

            for issue in issues:
                source_item = entries[0][1]
                for start, end, item in offset_map:
                    if start <= issue["offset"] < end:
                        source_item = item
                        break
                findings.append(
                    self._make_finding(
                        doc=doc,
                        ac_code="CH",
                        title=_CH_TITLE,
                        summary=issue["message"],
                        judge_status="to_be_judged",
                        human_status="proposed",
                        evidence_item=source_item,
                        snippet_override=issue.get("snippet"),
                        severity=issue["severity"],
                        confidence=0.75,
                    )
                )

        return findings[:_MAX_FINDINGS]

    def _check(self, text: str, lt_lang: str) -> list[dict[str, Any]]:
        import language_tool_python

        if lt_lang not in GrammarAnalyser._lt:
            logger.debug("Initialising LanguageTool(%r)", lt_lang)
            GrammarAnalyser._lt[lt_lang] = language_tool_python.LanguageTool(lt_lang)

        try:
            matches = GrammarAnalyser._lt[lt_lang].check(text)
        except Exception as exc:
            logger.warning("LanguageTool.check() failed: %s", exc)
            return []

        issues: list[dict[str, Any]] = []
        for match in matches:
            severity = _LT_SEVERITY.get(match.rule_issue_type)
            if severity is None:
                continue
            snippet = text[match.offset : match.offset + match.error_length]
            issues.append(
                {
                    "message": _make_message(
                        match.rule_issue_type,
                        snippet,
                        list(match.replacements),
                    ),
                    "snippet": snippet or None,
                    "offset": match.offset,
                    "severity": severity,
                }
            )
        return issues

"""Grammar and spelling analyser using LanguageTool (English and Slovak).

Author: Matúš Csirik
"""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from docling_core.types.doc.document import TextItem

from .base_analyser import BaseLLMAnalyser

if TYPE_CHECKING:
    from ..schemas.document import Document
    from ..schemas.finding import Finding
    from ..schemas.llm import LLMRule, Rulebook

logger = logging.getLogger(__name__)

_MIN_SECTION_WORDS: int = 10
_MAX_FINDINGS: int = 100

_LT_SEVERITY: dict[str, float] = {
    "grammar": 0.4,
    "misspelling": 0.4,
}

# Single-token snippets that LanguageTool consistently flags as errors
# Checked case-insensitively against the raw matched snippet before a finding is emitted
_IGNORED_WORDS: frozenset[str] = frozenset(
    {
        # Programming language / compiler terminology
        "arity",
        "lexer",
        "lexeme",
        "parser",
        "ast",
        "dom",
        "sys",
        "py",
        "params",
        "expr",
        "main",
        "self",
        "token",
        "send",
        "parse",
        "lark",
        "parglare",
        "lalr",
        "etree",
        "minidom",
        # Built-in values / keywords treated as prose
        "nil",
        "true",
        "false",
        "idx",
        "login",
        "pyreverse",
        # Course-specific class and Lark parser token names
        "xmlvisitor",
        "xmlgenerator",
        "backcolon",
        "frontcolon",
        "blockstat",
        "blockpar",
        "exprbase",
        "exprsel",
        "sourcecode",
        # Python built-ins and common tools
        "isinstance",
        "argparse",
        "powershell",
        "vscode",
        # British English spelling flagged by en-US LanguageTool
        "analyser",
        "analysers",
        "analysing",
        "analysed",
    }
)

_CH_TITLE = "Grammar and Spelling"
_ISSUE_TITLES: dict[str, str] = {
    "grammar": "Grammar Error",
    "misspelling": "Spelling Error",
}


_DOC_LANG_TO_LT: dict[str, str] = {
    "sk": "sk",
    "en": "en-US",
}


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
        language = params.get("language")
        if language == "cs":
            # Czech CH is handled by content_analyser.
            return []

        course = params.get("course")
        disabled: set[str] = set(params.get("disabled_codes") or [])
        return [
            rule
            for rule in rulebook.rules
            if rule.ac_code == "CH"
            and rule.ac_code not in disabled
            and (rule.course is None or rule.course == course)
            and (rule.language is None or rule.language == language)
        ]

    def analyse(
        self,
        doc: Document,
        rulebook: Rulebook | None = None,
        params: dict[str, Any] | None = None,
        llm_client: Any | None = None,
    ) -> list[Finding]:
        if (params or {}).get("grammar_engine", "local") == "local":
            if rulebook is not None:
                rules = self.get_rules(rulebook, params)
                if not rules:
                    return []
            return self._run_local_analysis(doc)
        return super().analyse(doc, rulebook, params, llm_client)

    def _run_local_analysis(self, doc: Document) -> list[Finding]:
        lt_lang = _DOC_LANG_TO_LT.get(doc.language)
        if lt_lang is None:
            logger.debug(
                "Skipping grammar check, language %r is not supported by LanguageTool",
                doc.language,
            )
            return []

        groups: dict[str, list[tuple[str, TextItem, str]]] = {}
        for item, _ in doc.docling_doc.iterate_items():
            if not isinstance(item, TextItem):
                continue
            cref = item.get_ref().cref
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

            issues = self._check(combined, lt_lang)

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
            snippet_lower = snippet.lower()
            if snippet_lower in _IGNORED_WORDS:
                continue
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

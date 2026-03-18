from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import instructor
from openai import OpenAI

if TYPE_CHECKING:
    from .schemas.finding import Finding
    from .schemas.ir import Document
    from .schemas.llm import (
        JudgeModelResponse,
        JudgeVerdict,
        LLMFinding,
        LLMRule,
        Rulebook,
    )

logger = logging.getLogger(__name__)

JUDGE_MIN_CONFIDENCE: float = 0.1


class LLMClient:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = instructor.from_openai(
            OpenAI(api_key=os.environ.get(api_key_env))
        )

    def _build_grader_model_prompt(
        self, rules: list[LLMRule], rulebook: Rulebook
    ) -> str:
        rules_text = ""
        for r in rules:
            codes_str = "/".join(r.ac_codes)
            rules_text += f"- [{codes_str}]: {r.prompt_instruction}\n"

        template = "\n".join(rulebook.grader_model_prompt_template)
        return template.replace("{rules}", rules_text)

    def analyse_document(
        self, doc: Document, rules: list[LLMRule], rulebook: Rulebook
    ) -> list[LLMFinding]:
        """
        Extracts text from the document, adds cref tags and section context,
        includes table and code items, calls the LLM, and returns findings.
        """
        from .schemas.llm import GraderModelResponse

        logger.debug("analyse_document start")

        text_chunk = ""
        for cref, item in doc.text_items.items():
            section = doc.section_paths.get(cref, "")
            section_prefix = f"[Section: {section}] " if section else ""
            text_chunk += f"[Ref: {cref}] {section_prefix}{item.text}\n\n"

        if not text_chunk.strip() or not rules:
            logger.debug("No text to analyse or no rules provided. Skipping LLM call.")
            return []
        system_prompt = self._build_grader_model_prompt(rules, rulebook)
        logger.debug(f"Sending request to {self.model}")
        logger.debug("SYSTEM PROMPT:")
        logger.debug(system_prompt)

        try:
            response: GraderModelResponse = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_model=GraderModelResponse,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_chunk},
                ],
            )
        except Exception as e:
            logger.error(f"LLM API call or processing failed: {e}")
            return []

        logger.info(f"LLM Reasoning Chain: {response.reasoning_chain}")
        logger.info(f"Successfully parsed {len(response.findings)} findings from LLM.")
        return response.findings

    def judge_findings(
        self,
        findings: list[Finding],
        doc: Document,
        rulebook: Rulebook,
    ) -> None:
        """Run the judge model on proposed findings, modifying them in-place."""
        from .schemas.llm import JudgeModelResponse

        # Build a lookup of ac_code to LLMRule for prompt_instruction retrieval
        ac_to_rule: dict[str, LLMRule] = {}
        for rule in rulebook.rules:
            for code in rule.ac_codes:
                ac_to_rule[code] = rule

        # Pre-filter: auto-dismiss findings that are not worth judging.
        to_judge: list[Finding] = []
        for f in findings:
            if not f.anchors:
                logger.warning(
                    f"Auto-dismissing finding '{f.finding_id}' "
                    f"({f.ac_code}): no anchors"
                )
                f.status = "dismissed"
                continue
            if f.confidence is not None and f.confidence < JUDGE_MIN_CONFIDENCE:
                logger.debug(
                    f"Auto-dismissing finding '{f.finding_id}' "
                    f"({f.ac_code}): confidence {f.confidence:.2f} below threshold"
                )
                f.status = "dismissed"
                continue
            to_judge.append(f)

        if not to_judge:
            logger.info("No findings passed pre-filter; judge model skipped.")
            return

        logger.info(f"Sending {len(to_judge)} findings to judge model.")
        user_message = self._build_judge_user_message(to_judge, doc, ac_to_rule)

        try:
            response: JudgeModelResponse = self._client.chat.completions.create(
                model=self.model,
                temperature=0.0,
                max_tokens=self.max_tokens,
                response_model=JudgeModelResponse,
                messages=[
                    {
                        "role": "system",
                        "content": "\n".join(rulebook.judge_model_prompt),
                    },
                    {"role": "user", "content": user_message},
                ],
            )
        except Exception:
            logger.exception("Judge model LLM call failed.")
            return

        logger.debug(f"Judge reasoning: {response.reasoning_chain}")
        self._apply_verdicts(to_judge, response)

    def _build_judge_user_message(
        self,
        findings: list[Finding],
        doc: Document,
        ac_to_rule: dict[str, LLMRule],
    ) -> str:
        """Construct the user message for the Judge from a list of findings."""
        lines: list[str] = []
        for f in findings:
            # Retrieve passage text and section path from document
            cref = f.anchors[0].target.cref if f.anchors else ""
            passage = ""
            section_path = ""

            text_item = doc.text_items.get(cref)
            passage = getattr(text_item, "text", "") or "" if text_item else ""
            section_path = doc.section_paths.get(cref, "") if text_item else ""

            rule = ac_to_rule.get(f.ac_code)
            rule_def = (
                rule.prompt_instruction if rule else "(rule definition unavailable)"
            )

            snippet = f.anchors[0].snippet if f.anchors else None
            snippet_str = f'Snippet: "{snippet}"' if snippet else "Snippet: (none)"

            lines.append(
                f"### Finding ID: {f.finding_id}\n"
                f"AC Rule [{f.ac_code}]: {rule_def}\n"
                f"Section: {section_path or '(unknown)'}\n"
                f"Passage: {passage or '(unavailable)'}\n"
                f"{snippet_str}\n"
                f"Analyser Reason: {f.summary}\n"
                f"Severity: {f.severity}"
                f"Confidence: {f.confidence}"
            )

        return "\n\n".join(lines)

    def _apply_verdicts(
        self,
        findings: list[Finding],
        response: JudgeModelResponse,
    ) -> None:
        """Apply judge model verdicts to findings in-place."""
        verdict_map: dict[str, JudgeVerdict] = {
            v.finding_id: v for v in response.verdicts
        }

        for f in findings:
            verdict = verdict_map.get(f.finding_id)
            if verdict is None:
                logger.warning(
                    f"Judge returned no verdict for finding '{f.finding_id}', leaving as 'proposed'"
                )
                continue

            if verdict.decision == "dismissed":
                f.status = "dismissed"
            elif verdict.decision == "approved":
                f.status = "approved"
            elif verdict.decision == "adjusted":
                f.status = "approved"
                if verdict.adjusted_severity is not None:
                    f.severity = verdict.adjusted_severity
                if verdict.adjusted_confidence is not None:
                    f.confidence = verdict.adjusted_confidence

            logger.debug(
                f"Judge verdict for '{f.finding_id}': "
                f"{verdict.decision} — {verdict.rationale}"
            )

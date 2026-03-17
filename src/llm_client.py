from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from openai import OpenAI

if TYPE_CHECKING:
    from .schemas.ir import Document
    from .schemas.llm import LLMFinding, LLMRule, Rulebook

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        model: str = "gpt-4.1-nano",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = OpenAI(api_key=os.environ[api_key_env])

    def run_raw(self, system_prompt: str, text: str) -> dict[str, Any]:
        """Simple prompt and response, returns parsed JSON dict from the LLM."""
        logger.debug(f"Sending request to {self.model}")
        logger.debug("SYSTEM PROMPT:")
        logger.debug(system_prompt)

        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content
        logger.debug("RESPONSE:")
        logger.debug(content)

        if content is None:
            logger.error("LLM response content is empty.")
            return {}
        return json.loads(content)

    def _build_system_prompt(self, rules: list[LLMRule], rulebook: Rulebook) -> str:
        rules_text = ""
        for r in rules:
            codes_str = ", ".join(r.ac_codes)
            rules_text += f"- [{codes_str}]: {r.prompt_instruction}\n"

        joined_prompt = "\n".join(rulebook.system_prompt_template)
        return joined_prompt.replace("{rules}", rules_text)

    def analyse_document(
        self, doc: Document, rules: list[LLMRule], rulebook: Rulebook
    ) -> list[LLMFinding]:
        """
        Extracts text from the document, adds cref tags, calls the LLM,
        and returns findings.
        """
        from .schemas.llm import LLMFinding

        logger.debug("analyse_document start")

        text_chunk = ""
        for cref, item in doc.text_items.items():
            text_chunk += f"[Ref: {cref}] {item.text}\n\n"
        if not text_chunk.strip() or not rules:
            logger.debug("No text to analyse or no rules provided. Skipping LLM call.")
            return []
        system_prompt = self._build_system_prompt(rules, rulebook)
        try:
            raw_json = self.run_raw(system_prompt, text_chunk)
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return []

        llm_findings: list[LLMFinding] = []
        raw_findings = raw_json.get("findings", [])
        logger.debug(f"LLM returned {len(raw_findings)} raw findings.")

        for f_dict in raw_findings:
            try:
                llm_findings.append(LLMFinding(**f_dict))
            except Exception as e:
                logger.warning(f"Failed to parse LLM finding payload {f_dict}: {e}")

        logger.info(f"Successfully parsed {len(llm_findings)} findings from LLM.")
        return llm_findings

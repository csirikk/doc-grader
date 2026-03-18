from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import instructor
from openai import OpenAI

if TYPE_CHECKING:
    from .schemas.ir import Document
    from .schemas.llm import LLMFinding, LLMRule, Rulebook

logger = logging.getLogger(__name__)


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

    def _build_system_prompt(self, rules: list[LLMRule], rulebook: Rulebook) -> str:
        rules_text = ""
        for r in rules:
            codes_str = "/".join(r.ac_codes)
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
        from .schemas.llm import LLMResponse

        logger.debug("analyse_document start")

        text_chunk = ""
        for cref, item in doc.text_items.items():
            text_chunk += f"[Ref: {cref}] {item.text}\n\n"
        if not text_chunk.strip() or not rules:
            logger.debug("No text to analyse or no rules provided. Skipping LLM call.")
            return []
        system_prompt = self._build_system_prompt(rules, rulebook)
        logger.debug(f"Sending request to {self.model}")
        logger.debug("SYSTEM PROMPT:")
        logger.debug(system_prompt)

        try:
            response: LLMResponse = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_model=LLMResponse,
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

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from openai import OpenAI
from pydantic import ValidationError

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
        self._client = OpenAI(api_key=os.environ.get(api_key_env))

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

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from LLM: {e}")
            logger.debug(f"Raw content: {content}")
            return {}

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
        try:
            raw_json = self.run_raw(system_prompt, text_chunk)
            if not raw_json:
                return []

            validated_response = LLMResponse.model_validate(raw_json)
            logger.info(f"LLM Reasoning Chain: {validated_response.reasoning_chain}")
            llm_findings = validated_response.findings

        except ValidationError as e:
            logger.error(f"Pydantic validation failed for LLM response: {e}")
            return []
        except Exception as e:
            logger.error(f"LLM API call or processing failed: {e}")
            return []

        logger.info(f"Successfully parsed {len(llm_findings)} findings from LLM.")
        return llm_findings

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from openai import OpenAI

if TYPE_CHECKING:
    from .schemas.ir import Document
    from .schemas.llm import LLMEvaluation, LLMRule

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
        self._client = OpenAI(api_key=os.environ[api_key_env])

    def run_raw(self, system_prompt: str, text: str) -> dict[str, Any]:
        """Simple prompt and response, returns parsed JSON dict from the LLM."""
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
        if content is None:
            logger.error("LLM response content is empty.")
            return {}
        return json.loads(content)

    def _build_system_prompt(self, rules: list[LLMRule]) -> str:
        prompt = (
            "You are a strict academic reviewer for university project documentation.\n"
            "Analyze the provided text passages against these specific rules:\n\n"
        )

        for r in rules:
            prompt += f"- [{r.ac_code}]: {r.prompt_instruction}\n"

        prompt += (
            "\nThe text passages are prefixed with a canonical reference tag, e.g., [Ref: #/texts/1].\n"
            "You MUST return ONLY a JSON object with a single key 'findings', "
            "which is a list of objects. Each object MUST have:\n"
            "'ac_code': the code of the violated rule (e.g., 'HOV')\n"
            "'item_cref': the exact reference string of the offending paragraph (e.g., '#/texts/1')\n"
            "'snippet': the exact offending substring from the input text\n"
            "'reason': a brief one-sentence explanation for the student in English\n"
            "'severity': a float between 0.0 (trivial) and 1.0 (critical)\n\n"
            "If no issues exist, return {'findings': []}."
        )
        return prompt

    def evaluate_document(
        self, doc: Document, rules: list[LLMRule]
    ) -> list[LLMEvaluation]:
        """
        Extracts text from the document, adds cref tags, calls the LLM,
        and returns evaluations.
        """
        from .schemas.llm import LLMEvaluation

        text_chunk = ""
        for cref, item in doc.text_items.items():
            text_chunk += f"[Ref: {cref}] {item.text}\n\n"
        if not text_chunk.strip() or not rules:
            logger.debug("No text to evaluate or no rules provided.")
            return []

        system_prompt = self._build_system_prompt(rules)
        try:
            raw_json = self.run_raw(system_prompt, text_chunk)
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return []

        evals: list[LLMEvaluation] = []
        for f_dict in raw_json.get("findings", []):
            try:
                evals.append(LLMEvaluation(**f_dict))
            except Exception as e:
                logger.warning(f"Failed to parse LLM finding payload {f_dict}: {e}")

        return evals

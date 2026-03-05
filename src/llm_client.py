from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


class LLMClient:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = OpenAI(api_key=os.environ[api_key_env])

    def run(self, system_prompt: str, text: str) -> dict[str, Any]:
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
        return json.loads(response.choices[0].message.content)

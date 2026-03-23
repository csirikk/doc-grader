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
        LLMFinding,
        LLMRule,
        Rulebook,
        VisionModelResponse,
    )

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
        self,
        doc: Document,
        rules: list[LLMRule],
        rulebook: Rulebook,
        model: str | None = None,
    ) -> list[LLMFinding]:
        """Extract document text, call the grader model, and return findings."""
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
        logger.debug(
            f"Sending request to {self.model}. SYSTEM PROMPT:\n{system_prompt}"
        )

        try:
            response: GraderModelResponse = self._client.chat.completions.create(
                model=model or self.model,
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

    def _build_vision_grader_prompt(
        self, rules: list[LLMRule], rulebook: Rulebook
    ) -> str:
        rules_text = ""
        for r in rules:
            codes_str = "/".join(r.ac_codes)
            rules_text += f"- [{codes_str}]: {r.prompt_instruction}\n"

        template = "\n".join(rulebook.vision_model_prompt_template)
        return template.replace("{rules}", rules_text)

    def analyse_assets(
        self,
        doc: Document,
        rules: list[LLMRule],
        rulebook: Rulebook,
        model: str | None = None,
    ) -> list:
        """Encode all PictureItems (with page context) and call the vision model."""
        import base64
        import io

        from .schemas.llm import VisionModelResponse

        if not rules:
            logger.debug("No asset rules provided. Skipping vision LLM call.")
            return []

        def _encode_pil(pil_image) -> str:
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")

        user_content: list[dict] = []
        n_images = 0
        for item in doc.docling_doc.pictures:
            cref = item.get_ref().cref

            # Send the surrounding page image first so the model can judge
            # contrast against the document background (BW).
            if item.prov:
                page_no = item.prov[0].page_no
                page = doc.docling_doc.pages.get(page_no)
                if page and page.image and page.image.pil_image:
                    b64 = _encode_pil(page.image.pil_image)
                    user_content.append(
                        {"type": "text", "text": f"[Page context for {cref}]"}
                    )
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        }
                    )

            user_content.append({"type": "text", "text": f"[Ref: {cref}]"})
            if item.image is not None and item.image.pil_image is not None:
                b64 = _encode_pil(item.image.pil_image)
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
                n_images += 1

        if n_images == 0:
            logger.debug("No picture images available. Skipping vision LLM call.")
            return []

        user_content.append(
            {
                "type": "text",
                "text": "Analyse the diagram(s) above for violations.",
            }
        )

        system_prompt = self._build_vision_grader_prompt(rules, rulebook)
        logger.debug(f"Sending {n_images} picture(s) to vision model.")

        messages: list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response: VisionModelResponse = self._client.chat.completions.create(
                model=model or self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_model=VisionModelResponse,
                messages=messages,
            )
        except Exception as e:
            logger.error(f"Vision LLM API call failed: {e}")
            return []

        logger.info(f"Vision LLM Reasoning Chain: {response.reasoning_chain}")
        logger.info(f"Successfully parsed {len(response.findings)} vision findings.")
        return response.findings

    def judge_findings(
        self,
        findings: list[Finding],
        doc: Document,
        rulebook: Rulebook,
    ) -> JudgeModelResponse | None:
        """Run the judge model and return its response."""
        from .schemas.llm import JudgeModelResponse

        # Build a lookup of ac_code to LLMRule for prompt_instruction retrieval
        ac_to_rule: dict[str, LLMRule] = {}
        for rule in rulebook.rules:
            for code in rule.ac_codes:
                ac_to_rule[code] = rule

        if not findings:
            logger.info("No findings passed to judge model.")
            return None

        logger.info(f"Sending {len(findings)} findings to judge model.")
        user_message = self._build_judge_user_message(findings, doc, ac_to_rule)

        try:
            response: JudgeModelResponse = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
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
            return None

        logger.debug(f"Judge reasoning: {response.reasoning_chain}")
        return response

    def _build_judge_user_message(
        self,
        findings: list[Finding],
        doc: Document,
        ac_to_rule: dict[str, LLMRule],
    ) -> str:
        """Construct the user message for the Judge from a list of findings."""
        parts: list[str] = []
        for f in findings:
            # Retrieve passage text and section path from document
            cref = f.anchors[0].target.cref if f.anchors else ""
            text_item = doc.text_items.get(cref)
            passage = getattr(text_item, "text", "") or "" if text_item else ""
            section_path = doc.section_paths.get(cref, "") if text_item else ""

            rule = ac_to_rule.get(f.ac_code)
            rule_def = (
                rule.prompt_instruction if rule else "(rule definition unavailable)"
            )

            snippet = f.anchors[0].snippet if f.anchors else None
            snippet_str = f'Snippet: "{snippet}"' if snippet else "Snippet: (none)"

            parts.append(
                f"### Finding ID: {f.finding_id}\n"
                f"AC Rule [{f.ac_code}]: {rule_def}\n"
                f"Section: {section_path or '(unknown)'}\n"
                f"Passage: {passage or '(unavailable)'}\n"
                f"{snippet_str}\n"
                f"Detector Reason: {f.summary}\n"
                f"Severity: {f.severity}\n"
                f"Confidence: {f.confidence}"
            )

        return "\n\n".join(parts)

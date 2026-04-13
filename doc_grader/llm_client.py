from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, TypedDict

from openai import OpenAI

if TYPE_CHECKING:
    from .schemas.finding import Finding
    from .schemas.ir import Document
    from .schemas.llm import (
        JudgeModelResponse,
        LLMFinding,
        LLMRule,
        Rulebook,
    )

# Pricing table: (input_usd_per_1m, cached_usd_per_1m, output_usd_per_1m)
# Sources: https://developers.openai.com/api/docs/pricing and microsoft (as of 4/7/2026)
_MODEL_PRICING: list[tuple[str, tuple[float, float, float]]] = [
    ("gpt-5.4-nano", (0.20, 0.02, 1.25)),
    ("gpt-5.4-mini", (0.75, 0.075, 4.50)),
    ("gpt-5.4", (2.50, 0.25, 15.00)),
    ("gpt-5", (15.25, 0.125, 10.00)),
    ("gpt-5-mini", (0.25, 0.0025, 2.00)),
    ("gpt-4.1", (2.00, 0.50, 8.00)),  # fine-tuned baduml binary classifier base
]

_USD_TO_EUR: float = 0.92


def _lookup_pricing(model: str) -> tuple[float, float, float] | None:
    """Return (input, cached_input, output) rates in USD per 1M tokens, or None."""
    lower = model.lower()
    for prefix, rates in _MODEL_PRICING:
        if prefix in lower:
            return rates
    return None


class _UsageEntry(TypedDict):
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    cost_eur: float | None


logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        model: str = "gpt-5.4-nano-2026-03-17",
        temperature: float = 0.0,
        max_completion_tokens: int = 2048,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self._client = OpenAI(api_key=os.environ.get(api_key_env))
        self._usage_by_model: dict[str, _UsageEntry] = {}

    def reset_usage(self) -> None:
        """Clear per-document usage accumulators."""
        self._usage_by_model = {}

    def _record_usage(self, model: str, usage: object | None) -> None:
        """Accumulate token counts and cost from a single API response."""
        if usage is None:
            return
        prompt = getattr(usage, "prompt_tokens", 0) or 0
        completion = getattr(usage, "completion_tokens", 0) or 0
        details = getattr(usage, "prompt_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0

        rates = _lookup_pricing(model)
        billable_input = max(prompt - cached, 0)
        if rates is not None:
            in_rate, cached_rate, out_rate = rates
            call_cost_usd = (
                billable_input * in_rate + cached * cached_rate + completion * out_rate
            ) / 1_000_000.0
            call_cost_eur: float | None = round(call_cost_usd * _USD_TO_EUR, 6)
        else:
            call_cost_eur = None

        entry: _UsageEntry = self._usage_by_model.setdefault(
            model,
            _UsageEntry(
                calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                cached_tokens=0,
                cost_eur=0.0,
            ),
        )
        entry["calls"] += 1
        entry["prompt_tokens"] += prompt
        entry["completion_tokens"] += completion
        entry["cached_tokens"] += cached
        if call_cost_eur is None or entry["cost_eur"] is None:
            entry["cost_eur"] = None
        else:
            entry["cost_eur"] = round(entry["cost_eur"] + call_cost_eur, 6)

    def get_usage_summary(self) -> dict:
        """Return accumulated token usage and cost for the current document."""
        total_prompt: int = sum(
            (e["prompt_tokens"] for e in self._usage_by_model.values()), 0
        )
        total_completion: int = sum(
            (e["completion_tokens"] for e in self._usage_by_model.values()), 0
        )
        total_cached: int = sum(
            (e["cached_tokens"] for e in self._usage_by_model.values()), 0
        )
        costs = [e["cost_eur"] for e in self._usage_by_model.values()]
        total_cost: float | None = (
            None
            if any(c is None for c in costs)
            else round(sum(c for c in costs if c is not None), 6)
        )
        return {
            "by_model": self._usage_by_model,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_cached_tokens": total_cached,
            "total_cost_eur": total_cost,
        }

    @staticmethod
    def _encode_pil(pil_image) -> str:
        import base64
        import io

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def analyse_document(
        self,
        doc: Document,
        system_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> list[LLMFinding]:
        """Extract document text, call the grader model, and return findings."""
        from docling_core.types.doc.document import TextItem

        from .schemas.llm import GraderModelResponse

        logger.debug("analyse_document start")

        text_chunk = ""
        for item, _ in doc.docling_doc.iterate_items():
            if not isinstance(item, TextItem):
                continue
            cref = item.get_ref().cref
            section = doc.section_paths.get(cref, "")
            section_prefix = f"[Section: {section}] " if section else ""
            text_chunk += f"[Ref: {cref}] {section_prefix}{item.text}\n\n"

        if not text_chunk.strip() or not system_prompt:
            logger.debug(
                "No text to analyse or no system prompt provided. Skipping LLM call."
            )
            return []
        logger.debug(
            f"Sending request to {self.model}. SYSTEM PROMPT:\n{system_prompt}"
        )

        try:
            response = self._client.beta.chat.completions.parse(
                model=model or self.model,
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                max_completion_tokens=self.max_completion_tokens,
                response_format=GraderModelResponse,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_chunk},
                ],
            )
        except Exception as e:
            logger.error(f"LLM API call or processing failed: {e}")
            return []

        self._record_usage(model or self.model, response.usage)
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("LLM returned unparseable response.")
            return []
        logger.info(f"LLM Reasoning Chain: {parsed_response.reasoning_chain}")
        logger.info(
            f"Successfully parsed {len(parsed_response.findings)} findings from LLM."
        )
        return parsed_response.findings

    def analyse_assets(
        self,
        doc: Document,
        system_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> list:
        """Run the OpenAI vision LLM on all pictures in the document.

        Returns raw VisionFinding-compatible objects as produced by the model.
        """
        from .schemas.llm import VisionModelResponse

        user_content: list[dict] = []
        n_images = 0
        for idx, item in enumerate(doc.docling_doc.pictures):
            cref = item.get_ref().cref
            # Send the surrounding page image first so the model can judge
            # contrast against the document background (BW).
            if item.prov:
                page_no = item.prov[0].page_no
                page = doc.docling_doc.pages.get(page_no)
                if page and page.image and page.image.pil_image:
                    b64 = self._encode_pil(page.image.pil_image)
                    user_content.append(
                        {"type": "text", "text": f"[Page context for {cref}]"}
                    )
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        }
                    )

            pil_img = doc.get_picture_pil(idx, item)
            if pil_img is not None:
                b64 = self._encode_pil(pil_img)
                user_content.append({"type": "text", "text": f"[Ref: {cref}]"})
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

        logger.debug(f"Sending {n_images} picture(s) to vision model.")

        messages: list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response = self._client.beta.chat.completions.parse(
                model=model or self.model,
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                max_completion_tokens=self.max_completion_tokens,
                response_format=VisionModelResponse,
                messages=messages,
            )
        except Exception as e:
            logger.error(f"Vision LLM API call failed: {e}")
            return []

        self._record_usage(model or self.model, response.usage)
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("Vision LLM returned unparseable response.")
            return []
        logger.info(f"Vision LLM Reasoning Chain: {parsed_response.reasoning_chain}")
        logger.info(
            f"Successfully parsed {len(parsed_response.findings)} vision findings."
        )
        return parsed_response.findings

    def run_vision_classifier(
        self,
        doc: Document,
        system_prompt: str,
        model: str,
    ) -> dict[str, str]:
        """Send each picture in the document to the fine-tuned OpenAI vision model
        and return the raw text label keyed by the picture cref.
        """
        results: dict[str, str] = {}

        for idx, item in enumerate(doc.docling_doc.pictures):
            cref = item.get_ref().cref
            pil_img = doc.get_picture_pil(idx, item)
            if pil_img is None:
                logger.warning(
                    "No image available for %s, skipping classification.", cref
                )
                continue

            b64 = self._encode_pil(pil_img)
            try:
                response = self._client.beta.chat.completions.parse(
                    model=model,
                    temperature=self.temperature,
                    max_completion_tokens=self.max_completion_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Analyze this diagram for UML compliance.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        },
                    ],
                )
            except Exception as e:
                logger.error("Classifier call failed for %s: %s", cref, e)
                continue

            self._record_usage(model or self.model, response.usage)
            results[cref] = (response.choices[0].message.content or "").strip()
            logger.info("Classified [%s] as %r", cref, results[cref])

        return results

    def judge_findings(
        self,
        findings: list[Finding],
        doc: Document,
        rulebook: Rulebook,
        model: str | None = None,
        temperature: float | None = None,
    ) -> JudgeModelResponse | None:
        """Run the judge model and return its response."""
        from .schemas.llm import JudgeModelResponse

        if not findings:
            logger.info("No findings passed to judge model.")
            return None

        ac_to_rule: dict[str, LLMRule] = {}
        for rule in rulebook.rules:
            for code in rule.ac_codes:
                ac_to_rule[code] = rule

        prompt_lines = rulebook.judge_model_prompt_template
        logger.info("Sending %d findings to the judge model.", len(findings))

        user_message = self._build_judge_user_message(findings, doc, ac_to_rule)

        messages: list = [
            {"role": "system", "content": "\n".join(prompt_lines)},
            {"role": "user", "content": user_message},
        ]

        try:
            response = self._client.beta.chat.completions.parse(
                model=model or self.model,
                temperature=temperature
                if temperature is not None
                else self.temperature,
                response_format=JudgeModelResponse,
                messages=messages,
            )
        except Exception:
            logger.exception("Judge model LLM call failed.")
            return None

        self._record_usage(model or self.model, response.usage)
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("Judge LLM returned unparseable response.")
            return None

        logger.debug("Judge reasoning: %s", parsed_response.reasoning_chain)
        return parsed_response

    def _build_judge_user_message(
        self,
        findings: list[Finding],
        doc: Document,
        ac_to_rule: dict[str, LLMRule],
    ) -> str | list[dict]:
        """Construct the user message for the Judge from a list of findings.

        For PDF source documents the full file is attached as an inline base64
        file content part so the model can read the original layout and context.
        For markdown source documents the raw text is prepended as a document
        section before the findings list.
        """
        parts: list[str] = []
        for f in findings:
            # Primary passage
            cref = f.anchors[0].target.cref if f.anchors else ""
            is_picture = cref.startswith("#/pictures/")
            from docling_core.types.doc.document import RefItem

            if is_picture:
                try:
                    picture_item = RefItem.model_validate({"$ref": cref}).resolve(
                        doc=doc.docling_doc
                    )
                except Exception:
                    picture_item = None
                page_no = (
                    picture_item.prov[0].page_no
                    if picture_item and picture_item.prov
                    else None
                )
                passage = f"(Visual finding, inspect the diagram {cref}" + (
                    f" on page {page_no})" if page_no else ")"
                )
                section_path = f"Page {page_no}" if page_no else cref
            else:
                try:
                    text_item = RefItem.model_validate({"$ref": cref}).resolve(
                        doc=doc.docling_doc
                    )
                except Exception:
                    text_item = None
                passage = getattr(text_item, "text", "") or "" if text_item else ""
                section_path = doc.section_paths.get(cref, "") if text_item else ""

            rule = ac_to_rule.get(f.ac_code)
            if rule:
                rule_def = rule.prompt_instruction
                if rule.judge_instruction:
                    rule_def += f"\n[JUDGE OVERRIDE]: {rule.judge_instruction}"
            else:
                rule_def = "(rule definition unavailable)"

            anchor_lines: list[str] = []
            for i, anchor in enumerate(f.anchors, 1):
                loc = anchor.section_path or anchor.target.cref or "?"
                snip = anchor.snippet or "(no snippet)"
                anchor_lines.append(f"[{i}] {loc}: {snip}")
            anchors_str = "\n".join(anchor_lines) if anchor_lines else "  (none)"

            eval_lines: list[str] = []
            for ev in f.model_evals:
                score_str = f"{ev.score:.3f}" if ev.score is not None else "n/a"
                spec_text = (ev.raw or {}).get("spec_text", "") if ev.raw else ""
                if spec_text:
                    eval_lines.append(
                        f"sim={score_str} ({ev.label or 'match'})"
                        f"\nSpec passage: {spec_text[:300]}"
                    )
            evals_str = "\n".join(eval_lines) if eval_lines else "(no model evidence)"

            # Stats as a compact one-liner
            stats_str = ", ".join(f"{s.name}={s.value}" for s in f.stats) or "(none)"

            parts.append(
                f"### Finding ID: {f.finding_id}\n"
                f"AC Rule [{f.ac_code}]: {rule_def}\n"
                f"Section: {section_path or '(unknown)'}\n"
                f"Passage: {passage or '(unavailable)'}\n"
                f"Judge status: {f.judge_status}\n"
                f"Human status: {f.human_status}\n"
                f"Anchor snippets:\n{anchors_str}\n"
                f"Similarity evidence (student vs spec):\n{evals_str}\n"
                f"Stats: {stats_str}\n"
                f"Detector Reason: {f.summary}\n"
                f"Severity: {f.severity}\n"
                f"Confidence: {f.confidence}"
            )

        findings_text = "\n\n".join(parts)

        has_page_images = bool(doc.docling_doc.pages)
        doc_context_intro = "### ORIGINAL DOCUMENT CONTENT\n"
        if has_page_images:
            doc_context_intro += (
                "The original PDF page images are attached below. "
                "For visual or typography-sensitive checks (for example spacing "
                "before punctuation such as ' .' or ',') use the page images as "
                "the source of truth. Do not rely only on extracted text for these "
                "checks.\n"
            )

        user_content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"### FINDINGS TO EVALUATE\n{findings_text}\n\n{doc_context_intro}"
                ),
            }
        ]

        pages = doc.docling_doc.pages
        if pages:
            for page_no, page in sorted(pages.items()):
                if page.image and page.image.pil_image:
                    b64 = self._encode_pil(page.image.pil_image)
                    user_content.append({"type": "text", "text": f"[Page {page_no}]"})
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        }
                    )
        else:
            from pathlib import Path

            source = Path(doc.doc_ref.source_path)
            try:
                raw_text = source.read_text(encoding="utf-8")
                user_content.append({"type": "text", "text": raw_text})
            except Exception as e:
                logger.warning(
                    "Could not read source file %s for judge context: %s", source, e
                )

            for idx, item in enumerate(doc.docling_doc.pictures):
                cref = item.get_ref().cref
                pil_img = doc.get_picture_pil(idx, item)
                if pil_img is not None:
                    b64 = self._encode_pil(pil_img)
                    user_content.append({"type": "text", "text": f"[Diagram {cref}]"})
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        }
                    )

        return user_content

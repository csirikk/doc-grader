"""Wrapper around the LLM API used by the grader.

Author: Matúš Csirik

This module encapsulates calls to the OpenAI client for text and vision
workloads, token usage accounting and simple cost estimation helpers.
"""

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
        Rulebook,
    )

from .schemas.ir import get_picture_pil

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


def merge_usage(
    a: dict[str, _UsageEntry], b: dict[str, _UsageEntry]
) -> dict[str, _UsageEntry]:
    """Merge two by-model usage dictionaries.

    Args:
        a: First usage mapping keyed by model name.
        b: Second usage mapping keyed by model name.

    Returns:
        A new mapping keyed by model name with aggregated usage counts and
        monetary cost when available.
    """
    result: dict[str, _UsageEntry] = dict(a)
    for model, entry in b.items():
        if model in result:
            existing = result[model]
            cost_a = existing["cost_eur"]
            cost_b = entry["cost_eur"]
            merged_cost: float | None = (
                None
                if (cost_a is None or cost_b is None)
                else round(cost_a + cost_b, 6)
            )
            result[model] = _UsageEntry(
                calls=existing["calls"] + entry["calls"],
                prompt_tokens=existing["prompt_tokens"] + entry["prompt_tokens"],
                completion_tokens=(
                    existing["completion_tokens"] + entry["completion_tokens"]
                ),
                cached_tokens=existing["cached_tokens"] + entry["cached_tokens"],
                cost_eur=merged_cost,
            )
        else:
            result[model] = entry
    return result


def summarise_usage(by_model: dict[str, _UsageEntry]) -> dict:
    """Compute aggregate totals from a by-model usage mapping.

    The returned mapping includes per-model copies plus totals for prompt,
    completion and cached tokens and the total cost in euros when available.

    Args:
        by_model: Mapping of usage entries keyed by model name.

    Returns:
        A dictionary containing the original ``by_model`` mapping and aggregate
        totals.
    """
    total_prompt = sum(e["prompt_tokens"] for e in by_model.values())
    total_completion = sum(e["completion_tokens"] for e in by_model.values())
    total_cached = sum(e["cached_tokens"] for e in by_model.values())
    costs = [e["cost_eur"] for e in by_model.values()]
    total_cost: float | None = (
        None
        if any(c is None for c in costs)
        else round(sum(c for c in costs if c is not None), 6)
    )
    return {
        "by_model": dict(by_model),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_cached_tokens": total_cached,
        "total_cost_eur": total_cost,
    }


class LLMClient:
    def __init__(
        self,
        model: str = "gpt-5.4-nano-2026-03-17",
        temperature: float = 0.0,
        max_completion_tokens: int = 8192,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self._client = OpenAI(api_key=os.environ.get(api_key_env))

    def _build_call_usage(
        self, model: str, usage: object | None
    ) -> dict[str, _UsageEntry]:
        """Build a by-model usage dict for a single API response."""
        if usage is None:
            return {}
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

        return {
            model: _UsageEntry(
                calls=1,
                prompt_tokens=prompt,
                completion_tokens=completion,
                cached_tokens=cached,
                cost_eur=call_cost_eur,
            )
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
    ) -> tuple[list[LLMFinding], dict[str, _UsageEntry]]:
        """Extract document text, call the grader model and return findings.

        The method serialises the document into a single text chunk, sends it
        to the configured grader model and returns parsed findings together
        with per-model token usage information.

        Args:
            doc: Document wrapper providing Docling content and page images.
            system_prompt: System prompt text or template for the grader.
            model: Optional override model name for this call.
            temperature: Optional temperature override for this call.

        Returns:
            A tuple ``(findings, usage)`` where ``findings`` is a list of
            parsed LLM findings and ``usage`` is a by-model usage mapping.
        """
        from docling_core.types.doc.document import TableItem, TextItem

        from .schemas.llm import GraderModelResponse

        logger.debug("analyse_document start")

        text_chunk = ""
        for item, _ in doc.docling_doc.iterate_items():
            if isinstance(item, TextItem):
                text_content = item.text
            elif isinstance(item, TableItem):
                text_content = item.export_to_markdown(doc=doc.docling_doc)
            else:
                continue

            cref = item.get_ref().cref
            section = doc.section_paths.get(cref, "")
            section_prefix = f"[Section: {section}] " if section else ""
            text_chunk += f"[Ref: {cref}] {section_prefix}{text_content}\n\n"

        if not text_chunk.strip() or not system_prompt:
            logger.debug(
                "No text to analyse or no system prompt provided. Skipping LLM call."
            )
            return [], {}
        logger.debug("Sending request to %s.", self.model)
        messages: list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text_chunk},
        ]

        try:
            response = self._client.beta.chat.completions.parse(
                model=model or self.model,
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                max_completion_tokens=self.max_completion_tokens,
                response_format=GraderModelResponse,
                messages=messages,
            )
        except Exception as e:
            logger.error("LLM API call or processing failed: %s", e)
            return [], {}

        call_usage = self._build_call_usage(response.model, response.usage)
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("LLM returned unparseable response.")
            return [], call_usage

        for f in parsed_response.findings:
            f.model_name = response.model

        logger.info("LLM Reasoning Chain: %s", parsed_response.reasoning_chain)
        logger.info(
            "Successfully parsed %d findings from LLM.", len(parsed_response.findings)
        )
        return parsed_response.findings, call_usage

    def _build_page_context_content(self, doc: Document, header: str) -> list[dict]:
        """Return user-content blocks for all document pages, ordered by page number.

        Args:
            doc: Document containing pages with images.
            header: Introductory header text to include once.

        Returns:
            A list of content blocks suitable for inclusion in the LLM input.
        """
        content: list[dict] = []
        valid_pages = [
            (page_no, page)
            for page_no, page in sorted(doc.docling_doc.pages.items())
            if page and page.image and page.image.pil_image
        ]
        if not valid_pages:
            return content
        content.append({"type": "text", "text": header})
        for page_no, page in valid_pages:
            b64 = self._encode_pil(page.image.pil_image)  # type: ignore[union-attr]
            content.append({"type": "text", "text": f"[Context: Full Page {page_no}]"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )
        return content

    def analyse_assets(
        self,
        doc: Document,
        system_prompt: str,
        rulebook: Rulebook,
        model: str | None = None,
        temperature: float | None = None,
    ) -> tuple[list, dict[str, _UsageEntry]]:
        """Run the vision LLM on all pictures in the document.

        The method collects images from the document, attaches optional
        page-level context and forwards them to the vision model defined in
        the rulebook. It returns the raw model findings and token usage.

        Args:
            doc: Document containing pictures to analyse.
            system_prompt: Vision model system prompt.
            rulebook: Rulebook providing vision prompt templates.
            model: Optional model override.
            temperature: Optional temperature override.

        Returns:
            Tuple of (vision findings list, by-model usage mapping).
        """
        from .schemas.llm import VisionModelResponse

        user_content: list[dict] = []
        n_images = 0

        # Send all document pages as context
        page_context = self._build_page_context_content(
            doc, rulebook.vision_page_context_header
        )
        user_content.extend(page_context)

        user_content.append({"type": "text", "text": rulebook.vision_diagrams_header})
        for idx, item in enumerate(doc.docling_doc.pictures):
            cref = item.get_ref().cref
            pil_img = get_picture_pil(doc, idx, item)
            if pil_img is not None:
                b64 = self._encode_pil(pil_img)
                page_ref = f" (on Page {item.prov[0].page_no})" if item.prov else ""

                user_content.append(
                    {"type": "text", "text": f"[Ref: {cref}]{page_ref}"}
                )
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
                n_images += 1

        if n_images == 0:
            logger.debug("No picture images available. Skipping vision LLM call.")
            return [], {}

        user_content.append({"type": "text", "text": rulebook.vision_diagrams_footer})

        logger.debug("Sending %d picture(s) to vision model.", n_images)

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
            logger.error("Vision LLM API call failed: %s", e)
            return [], {}

        call_usage = self._build_call_usage(response.model, response.usage)
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("Vision LLM returned unparseable response.")
            return [], call_usage

        for f in parsed_response.findings:
            f.model_name = response.model

        logger.info("Vision LLM Reasoning Chain: %s", parsed_response.reasoning_chain)
        logger.info(
            "Successfully parsed %d vision findings.", len(parsed_response.findings)
        )
        return parsed_response.findings, call_usage

    def analyse_pages_only(
        self,
        doc: Document,
        system_prompt: str,
        rulebook: Rulebook,
        model: str | None = None,
        temperature: float | None = None,
    ) -> tuple[list, dict[str, _UsageEntry]]:
        """Run the vision LLM on document pages when no diagrams are present.

        This is used for PDFs without diagram images so the vision model can
        still evaluate page-level properties. Each page is labelled to allow
        citation from the model output.

        Args:
            doc: Document with page images to send.
            system_prompt: Vision model system prompt.
            rulebook: Rulebook providing page-level prompt templates.
            model: Optional model override.
            temperature: Optional temperature override.

        Returns:
            Tuple of (vision findings list, by-model usage mapping).
        """
        from .schemas.llm import VisionModelResponse

        user_content: list[dict] = []
        n_pages = 0

        for page_no, page in sorted(doc.docling_doc.pages.items()):
            if not (page and page.image and page.image.pil_image):
                continue
            b64 = self._encode_pil(page.image.pil_image)
            user_content.append({"type": "text", "text": f"[Ref: #/pages/{page_no}]"})
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )
            n_pages += 1

        if not n_pages:
            logger.debug("No page images available. Skipping pages-only vision call.")
            return [], {}

        user_content.append({"type": "text", "text": rulebook.vision_pages_only_footer})

        logger.debug("Sending %d pages to vision model", n_pages)

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
            logger.error("Pages-only vision LLM API call failed: %s", e)
            return [], {}

        call_usage = self._build_call_usage(response.model, response.usage)
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("Pages-only vision LLM returned unparseable response.")
            return [], call_usage

        for f in parsed_response.findings:
            f.model_name = response.model

        logger.info(
            "Pages-only vision LLM reasoning: %s", parsed_response.reasoning_chain
        )
        logger.info(
            "Successfully parsed %d pages-only vision findings.",
            len(parsed_response.findings),
        )
        return parsed_response.findings, call_usage

    def run_vision_classifier(
        self,
        doc: Document,
        system_prompt: str,
        model: str,
    ) -> tuple[dict[str, dict[str, str]], dict[str, _UsageEntry]]:
        """Classify each picture using a fine-tuned vision classifier.

        Args:
            doc: Document containing pictures to classify.
            system_prompt: System prompt for the classifier.
            model: Model name of the fine-tuned classifier.

        Returns:
            A tuple ``(results, usage)`` where ``results`` maps picture cref to
            a dict containing the assigned label and raw response text, and
            ``usage`` aggregates token usage across classifier calls.
        """
        results: dict[str, dict[str, str]] = {}
        call_usage: dict[str, _UsageEntry] = {}

        for idx, item in enumerate(doc.docling_doc.pictures):
            cref = item.get_ref().cref
            pil_img = get_picture_pil(doc, idx, item)
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
                    # System prompt is hardcoded to the one
                    # that was used for fine-tuning
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

            call_usage = merge_usage(
                call_usage, self._build_call_usage(model, response.usage)
            )
            raw_content = (response.choices[0].message.content or "").strip()

            u = raw_content.upper()
            if "BADUML" in u:
                label = "BADUML"
            elif "GOODUML" in u:
                label = "GOODUML"
            else:
                label = "UNKNOWN"

            results[cref] = {"label": label, "raw": raw_content}
            logger.info("Classified %s as %r", cref, label)

        return results, call_usage

    def judge_findings(
        self,
        findings: list[Finding],
        doc: Document,
        rulebook: Rulebook,
        model: str | None = None,
        temperature: float | None = None,
    ) -> tuple[JudgeModelResponse | None, dict[str, _UsageEntry]]:
        """Run the judge model on a set of findings and return its response.

        The judge model receives a compact representation of each finding
        together with optional document context and page images when
        available. The method returns the parsed judge response and token
        usage. If no findings are provided it returns ``(None, {})``.

        Args:
            findings: List of findings to submit to the judge.
            doc: Document used to provide contextual material.
            rulebook: Rulebook that defines judge prompt templates.
            model: Optional model override.
            temperature: Optional temperature override.

        Returns:
            Tuple of (parsed JudgeModelResponse or None, by-model usage mapping).
        """
        from .schemas.llm import JudgeModelResponse

        if not findings:
            logger.info("No findings passed to judge model.")
            return None, {}

        prompt_lines = rulebook.judge_model_prompt_template
        user_message = self._build_judge_user_message(findings, doc, rulebook)

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
            return None, {}

        call_usage = self._build_call_usage(response.model, response.usage)
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("Judge LLM returned unparseable response.")
            return None, call_usage

        parsed_response.model_name = response.model

        logger.debug("Judge reasoning: %s", parsed_response.reasoning_chain)
        return parsed_response, call_usage

    def _build_judge_user_message(
        self,
        findings: list[Finding],
        doc: Document,
        rulebook: Rulebook,
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

            rule = rulebook.rules_by_code.get(f.ac_code)
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
        doc_context_intro = f"{rulebook.judge_doc_context_header}\n"
        if has_page_images:
            doc_context_intro += f"{rulebook.judge_doc_context_pdf_note}\n"

        user_content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"{rulebook.judge_findings_header}\n"
                    f"{findings_text}\n\n{doc_context_intro}"
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
                pil_img = get_picture_pil(doc, idx, item)
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

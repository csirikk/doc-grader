from __future__ import annotations  # TODO: add better token usage tracking

import logging
import os
from typing import TYPE_CHECKING

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

    @staticmethod
    def _encode_pil(pil_image) -> str:
        import base64
        import io

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _build_grader_model_prompt(
        self, rules: list[LLMRule], rulebook: Rulebook
    ) -> str:
        rules_text = ""
        for r in rules:
            codes_str = "/".join(r.ac_codes)
            rules_text += f"- {codes_str}: {r.prompt_instruction}\n"

        template = "\n".join(rulebook.grader_model_prompt_template)
        return template.replace("{rules}", rules_text)

    def analyse_document(
        self,
        doc: Document,
        rules: list[LLMRule],
        rulebook: Rulebook,
        model: str | None = None,
        params: dict | None = None,
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

        has_copy_rule = any("COPY" in r.ac_codes for r in rules)
        if has_copy_rule and params and params.get("spec_path"):
            from pathlib import Path

            from .parsers.parser import DocumentParser

            spec_path = Path(params["spec_path"])
            try:
                spec_parse = DocumentParser().parse(spec_path)
                if spec_parse.ir is not None:
                    spec_text = "".join(
                        item.text + "\n"
                        for item in spec_parse.ir.text_items.values()
                        if item.text
                    )
                    system_prompt += (
                        "\n\n### ASSIGNMENT SPECIFICATION"
                        " (For COPY rule comparison)\n" + spec_text
                    )
                    logger.debug(
                        "Appended spec text (%d chars) to grader prompt",
                        len(spec_text),
                    )
            except Exception as exc:
                logger.warning("Could not load spec for COPY rule comparison: %s", exc)
        logger.debug(
            f"Sending request to {self.model}. SYSTEM PROMPT:\n{system_prompt}"
        )

        try:
            response = self._client.beta.chat.completions.parse(
                model=model or self.model,
                temperature=self.temperature,
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

        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("LLM returned unparseable response.")
            return []
        logger.info(f"LLM Reasoning Chain: {parsed_response.reasoning_chain}")
        logger.info(
            f"Successfully parsed {len(parsed_response.findings)} findings from LLM."
        )
        return parsed_response.findings

    def _build_vision_grader_prompt(
        self, rules: list[LLMRule], rulebook: Rulebook
    ) -> str:
        rules_text = ""
        for r in rules:
            if "NOUML" in r.ac_codes:
                continue
            codes_str = "/".join(r.ac_codes)
            rules_text += f"- {codes_str}: {r.prompt_instruction}\n"

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
        from .schemas.llm import VisionModelResponse

        if not rules:
            logger.debug("No asset rules provided. Skipping vision LLM call.")
            return []

        user_content: list[dict] = []
        n_images = 0
        md_image_uris: list[str] = getattr(doc, "md_image_uris", []) or []
        for idx, (cref, item) in enumerate(doc.picture_items.items()):
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

            from pathlib import Path
            from urllib.parse import unquote

            from PIL import Image

            pil_img = None
            # Pdfs have pils, md not
            if item.image is not None and item.image.pil_image is not None:
                pil_img = item.image.pil_image
            else:
                img_path_str = None
                if item.image is not None and getattr(item.image, "uri", None):
                    img_path_str = str(item.image.uri)
                elif getattr(item, "uri", None):
                    img_path_str = str(item.uri)

                if not img_path_str and md_image_uris and idx < len(md_image_uris):
                    img_path_str = md_image_uris[idx]

                if img_path_str:
                    if img_path_str.startswith("file://"):
                        img_path_str = img_path_str[7:]
                    img_path_str = unquote(img_path_str)

                    source_dir = Path(doc.doc_ref.source_path).parent
                    img_path = (source_dir / img_path_str).resolve()

                    if img_path.exists() and img_path.is_file():
                        try:
                            pil_img = Image.open(img_path)
                        except Exception as e:
                            logger.warning(
                                "Failed to load local image %s: %s", img_path, e
                            )

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

        system_prompt = self._build_vision_grader_prompt(rules, rulebook)
        logger.debug(f"Sending {n_images} picture(s) to vision model.")

        messages: list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            response = self._client.beta.chat.completions.parse(
                model=model or self.model,
                temperature=self.temperature,
                max_completion_tokens=self.max_completion_tokens,
                response_format=VisionModelResponse,
                messages=messages,
            )
        except Exception as e:
            logger.error(f"Vision LLM API call failed: {e}")
            return []

        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("Vision LLM returned unparseable response.")
            return []
        logger.info(f"Vision LLM Reasoning Chain: {parsed_response.reasoning_chain}")
        logger.info(
            f"Successfully parsed {len(parsed_response.findings)} vision findings."
        )
        return parsed_response.findings

    def judge_findings(
        self,
        findings: list[Finding],
        doc: Document,
        rulebook: Rulebook,
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
                model=self.model,
                temperature=self.temperature,
                response_format=JudgeModelResponse,
                messages=messages,
            )
        except Exception:
            logger.exception("Judge model LLM call failed.")
            return None

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
            text_item = doc.text_items.get(cref)
            passage = getattr(text_item, "text", "") or "" if text_item else ""
            section_path = doc.section_paths.get(cref, "") if text_item else ""

            rule = ac_to_rule.get(f.ac_code)
            rule_def = (
                rule.prompt_instruction if rule else "(rule definition unavailable)"
            )

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

        user_content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"### FINDINGS TO EVALUATE\n{findings_text}\n\n"
                    "### ORIGINAL DOCUMENT CONTENT\n"
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

        return user_content

"""Caption Analyzer.

Validates figure and table captions and checks for cross-references in text.
Emits findings for missing captions or unreferenced assets.
"""

import re
from typing import List, Optional

from .base_detector import BaseDetector
from ..schemas.ir import Document, Figure, Table, Paragraph, Block
from ..schemas.finding import Finding, Stat

# TODO: add table checks?
REFERENCE_PATTERNS = {
    "figure": [
        "figure",
        "fig",
        "obrázek",
        "obrázok",
        "obrazek",
        "obrazok",
        "obr",
        "image",
        "img",
    ],
}

DEFAULTS = dict(
    allow_uncaptioned_if_referenced=True,
    min_caption_length=5,
)


class CaptionAnalyzer(BaseDetector):
    code = "CAPTION"
    name = "CaptionAnalyzer"
    version = "0.2"
    param_spec = {
        "allow_uncaptioned_if_referenced": "Allow assets without captions if referenced in text",
        "min_caption_length": "Minimum caption length before flagging as vague",
    }

    def __init__(self, *, run_id: Optional[str] = None, params: Optional[dict] = None):
        updated_params = DEFAULTS.copy()
        if params:
            updated_params.update(
                {key: value for key, value in params.items() if key in DEFAULTS}
            )
        super().__init__(run_id=run_id, params=updated_params)
        self.cfg = updated_params

    def detect(self, doc: Document, doc_hash: str) -> List[Finding]:
        findings: List[Finding] = []

        # Extract all figures using base detector utilities
        figures = self.get_blocks(doc, "Figure")

        # Extract all text for reference checking
        all_text = self.extract_text(doc, separator=" ")

        # Check figures
        for fig_num, figure in enumerate(figures, 1):
            findings.extend(
                self._check_figure_caption(doc, doc_hash, figure, fig_num, all_text)
            )
        return findings

    def _check_figure_caption(
        self, doc: Document, doc_hash: str, figure: Figure, fig_num: int, all_text: str
    ) -> List[Finding]:
        """Check if figure has caption and is referenced."""
        findings: List[Finding] = []

        # Check for caption
        has_caption = bool(figure.caption or figure.title or figure.alt)

        # Check for references in text using figure patterns
        is_referenced = self._is_asset_referenced(
            all_text, REFERENCE_PATTERNS["figure"], fig_num
        )

        # Missing caption
        if not has_caption:
            if self.cfg["allow_uncaptioned_if_referenced"] and is_referenced:
                # Allow it if referenced
                pass
            else:
                findings.append(
                    self.emit(
                        doc=doc,
                        doc_hash=doc_hash,
                        slug="missing_caption",
                        title="Figure without caption",
                        message=f"Figure {fig_num} (src: {figure.src}) has no caption or alt text",
                        severity_rank=2,
                        confidence=0.9,
                        anchor_block=figure,
                        tags=["caption", "figure"],
                        extra_evidence=[
                            Stat(name="figure_number", value=fig_num),
                            Stat(name="figure_src", value=figure.src),
                            Stat(name="has_caption", value=False),
                        ],
                    )
                )

        # Unreferenced figure
        if not is_referenced:
            findings.append(
                self.emit(
                    doc=doc,
                    doc_hash=doc_hash,
                    slug="unreferenced_asset",
                    title="Figure not referenced in text",
                    message=f"Figure {fig_num} (src: {figure.src}) is not referenced in the document text",
                    severity_rank=3,
                    confidence=0.75,
                    anchor_block=figure,
                    tags=["caption", "figure", "reference"],
                    extra_evidence=[
                        Stat(name="figure_number", value=fig_num),
                        Stat(name="figure_src", value=figure.src),
                        Stat(name="is_referenced", value=False),
                    ],
                )
            )

        # Vague caption
        if has_caption:
            caption_text = figure.caption or figure.title or figure.alt or ""
            if len(caption_text) < self.cfg["min_caption_length"]:
                findings.append(
                    self.emit(
                        doc=doc,
                        doc_hash=doc_hash,
                        slug="caption_vague",
                        title="Figure caption too brief",
                        message=f"Figure {fig_num} caption is very short ('{caption_text}'), may not be descriptive enough",
                        severity_rank=3,
                        confidence=0.70,
                        anchor_block=figure,
                        tags=["caption", "figure", "vague"],
                        extra_evidence=[
                            Stat(name="figure_number", value=fig_num),
                            Stat(name="caption_length", value=len(caption_text)),
                            Stat(name="caption_text", value=caption_text),
                        ],
                    )
                )

        return findings

    def _is_asset_referenced(
        self, text: str, asset_types: List[str], number: int
    ) -> bool:
        """Check if an asset is referenced in text using any of the given asset types."""
        for asset_type in asset_types:
            # Check multiple pattern variations for each asset type

            # The following patterns are generated by Copilot, model Claude Haiku 4.5
            patterns = [
                rf"\b{asset_type}\s*{number}\b",  # "figure 1", "table 2"
                rf"\b{asset_type}\s*\.?\s*{number}\b",  # "figure. 1"
                rf"\b{asset_type[0:3]}\.\s*{number}\b",  # "fig. 1", "tab. 2"
            ]

            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return True

        return False

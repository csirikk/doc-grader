"""LLM-based asset analyser. Visual quality of diagrams and figures.

Responsible for AC:
- 'BADUML': UML class diagram is syntactically incorrect, uses the wrong type,
  is auto-generated without curation, or fails to convey class interactions.
- 'OWNDIF': Diagram does not visually distinguish custom (student) classes from
  framework/library classes (e.g. ipp-core).
- 'BW': Dark-background diagram pasted into a light-background document.

todo: vision fine tune a binary image classifier for baduml?
"""

from __future__ import annotations

from typing import ClassVar

from .base_analyser import BaseLLMAnalyser


class AssetAnalyser(BaseLLMAnalyser):
    """
    Analyses visual assets (diagrams, figures) using an OpenAI vision model.
    Each PictureItem in the document is sent as an image for evaluation.
    """

    analyser_id: ClassVar[str] = "asset_analyser"
    name: ClassVar[str] = "Asset Analyser"

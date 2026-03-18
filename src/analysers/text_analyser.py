"""LLM-based text analyser. Deterministic, objective aim, proofreading.

Responsible for AC codes:
- 'CH': Spelling or grammar mistakes.
- 'ICH': First-person singular usage.
- 'TERM': Incorrect or imprecise technical terminology.
- 'LANG': Language mixing.

Future AC codes to consider:
- 'TODO': unresolved placeholders, todos lorem ipsum, etc.
- 'ACRO': unexplained acronyms or abbreviations
- 'CODE': unformatted code snippets
Grammar subtypes, instead of CH:
- 'TENSE': inconsistent or incorrect verb tense
- 'AGREE': subject-verb agreement errors
- 'PUNCT': punctuation errors
- 'SPELL': spelling mistakes

"""

from __future__ import annotations

from typing import ClassVar

from .base_analyser import BaseLLMAnalyser


class TextAnalyser(BaseLLMAnalyser):
    analyser_id: ClassVar[str] = "text_analyser"
    name: ClassVar[str] = "Text Analyser"

"""LLM-based content analyser. Technical adequacy and topical relevance of sections.
Required domain topics presence and their content.

Responsible for AC:
- 'CONTENT': Sections off-topic, such as subjective feelings or time spent.
- 'SA': Insufficient syntax analysis description.
- 'SAV': Insufficient syntax analysis of expressions description.
- 'SéA': Insufficient semantic analysis description.
- 'PSA': Insufficient precedence syntax analysis description.
- 'TS': Insufficient symbol table description.
- 'GK': Insufficient code generation description.
- 'IR': Insufficient internal representation description.
- 'JAK': Insufficient implementation description.
- 'RP': Insufficient division of work section.
- 'NVPDOC': Missing or insufficient NVP extension document.

Future AC codes to consider:
- 'NOTEST': Missing testing methodology or validation description.
- 'EDGE': Document only covers the happy path and ignores error or edge cases.
- 'MEM': Missing explanation of memory management.
- 'LIMIT': Explicitly documenting known limitations, functional bugs.
"""

from __future__ import annotations

from typing import ClassVar

from .base_analyser import BaseLLMAnalyser


class ContentAnalyser(BaseLLMAnalyser):
    """
    Analyses section-level content adequacy and topical relevance.
    Verifies if specific concepts are described accurately and efficiently.
    """

    analyser_id: ClassVar[str] = "content_analyser"
    name: ClassVar[str] = "Content Analyser"

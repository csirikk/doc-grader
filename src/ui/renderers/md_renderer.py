from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

import streamlit as st
import streamlit.components.v1 as components

if TYPE_CHECKING:
    from pathlib import Path


def _find_finding_snippets(finding: dict | None) -> list[str]:
    if not finding:
        return []

    return [
        anchor["snippet"]
        for anchor in finding.get("anchors", [])
        if anchor.get("snippet")
    ]


def _highlight_snippets(text: str, snippets: list[str], safe_id: str) -> str:
    if not snippets:
        return text

    highlighted = text
    for snippet in sorted(set(snippets), key=len, reverse=True):
        replacement = (
            f'<span data-finding-id="{safe_id}" class="finding-mark">'
            f"{html.escape(snippet)}</span>"
        )
        highlighted = highlighted.replace(snippet, replacement)

    return highlighted


def render_markdown(
    path: Path, selected_finding: dict | None, height: int = 820
) -> None:
    """Render a Markdown document with optional active-finding highlights."""
    text = path.read_text(encoding="utf-8")

    st.html(
        """
        <style>
            .finding-mark {
                background-color: rgba(255, 170, 0, 0.18);
                border-radius: 3px;
                padding: 0 0.15rem;
            }

            .finding-mark[data-active="true"] {
                background-color: rgba(255, 170, 0, 0.42);
                outline: 1px solid rgba(255, 140, 0, 0.85);
            }
            
            .markdown-surface {
                background-color: rgba(255, 255, 255, 0.02); /* Tint for dark mode */
                border-radius: 0.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 1.5rem;
            }
        </style>
        """
    )

    active_id = None
    snippets = []
    if selected_finding:
        active_id = selected_finding.get("finding_id", "").replace(":", "-")
        snippets = _find_finding_snippets(selected_finding)

    rendered_text = _highlight_snippets(text, snippets, active_id or "")

    if active_id and snippets:
        rendered_text = rendered_text.replace(
            f'data-finding-id="{active_id}"',
            f'data-finding-id="{active_id}" data-active="true"',
        )

    with st.container(height=height, border=False):
        st.markdown(
            f'<div class="markdown-surface">\n\n{rendered_text}\n\n</div>',
            unsafe_allow_html=True,
        )

    if active_id and snippets:
        components.html(
            f"""
            <script>
                const element = window.parent.document.querySelector(
                    {json.dumps(f'[data-finding-id="{active_id}"]')}
                );
                if (element) {{
                    element.scrollIntoView({{
                        behavior: 'smooth',
                        block: 'center'
                    }});
                }}
            </script>
            """,
            height=0,
        )

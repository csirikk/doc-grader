from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
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

    for snippet in sorted(set(snippets), key=len, reverse=True):
        replacement = (
            f'<span data-finding-id="{safe_id}" class="finding-mark">'
            f"{html.escape(snippet)}</span>"
        )
        text = text.replace(snippet, replacement)

    return text


def _embed_local_images(text: str, base_dir: Path) -> str:
    """Finds local markdown images and converts them to base64 data URIs using re.sub."""
    base_resolved = base_dir.resolve()

    def replace_image(match: re.Match) -> str:
        alt_text, inner = match.groups()
        inner = inner.strip()

        # Ignore web URLs
        if inner.startswith(("http://", "https://")):
            return match.group(0)

        # Clean up optional <url> syntax and trim titles
        img_ref = (
            inner[1:-1].strip()
            if inner.startswith("<") and inner.endswith(">")
            else inner.split(None, 1)[0]
        )

        try:
            img_path = (base_dir / img_ref).resolve()

            # Security check
            if not img_path.is_file() or not img_path.is_relative_to(base_resolved):
                return match.group(0)

            mime_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
            encoded = base64.b64encode(img_path.read_bytes()).decode("ascii")

            return f"![{alt_text}](data:{mime_type};base64,{encoded})"
        except Exception:
            return match.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, text)


def render_markdown(
    path: Path, selected_finding: dict | None, height: int = 820
) -> None:
    """Render a Markdown document with optional active-finding highlights."""
    text = path.read_text(encoding="utf-8")
    text = _embed_local_images(text, path.parent)

    st.html(
        """
        <style>
            finding-mark {
                background-color: rgba(255, 170, 0, 0.18);
                border-radius: 3px;
                padding: 0 0.15rem;
            }

            finding-mark[data-active="true"] {
                background-color: rgba(255, 170, 0, 0.42);
                outline: 1px solid rgba(255, 140, 0, 0.85);
            }
            
            .markdown-surface {
                background-color: rgba(255, 255, 255, 0.02);
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

    # Inject scroll logic
    if active_id and snippets:
        components.html(
            f"""
            <script>
                setTimeout(() => {{
                    const element = window.parent.document.querySelector(
                        {json.dumps(f'[data-finding-id="{active_id}"]')}
                    );
                    if (element) {{
                        element.scrollIntoView({{
                            behavior: 'smooth',
                            block: 'center'
                        }});
                    }}
                }}, 100);
            </script>
            """,
            height=0,
        )

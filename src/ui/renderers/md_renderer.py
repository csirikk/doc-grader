from __future__ import annotations

import base64
import mimetypes
import re
from typing import TYPE_CHECKING
from urllib.parse import unquote

import marko
import streamlit as st
import streamlit.components.v1 as components

if TYPE_CHECKING:
    from pathlib import Path


def _embed_html_images(html_body: str, base_dir: Path) -> str:
    """Find local images in rendered HTML and convert them to base64 data URIs."""
    base_resolved = base_dir.resolve()

    def replace_img_src(match: re.Match) -> str:
        full_tag = match.group(0)
        src_uri = match.group(1)

        # Ignore web URLs and data URIs
        if src_uri.startswith(("http://", "https://", "data:")):
            return full_tag

        try:
            clean_src = unquote(src_uri)
            img_path = (base_dir / clean_src).resolve()

            if not img_path.is_file() or not img_path.is_relative_to(base_resolved):
                return full_tag

            mime_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
            encoded = base64.b64encode(img_path.read_bytes()).decode("ascii")

            new_src = f"data:{mime_type};base64,{encoded}"
            return full_tag.replace(f'src="{src_uri}"', f'src="{new_src}"')
        except Exception:
            return full_tag

    # Matches Marko img tags <img src="something" ...>
    return re.sub(r'<img\s+[^>]*src="([^"]+)"', replace_img_src, html_body)


def _inject_html_highlights(
    html_body: str, ranges: list[dict], active_id: str | None
) -> str:
    """Inject highlight spans into rendered HTML."""
    search_cursor = 0

    for r in ranges:
        snippet = r.get("snippet")
        if not snippet:
            continue

        # Strip links and formatting
        snippet = re.sub(r"!\[.*?\]\(.*?\)", "", snippet)
        snippet = snippet.strip("*_`# \n")
        words = snippet.split()
        if not words:
            continue

        # Match words, ignore HTML tags and spaces
        pattern = r"(?:<[^>]+>|\s)*".join(re.escape(w) for w in words)

        try:
            match = re.search(pattern, html_body[search_cursor:])
            if match:
                start_idx = search_cursor + match.start()
                end_idx = search_cursor + match.end()
            else:
                match = re.search(pattern, html_body)
                if not match:
                    continue
                start_idx = match.start()
                end_idx = match.end()
                if start_idx < search_cursor:
                    continue

            if active_id:
                span_open = f'<span data-finding-id="{active_id}" data-active="true" class="finding-mark">'
            else:
                span_open = '<span class="finding-mark">'
            span_close = "</span>"

            html_body = (
                html_body[:start_idx]
                + span_open
                + html_body[start_idx:end_idx]
                + span_close
                + html_body[end_idx:]
            )
            search_cursor = (
                start_idx + len(span_open) + (end_idx - start_idx) + len(span_close)
            )
        except Exception:
            pass

    return html_body


def render_markdown(path: Path, selected_finding: dict | None) -> None:
    """Render a Markdown document with optional highlights."""
    text = path.read_text(encoding="utf-8")

    # highlight data
    active_id = None
    ranges: list[dict] = []
    if selected_finding:
        active_id = selected_finding.get("finding_id", "").replace(":", "-")
        for anchor in selected_finding.get("anchors", []):
            snippet = anchor.get("snippet")
            if snippet:
                ranges.append({"snippet": snippet})

    html_body = marko.Markdown().convert(text)

    if ranges:
        html_body = _inject_html_highlights(html_body, ranges, active_id)
    html_body = _embed_html_images(html_body, path.parent)

    st.markdown(
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
            .markdown-surface { background-color: rgba(255, 255, 255, 0.02);
                border-radius: 0.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 1.5rem;
            }
            .markdown-surface img { 
                max-width: 100%;
                border-radius: 4px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=False):
        st.markdown(
            f'<div class="markdown-surface">\n\n{html_body}\n\n</div>',
            unsafe_allow_html=True,
        )

    # Inject scroll logic
    if active_id and ranges:
        components.html(
            f"""
            <script>
                setTimeout(() => {{
                    try {{
                        const selector = '[data-finding-id="{active_id}"]';
                        const el = window.parent.document.querySelector(selector);
                        if (el) {{
                            el.scrollIntoView({{ 
                                behavior: 'smooth',
                                block: 'center'
                            }});
                        }}
                    }} catch (e) {{ console.error(e); }}
                }}, 100);
            </script>
            """,
        )

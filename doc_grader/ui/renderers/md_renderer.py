"""Markdown renderer for the Streamlit UI.

Author: Matúš Csirik
"""

import base64
import html
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
        full_tag, src_uri = match.group(0), match.group(1)
        if src_uri.startswith(("http://", "https://", "data:")):
            return full_tag

        try:
            img_path = (base_resolved / unquote(src_uri)).resolve()
            if not img_path.is_relative_to(base_resolved) or not img_path.is_file():
                return full_tag

            mime_type = mimetypes.guess_type(img_path)[0] or "image/png"
            encoded = base64.b64encode(img_path.read_bytes()).decode("ascii")
            return full_tag.replace(
                f'src="{src_uri}"', f'src="data:{mime_type};base64,{encoded}"'
            )
        except OSError:
            return full_tag

    # Matches Marko img tags <img src="something" ...>
    return re.sub(r'<img\s+[^>]*src="([^"]+)"', replace_img_src, html_body)


def _inject_html_highlights(
    html_body: str, ranges: list[dict], active_id: str | None
) -> str:
    """Inject highlight spans into rendered HTML using reverse-order splicing."""
    modifications = []
    search_cursor = 0

    for r in ranges:
        target_ref = r.get("target", {}).get("$ref", "")
        pic_match = re.search(r"/pictures/(\d+)$", target_ref)

        if pic_match:
            idx = int(pic_match.group(1))
            matches = list(re.finditer(r"<img\b[^>]*>", html_body))
            if idx < len(matches):
                modifications.append((matches[idx].start(), matches[idx].end()))
        elif snippet := r.get("snippet"):
            snippet = re.sub(r"!\[.*?\]\(.*?\)", "", snippet).strip("*_`# \n")
            words = snippet.split()
            if not words:
                continue

            # Match words, ignore HTML tags and spaces
            pattern = r"(?:<[^>]+>|\s)*".join(re.escape(w) for w in words)
            match = re.search(pattern, html_body[search_cursor:])
            if match:
                start = search_cursor + match.start()
                end = search_cursor + match.end()
                modifications.append((start, end))
                search_cursor = end

    # Apply modifications in reverse to maintain index order
    span_attr = (
        f' data-finding-id="{active_id}" data-active="true"' if active_id else ""
    )
    for start, end in sorted(modifications, key=lambda x: x[0], reverse=True):
        html_body = (
            f'{html_body[:start]}<span class="finding-mark"{span_attr}>'
            f"{html_body[start:end]}</span>{html_body[end:]}"
        )
    return html_body


def render_markdown(path: Path, selected_finding: dict | None) -> None:
    """Render Markdown content with highlights and embedded local images.

    Args:
        path: Path to the Markdown file to render.
        selected_finding: Optional finding dictionary whose anchors will be
            highlighted in the rendered output.

    Returns:
        None
    """
    md_content = html.escape(path.read_text(encoding="utf-8"), quote=False)
    html_body = marko.Markdown().convert(md_content)

    active_id = (selected_finding or {}).get("finding_id", "").replace(":", "-")
    ranges = [
        {"snippet": a.get("snippet"), "target": a.get("target")}
        for a in (selected_finding or {}).get("anchors", [])
    ]

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
            .finding-mark img {
                outline: 3px solid rgba(255, 140, 0, 0.85);
                border-radius: 4px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="markdown-surface">{html_body}</div>', unsafe_allow_html=True
    )

    if active_id and ranges:
        components.html(
            f"""
            <script>
                setTimeout(() => {{
                    const el = window.parent.document.querySelector('[data-finding-id="{active_id}"]');
                    if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}, 150);
            </script>
        """,
            height=0,
        )

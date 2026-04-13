"""Left-column document viewer panel."""

from pathlib import Path

import streamlit as st
from renderers.md_renderer import render_markdown
from renderers.pdf_renderer import render_pdf


def render_document(
    source_path: str | None,
    selected_finding: dict | None,
    height: int = 820,
) -> None:
    """Render the student document in the left column."""
    if not source_path:
        st.info("No document loaded.")
        return

    path = Path(source_path)
    if not path.exists():
        st.warning(f"Source file not found: `{source_path}`")
        return

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        render_pdf(path, selected_finding)

    elif suffix == ".md":
        render_markdown(path, selected_finding)

    else:
        st.warning(
            f"Unsupported file type: `{suffix}`. Only PDF and Markdown are supported."
        )

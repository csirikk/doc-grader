"""Left-column document viewer panel."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer


def _page_from_finding(finding: dict | None) -> int | None:
    """Return the 1-based page number from the first anchor's provenance, or None.
    TODO: add support for MD showing
    TODO: make this be able to showcase any anchor
    """
    if finding is None:
        return None
    anchors = finding.get("anchors") or []
    if not anchors:
        return None
    prov = anchors[0].get("prov") or []
    if not prov:
        return None
    page_no = prov[0].get("page_no")
    return int(page_no) if page_no is not None else None


def render_document(source_path: str | None, selected_finding: dict | None) -> None:
    """Render the student document in the left column.

    For PDF files uses streamlit-pdf-viewer.
    For Markdown files renders the raw source with st.markdown.
    """
    if not source_path:
        return

    path = Path(source_path)
    if not path.exists():
        st.warning(f"Source file not found: `{source_path}`")
        return

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        if pdf_viewer is None:
            st.error("streamlit-pdf-viewer is not installed.")
            return

        page = _page_from_finding(selected_finding)

        scroll_trigger = st.session_state.get("scroll_trigger", 0)
        pdf_viewer(
            input=str(path),
            width="100%",
            height=800,
            scroll_to_page=page,
            render_text=True,
            key=f"pdf_{path.stem}_{scroll_trigger}",
        )

    elif suffix == ".md":
        text = path.read_text(encoding="utf-8")
        st.markdown(text)

    else:
        st.warning(
            f"Unsupported file type: `{suffix}`. Only PDF and Markdown are supported."
        )

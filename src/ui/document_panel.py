"""Left-column document viewer panel."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from src.ui.utils import STATUS_COLOURS


def _handle_annotation_click(clicked_annotation: dict):
    """Callback fired when a user clicks a bounding box in the PDF."""
    if not clicked_annotation or "id" not in clicked_annotation:
        return

    new_id = clicked_annotation["id"]
    old_id = st.session_state.get("active_finding_id")

    # Only increment the scroll trigger if switching to a different finding
    if new_id != old_id:
        st.session_state["active_finding_id"] = new_id
        st.session_state["scroll_trigger"] = (
            st.session_state.get("scroll_trigger", 0) + 1
        )
    else:
        st.session_state["active_finding_id"] = new_id


def _get_annotations(
    findings: list[dict], active_id: str | None, show_all: bool
) -> list[dict]:
    expanded_fids = set(st.session_state.get("expanded_fids", []))
    annotations = []

    for finding in findings:
        safe_id = finding.get("finding_id", "").replace(":", "-")
        is_active = safe_id == active_id
        is_expanded = safe_id in expanded_fids
        status_color = STATUS_COLOURS.get(finding.get("status", "proposed"), "blue")

        if show_all:
            color = status_color if (is_active or is_expanded) else "lightgray"
        else:
            color = status_color if (is_active or is_expanded) else "rgba(0,0,0,0)"

        for anchor in finding.get("anchors", []):
            for prov in anchor.get("prov", []):
                if bbox := prov.get("bbox"):
                    annotations.append(
                        {
                            "page": prov["page_no"],
                            "x": bbox["l"],
                            "y": bbox["t"],
                            "width": bbox["r"] - bbox["l"],
                            "height": bbox["b"] - bbox["t"],
                            "color": color,
                            "id": safe_id,
                        }
                    )
    return annotations


def render_document(source_path: str | None, selected_finding: dict | None) -> None:
    """Render the student document in the left column."""
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

        show_all = st.toggle("Show all findings on document", value=False)
        findings = st.session_state.get("findings", [])
        active_id = st.session_state.get("active_finding_id")
        target_annotations = _get_annotations(findings, active_id, show_all)

        target_page = None
        if selected_finding:
            anchors = selected_finding.get("anchors") or []
            if anchors and anchors[0].get("prov"):
                target_page = anchors[0]["prov"][0].get("page_no")

        scroll_trigger = st.session_state.get("scroll_trigger", 0)
        pdf_viewer(
            input=str(path),
            width="100%",
            height=800,
            render_text=False,
            annotations=target_annotations,
            scroll_to_page=target_page,
            scroll_behavior="instant",
            on_annotation_click=_handle_annotation_click,
            key=f"pdf_{path.stem}_{scroll_trigger}_{show_all}",
        )

    elif suffix == ".md":
        text = path.read_text(encoding="utf-8")
        st.markdown(text)

    else:
        st.warning(
            f"Unsupported file type: `{suffix}`. Only PDF and Markdown are supported."
        )

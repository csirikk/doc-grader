from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from src.ui.utils import STATUS_COLOURS

if TYPE_CHECKING:
    from pathlib import Path


def _handle_annotation_click(clicked_annotation: dict) -> None:
    """Callback fired when a user clicks a bounding box in the PDF."""
    if not clicked_annotation or "id" not in clicked_annotation:
        return

    new_id = clicked_annotation["id"]
    old_id = st.session_state.get("active_finding_id")

    if new_id != old_id:
        st.session_state["active_finding_id"] = new_id
        st.session_state["scroll_trigger"] = (
            st.session_state.get("scroll_trigger", 0) + 1
        )
    else:
        st.session_state["active_finding_id"] = new_id


def _get_annotations(finding: dict | None) -> list[dict]:
    if not finding:
        return []

    safe_id = finding.get("finding_id", "").replace(":", "-")
    status_color = STATUS_COLOURS.get(finding.get("status", "proposed"), "blue")

    annotations = []
    for anchor in finding.get("anchors", []):
        for prov in anchor.get("prov", []):
            bbox = prov.get("bbox")
            if not bbox:
                continue

            annotations.append(
                {
                    "page": prov["page_no"],
                    "x": bbox["l"],
                    "y": bbox["t"],
                    "width": bbox["r"] - bbox["l"],
                    "height": bbox["b"] - bbox["t"],
                    "color": status_color,
                    "id": safe_id,
                }
            )

    return annotations


def render_pdf(
    path: Path,
    selected_finding: dict | None,
    viewer_height: int,
) -> None:
    """Render a PDF document with clickable findings annotations."""
    if pdf_viewer is None:
        st.error("streamlit-pdf-viewer is not installed.")
        return

    target_annotations = _get_annotations(selected_finding)

    target_page = None
    if selected_finding:
        anchors = selected_finding.get("anchors") or []
        if anchors and anchors[0].get("prov"):
            target_page = anchors[0]["prov"][0].get("page_no")

    scroll_trigger = st.session_state.get("scroll_trigger", 0)
    selected_id = (selected_finding or {}).get("finding_id", "").replace(":", "-")
    pdf_viewer(
        input=str(path),
        width="100%",
        height=viewer_height,
        render_text=False,
        annotations=target_annotations,
        scroll_to_page=target_page,
        scroll_behavior="instant",
        on_annotation_click=_handle_annotation_click,
        key=f"pdf_{path.stem}_{scroll_trigger}_{selected_id}",
    )

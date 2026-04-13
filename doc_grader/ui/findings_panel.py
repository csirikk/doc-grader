"""Right-column findings panel: list and review findings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st
from utils import (
    FILTER_OPTIONS,
    STATUS_COLOURS,
)

if TYPE_CHECKING:
    from pathlib import Path

# CSS for tinting expander headers based on the hidden judge-status marker
_STATUS_TINT_CSS = """
<style>
details:has([data-status-marker="judged_approved"]) > summary {
    background-color: rgba(33, 195, 84, 0.1);
}
details:has([data-status-marker="judged_adjusted"]) > summary {
    background-color: rgba(255, 211, 74, 0.12);
}
details:has([data-status-marker="judged_dismissed"]) > summary {
    background-color: rgba(255, 75, 75, 0.1);
}
details:has([data-status-marker="to_be_judged"]) > summary {
    background-color: rgba(255, 170, 0, 0.1);
}
</style>
"""


def _severity_label(severity: float | None) -> str:
    if severity is None:
        return "n/a"
    return f"{severity:.2f}"


def _render_judge(finding: dict) -> None:
    """Render judge decision, rationale and field-level changes in the main body."""
    meta: dict | None = finding.get("meta")
    if not meta:
        return
    judge: dict | None = meta.get("judge")
    if not judge:
        return

    with st.expander("Judge", expanded=False):
        st.markdown(judge.get("rationale", ""))

        if reasoning := judge.get("reasoning_chain"):
            st.markdown(reasoning)

        change: dict | None = judge.get("change")
        if not change:
            return

        fields: list[str] = change.get("fields") or []
        before: dict = change.get("before") or {}
        after: dict = change.get("after") or {}
        if not fields:
            return

        st.markdown("### Adjustments")
        for field in fields:
            b = before.get(field)
            a = after.get(field)
            st.markdown(f"#### {field}")
            col_b, col_a = st.columns(2)
            col_b.caption("Before")
            col_b.markdown(str(b) if b is not None else "_n/a_")
            col_a.caption("After")
            col_a.markdown(str(a) if a is not None else "_n/a_")


def _render_evidence(finding: dict) -> None:
    """Render anchors, stats, model evals and miscellaneous meta."""
    anchors: list[dict] = finding.get("anchors") or []
    stats: list[dict] = finding.get("stats") or []
    model_evals: list[dict] = finding.get("model_evals") or []
    meta: dict | None = finding.get("meta")
    other_meta = {k: v for k, v in meta.items() if k != "judge"} if meta else {}

    has_evidence = anchors or stats or model_evals or other_meta
    if not has_evidence:
        return

    with st.expander("Evidence", expanded=False):
        if anchors:
            for i, anchor in enumerate(anchors, 1):
                ref = (anchor.get("target") or {}).get("$ref", "")
                snippet = anchor.get("snippet")
                prov_list: list[dict] = anchor.get("prov") or []

                valid_pages = (
                    int(p["page_no"])
                    for p in prov_list
                    if p.get("page_no") is not None and str(p["page_no"]).isdigit()
                )

                prov_parts = [f"p.{pn}" for pn in sorted(set(valid_pages))]

                loc = ", ".join(prov_parts) if prov_parts else "no provenance"
                label = anchor.get("section_path") or ref

                st.text(f"[{i}] {label} ({loc})")
                if snippet:
                    st.caption(snippet)

        if stats:
            st.caption("Stats")
            rows = [
                {
                    "Name": s.get("name", ""),
                    "Value": f"{s.get('value')} {s.get('unit', '')}".strip()
                    if s.get("value") is not None
                    else "n/a",
                    "Notes": s.get("notes") or "",
                }
                for s in stats
            ]
            st.dataframe(rows, width="stretch", hide_index=True)

        if model_evals:
            st.caption("Model Evals")
            for ev in model_evals:
                model, label, score = (
                    ev.get("model_name", "model"),
                    ev.get("label", "n/a"),
                    ev.get("score"),
                )
                score_str = f"{score:.3f}" if score is not None else "n/a"
                st.text(f"{model}: {label} (score {score_str})")

        if other_meta:
            st.caption("Meta")
            st.json(other_meta, expanded=False)


def _on_view_anchor(safe_fid: str):
    """Explicit button click to focus a finding."""
    st.session_state["active_finding_id"] = safe_fid


def render_findings(findings: list[dict], out_dir: Path) -> None:
    """Render the full findings panel in the right column."""

    filter_col, sort_col = st.columns([1, 1], vertical_alignment="bottom")
    status_filter = filter_col.selectbox(
        "Filter by judge status", FILTER_OPTIONS, key="findings_filter"
    )
    sort_by = sort_col.radio(
        "Sort by descending",
        ["Severity", "Confidence"],
        horizontal=True,
        key="findings_sort",
    )

    visible = [f for f in findings if status_filter in ("All", f["judge_status"])]
    sort_key = sort_by.lower()
    visible = sorted(visible, key=lambda x: x.get(sort_key) or 0.0, reverse=True)

    if not visible:
        st.info("No findings match the current filter.")
        return

    st.html(_STATUS_TINT_CSS)

    for finding in visible:
        fid = finding.get("finding_id", "?")
        safe_fid = fid.replace(":", "-")
        judge_status = finding["judge_status"]
        human_status = finding["human_status"]
        severity = finding.get("severity")
        confidence = finding.get("confidence")
        colour = STATUS_COLOURS.get(judge_status, "grey")

        is_active = safe_fid == st.session_state.get("active_finding_id")
        anchors: list[dict] = finding.get("anchors") or []
        has_anchors = bool(anchors)

        with st.expander(
            f"[{fid}] {finding.get('title', '(untitled)')}",
            expanded=is_active,
        ):
            # colour the expander
            st.html(
                f'<span data-status-marker="{judge_status}" style="display:none"></span>'
            )

            header_l, header_r = st.columns([3, 1], vertical_alignment="center")

            with header_l:
                analyser = (finding.get("analyser") or {}).get(
                    "name", "Unknown Analyser"
                )
                st.markdown(f"### {analyser}")
                st.markdown(
                    f":{colour}[{judge_status}], "
                    f"human `{human_status}`, "
                    f"sev `{_severity_label(severity)}`, "
                    f"conf `{_severity_label(confidence)}`"
                )

            with header_r:
                st.button(
                    "View anchor",
                    key=f"btn_{safe_fid}",
                    width="stretch",
                    on_click=_on_view_anchor,
                    args=(safe_fid,),
                    disabled=not has_anchors,
                )

            st.markdown(finding.get("summary", ""))

            if notes := finding.get("notes"):
                st.caption(", ".join(notes))

            _render_judge(finding)
            _render_evidence(finding)

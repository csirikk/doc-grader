"""Right-column findings panel: list and review findings."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import streamlit as st

_STATUS_COLOURS: dict[str, str] = {
    "approved": "green",
    "dismissed": "red",
    "proposed": "orange",
}
_ALL_STATUSES: list[str] = ["proposed", "approved", "dismissed"]
_FILTER_OPTIONS: list[str] = ["All", *_ALL_STATUSES]

# AI generated css:
_STATUS_TINT_CSS = """
<style>
details:has([data-status-marker="approved"]) > summary {
    background-color: rgba(33, 195, 84, 0.1);
}
details:has([data-status-marker="dismissed"]) > summary {
    background-color: rgba(255, 75, 75, 0.1);
}
details:has([data-status-marker="proposed"]) > summary {
    background-color: rgba(255, 170, 0, 0.1);
}
</style>
"""


def _severity_label(severity: float | None) -> str:
    if severity is None:
        return "n/a"
    return f"{severity:.2f}"


def _render_evidence(finding: dict) -> None:
    """Render anchors, stats and model evals as structured evidence."""
    anchors: list[dict] = finding.get("anchors") or []
    stats: list[dict] = finding.get("stats") or []
    model_evals: list[dict] = finding.get("model_evals") or []
    meta: dict | None = finding.get("meta")

    has_evidence = anchors or stats or model_evals or meta
    if not has_evidence:
        return

    with st.expander("Evidence", expanded=False):
        if anchors:
            for i, anchor in enumerate(anchors, 1):
                ref = (anchor.get("target") or {}).get("$ref", "")
                snippet = anchor.get("snippet")
                prov_list: list[dict] = anchor.get("prov") or []

                prov_parts: list[str] = []
                for prov in prov_list:
                    page = prov.get("page_no")
                    if page is not None:
                        prov_parts.append(f"p.{page}")

                loc = ", ".join(prov_parts) if prov_parts else "no provenance"
                label = anchor.get("section_path") or ref
                st.text(f"[{i}] {label} ({loc})")
                if snippet:
                    st.caption(snippet)

        if stats:
            st.caption("Stats")
            rows = []
            for s in stats:
                val = s.get("value")
                unit = s.get("unit") or ""
                notes = s.get("notes") or ""
                rows.append(
                    {
                        "Name": s.get("name", ""),
                        "Value": f"{val} {unit}".strip() if val is not None else "n/a",
                        "Notes": notes,
                    }
                )
            st.dataframe(rows, width="stretch", hide_index=True)

        if model_evals:
            st.caption("Model Evals")
            for ev in model_evals:
                model = ev.get("model_name") or "model"
                label = ev.get("label") or "n/a"
                score = ev.get("score")
                score_str = f"{score:.3f}" if score is not None else "n/a"
                st.text(f"{model}: {label} (score {score_str})")

        if meta:
            judge = meta.get("judge")
            rest = {k: v for k, v in meta.items() if k != "judge"}

            if judge:
                st.markdown("#### Judge")
                decision = judge.get("decision", "")
                colour = _STATUS_COLOURS.get(
                    "approved" if decision in ("approved", "adjusted") else decision,
                    "grey",
                )
                rationale = judge.get("rationale", "")
                st.markdown(f":{colour}[{decision}]: {rationale}")
                reasoning = judge.get("reasoning_chain", "")
                if reasoning:
                    st.caption(reasoning)

            if rest:
                st.caption("Meta")
                st.json(rest, expanded=False)


def render_findings(findings: list[dict], out_dir: Path) -> None:
    """Render the full findings panel in the right column."""

    # Filter controls
    filter_col, sort_col = st.columns([1, 1], vertical_alignment="bottom")
    status_filter = filter_col.selectbox(
        "Filter by status", _FILTER_OPTIONS, key="findings_filter"
    )
    sort_by = sort_col.radio(
        "Sort by descending",
        ["Severity", "Confidence"],
        horizontal=True,
        key="findings_sort",
    )

    # Apply filter and sort
    visible = [
        (i, f)
        for i, f in enumerate(findings)
        if status_filter == "All" or f.get("status") == status_filter
    ]
    sort_key = "severity" if sort_by == "Severity" else "confidence"
    visible.sort(key=lambda x: x[1].get(sort_key) or 0.0, reverse=True)

    if not visible:
        st.info("No findings match the current filter.")
        return

    st.markdown(_STATUS_TINT_CSS, unsafe_allow_html=True)

    # Per-finding expanders
    for original_idx, finding in visible:
        fid = finding.get("finding_id", "?")
        ftitle = finding.get("title", "(untitled)")
        status = finding.get("status", "proposed")
        severity = finding.get("severity")
        colour = _STATUS_COLOURS.get(status, "grey")

        label = f"[{fid}] {ftitle}"

        with st.expander(label):
            st.markdown(
                f'<span data-status-marker="{status}" style="display:none"></span>',
                unsafe_allow_html=True,
            )
            left_col, right_col = st.columns([3, 1], vertical_alignment="center")

            with left_col:
                analyser_name = (finding.get("analyser") or {}).get("name", "")
                st.markdown("### " + analyser_name)
                meta_parts = [
                    f":{colour}[{status}], ",
                    f"sev `{_severity_label(severity)}`, ",
                    f"conf `{_severity_label(finding.get('confidence'))}`",
                ]
                st.markdown("".join(meta_parts))

            with right_col:
                if st.button(
                    "View anchor",
                    key=f"sel_{fid}",
                    width="stretch",
                ):
                    st.session_state["selected_idx"] = original_idx
                    st.session_state["scroll_trigger"] = (
                        st.session_state.get("scroll_trigger", 0) + 1
                    )
                    st.rerun()

            st.markdown(finding.get("summary", ""))

            notes_list: list[str] = finding.get("notes") or []
            if notes_list:
                st.caption(", ".join(notes_list))

            _render_evidence(finding)

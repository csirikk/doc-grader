"""Right-column findings panel, listing findings for review.

Author: Matúš Csirik
"""

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from pathlib import Path

# CSS for tinting expander headers based on confidence: lower confidence gets
# stronger red tint to draw reviewer attention.
_STATUS_TINT_CSS = """
<style>
details:has([data-confidence-band="very_high"]) > summary {
    background-color: rgba(255, 0, 0, 0.03);
}
details:has([data-confidence-band="high"]) > summary {
    background-color: rgba(255, 0, 0, 0.07);
}
details:has([data-confidence-band="medium"]) > summary {
    background-color: rgba(255, 0, 0, 0.12);
}
details:has([data-confidence-band="low"]) > summary {
    background-color: rgba(255, 0, 0, 0.18);
}
details:has([data-confidence-band="very_low"]) > summary {
    background-color: rgba(255, 0, 0, 0.25);
}
details:has([data-confidence-band="unknown"]) > summary {
    background-color: rgba(255, 0, 0, 0.14);
}
details:has([data-dismissed-candidate="true"]) > summary {
    opacity: 0.7;
    filter: grayscale(0.5);
}
</style>
"""

STATUS_LABELS: dict[str, str] = {
    "not_to_be_judged": "Automatic judge not run",
    "to_be_judged": "Pending automatic judge review",
    "judged_approved": "Automatically confirmed",
    "judged_adjusted": "Automatically confirmed with changes",
    "judged_dismissed": "Automatically dismissed",
}


def _code_filter_options(findings: list[dict]) -> list[str]:
    """Return code filter options as [All, ...sorted unique codes]."""
    codes = sorted({str(f.get("ac_code") or "-") for f in findings})
    return ["All", *codes]


def _severity_label(severity: float | None) -> str:
    if severity is None:
        return "n/a"
    return f"{severity:.2f}"


def _impact_label(impact: float | None) -> str:
    if impact is None:
        return "n/a"
    try:
        formatted = f"{float(impact):+.2f}"
    except TypeError, ValueError:
        return "n/a"
    return "-0.00" if formatted == "+0.00" else formatted


def _impact_title(impact: float | None) -> str:
    """Compact impact string for use in the expander title."""
    if impact is None:
        return ""
    label = _impact_label(impact)
    return f"  ({label} minipoints)" if label != "n/a" else ""


def _confidence_tint_band(value: float | None) -> str:
    """Return confidence band used for expander background tinting."""
    if value is None:
        return "unknown"
    if value >= 0.85:
        return "very_high"
    if value >= 0.70:
        return "high"
    if value >= 0.50:
        return "medium"
    if value >= 0.30:
        return "low"
    return "very_low"


def _criterion_title(finding: dict, rubric_by_code: dict[str, dict[str, str]]) -> str:
    ac_code = finding.get("ac_code", "")
    if not ac_code:
        return finding.get("title", "Untitled finding")

    rubric = rubric_by_code.get(ac_code, {})
    return rubric.get("title") or finding.get("title") or ac_code


def _criterion_text(
    finding: dict, rubric_by_code: dict[str, dict[str, str]]
) -> str | None:
    ac_code = finding.get("ac_code", "")
    if not ac_code:
        return None
    rubric = rubric_by_code.get(ac_code, {})
    criterion_text = rubric.get("criterion_text")
    return criterion_text or None


def _impact_explanation(finding: dict) -> str:
    impact = finding.get("impact")
    severity = finding.get("severity")
    confidence = finding.get("confidence")
    confidence_text = (
        f"{float(confidence):.2f}" if confidence is not None else "unavailable"
    )

    if impact is None:
        return (
            "This finding may affect minipoints under the matched criterion. "
            f"Evidence confidence is {confidence_text}."
        )

    if impact < 0:
        return (
            f"Estimated deduction: {abs(float(impact)):.2f} minipoints. "
            f"The deduction size reflects issue severity ({_severity_label(severity)}) "
            f"and evidence confidence ({confidence_text})."
        )

    if impact > 0:
        return (
            f"Estimated positive adjustment: {float(impact):.2f} minipoints. "
            f"Evidence confidence is {confidence_text}."
        )

    return (
        "No point change estimated for this item. "
        f"Evidence confidence is {confidence_text}."
    )


def _render_judge(finding: dict, show_technical_details: bool) -> None:
    """Render automated judge notes in teacher-friendly wording."""
    meta: dict | None = finding.get("meta")
    if not meta:
        return
    judge: dict | None = meta.get("judge")
    if not judge:
        return

    with st.expander("Automatic review note", expanded=False):
        rationale = judge.get("rationale")
        if rationale:
            st.markdown(rationale)

        if show_technical_details and (reasoning := judge.get("reasoning_chain")):
            st.caption("Technical reasoning trace")
            st.markdown(reasoning)

        _ = show_technical_details


def _render_evidence(finding: dict, show_technical_details: bool) -> None:
    """Render evidence for the finding and optional technical metadata."""
    anchors: list[dict] = finding.get("anchors") or []
    stats: list[dict] = finding.get("stats") or []
    model_evals: list[dict] = finding.get("model_evals") or []
    meta: dict | None = finding.get("meta")
    other_meta = {k: v for k, v in meta.items() if k != "judge"} if meta else {}

    has_evidence = (
        anchors or stats or (show_technical_details and (model_evals or other_meta))
    )
    if not has_evidence:
        return

    with st.expander("Evidence from the document", expanded=False):
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

                loc = ", ".join(prov_parts) if prov_parts else "location unavailable"
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

        if show_technical_details and model_evals:
            st.caption("Model evaluations")
            for ev in model_evals:
                model, label, score = (
                    ev.get("model_name", "model"),
                    ev.get("label", "n/a"),
                    ev.get("score"),
                )
                if score is None:
                    st.text(f"{model}: {label}")
                else:
                    st.text(f"{model}: {label} (score {score:.3f})")
                if raw := ev.get("raw"):
                    st.json(raw, expanded=False)

        if show_technical_details and other_meta:
            st.caption("Technical metadata")
            st.json(other_meta, expanded=False)


def _on_view_anchor(safe_fid: str):
    """Explicit button click to focus a finding."""
    st.session_state["active_finding_id"] = safe_fid


def render_findings(
    findings: list[dict],
    dismissed_candidates: list[dict],
    out_dir: Path,
    rubric_by_code: dict[str, dict[str, str]],
    student_id: str | None,
    points_over_max: str,
    total_findings: int,
) -> None:
    """Render the full findings panel in the right column.

    Args:
        findings: List of finding dictionaries as produced by the grader.
        out_dir: Path to the run output directory (used for context if needed).

    Returns:
        None
    """

    _ = out_dir

    summary_student = student_id or "n/a"
    with st.container(border=True):
        summary_col_l, summary_col_m, summary_col_r = st.columns([1.0, 1.0, 1.0])
        summary_col_l.markdown(f"Student ID: **{summary_student}**")
        summary_col_m.markdown(f"Points: **{points_over_max}**")
        summary_col_r.markdown(f"Total findings: **{total_findings}**")

    toggle_col_l, toggle_col_m = st.columns([1.0, 1.0], vertical_alignment="bottom")
    toggle_col_l.checkbox(
        "Show dismissed candidates",
        key="show_dismissed_candidates",
        help=(
            "When enabled, the list includes unscored finding candidates "
            "dismissed by the a judge model during the pipeline, enabling this "
            "allows viewing these exclusioons can serve as supplementary information "
            "for other possible uncaught findings."
        ),
    )
    toggle_col_m.checkbox(
        "Show technical details",
        key="show_technical_details",
        help=(
            "Shows extra diagnostic content inside each finding, including "
            "model evaluations and raw outputs in Evidence from the "
            "document, plus technical metadata and judge before/after "
            "field changes in Technical details."
        ),
    )

    merged_findings = list(findings)
    if st.session_state.get("show_dismissed_candidates"):
        merged_findings.extend(dismissed_candidates)

    code_options = _code_filter_options(merged_findings)
    if st.session_state.get("findings_code_filter") not in code_options:
        st.session_state["findings_code_filter"] = "All"

    filter_col, sort_col = st.columns([1.0, 1.0], vertical_alignment="bottom")

    code_filter = filter_col.selectbox(
        "Filter by code",
        code_options,
        key="findings_code_filter",
    )
    sort_by = sort_col.radio(
        "Sort findings by (Descending)",
        ["Deduction", "Confidence"],
        horizontal=True,
        key="findings_sort",
    )

    show_technical_details = bool(st.session_state.get("show_technical_details"))

    visible = [
        f
        for f in merged_findings
        if code_filter in ("All", str(f.get("ac_code") or "-"))
    ]
    if sort_by == "Deduction":
        visible = sorted(
            visible,
            key=lambda x: (
                abs(float(x["impact"])) if x.get("impact") is not None else 0.0
            ),
            reverse=True,
        )
    else:
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
        severity = finding.get("severity")
        confidence = finding.get("confidence")
        ac_code = finding.get("ac_code", "-")
        criterion_title = _criterion_title(finding, rubric_by_code)
        confidence_tint_band = _confidence_tint_band(confidence)
        is_dismissed_candidate = bool(finding.get("is_dismissed_candidate"))

        is_active = safe_fid == st.session_state.get("active_finding_id")
        anchors: list[dict] = finding.get("anchors") or []
        has_anchors = bool(anchors)

        impact = finding.get("impact")
        with st.expander(
            f"[{ac_code}] {criterion_title}{_impact_title(impact)}",
            expanded=is_active,
        ):
            # colour the expander
            marker_html = (
                f'<span data-confidence-band="{confidence_tint_band}" '
                "data-dismissed-candidate="
                f'"{"true" if is_dismissed_candidate else "false"}" '
                'style="display:none"></span>'
            )
            st.html(marker_html)

            header_l, header_r = st.columns([3, 1], vertical_alignment="center")

            with header_l:
                st.markdown(f"### Criterion {ac_code}")
                st.markdown(criterion_title)

                criterion_text = _criterion_text(finding, rubric_by_code)
                if criterion_text:
                    st.caption(f"Criterion definition:\n {criterion_text}")

                severity_help = (
                    "Severity scale for this criterion: 1.00 means the worst error "
                    "of this type under this AC; 0.00 means it still belongs to this "
                    "AC but is very minor."
                )
                confidence_help = (
                    "Confidence shows how certain the automated analysis is. Lower "
                    "confidence findings should be reviewed more carefully."
                )
                severity_value = _severity_label(severity)
                confidence_value = _severity_label(confidence)

                st.markdown(
                    "Status: "
                    f"{STATUS_LABELS.get(judge_status, judge_status)} | "
                    "Severity: "
                    f"<span title='{severity_help}'>{severity_value}</span> | "
                    "Confidence: "
                    f"<span title='{confidence_help}'>{confidence_value}</span> "
                    f"{
                        '| Estimated deduction: '
                        + _impact_label(impact)
                        + ' minipoints'
                        if impact is not None and impact < 0
                        else ''
                    }",
                    unsafe_allow_html=True,
                )

                if is_dismissed_candidate:
                    st.warning(
                        "Dismissed candidate: this was considered by the automatic "
                        "judge but excluded from final findings."
                    )

            with header_r:
                st.button(
                    "Show anchor",
                    key=f"btn_{safe_fid}",
                    width="stretch",
                    on_click=_on_view_anchor,
                    args=(safe_fid,),
                    disabled=not has_anchors,
                )

            st.markdown("**What was detected**")
            st.markdown(finding.get("summary", "No summary available."))

            st.markdown("**Why this affected points**")
            st.markdown(_impact_explanation(finding))

            if notes := finding.get("notes"):
                st.caption(", ".join(notes))

            _render_judge(finding, show_technical_details=show_technical_details)
            _render_evidence(finding, show_technical_details=show_technical_details)

            if show_technical_details:
                with st.expander("Technical details", expanded=False):
                    analyser = (finding.get("analyser") or {}).get(
                        "name", "Unknown analyser"
                    )
                    confidence = finding.get("confidence")
                    st.markdown(f"Finding ID: `{fid}`")
                    st.markdown(f"Analyser: `{analyser}`")
                    st.markdown(f"Judge status: `{judge_status}`")
                    st.markdown(f"Confidence: `{_severity_label(confidence)}`")

                    judge = (finding.get("meta") or {}).get("judge") or {}
                    change = judge.get("change") or {}
                    fields: list[str] = change.get("fields") or []
                    before: dict = change.get("before") or {}
                    after: dict = change.get("after") or {}
                    if fields:
                        st.markdown("### Judge field changes (before/after)")
                        for field in fields:
                            b = before.get(field)
                            a = after.get(field)
                            st.markdown(f"#### {field}")
                            col_b, col_a = st.columns(2)
                            col_b.caption("Before")
                            col_b.markdown(str(b) if b is not None else "_n/a_")
                            col_a.caption("After")
                            col_a.markdown(str(a) if a is not None else "_n/a_")

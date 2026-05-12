"""Right-column findings panel, listing findings for review.

Author: Matúš Csirik
"""

import json
import re
from importlib import import_module
from typing import Any

import streamlit as st


def _build_local_storage() -> Any:
    try:
        module = import_module("streamlit_local_storage")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'streamlit-local-storage'. Install it to enable "
            "summary state persistence in browser localStorage."
        ) from exc

    local_storage_cls = getattr(module, "LocalStorage", None)
    if local_storage_cls is None:
        raise RuntimeError(
            "Package 'streamlit-local-storage' does not expose LocalStorage."
        )
    return local_storage_cls()


_LOCAL_STORAGE = _build_local_storage()

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
    """Return criterion filter options as [All, ...sorted unique codes]."""
    codes = sorted({str(f.get("ac_code") or "-") for f in findings})
    return ["All", *codes]


def _severity_confidence_label(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


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


def _criterion_title(
    finding: dict, rubric_by_code: dict[str, dict[str, str | float | None]]
) -> str:
    ac_code = finding.get("ac_code", "")
    if not ac_code:
        title = finding.get("title")
        return title if isinstance(title, str) and title else "Untitled finding"

    rubric = rubric_by_code.get(ac_code, {})
    rubric_title = _rubric_str_value(rubric, "title")
    if rubric_title:
        return rubric_title
    title = finding.get("title")
    if isinstance(title, str) and title:
        return title
    return str(ac_code)


def _criterion_text(
    finding: dict, rubric_by_code: dict[str, dict[str, str | float | None]]
) -> str | None:
    ac_code = finding.get("ac_code", "")
    if not ac_code:
        return None
    rubric = rubric_by_code.get(ac_code, {})
    return _rubric_str_value(rubric, "criterion_text")


def _rubric_str_value(rubric: dict[str, str | float | None], key: str) -> str | None:
    value = rubric.get(key)
    return value if isinstance(value, str) and value else None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _safe_key_fragment(value: str | None, *, fallback: str, max_len: int = 96) -> str:
    if value is None:
        return fallback
    clean_value = str(value).strip()
    if not clean_value:
        return fallback
    safe = re.sub(r"[^a-zA-Z0-9:-]", "_", clean_value).strip("_")
    if not safe:
        return fallback
    return safe[:max_len]


def _summary_storage_key(student_storage_id: str | None) -> str:
    student_key = _safe_key_fragment(student_storage_id, fallback="unknown_student")
    return f"doc_grader.summary.include.{student_key}"


def _summary_signature_key(student_storage_id: str | None) -> str:
    student_key = _safe_key_fragment(student_storage_id, fallback="unknown_student")
    return f"summary_storage_signature_{student_key}"


def _summary_checkbox_key(student_storage_id: str | None, finding_id: str) -> str:
    student_key = _safe_key_fragment(student_storage_id, fallback="student")
    finding_key = _safe_key_fragment(finding_id, fallback="finding", max_len=140)
    return f"summary_include_{student_key}_{finding_key}"


def _finding_id(finding: dict) -> str:
    raw_finding_id = finding.get("finding_id")
    if raw_finding_id is None:
        fallback_source = (
            f"{finding.get('ac_code') or 'unknown'}_"
            f"{finding.get('summary') or 'missing'}"
        )
        return _safe_key_fragment(
            str(fallback_source), fallback="missing_finding_id", max_len=140
        )
    finding_id = str(raw_finding_id).strip()
    if finding_id:
        return finding_id
    return "missing_finding_id"


def _hydrate_summary_state(
    findings: list[dict],
    student_storage_id: str | None,
) -> None:
    storage_key = _summary_storage_key(student_storage_id)
    signature_key = _summary_signature_key(student_storage_id)
    try:
        raw_payload = _LOCAL_STORAGE.getItem(storage_key) or "{}"
    except TypeError:
        raw_payload = "{}"
    payload_signature = raw_payload if isinstance(raw_payload, str) else ""

    overrides: dict[str, bool] = {}
    if isinstance(raw_payload, str):
        try:
            payload = json.loads(raw_payload) if raw_payload.startswith("{") else {}
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            overrides = {
                finding_id: bool(include)
                for finding_id, include in payload.items()
                if isinstance(finding_id, str) and finding_id
            }

    # Re-apply only when browser payload changed (for example after hydration).
    if st.session_state.get(signature_key) != payload_signature:
        for finding in findings:
            finding_id = _finding_id(finding)
            state_key = _summary_checkbox_key(student_storage_id, finding_id)
            if finding_id in overrides:
                st.session_state[state_key] = overrides[finding_id]
            elif state_key not in st.session_state:
                st.session_state[state_key] = True
        st.session_state[signature_key] = payload_signature
        return

    for finding in findings:
        finding_id = _finding_id(finding)
        state_key = _summary_checkbox_key(student_storage_id, finding_id)
        if state_key in st.session_state:
            continue
        st.session_state[state_key] = overrides.get(finding_id, True)


def _is_included_in_summary(finding: dict, student_storage_id: str | None) -> bool:
    finding_id = _finding_id(finding)
    state_key = _summary_checkbox_key(student_storage_id, finding_id)
    return bool(st.session_state.get(state_key, True))


def _persist_summary_state(
    findings: list[dict],
    student_storage_id: str | None,
) -> None:
    payload: dict[str, bool] = {}

    for finding in findings:
        finding_id = _finding_id(finding)
        state_key = _summary_checkbox_key(student_storage_id, finding_id)
        include = bool(st.session_state.get(state_key, True))
        payload[finding_id] = include

    payload_text = json.dumps(payload, separators=(",", ":"))
    storage_key = _summary_storage_key(student_storage_id)
    _LOCAL_STORAGE.setItem(storage_key, payload_text)
    st.session_state[_summary_signature_key(student_storage_id)] = payload_text


def _summary_rows(
    findings: list[dict],
    rubric_by_code: dict[str, dict[str, str | float | None]],
    student_storage_id: str | None,
    max_doc_points: int | float | str | None,
) -> list[dict[str, str]]:
    max_points = _as_float(max_doc_points)
    by_code: dict[str, dict[str, float | int]] = {}

    for finding in findings:
        include = _is_included_in_summary(finding, student_storage_id)

        code = str(finding.get("ac_code") or "-")
        bucket = by_code.setdefault(
            code,
            {
                "included_count": 0,
                "total_count": 0,
                "impact_sum": 0.0,
                "inferred_max_penalty": 0.0,
            },
        )

        bucket["total_count"] += 1

        impact = _as_float(finding.get("impact"))
        severity = _as_float(finding.get("severity"))
        if impact is not None and severity is not None and severity > 0:
            inferred_max_penalty = abs(impact) / severity
            if inferred_max_penalty > float(bucket["inferred_max_penalty"]):
                bucket["inferred_max_penalty"] = inferred_max_penalty

        if include:
            bucket["included_count"] += 1
            if impact is not None:
                bucket["impact_sum"] += abs(impact)

    prepared_rows: list[dict[str, str]] = []
    sortable_rows: list[tuple[float, str, dict[str, str]]] = []

    for code, bucket in by_code.items():
        included_count = int(bucket["included_count"])
        total_count = int(bucket["total_count"])
        impact_sum = float(bucket["impact_sum"])
        inferred_max_penalty = float(bucket["inferred_max_penalty"])

        severity_weight = _as_float(
            (rubric_by_code.get(code) or {}).get("severity_weight")
        )

        max_penalty: float | None = None
        if (
            severity_weight is not None
            and max_points is not None
            and severity_weight > 0
            and max_points > 0
        ):
            max_penalty = severity_weight * max_points
        elif inferred_max_penalty > 0:
            # Fallback for legacy codes missing rulebook metadata (for example ICH).
            max_penalty = inferred_max_penalty

        normalised: float | None = None
        if max_penalty is not None and max_penalty > 0:
            normalised = min(1.0, impact_sum / max_penalty)

        row = {
            "Code": code,
            "Normalised deduction": (
                f"{normalised:.2f}" if normalised is not None else "n/a"
            ),
            "Count": f"{included_count}/{total_count}",
        }
        sort_value = normalised if normalised is not None else -1.0
        sortable_rows.append((sort_value, code, row))

    for _, _, row in sorted(sortable_rows, key=lambda item: (-item[0], item[1])):
        prepared_rows.append(row)

    return prepared_rows


def _points_over_max_for_summary(
    findings: list[dict],
    student_storage_id: str | None,
    max_doc_points: int | float | str | None,
) -> str:
    max_points = _as_float(max_doc_points)
    if max_points is None:
        return "n/a"

    total_impact = 0.0
    for finding in findings:
        if not _is_included_in_summary(finding, student_storage_id):
            continue

        impact = _as_float(finding.get("impact"))
        if impact is None:
            continue
        total_impact += impact

    return f"{max_points + total_impact:.2f}/{max_points:.2f}"


def _render_summary(
    findings: list[dict],
    rubric_by_code: dict[str, dict[str, str | float | None]],
    student_storage_id: str | None,
    max_doc_points: int | float | str | None,
) -> None:
    rows = _summary_rows(findings, rubric_by_code, student_storage_id, max_doc_points)
    with st.container(border=True):
        st.markdown("### Summary")
        st.caption(
            "Normalised deduction is capped at 1.00 per code and reflects "
            "accumulated finding frequency/intensity rather than a final grade."
        )
        if not rows:
            st.info("No findings available for summary.")
            return
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_judge(finding: dict, show_technical_details: bool) -> None:
    """Render automated judge notes in teacher-friendly wording."""
    meta: dict | None = finding.get("meta")
    if not meta:
        return
    judge: dict | None = meta.get("judge")
    if not judge:
        return

    # Extract any before/after change recorded by the judge (grader -> judge)
    change: dict = judge.get("change") or {}
    before: dict = change.get("before") or {}
    after: dict = change.get("after") or {}

    grader_summary = before.get("summary")
    adjusted_summary = after.get("summary")

    with st.expander("Automatic review note", expanded=False):
        if grader_summary:
            st.caption("Grader model summary (original):")
            st.markdown(grader_summary)
        else:
            # Fall back to the current finding summary when original not recorded
            if finding.get("summary"):
                st.caption("Grader model summary:")
                st.markdown(finding.get("summary"))

        decision = judge.get("decision")
        rationale = judge.get("rationale")
        if decision or rationale or adjusted_summary:
            st.caption("Judge model response:")
            if decision:
                st.markdown(f"**Decision:** {decision}")
            if rationale:
                st.markdown(rationale)

            if adjusted_summary:
                # Show adjusted summary only if it differs from the grader summary
                if adjusted_summary != grader_summary:
                    st.caption("Judge-adjusted summary:")
                    st.markdown(adjusted_summary)
                else:
                    st.markdown(adjusted_summary)

        # Optional reasoning from the judge model
        if show_technical_details and (reasoning := judge.get("reasoning_chain")):
            st.caption("Judge model reasoning:")
            st.markdown(reasoning)


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

    with st.expander("Anchors within the document", expanded=False):
        st.caption("Document excerpts and locations that triggered this finding:")
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
                    st.markdown(f"*{snippet}*")

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
    st.session_state["expanded_finding_id"] = safe_fid


def _on_toggle_include(safe_fid: str) -> None:
    """Keep the current finding expanded after Include checkbox rerun."""
    st.session_state["expanded_finding_id"] = safe_fid


def render_findings(
    findings: list[dict],
    dismissed_candidates: list[dict],
    rubric_by_code: dict[str, dict[str, str | float | None]],
    student_id: str | None,
    student_storage_id: str | None,
    max_doc_points: int | float | str | None,
) -> None:
    """Render the full findings panel in the right column.

    Args:
        findings: Final findings pre-filtered for UI-excluded codes.
        dismissed_candidates: Dismissed candidates pre-filtered for UI exclusions.
        rubric_by_code: Rubric metadata keyed by assessment criterion code.
        student_id: Student identifier shown in the panel header.
        student_storage_id: Stable per-student key for UI state persistence.
        max_doc_points: Maximum document points configured for the run.

    Returns:
        None
    """

    summary_student = student_id or "n/a"
    all_known_findings = [*findings, *dismissed_candidates]
    _hydrate_summary_state(all_known_findings, student_storage_id)
    st.session_state.setdefault("show_summary", True)
    st.session_state.setdefault("expanded_finding_id", None)
    st.session_state.setdefault("show_excluded_summary_findings", True)

    summary_findings = list(findings)
    if st.session_state.get("show_dismissed_candidates"):
        summary_findings.extend(dismissed_candidates)
    dynamic_points_over_max = _points_over_max_for_summary(
        summary_findings,
        student_storage_id,
        max_doc_points,
    )

    with st.container(border=True):
        info_col, toggles_col = st.columns([1.25, 1], vertical_alignment="top")

        toggles_col.checkbox(
            "Show summary panel",
            key="show_summary",
            help="Display or hide the Summary panel.",
        )
        toggles_col.checkbox(
            "Show findings excluded from summary",
            key="show_excluded_summary_findings",
            help=(
                "When disabled, only findings with Include in summary enabled "
                "remain visible in this list."
            ),
        )
        toggles_col.checkbox(
            "Show findings dismissed by judge",
            key="show_dismissed_candidates",
            help=(
                "When enabled, the list includes finding candidates dismissed "
                "by the judge model."
            ),
        )
        toggles_col.checkbox(
            "Show detailed diagnostics",
            key="show_technical_details",
            help=(
                "Shows additional content inside each finding, including "
                "Automatic review note, Anchors within the document, and "
                "Technical details."
            ),
        )

        merged_findings = list(findings)
        if st.session_state.get("show_dismissed_candidates"):
            merged_findings.extend(dismissed_candidates)

        display_findings = list(merged_findings)
        if not st.session_state.get("show_excluded_summary_findings"):
            display_findings = [
                finding
                for finding in merged_findings
                if _is_included_in_summary(finding, student_storage_id)
            ]

        code_options = _code_filter_options(display_findings)
        if st.session_state.get("findings_code_filter") not in code_options:
            st.session_state["findings_code_filter"] = "All"

        with info_col:
            st.markdown(f"Student ID: **{summary_student}**")
            st.markdown(f"Points: **{dynamic_points_over_max}**")

            code_filter = st.selectbox(
                "Filter by criterion",
                code_options,
                key="findings_code_filter",
            )
            sort_by = st.radio(
                "Sort findings by (descending)",
                ["Deduction", "Confidence"],
                horizontal=True,
                key="findings_sort",
            )

    if st.session_state.get("show_summary"):
        _render_summary(
            summary_findings,
            rubric_by_code,
            student_storage_id,
            max_doc_points,
        )

    _persist_summary_state(all_known_findings, student_storage_id)

    show_technical_details = bool(st.session_state.get("show_technical_details"))

    visible = [
        f
        for f in display_findings
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
        fid = _finding_id(finding)
        safe_fid = fid.replace(":", "-")
        judge_status = finding["judge_status"]
        severity = finding.get("severity")
        confidence = finding.get("confidence")
        ac_code = finding.get("ac_code", "-")
        criterion_title = _criterion_title(finding, rubric_by_code)
        confidence_tint_band = _confidence_tint_band(confidence)
        is_dismissed_candidate = bool(finding.get("is_dismissed_candidate"))

        expanded_fid = st.session_state.get("expanded_finding_id")
        active_fid = st.session_state.get("active_finding_id")
        is_active = safe_fid == (expanded_fid or active_fid)
        anchors: list[dict] = finding.get("anchors") or []
        has_anchors = bool(anchors)
        include_key = _summary_checkbox_key(student_storage_id, fid)
        include_in_summary = _is_included_in_summary(finding, student_storage_id)
        expander_criterion_title = (
            criterion_title if include_in_summary else f"~~{criterion_title}~~"
        )

        impact = finding.get("impact")
        with st.expander(
            f"[{ac_code}] {expander_criterion_title} {_impact_title(impact)}",
            expanded=is_active,
        ):
            # Inject a hidden marker so global CSS can tint this expander by confidence.
            marker_html = (
                f'<span data-confidence-band="{confidence_tint_band}" '
                "data-dismissed-candidate="
                f'"{"true" if is_dismissed_candidate else "false"}" '
                'style="display:none"></span>'
            )
            st.html(marker_html)

            header_l, header_r = st.columns([2, 2], vertical_alignment="center")

            with header_l:
                st.markdown(f"#### {ac_code}: {criterion_title}")
            with header_r:
                include_col, anchor_col = st.columns(
                    [1.2, 1], vertical_alignment="center"
                )
                with include_col:
                    st.checkbox(
                        "Include in summary",
                        key=include_key,
                        on_change=_on_toggle_include,
                        args=(safe_fid,),
                        help=(
                            "Controls whether this finding contributes to the "
                            "Summary panel and the Points value."
                        ),
                    )
                with anchor_col:
                    st.button(
                        "Show anchor",
                        key=f"btn_{safe_fid}",
                        width="stretch",
                        on_click=_on_view_anchor,
                        args=(safe_fid,),
                        disabled=not has_anchors,
                    )

            criterion_text = _criterion_text(finding, rubric_by_code)
            if criterion_text:
                st.caption(f"{ac_code} definition:\n {criterion_text}")

            severity_help = (
                "Severity scale for this criterion: 1.00 means the worst error "
                "of this type under this AC, 0.00 means it still belongs to this "
                "criterion but is very minor."
            )
            confidence_help = (
                "Confidence shows how certain the automated analysis is. Lower "
                "confidence findings should be reviewed more carefully."
            )
            severity_value = _severity_confidence_label(severity)
            confidence_value = _severity_confidence_label(confidence)
            deduction_html = ""
            if impact is not None and impact < 0:
                deduction_html = (
                    f"<div>Estimated deduction: {_impact_label(impact)} "
                    "minipoints</div>"
                )

            st.markdown(
                f"<div><span title='{severity_help}'>"
                f"Severity {severity_value}</span></div>"
                f"<span title='{confidence_help}'>"
                f"<div>Confidence: {confidence_value}</span></div>"
                f"{deduction_html}",
                unsafe_allow_html=True,
            )

            if is_dismissed_candidate:
                st.warning(
                    "Dismissed candidate: this was considered by the automatic "
                    "judge but excluded from final findings."
                )

            st.markdown("#### What was detected:")
            st.markdown(finding.get("summary", "No summary available."))

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
                    st.markdown(
                        f"Confidence: `{_severity_confidence_label(confidence)}`"
                    )

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

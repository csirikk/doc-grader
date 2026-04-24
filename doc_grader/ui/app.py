"""doc-grader review UI main Streamlit application.

Author: Matúš Csirik

Launch with:
    streamlit run src/ui/app.py
"""

from pathlib import Path

import streamlit as st
from document_panel import render_document
from findings_panel import render_findings

from doc_grader.ui.data import (
    load_dismissed_candidates,
    load_run,
    rubric_lookup,
    run_display_name,
    run_student_prefix,
    source_path_from_info,
)

_PROJECT_ROOT = Path(__file__).parent.parent.parent

st.set_page_config(
    page_title="doc-grader review",
    layout="wide",
    initial_sidebar_state="expanded",
)
_DEFAULT_OUT = _PROJECT_ROOT / "out"

# AI generated css for scrolling fixes:
_CUSTOM_SCROLL_CSS = """
<style>
/* 1. Shrink the actual top bar (hamburger menu) */
[data-testid="stHeader"] {
    height: 1rem !important; /* Keep the header compact */
}

/* 2. Reduce the whitespace at the top of the page */
[data-testid="stMainBlockContainer"] {
    padding-top: 4rem !important; /* Trim the top gap */
    padding-bottom: 0px !important;
    overflow: hidden !important;
}

/* 3. Lock the absolute top-level Streamlit containers to stop page jumping */
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    overflow: hidden !important;
}

/* 4. Make top level columns be the height of the screen */
[data-testid="stColumn"] {
    height: calc(100vh - 6rem); 
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin; 
}
[data-testid="stColumn"] [data-testid="stColumn"] {
    height: auto;
    overflow-y: visible;
    overflow-x: visible;
}
</style>
"""
st.html(_CUSTOM_SCROLL_CSS)


def _normalise_student_prefix(value: str | None) -> str | None:
    """Return the first 6 characters from a student identifier value."""
    if not value:
        return None
    clean_value = str(value).strip()
    if not clean_value:
        return None
    return clean_value[:6]


def _get_query_student_prefix() -> str | None:
    """Get student prefix from URL query parameter ``student_id``."""
    query_value = st.query_params.get("student_id")
    if isinstance(query_value, list):
        query_value = query_value[0] if query_value else None
    return _normalise_student_prefix(query_value)


def _set_query_student_prefix(prefix: str | None) -> None:
    """Set URL query parameter ``student_id`` to a 6-character prefix."""
    clean_prefix = _normalise_student_prefix(prefix)
    current = _get_query_student_prefix()
    if current == clean_prefix:
        return

    if clean_prefix is None:
        if "student_id" in st.query_params:
            del st.query_params["student_id"]
        return

    st.query_params["student_id"] = clean_prefix


def _run_for_student_prefix(
    discovered: list[Path], student_prefix: str | None
) -> Path | None:
    """Return the first discovered run matching a student prefix."""
    if student_prefix is None:
        return None
    for run_dir in discovered:
        if run_student_prefix(run_dir) == student_prefix:
            return run_dir
    return None


def _points_over_max(
    findings: list[dict], max_doc_points: int | float | str | None
) -> str:
    """Return current_points/max_points string computed from finding impacts."""
    if max_doc_points is None:
        return "n/a"

    try:
        max_points = float(max_doc_points)
    except TypeError, ValueError:
        return "n/a"

    total_impact = 0.0
    for finding in findings:
        impact = finding.get("impact")
        if impact is None:
            continue
        try:
            total_impact += float(impact)
        except TypeError, ValueError:
            continue

    return f"{max_points + total_impact:.2f}/{max_points:.2f}"


def _load_target_run(target: Path) -> None:
    """Load final findings, dismissed candidates and run info into state."""
    findings, info = load_run(target, stage="Final")
    dismissed_candidates = load_dismissed_candidates(target)
    st.session_state.update(
        {
            "out_dir": target,
            "findings": findings,
            "dismissed_candidates": dismissed_candidates,
            "info": info,
        }
    )
    _reset_run_ui_state()


def _reset_run_ui_state() -> None:
    st.session_state["active_finding_id"] = None
    st.session_state["findings_code_filter"] = "All"
    st.session_state["findings_sort"] = "Deduction"
    st.session_state["show_dismissed_candidates"] = False


def _init_state() -> None:
    st.session_state.setdefault("out_dir", None)
    st.session_state.setdefault("findings", [])
    st.session_state.setdefault("dismissed_candidates", [])
    st.session_state.setdefault("info", {})
    st.session_state.setdefault("active_finding_id", None)
    st.session_state.setdefault("findings_code_filter", "All")
    st.session_state.setdefault("findings_sort", "Deduction")
    st.session_state.setdefault("show_dismissed_candidates", False)
    st.session_state.setdefault("show_technical_details", False)
    st.session_state.setdefault("last_query_student_prefix", None)


_init_state()


with st.sidebar:
    st.title("doc-grader")

    base_out = _DEFAULT_OUT
    discovered: list[Path] = []
    if base_out.exists():
        # Recursively find all directories containing findings.json
        discovered = sorted(
            {p.parent for p in base_out.rglob("findings.json")},
            key=lambda p: p.name,
        )

    selected_run: Path | None = None
    if discovered:
        query_student_prefix = _get_query_student_prefix()
        query_target_run = _run_for_student_prefix(discovered, query_student_prefix)
        last_query_student_prefix = st.session_state.get("last_query_student_prefix")
        query_changed_externally = query_student_prefix != last_query_student_prefix

        if "selected_run_picker" not in st.session_state:
            initial_picker_value = query_target_run or st.session_state.get("out_dir")
            st.session_state["selected_run_picker"] = (
                initial_picker_value
                if initial_picker_value in discovered
                else discovered[0]
            )

        if st.session_state["selected_run_picker"] not in discovered:
            st.session_state["selected_run_picker"] = discovered[0]

        if (
            query_changed_externally
            and query_target_run is not None
            and st.session_state["selected_run_picker"] != query_target_run
        ):
            st.session_state["selected_run_picker"] = query_target_run

        selected_run = st.selectbox(
            "Available directories",
            discovered,
            format_func=run_display_name,
            key="selected_run_picker",
        )

        selected_prefix = run_student_prefix(selected_run)
        _set_query_student_prefix(selected_prefix)
        st.session_state["last_query_student_prefix"] = _get_query_student_prefix()

        if query_student_prefix and query_target_run is None:
            st.caption(f"No run found for student ID prefix `{query_student_prefix}`.")

        if (
            query_changed_externally
            and query_target_run is not None
            and st.session_state.get("out_dir") != query_target_run
        ):
            _load_target_run(query_target_run)
    else:
        st.caption(f"No runs found under `{base_out}`.")

    load_clicked = st.button("Load", type="primary", use_container_width=True)

    if load_clicked:
        target = selected_run

        if not target:
            st.error("No run selected.")
        else:
            if not target.exists():
                st.error(f"Directory not found: `{target}`")
            elif not (target / "findings.json").exists():
                st.error(f"No `findings.json` in `{target}`")
            else:
                _load_target_run(target)

    info_local = st.session_state.get("info", {})
    source_path_local = source_path_from_info(info_local)

    # Determine a short student prefix to use for downloaded filenames.
    student_prefix_local: str | None = None
    if isinstance(info_local, dict):
        student_id_val = info_local.get("input", {}).get("student_id")
        if isinstance(student_id_val, str):
            s = student_id_val.strip()
            if s:
                student_prefix_local = s[:6]

    if not student_prefix_local:
        out_dir_local = st.session_state.get("out_dir")
        if isinstance(out_dir_local, Path) and out_dir_local is not None:
            student_prefix_local = run_student_prefix(out_dir_local)

    if source_path_local:
        path_local = Path(source_path_local)
        suffix = path_local.suffix.lower()

        if suffix == ".pdf":
            pdf_bytes = path_local.read_bytes()
            file_name = (
                f"{student_prefix_local}_review{suffix}"
                if student_prefix_local
                else path_local.name
            )

            st.download_button(
                label="Download original PDF",
                data=pdf_bytes,
                file_name=file_name,
                mime="application/pdf",
                use_container_width=True,
            )

        elif suffix == ".md":
            from renderers.md_renderer import get_standalone_html

            html_content = get_standalone_html(path_local)
            file_name = (
                f"{student_prefix_local}_review.html"
                if student_prefix_local
                else f"{path_local.stem}_rendered.html"
            )

            st.download_button(
                label="Download rendered HTML",
                data=html_content,
                file_name=file_name,
                mime="text/html",
                use_container_width=True,
            )

    st.warning(
        "## Disclaimer\n"
        "This user interface showcases suggestions from a prototype "
        "**machine learning-based** based tool. It is designed to aid graders "
        "and is not a meant to be a full grading interface. "
        "Please expect both false positives and false negatives. This tool is designed"
        " to be used only as a complementary aid to the current manual grading process."
    )

    with st.expander("Usage", expanded=True):
        st.markdown(
            "1. Navigate the external grading CSV and click the links embedded in "
            " the link columns, or search for any student in the picker above.\n"
            "2. View and filter findings within the right panel."
        )
    with st.expander("Help", expanded=False):
        st.markdown(
            "- Findings are tinted based on the confidence of the model."
            " The confidence value is not always reliable.\n"
            "- Extra caution is advised when the related document is non-traditionally"
            " formatted or a **DOCTYPE** finding is present.\n"
            "- Due to some students not following file-naming instructions, "
            "it is possible that the scored document is not a documentation.\n"
            "- Evidence anchors do not always point to the exact intended evidence."
        )

out_dir: Path = st.session_state["out_dir"]
findings: list[dict] = st.session_state["findings"]
dismissed_candidates: list[dict] = st.session_state["dismissed_candidates"]
info: dict = st.session_state["info"]

source_path = source_path_from_info(info)
course = info.get("config", {}).get("course") if info else None
rubric_by_code = rubric_lookup(course)
student_id = run_student_prefix(out_dir) if out_dir is not None else None
max_doc_points = info.get("config", {}).get("max_doc_points") if info else None
points_over_max = _points_over_max(findings, max_doc_points)
total_findings = len(findings)

if out_dir is not None:

    @st.fragment
    def workspace():
        doc_col, findings_col = st.columns([0.55, 0.45], gap="medium")

        findings_for_selection = list(findings)
        if st.session_state.get("show_dismissed_candidates"):
            findings_for_selection.extend(dismissed_candidates)

        active_id = st.session_state.get("active_finding_id")
        selected_finding = next(
            (
                f
                for f in findings_for_selection
                if f.get("finding_id", "").replace(":", "-") == active_id
            ),
            None,
        )

        with doc_col:
            render_document(source_path, selected_finding)

        with findings_col:
            with st.container(border=False):
                render_findings(
                    findings,
                    dismissed_candidates,
                    out_dir,
                    rubric_by_code,
                    student_id,
                    points_over_max,
                    total_findings,
                )

    workspace()

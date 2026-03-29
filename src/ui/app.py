"""doc-grader review UI main Streamlit application.

Launch with:
    streamlit run src/ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when launched directly via streamlit run.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from src.ui.document_panel import render_document  # noqa: E402
from src.ui.findings_panel import render_findings  # noqa: E402
from src.ui.io import (  # noqa: E402
    available_stages,
    load_run,
    run_display_name,
    source_path_from_info,
)

st.set_page_config(
    page_title="doc-grader review",
    layout="wide",
    initial_sidebar_state="expanded",
)

_DEFAULT_OUT = _PROJECT_ROOT / "out"
_WORKSPACE_HEIGHT = 820  # todo: make dynamic

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
</style>
"""
st.html(_CUSTOM_SCROLL_CSS)


def _on_stage_change():
    new_stage = st.session_state["stage_radio"]
    current_dir = st.session_state["out_dir"]
    new_findings, _ = load_run(current_dir, stage=new_stage)

    st.session_state["findings"] = new_findings
    st.session_state["active_finding_id"] = None  # Reset selection on stage change


def _reset_run_ui_state(initial_stage: str = "Final") -> None:
    st.session_state["active_finding_id"] = None
    st.session_state["stage_radio"] = initial_stage
    st.session_state["findings_filter"] = "All"
    st.session_state["findings_sort"] = "Severity"


def _init_state() -> None:
    st.session_state.setdefault("out_dir", None)
    st.session_state.setdefault("findings", [])
    st.session_state.setdefault("info", {})
    st.session_state.setdefault("active_finding_id", None)
    st.session_state.setdefault("findings_filter", "All")
    st.session_state.setdefault("findings_sort", "Severity")


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
        selected_run = st.selectbox(
            "Discovered runs",
            discovered,
            format_func=run_display_name,
        )
    else:
        st.caption(f"No runs found under `{base_out}`.")

    load_clicked = st.button("Load run", type="primary", use_container_width=True)

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
                initial_stage = "Final"
                findings, info = load_run(target, stage=initial_stage)
                st.session_state.update(
                    {
                        "out_dir": target,
                        "findings": findings,
                        "info": info,
                    }
                )
                _reset_run_ui_state(initial_stage)

    # Run info
    if st.session_state["out_dir"]:
        current_dir: Path = st.session_state["out_dir"]
        info = st.session_state["info"]
        run_meta = info.get("run", {})
        parse_meta = info.get("parse", {})

        st.markdown(f"Run: `{run_meta.get('run_id', '-')}`")
        st.markdown(f"Parsed OK: `{parse_meta.get('parsed_ok', '-')}`")
        source = source_path_from_info(info)
        student_id = info.get("input", {}).get("student_id")
        if student_id:
            st.markdown(f"Student: `{student_id}`")
        elif source:
            st.markdown(f"Source: `{Path(source).name}`")

        # Pipeline stage selector
        stages = available_stages(current_dir)
        if len(stages) > 1:
            st.radio(
                "Pipeline stage",
                stages,
                index=stages.index(st.session_state.get("stage_radio", "Final"))
                if st.session_state.get("stage_radio", "Final") in stages
                else 0,
                horizontal=True,
                key="stage_radio",
                on_change=_on_stage_change,
            )
        current_findings = st.session_state["findings"]

        n_total = len(current_findings)
        n_not_to_be_judged = sum(
            1 for f in current_findings if f["judge_status"] == "not_to_be_judged"
        )
        n_to_be_judged = sum(
            1 for f in current_findings if f["judge_status"] == "to_be_judged"
        )
        n_judged_approved = sum(
            1 for f in current_findings if f["judge_status"] == "judged_approved"
        )
        n_judged_adjusted = sum(
            1 for f in current_findings if f["judge_status"] == "judged_adjusted"
        )
        n_judged_dismissed = sum(
            1 for f in current_findings if f["judge_status"] == "judged_dismissed"
        )

        st.markdown(
            f"{n_total} findings total:\n"
            f"- {n_not_to_be_judged} not to be judged\n"
            f"- {n_to_be_judged} to be judged\n"
            f"- {n_judged_approved} judged approved\n"
            f"- {n_judged_adjusted} judged adjusted\n"
            f"- {n_judged_dismissed} judged dismissed\n"
        )

out_dir: Path = st.session_state["out_dir"]
findings: list[dict] = st.session_state["findings"]
info: dict = st.session_state["info"]

source_path = source_path_from_info(info)

if out_dir is not None:

    @st.fragment
    def workspace():
        doc_col, findings_col = st.columns([0.55, 0.45], gap="medium")

        active_id = st.session_state.get("active_finding_id")
        selected_finding = next(
            (
                f
                for f in findings
                if f.get("finding_id", "").replace(":", "-") == active_id
            ),
            None,
        )

        with doc_col:
            render_document(source_path, selected_finding, height=_WORKSPACE_HEIGHT)

        with findings_col:
            with st.container(height=_WORKSPACE_HEIGHT, border=False):
                render_findings(findings, out_dir)

    workspace()

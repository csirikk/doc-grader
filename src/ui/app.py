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
from src.ui.io import available_stages, load_run, source_path_from_info  # noqa: E402

st.set_page_config(
    page_title="doc-grader review",
    layout="wide",
    initial_sidebar_state="expanded",
)

_DEFAULT_OUT = _PROJECT_ROOT / "out"

# Sticky document-column CSS.
# Streamlit renders columns in a flex row with align-items:stretch, forcing
# both columns to share the same height and preventing sticky positioning.
# Resetting to flex-start gives the columns independent heights so the
# document column can stick to the viewport top while findings scroll.
_STICKY_CSS = """
<style>
div[data-testid="stHorizontalBlock"] {
    align-items: flex-start;
}
div[data-testid="stHorizontalBlock"]
> div[data-testid="stColumn"]:first-child {
    position: sticky;
    top: 3.5rem;          /* clear Streamlit's top toolbar */
}
</style>
"""
st.markdown(_STICKY_CSS, unsafe_allow_html=True)


def _init_state() -> None:
    defaults: dict = {
        "out_dir": None,
        "findings": [],
        "info": {},
        "selected_idx": None,
        "stage": "Final",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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

    run_options: list[str] = [str(p) for p in discovered]
    selected_run_str: str | None = None

    if run_options:
        selected_run_str = st.selectbox(
            "Discovered runs",
            options=run_options,
            format_func=lambda p: Path(p).name,
        )
    else:
        st.caption(f"No runs found under `{base_out}`.")

    manual_path = st.text_input(
        "Or enter path manually",
        placeholder="/path/to/out/name/",
    )

    load_clicked = st.button("Load run", type="primary", width="stretch")

    if load_clicked:
        target = (
            Path(manual_path.strip())
            if manual_path.strip()
            else (Path(selected_run_str) if selected_run_str else None)
        )
        if target is None:
            st.error("No run selected.")
        elif not target.exists():
            st.error(f"Directory not found: `{target}`")
        elif not (target / "findings.json").exists():
            st.error(f"No `findings.json` in `{target}`")
        else:
            findings, info = load_run(target, stage="Final")
            st.session_state["out_dir"] = target
            st.session_state["findings"] = findings
            st.session_state["info"] = info
            st.session_state["selected_idx"] = None
            st.session_state["stage"] = "Final"
            st.caption(f"Loaded {len(findings)} findings from `{target.name}`")

    # Run info
    if st.session_state["out_dir"]:
        st.divider()
        current_dir: Path = st.session_state["out_dir"]
        info = st.session_state["info"]
        run_meta = info.get("run", {})
        parse_meta = info.get("parse", {})
        counts = info.get("counts", {})
        re_info = info.get("rule_engine", {})

        st.markdown(f"Run: `{run_meta.get('run_id', '-')}`")
        st.markdown(f"Parsed OK: `{parse_meta.get('parsed_ok', '-')}`")
        source = source_path_from_info(info)
        if source:
            st.markdown(f"Source: `{Path(source).name}`")

        # Pipeline stage selector
        stages = available_stages(current_dir)
        if len(stages) > 1:
            stage = st.radio(
                "Pipeline stage",
                stages,
                index=stages.index(st.session_state.get("stage", "Final"))
                if st.session_state.get("stage", "Final") in stages
                else 0,
                horizontal=True,
                key="stage_radio",
            )
            if stage != st.session_state.get("stage"):
                new_findings, _ = load_run(current_dir, stage=stage)
                st.session_state["findings"] = new_findings
                st.session_state["stage"] = stage
                st.session_state["selected_idx"] = None
                st.rerun()
        else:
            stage = st.session_state.get("stage", "Final")

        current_findings = st.session_state["findings"]
        stage: str = st.session_state.get("stage", "Final")

        n_total = len(current_findings)
        n_approved = sum(1 for f in current_findings if f.get("status") == "approved")
        n_dismissed = sum(1 for f in current_findings if f.get("status") == "dismissed")
        n_proposed = sum(1 for f in current_findings if f.get("status") == "proposed")

        st.markdown(
            f"{n_total} findings total:\n"
            f"- {n_approved} approved\n"
            f"- {n_dismissed} dismissed\n"
            f"- {n_proposed} proposed"
        )

out_dir: Path | None = st.session_state["out_dir"]
findings: list[dict] = st.session_state["findings"]
info: dict = st.session_state["info"]
selected_idx: int | None = st.session_state.get("selected_idx")

source_path = source_path_from_info(info)
selected_finding = (
    findings[selected_idx]
    if (selected_idx is not None and 0 <= selected_idx < len(findings))
    else None
)

if out_dir is None:
    st.info("Select a run from the sidebar and click **Load run** to begin.")
else:
    doc_col, findings_col = st.columns([0.55, 0.45], gap="medium")

    with doc_col:
        render_document(source_path, selected_finding)

    with findings_col:
        render_findings(findings, out_dir)

# -*- coding: utf-8 -*-
"""
Vlogger Streamlit GUI — local-only post-match analysis browser.

Run from the repo root:
    poetry run streamlit run gui/app.py

Sidebar workflow:
    1. Enter a log directory (recursively scanned for *.wpilog).
    2. Pick which matches to include.
    3. Pick which analyses to run.
    4. Each tab renders per-match drill-down + season aggregate.

Results are cached per (log_path, mtime, kind) — re-runs only re-parse logs
that have changed on disk.
"""

import os
from pathlib import Path

import streamlit as st

from gui.data import find_logs, load_results, match_label
from gui.tabs import flywheel as flywheel_tab
from gui.tabs import intake as intake_tab
from gui.tabs import joystick as joystick_tab


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = str(REPO_ROOT / "logs")

ALL_KINDS = ("flywheel", "intake", "joystick")

st.set_page_config(
    page_title="vlogger — match analysis",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _sidebar() -> tuple[list[str], list[str]]:
    """Render the sidebar. Returns (selected_log_paths, selected_kinds)."""
    st.sidebar.title("vlogger")
    st.sidebar.caption("Post-match analysis · Valor 6800")

    # -- Directory input (Streamlit auto-persists via session_state under `key`)
    log_dir = st.sidebar.text_input(
        "Log directory",
        value=DEFAULT_LOG_DIR,
        help="Recursively scanned for *.wpilog files.",
        key="log_dir",
    )

    if st.sidebar.button("Rescan / clear cache", use_container_width=True):
        st.cache_data.clear()
        st.toast("Cache cleared — logs will be re-parsed.", icon="↻")

    # -- Log discovery
    logs = find_logs(log_dir)
    if not log_dir:
        st.sidebar.info("Enter a log directory above to get started.")
        return [], []
    if not os.path.isdir(log_dir):
        st.sidebar.error(f"Directory not found: `{log_dir}`")
        return [], []
    if not logs:
        st.sidebar.warning("No `.wpilog` files found in this directory.")
        return [], []

    st.sidebar.caption(f"Found **{len(logs)}** log file{'s' if len(logs) != 1 else ''}.")

    # -- Match multiselect
    labels = [match_label(p) for p in logs]
    label_to_path = dict(zip(labels, logs))
    default_sel = labels  # default: all
    selected_labels = st.sidebar.multiselect(
        "Matches",
        options=labels,
        default=default_sel,
        key="match_pick",
    )
    selected_paths = [label_to_path[l] for l in selected_labels]

    st.sidebar.divider()

    # -- Analysis toggles
    st.sidebar.subheader("Analyses")
    kinds: list[str] = []
    for k in ALL_KINDS:
        if st.sidebar.checkbox(k.capitalize(), value=True, key=f"toggle_{k}"):
            kinds.append(k)

    return selected_paths, kinds


def _run_and_render(tab_module, results: list[dict]) -> None:
    tab_module.render(results)


def main() -> None:
    selected_paths, kinds = _sidebar()

    st.title("Match analysis")

    if not selected_paths:
        st.info(
            "Pick a log directory and at least one match in the sidebar, "
            "then choose which analyses to run."
        )
        return
    if not kinds:
        st.info("All analyses are toggled off — enable at least one in the sidebar.")
        return

    st.caption(
        f"**{len(selected_paths)} match{'es' if len(selected_paths) != 1 else ''}** selected · "
        f"running: {', '.join(kinds)}"
    )

    # Run all selected analyses up-front (cached, so subsequent reruns are fast).
    by_kind: dict[str, tuple[list[dict], list[str]]] = {}
    for k in kinds:
        ok, failed = load_results(selected_paths, k)
        by_kind[k] = (ok, failed)
        if failed:
            st.warning(
                f"{k}: {len(failed)} log(s) had no usable data — "
                + ", ".join(os.path.basename(p) for p in failed[:5])
                + (" ..." if len(failed) > 5 else "")
            )

    # Tabs (only shown for enabled analyses)
    tab_modules = {
        "flywheel": flywheel_tab,
        "intake":   intake_tab,
        "joystick": joystick_tab,
    }
    tabs = st.tabs([k.capitalize() for k in kinds])
    for tab, k in zip(tabs, kinds):
        with tab:
            _run_and_render(tab_modules[k], by_kind[k][0])


main()

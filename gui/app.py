# -*- coding: utf-8 -*-
"""
Vlogger Streamlit GUI — local-only post-match analysis browser.

Run from the repo root:
    poetry run streamlit run gui/app.py

Sidebar workflow:
    1. Pick which analyses to run (defaults off — nothing runs until opt-in).
    2. Enter or browse to a log directory (recursively scanned for *.wpilog).
    3. Pick which matches to include.
    4. Each tab renders per-match drill-down + season aggregate.

Caching:
    Results are cached two ways:
    * Streamlit `@st.cache_data` — in-memory, per-session.
    * Disk pickle next to each log — `<log_dir>/.vlogger_cache/`. Survives
      Streamlit server restarts. Keyed by (mtime, schema-version) so file edits
      invalidate automatically. Use the **Re-run** button above the tabs to
      force a fresh re-analysis.
"""

import os
from pathlib import Path

import streamlit as st

from gui.data import find_logs, invalidate_disk_cache, load_results, match_label
from gui.tabs import drivetrain as drivetrain_tab
from gui.tabs import feeder as feeder_tab
from gui.tabs import flywheel as flywheel_tab
from gui.tabs import hopper as hopper_tab
from gui.tabs import intake as intake_tab
from gui.tabs import joystick as joystick_tab
from gui.tabs import shot as shot_tab


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = str(REPO_ROOT / "logs")
LOGO_PATH = str(Path(__file__).resolve().parent / "assets" / "valor_logo.png")

ALL_KINDS = ("flywheel", "feeder", "hopper", "intake", "drivetrain", "joystick", "shot")

# NB: set_page_config + st.logo were previously at module scope. They moved
# into main() so worker subprocesses (which on Windows re-import this file
# via multiprocessing.spawn) don't fire them and flood logs with
# "missing ScriptRunContext" warnings. Streamlit treats repeated identical
# set_page_config calls as a no-op, so calling on every rerender is fine.


def _pick_folder() -> str | None:
    """Open a native OS folder picker via tkinter.

    Works because Streamlit runs locally on the user's machine. Returns the
    chosen path, or None if the dialog is cancelled / tkinter is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askdirectory(
            parent=root,
            mustexist=True,
            title="Select log directory",
        )
    finally:
        root.destroy()
    return path or None


def _sidebar() -> tuple[list[str], list[str], bool]:
    """Render the sidebar. Returns (selected_log_paths, selected_kinds, skip_hoot)."""
    st.sidebar.title("vlogger")
    st.sidebar.caption("Post-match analysis · Valor 6800")

    # -- Analyses (rendered first so the user opts in before any logs auto-load).
    st.sidebar.subheader("Analyses")
    kinds: list[str] = []
    for k in ALL_KINDS:
        if st.sidebar.checkbox(k.capitalize(), value=False, key=f"toggle_{k}"):
            kinds.append(k)

    skip_hoot = st.sidebar.checkbox(
        "Skip hoot pairing",
        value=False,
        key="skip_hoot",
        help="Skip the per-motor hoot data (DeviceTemp, SupplyCurrent, "
             "TorqueCurrent). Cuts first-load time from minutes to seconds, "
             "but drops the motor-telemetry section in each tab.",
    )

    st.sidebar.divider()

    # -- Directory input. Initialise session_state once so the Browse button can
    #    update it before the text_input is rendered on the same run.
    if "log_dir" not in st.session_state:
        st.session_state.log_dir = DEFAULT_LOG_DIR

    if st.sidebar.button("Browse for folder…", width="stretch"):
        chosen = _pick_folder()
        if chosen:
            st.session_state.log_dir = chosen

    log_dir = st.sidebar.text_input(
        "Log directory",
        help="Recursively scanned for *.wpilog files. Use Browse for a native picker.",
        key="log_dir",
    )

    # -- Log discovery
    logs = find_logs(log_dir)
    if not log_dir:
        st.sidebar.info("Enter a log directory above to get started.")
        return [], kinds, skip_hoot
    if not os.path.isdir(log_dir):
        st.sidebar.error(f"Directory not found: `{log_dir}`")
        return [], kinds, skip_hoot
    if not logs:
        st.sidebar.warning("No `.wpilog` files found in this directory.")
        return [], kinds, skip_hoot

    st.sidebar.caption(f"Found **{len(logs)}** log file{'s' if len(logs) != 1 else ''}.")

    # -- Match multiselect
    labels = [match_label(p) for p in logs]
    label_to_path = dict(zip(labels, logs))

    # Scan button: re-walks the directory (already happens via find_logs above on
    # any rerun) and auto-adds any newly-discovered logs to the user's selection.
    # Rendered before the multiselect so it can write to session_state.match_pick
    # before the widget instantiates.
    if st.sidebar.button(
        "Scan for new logs",
        width="stretch",
        help="Auto-add any newly-downloaded match logs to your selection. "
             "Existing selections are preserved.",
    ):
        current = list(st.session_state.get("match_pick", labels))
        new_labels = [l for l in labels if l not in current]
        if new_labels:
            st.session_state.match_pick = current + new_labels
            st.toast(
                f"Added {len(new_labels)} new match log"
                f"{'s' if len(new_labels) != 1 else ''} to the selection."
            )
        else:
            st.toast("No new match logs found.")

    selected_labels = st.sidebar.multiselect(
        "Matches",
        options=labels,
        default=labels,  # only used on first run; session_state takes over after
        key="match_pick",
    )
    selected_paths = [label_to_path[l] for l in selected_labels]

    return selected_paths, kinds, skip_hoot


def _run_and_render(tab_module, results: list[dict]) -> None:
    tab_module.render(results)


def main() -> None:
    st.set_page_config(
        page_title="vlogger — match analysis",
        page_icon=LOGO_PATH,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    # App-level branding: shown in the top-left header and shrunk in the sidebar.
    st.logo(LOGO_PATH, size="large")

    selected_paths, kinds, skip_hoot = _sidebar()

    st.title("Match analysis")

    if not kinds:
        st.info(
            "Enable at least one analysis in the sidebar to get started — "
            "nothing runs until you opt in."
        )
        return
    if not selected_paths:
        st.info(
            "Pick a log directory and at least one match in the sidebar to "
            f"run: {', '.join(kinds)}."
        )
        return

    # Analysis gate: don't auto-run on every checkbox toggle. Selection
    # changes are cheap (Streamlit re-runs the script on each interaction);
    # we only kick off the slow load_results when the user explicitly clicks.
    # `analyzed_signature` is the (paths, kinds, skip_hoot) tuple last analyzed
    # — when it matches the current selection, results are still in cache and
    # we re-render; when it changes, we wait for another Analyze click.
    selection_signature = (tuple(selected_paths), tuple(kinds), bool(skip_hoot))

    # Toolbar: selection summary + Clear cache + Analyze.
    col_msg, col_clear, col_run = st.columns([4, 1, 1])
    with col_msg:
        st.markdown(
            f"**{len(selected_paths)} match{'es' if len(selected_paths) != 1 else ''}** "
            f"selected · queued: {', '.join(kinds)}"
            + ("  · _hoot pairing skipped_" if skip_hoot else "")
        )
    with col_clear:
        clear_clicked = st.button(
            "Clear cache",
            help="Delete cached results (memory + on-disk pickles) for the "
                 "selected matches & analyses. Click Analyze afterwards to "
                 "re-compute.",
            width="stretch",
        )
    with col_run:
        analyze_clicked = st.button(
            "Analyze",
            type="primary",
            help="Run the selected analyses across the selected matches.",
            width="stretch",
        )

    if clear_clicked:
        removed = invalidate_disk_cache(selected_paths, kinds)
        st.cache_data.clear()
        # Force the next Analyze click to actually run; without dropping the
        # signature, a subsequent rerender would still consider the selection
        # "already analyzed" and skip the load.
        st.session_state.pop("analyzed_signature", None)
        st.toast(
            f"Cleared {removed} disk cache file{'s' if removed != 1 else ''} "
            "+ in-memory cache. Click Analyze to re-compute."
        )
        st.rerun()

    if analyze_clicked:
        st.session_state["analyzed_signature"] = selection_signature

    if st.session_state.get("analyzed_signature") != selection_signature:
        st.info(
            "Adjust your selection in the sidebar, then click **Analyze** to run.\n\n"
            "_Selection changes don't trigger work until you click Analyze, "
            "so you can freely tweak match/analysis toggles before committing._"
        )
        return

    # Either the user just clicked Analyze, or the cache is already populated
    # for this exact selection — load_results hits cache fast either way.
    by_kind: dict[str, tuple[list[dict], list[str], dict]] = {}
    total_cached = total_fresh = 0
    for k in kinds:
        ok, failed, counts = load_results(selected_paths, k, skip_hoot=skip_hoot)
        by_kind[k] = (ok, failed, counts)
        total_cached += counts["cached"]
        total_fresh  += counts["fresh"]
        if failed:
            st.warning(
                f"{k}: {len(failed)} log(s) had no usable data — "
                + ", ".join(os.path.basename(p) for p in failed[:5])
                + (" ..." if len(failed) > 5 else "")
            )

    # Status caption with cache breakdown.
    parts = [f"running: {', '.join(kinds)}"]
    if total_cached:
        parts.append(f"{total_cached} from cache")
    if total_fresh:
        parts.append(f"{total_fresh} freshly analyzed")
    st.caption(" · ".join(parts))

    # Tabs (only shown for enabled analyses)
    tab_modules = {
        "flywheel":   flywheel_tab,
        "intake":     intake_tab,
        "joystick":   joystick_tab,
        "drivetrain": drivetrain_tab,
        "feeder":     feeder_tab,
        "hopper":     hopper_tab,
        "shot":       shot_tab,
    }
    tabs = st.tabs([k.capitalize() for k in kinds])
    for tab, k in zip(tabs, kinds):
        with tab:
            _run_and_render(tab_modules[k], by_kind[k][0])


# On Windows the parallel pool uses `spawn`, which re-imports __main__ in
# each worker and runs everything at module scope. Without this guard
# main() would run inside every spawned worker, flooding the parent with
# "missing ScriptRunContext" warnings and (worse) hitting the no-runtime
# error path. Streamlit sets __name__ to "__main__" for the entry script;
# spawn workers set it to "__mp_main__".
if __name__ == "__main__":
    main()

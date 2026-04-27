# -*- coding: utf-8 -*-
"""
Cached loaders that wrap the analysis scripts' analyze_log() functions.

Streamlit's @st.cache_data keys results by (path, mtime, kind) so re-runs only
re-parse logs that have changed on disk (e.g. a freshly downloaded match log
that overwrote a previous file).
"""

import os
import sys
import contextlib
import io
from pathlib import Path

import streamlit as st

# Make analysis/ importable when streamlit is launched from the repo root.
_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from analysis import flywheel_analysis, intake_analysis, joystick_analysis  # noqa: E402

ANALYSES = {
    "flywheel": flywheel_analysis,
    "intake":   intake_analysis,
    "joystick": joystick_analysis,
}


def find_logs(directory: str) -> list[str]:
    """Recursively scan a directory for *.wpilog files."""
    if not directory or not os.path.isdir(directory):
        return []
    found: list[str] = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".wpilog"):
                found.append(os.path.abspath(os.path.join(root, f)))
    return sorted(found)


def match_label(log_path: str) -> str:
    """Short label for a log file (parent dir + filename without extension)."""
    p = Path(log_path)
    parent = p.parent.name
    return f"{parent}/{p.stem}" if parent else p.stem


@st.cache_data(show_spinner=False, max_entries=500)
def cached_analyze(log_path: str, mtime: float, kind: str):
    """Cached call to the per-analysis analyze_log() function.

    `mtime` participates in the cache key so a file edit invalidates the entry.
    """
    return ANALYSES[kind].analyze_log(log_path)


def load_results(log_paths: list[str], kind: str):
    """Run cached_analyze() for each path. Returns (ok_results, failed_paths).

    A small Streamlit progress bar is shown while uncached files are processed.
    Cached entries return instantly.
    """
    if not log_paths:
        return [], []

    ok: list[dict] = []
    failed: list[str] = []
    bar = st.progress(0.0, text=f"Loading {kind} ({len(log_paths)} log{'s' if len(log_paths) != 1 else ''})...")
    try:
        for i, p in enumerate(log_paths):
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                failed.append(p)
                continue
            try:
                r = cached_analyze(p, mtime, kind)
            except Exception as e:                          # noqa: BLE001
                st.warning(f"{kind}: failed to analyze `{os.path.basename(p)}`: {e}")
                failed.append(p)
                continue
            if r is None:
                failed.append(p)
            else:
                ok.append(r)
            bar.progress(
                (i + 1) / len(log_paths),
                text=f"Loading {kind}... {i+1}/{len(log_paths)}",
            )
    finally:
        bar.empty()
    return ok, failed


def capture_text(fn, *args, **kwargs) -> str:
    """Run a print-based report function and capture its stdout to a string.

    Lets us reuse the existing print_per_log_report / print_combined_analysis
    functions verbatim and surface their text output inside a Streamlit
    expander as a feature-complete fallback.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()

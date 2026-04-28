# -*- coding: utf-8 -*-
"""
Cached, parallel loaders that wrap each analysis module's analyze_log().

The previous implementation looped serially over (log × kind) pairs. With many
matches and three analyses enabled, that meant 3N sequential DataLogReader
passes — exactly the bottleneck the CLI scripts already solve via a process
pool. This module mirrors that approach for the Streamlit GUI:

  * Each (path, mtime, kind) result is cached on disk via ``@st.cache_data``
    (``persist="disk"``), so re-runs only re-parse logs that changed.
  * Cache misses are batched and dispatched to a ProcessPoolExecutor sized to
    ``min(cpu_count, n_logs)`` and recycled between tasks
    (``max_tasks_per_child=1``) — same pattern as ``analysis/*_analysis.py``.
  * Each worker decodes the wpilog ONCE with a unioned regex and runs every
    requested analysis against the same series dict, so we don't pay the
    wpiutil decoding cost three times per match.

A small in-session memo (``st.session_state["_vlogger_seen"]``) avoids
re-batching results we've already stuffed into the cache this session, since
``@st.cache_data`` doesn't expose a public peek API.
"""

import os
import sys
import contextlib
import io
import concurrent.futures
from pathlib import Path

import streamlit as st

# Make analysis/ + src/ importable when streamlit is launched from the repo root.
_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from analysis import flywheel_analysis, intake_analysis, joystick_analysis  # noqa: E402
from gui import _worker  # noqa: E402  — import-light helper used by both pool workers and the inline path

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


# -- Cache trampoline -----------------------------------------------------------
# Sentinel distinguishes "no precomputed value" from a worker that returned None
# (the legitimate "missing signals" case, which we still want to memoize).

class _NotProvided:
    pass
_NOT_PROVIDED = _NotProvided()


@st.cache_data(show_spinner=False, max_entries=500, persist="disk")
def cached_analyze(log_path: str, mtime: float, kind: str, _precomputed=_NOT_PROVIDED):
    """Cached per-(path, mtime, kind) analysis result, persisted to disk.

    The leading-underscore ``_precomputed`` is excluded from Streamlit's cache
    key (Streamlit ignores parameters whose names start with ``_``). When
    provided it becomes the function's return value and gets memoized — that's
    how parallel-pool results get stuffed into the cache without re-running the
    inline analysis. With ``_precomputed`` omitted, the body falls back to
    running the standalone analyze_log so this remains a usable single-call
    entry point.
    """
    if not isinstance(_precomputed, _NotProvided):
        return _precomputed
    return ANALYSES[kind].analyze_log(log_path)


def _make_pool(workers: int):
    """ProcessPoolExecutor that recycles workers after each task — vlogger and
    wpiutil hold C-extension state that Python's GC can't reclaim, so without
    recycling peak RSS grows without bound across logs (same trick the CLI
    scripts use)."""
    kwargs = {"max_workers": workers}
    if sys.version_info >= (3, 11):
        kwargs["max_tasks_per_child"] = 1
    return concurrent.futures.ProcessPoolExecutor(**kwargs)


def load_results_multi(log_paths: list[str], kinds: list[str]) -> dict[str, tuple[list[dict], list[str]]]:
    """Run every requested analysis across every log path, in parallel.

    Returns ``{kind: (ok_results, failed_paths)}`` for each kind in ``kinds``.
    Results are appended to ``ok_results`` in input order so the per-match
    tabs render matches in a stable, user-recognisable sequence.
    """
    out: dict[str, tuple[list[dict], list[str]]] = {k: ([], []) for k in kinds}
    if not log_paths or not kinds:
        return out

    # Resolve mtimes up-front so cache keys are stable across the function.
    mtimes: dict[str, float] = {}
    fail_oserror: list[str] = []
    for p in log_paths:
        try:
            mtimes[p] = os.path.getmtime(p)
        except OSError:
            fail_oserror.append(p)

    # Streamlit's @st.cache_data has no peek API, so we keep our own short-
    # circuit set: anything in here is guaranteed to already be in the cache
    # (because we put it there earlier this session).
    seen: set = st.session_state.setdefault("_vlogger_seen", set())

    needed: list[tuple[str, tuple[str, ...]]] = []
    for p, m in mtimes.items():
        kinds_left = tuple(k for k in kinds if (p, m, k) not in seen)
        if kinds_left:
            needed.append((p, kinds_left))

    if needed:
        total = sum(len(ks) for _, ks in needed)
        n_workers = max(1, min(os.cpu_count() or 4, len(needed)))
        bar = st.progress(
            0.0,
            text=f"Decoding {len(needed)} log{'s' if len(needed) != 1 else ''} "
                 f"({total} analyses, {n_workers} worker{'s' if n_workers != 1 else ''})...",
        )
        done = 0
        try:
            def _store(p_done: str, results: dict[str, dict | None]) -> None:
                nonlocal done
                m = mtimes[p_done]
                for k, r in results.items():
                    cached_analyze(p_done, m, k, _precomputed=r)
                    seen.add((p_done, m, k))
                done += len(results)
                bar.progress(
                    done / max(total, 1),
                    text=f"Decoded {done}/{total}",
                )

            if n_workers == 1 or len(needed) == 1:
                # Inline fast-path — no spawn-pool overhead for a single match.
                for t in needed:
                    p_done, results = _worker.analyze_kinds(t)
                    _store(p_done, results)
            else:
                ex = _make_pool(n_workers)
                try:
                    futures = {ex.submit(_worker.analyze_kinds, t): t for t in needed}
                    for fut in concurrent.futures.as_completed(futures):
                        p_in, ks_in = futures[fut]
                        try:
                            p_done, results = fut.result()
                        except Exception as e:                  # noqa: BLE001
                            st.warning(
                                f"Failed to analyze `{os.path.basename(p_in)}`: {e}"
                            )
                            results = {k: None for k in ks_in}
                            p_done = p_in
                        _store(p_done, results)
                finally:
                    ex.shutdown(wait=True, cancel_futures=True)
        finally:
            bar.empty()

    # Read every (path, kind) back from the cache and bucket by kind. Iterating
    # log_paths (not mtimes) keeps the input order intact even if some paths
    # OS-errored.
    for p in log_paths:
        if p in fail_oserror:
            for k in kinds:
                out[k][1].append(p)
            continue
        m = mtimes[p]
        for k in kinds:
            try:
                r = cached_analyze(p, m, k)
            except Exception as e:                              # noqa: BLE001
                st.warning(f"{k}: failed `{os.path.basename(p)}`: {e}")
                out[k][1].append(p)
                continue
            if r is None:
                out[k][1].append(p)
            else:
                out[k][0].append(r)
    return out


def capture_text(fn, *args, **kwargs) -> str:
    """Run a print-based report function and capture its stdout to a string.

    Used by the tab modules to surface the legacy text reports inside an
    expander as a feature-complete fallback to the structured rendering.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()

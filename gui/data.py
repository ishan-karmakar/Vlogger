# -*- coding: utf-8 -*-
"""
Cached loaders that wrap the analysis scripts' analyze_log() functions.

Two-tier cache:
1. Streamlit `@st.cache_data` — in-memory, per-session. Instant warm hits.
2. Disk pickle next to each log — survives server restarts. Cache files live
   in `<log_dir>/.vlogger_cache/<stem>.<kind>.v<CACHE_VERSION>.pkl`. Keyed by
   (mtime, CACHE_VERSION) so file edits and analysis-schema bumps invalidate
   automatically.

`cached_analyze` returns `{"result": dict|None, "source": "disk"|"fresh"}` so
callers can show how many results came from cache vs were freshly computed.
"""

import os
import sys
import contextlib
import io
import pickle
from pathlib import Path

import streamlit as st

# Make analysis/ importable when streamlit is launched from the repo root.
_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from analysis import (  # noqa: E402
    _hoot,
    drivetrain_analysis,
    flywheel_analysis,
    intake_analysis,
    joystick_analysis,
)

ANALYSES = {
    "flywheel":   flywheel_analysis,
    "intake":     intake_analysis,
    "joystick":   joystick_analysis,
    "drivetrain": drivetrain_analysis,
}

# Bump when any analyze_log() return-dict shape changes — older pickles will be
# treated as misses and re-analyzed. Without this, old caches could silently
# feed stale dicts into the renderers.
# v2: added drivetrain analysis (new kind; doesn't invalidate other kinds, but
#     bumping is the simplest way to keep version monotonic).
# v3: drivetrain phase 2 — paired-hoot motor telemetry (DeviceTemp,
#     SupplyCurrent, TorqueCurrent) added under modules[*].drive.hoot /
#     azimuth.hoot, plus chassis.max_motor_temp_c and hoot_files_used.
# v4: same hoot pairing extended to flywheel (CAN 30/31/32 on canivore) and
#     intake (CAN 12/13 on rio). Result dicts gain hoot_motors list,
#     hoot_files_used, max_motor_temp_c.
# v5: skip_hoot toggle baked into the cache filename so hoot/no-hoot results
#     don't collide. Pickles compute identically across versions but the file
#     path was renamed.
CACHE_VERSION = 5
CACHE_DIR_NAME = ".vlogger_cache"


def find_logs(directory: str) -> list[str]:
    """Recursively scan a directory for *.wpilog files."""
    if not directory or not os.path.isdir(directory):
        return []
    found: list[str] = []
    for root, dirs, files in os.walk(directory):
        # Don't descend into our own cache dirs
        dirs[:] = [d for d in dirs if d != CACHE_DIR_NAME]
        for f in files:
            if f.lower().endswith(".wpilog"):
                found.append(os.path.abspath(os.path.join(root, f)))
    return sorted(found)


def match_label(log_path: str) -> str:
    """Short label for a log file (parent dir + filename without extension)."""
    p = Path(log_path)
    parent = p.parent.name
    return f"{parent}/{p.stem}" if parent else p.stem


def _disk_cache_path(log_path: str, kind: str, *, skip_hoot: bool = False) -> Path:
    log = Path(log_path)
    suffix = ".no_hoot" if skip_hoot else ""
    return log.parent / CACHE_DIR_NAME / f"{log.stem}.{kind}{suffix}.v{CACHE_VERSION}.pkl"


def _load_from_disk(log_path: str, mtime: float, kind: str, *, skip_hoot: bool = False):
    """Return the cached result dict, or None on miss / mismatch / corrupt file."""
    p = _disk_cache_path(log_path, kind, skip_hoot=skip_hoot)
    if not p.is_file():
        return None
    try:
        with open(p, "rb") as f:
            entry = pickle.load(f)
    except Exception:                                   # noqa: BLE001
        return None
    if entry.get("mtime") != mtime or entry.get("version") != CACHE_VERSION:
        return None
    return entry.get("result")


def _save_to_disk(log_path: str, mtime: float, kind: str, result, *, skip_hoot: bool = False) -> None:
    """Atomically write the result to disk. Cache write failures are swallowed
    so a read-only disk doesn't break analysis."""
    p = _disk_cache_path(log_path, kind, skip_hoot=skip_hoot)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            pickle.dump(
                {"mtime": mtime, "version": CACHE_VERSION, "result": result},
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        tmp.replace(p)  # atomic on Windows + POSIX
    except Exception:                                   # noqa: BLE001
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def invalidate_disk_cache(log_paths: list[str], kinds: list[str]) -> int:
    """Delete cache files for the given (path, kind) pairs across both
    skip_hoot variants. Returns count removed."""
    removed = 0
    for path in log_paths:
        for kind in kinds:
            for skip_hoot in (False, True):
                p = _disk_cache_path(path, kind, skip_hoot=skip_hoot)
                if p.is_file():
                    try:
                        p.unlink()
                        removed += 1
                    except OSError:
                        pass
    return removed


@st.cache_data(show_spinner=False, max_entries=500)
def cached_analyze(log_path: str, mtime: float, kind: str,
                   skip_hoot: bool = False, _on_progress=None) -> dict:
    """Cached wrapper around per-analysis analyze_log().

    `skip_hoot` participates in the cache key so hoot / no-hoot results stay
    distinct. `_on_progress` (leading underscore = ignored by Streamlit's
    hashing) is plumbed through to `_hoot.set_progress_callback` for the
    duration of one analyze_log call so the GUI can show inner status.

    Returns `{"result": dict | None, "source": "disk" | "fresh"}`. Tries the
    on-disk pickle first; on miss runs analyze_log() and writes the result back
    to disk for next time.
    """
    cached = _load_from_disk(log_path, mtime, kind, skip_hoot=skip_hoot)
    if cached is not None:
        return {"result": cached, "source": "disk"}

    _hoot.set_skip(skip_hoot)
    _hoot.set_progress_callback(_on_progress)
    try:
        result = ANALYSES[kind].analyze_log(log_path)
    finally:
        _hoot.set_progress_callback(None)
        _hoot.set_skip(False)

    if result is not None:
        _save_to_disk(log_path, mtime, kind, result, skip_hoot=skip_hoot)
    return {"result": result, "source": "fresh"}


def load_results(log_paths: list[str], kind: str, *, skip_hoot: bool = False):
    """Run cached_analyze() for each path.

    Returns `(ok_results, failed_paths, source_counts)` where source_counts is
    `{"cached": int, "fresh": int}` so the caller can show how many results
    came from disk vs were freshly computed.

    Streamlit's progress bar text reflects per-match status and (during a fresh
    analysis) inner hoot-conversion progress so the UI doesn't look frozen
    during the slow first load.
    """
    if not log_paths:
        return [], [], {"cached": 0, "fresh": 0}

    ok: list[dict] = []
    failed: list[str] = []
    counts = {"cached": 0, "fresh": 0}
    n = len(log_paths)
    bar = st.progress(0.0, text=f"Loading {kind} ({n} log{'s' if n != 1 else ''})...")
    try:
        for i, p in enumerate(log_paths):
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                failed.append(p)
                continue
            base_label = f"{kind} {i+1}/{n} · {os.path.basename(p)}"
            bar.progress(i / n, text=f"Loading {base_label} …")

            def _on_progress(msg: str, _label=base_label, _i=i, _n=n):
                bar.progress(_i / _n, text=f"Loading {_label} — {msg}")

            try:
                wrapped = cached_analyze(p, mtime, kind,
                                         skip_hoot=skip_hoot,
                                         _on_progress=_on_progress)
            except Exception as e:                      # noqa: BLE001
                st.warning(f"{kind}: failed to analyze `{os.path.basename(p)}`: {e}")
                failed.append(p)
                continue
            r   = wrapped["result"]
            src = wrapped["source"]
            if r is None:
                failed.append(p)
            else:
                ok.append(r)
                counts["fresh" if src == "fresh" else "cached"] += 1
            bar.progress((i + 1) / n, text=f"Loading {kind} … {i+1}/{n}")
    finally:
        bar.empty()
    return ok, failed, counts


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

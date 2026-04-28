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

Parallelism:
    Disk-cache misses are dispatched to a ProcessPoolExecutor sized to
    `min(cpu_count, n_misses)` and recycled between tasks
    (``max_tasks_per_child=1`` — same trick the analysis/*.py CLI scripts use,
    because vlogger / wpiutil hold C-extension state GC can't reclaim).
    Workers live in `gui/_worker.py` (streamlit-free import for fast spawn).
"""

import concurrent.futures
import contextlib
import io
import os
import pickle
import sys
from pathlib import Path

import streamlit as st

# Make analysis/ importable when streamlit is launched from the repo root.
_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from analysis import _hoot  # noqa: E402
from gui import _worker  # noqa: E402  — streamlit-free, holds ANALYSES + the worker entry point

# Single source of truth for the kind→module mapping lives in _worker so the
# pool's worker processes don't drag streamlit into their startup.
ANALYSES = _worker.ANALYSES

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


_SKIP_DIRS = frozenset({CACHE_DIR_NAME, _hoot.HOOT_CACHE_DIR_NAME})


def find_logs(directory: str) -> list[str]:
    """Recursively scan a directory for *.wpilog files.

    Excludes our own cache directories — both the per-result analysis cache
    (.vlogger_cache) and the owlet-output cache (.vlogger_hoot_cache). Without
    the hoot-cache exclusion, the GB-sized converted hoot wpilogs get mistaken
    for match logs, return None from every analyze_log (no NT signals match),
    AND can OOM-kill workers in the parallel pool.
    """
    if not directory or not os.path.isdir(directory):
        return []
    found: list[str] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
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


# Sentinel distinguishes "no precomputed value" from a worker that returned
# None (the legitimate "missing signals" case, which we still want to memoize).
class _NotProvided:
    pass
_NOT_PROVIDED = _NotProvided()


@st.cache_data(show_spinner=False, max_entries=500)
def cached_analyze(log_path: str, mtime: float, kind: str,
                   skip_hoot: bool = False,
                   _on_progress=None, _precomputed=_NOT_PROVIDED) -> dict:
    """Cached wrapper around per-analysis analyze_log().

    `skip_hoot` participates in the cache key so hoot / no-hoot results stay
    distinct. `_on_progress` (leading underscore = ignored by Streamlit's
    hashing) is plumbed through to `_hoot.set_progress_callback` for the
    duration of one analyze_log call so the GUI can show inner status.

    `_precomputed` (also leading-underscore, also ignored by hashing) is the
    parallel-pool trampoline: when supplied it short-circuits both the disk
    probe AND the inline analyze_log so workers' results can be stuffed
    straight into Streamlit's in-memory cache. The supplied value must already
    be in the ``{"result": ..., "source": ...}`` shape callers expect.

    Returns `{"result": dict | None, "source": "disk" | "fresh"}`. Tries the
    on-disk pickle first; on miss runs analyze_log() and writes the result back
    to disk for next time.
    """
    if not isinstance(_precomputed, _NotProvided):
        return _precomputed

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


def _make_pool(workers: int):
    """ProcessPoolExecutor that recycles workers after each task.

    Same trick the analysis/*.py CLI scripts use — vlogger / wpiutil hold
    C-extension state Python's GC can't reclaim, so without recycling peak
    RSS grows without bound across logs.
    """
    kwargs = {"max_workers": workers}
    if sys.version_info >= (3, 11):
        kwargs["max_tasks_per_child"] = 1
    return concurrent.futures.ProcessPoolExecutor(**kwargs)


def load_results(log_paths: list[str], kind: str, *, skip_hoot: bool = False):
    """Run cached_analyze() for each path, parallelized across cache misses.

    Returns `(ok_results, failed_paths, source_counts)` where source_counts is
    `{"cached": int, "fresh": int}` so the caller can show how many results
    came from disk vs were freshly computed. ``ok_results`` preserves
    ``log_paths`` order regardless of the order workers finish in.

    Phases:
        1. Disk-cache probe in the parent (pickle reads are fast). Hits warm
           Streamlit's in-memory cache via the ``_precomputed=`` trampoline.
        2. Misses get dispatched to a ProcessPoolExecutor sized to
           ``min(cpu_count, n_misses)`` with ``max_tasks_per_child=1`` (same
           recycling pattern as the analysis/*.py CLI scripts). Workers live
           in ``gui/_worker.py`` (streamlit-free import for fast spawn).
        3. As each worker finishes, the parent writes its result to the disk
           cache and warms ``@st.cache_data`` so subsequent reruns this
           session don't even hit the disk cache.

    Single-miss / single-CPU runs take an inline fast-path: same compute, no
    spawn-pool overhead, AND we keep the fine-grained hoot progress callback
    that can't survive a process boundary.
    """
    if not log_paths:
        return [], [], {"cached": 0, "fresh": 0}

    n = len(log_paths)
    ok_by_idx: dict[int, dict] = {}
    failed: list[str] = []
    counts = {"cached": 0, "fresh": 0}
    misses: list[tuple[int, str, float]] = []   # (idx, path, mtime)

    bar = st.progress(0.0, text=f"Loading {kind} ({n} log{'s' if n != 1 else ''})...")

    def _record_done(idx: int, p: str, mtime: float, result, *, fresh: bool) -> None:
        """Centralised bookkeeping for one finished (path, kind).

        Runs in the parent process for both inline and pool paths so disk
        cache writes + Streamlit cache warming live in one place.
        """
        if result is None:
            failed.append(p)
            return
        ok_by_idx[idx] = result
        if fresh:
            counts["fresh"] += 1
            _save_to_disk(p, mtime, kind, result, skip_hoot=skip_hoot)
        else:
            counts["cached"] += 1
        cached_analyze(
            p, mtime, kind, skip_hoot=skip_hoot,
            _precomputed={"result": result, "source": "fresh" if fresh else "disk"},
        )

    try:
        # Phase 1: disk-cache probe.
        for i, p in enumerate(log_paths):
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                failed.append(p)
                continue
            cached = _load_from_disk(p, mtime, kind, skip_hoot=skip_hoot)
            if cached is None:
                misses.append((i, p, mtime))
                continue
            _record_done(i, p, mtime, cached, fresh=False)
            done_total = len(ok_by_idx) + len(failed)
            bar.progress(done_total / n,
                         text=f"{kind}: {done_total}/{n} (from cache)")

        # Phase 2: compute the misses.
        if misses:
            n_misses = len(misses)
            n_workers = max(1, min(os.cpu_count() or 4, n_misses))
            done_misses = 0

            def _bump(p: str) -> None:
                """Push the progress bar after a single miss completes."""
                nonlocal done_misses
                done_misses += 1
                done_total = len(ok_by_idx) + len(failed)
                bar.progress(
                    done_total / n,
                    text=f"{kind}: {done_misses}/{n_misses} freshly analyzed "
                         f"({n_workers} worker{'s' if n_workers != 1 else ''})",
                )

            if n_workers == 1 or n_misses == 1:
                # Inline path: no spawn-pool overhead. Set the hoot progress
                # callback in the parent so the bar text reflects long owlet
                # conversions.
                for idx, p, mtime in misses:
                    label = f"{kind} · {os.path.basename(p)}"
                    bar.progress((len(ok_by_idx) + len(failed)) / n,
                                 text=f"Loading {label} …")

                    def _on_progress(msg: str, _label=label):
                        bar.progress(
                            (len(ok_by_idx) + len(failed)) / n,
                            text=f"Loading {_label} — {msg}",
                        )

                    _hoot.set_progress_callback(_on_progress)
                    try:
                        try:
                            _, _, result = _worker.analyze_one((p, kind, skip_hoot))
                        except Exception as e:           # noqa: BLE001
                            st.warning(f"{kind}: failed to analyze "
                                       f"`{os.path.basename(p)}`: {e}")
                            failed.append(p)
                            _bump(p)
                            continue
                    finally:
                        _hoot.set_progress_callback(None)
                    _record_done(idx, p, mtime, result, fresh=True)
                    _bump(p)
            else:
                ex = _make_pool(n_workers)
                pool_broken = False
                try:
                    submitted = {
                        ex.submit(_worker.analyze_one, (p, kind, skip_hoot)):
                            (idx, p, mtime)
                        for idx, p, mtime in misses
                    }
                    for fut in concurrent.futures.as_completed(submitted):
                        idx, p, mtime = submitted[fut]
                        try:
                            _, _, result = fut.result()
                        except concurrent.futures.process.BrokenProcessPool:
                            # A worker died abruptly (OOM kill, segfault, etc.).
                            # Every remaining future will raise the same thing;
                            # surface ONE warning, mark every pending future as
                            # failed, and bail out of the loop.
                            if not pool_broken:
                                st.error(
                                    f"{kind}: worker process died abruptly while "
                                    f"analyzing `{os.path.basename(p)}` (likely "
                                    f"OOM). Remaining {kind} matches in this "
                                    f"batch will be skipped — try reducing the "
                                    f"selection, toggling **Skip hoot pairing**, "
                                    f"or running with fewer matches at a time."
                                )
                                pool_broken = True
                            failed.append(p)
                            _bump(p)
                            continue
                        except Exception as e:           # noqa: BLE001
                            st.warning(f"{kind}: failed to analyze "
                                       f"`{os.path.basename(p)}`: {e}")
                            failed.append(p)
                            _bump(p)
                            continue
                        _record_done(idx, p, mtime, result, fresh=True)
                        _bump(p)
                finally:
                    ex.shutdown(wait=True, cancel_futures=True)
    finally:
        bar.empty()

    ok = [ok_by_idx[i] for i in sorted(ok_by_idx)]
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

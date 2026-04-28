# -*- coding: utf-8 -*-
"""
Shared plumbing for analyses that pair `*.hoot` files alongside the WPILog.

Each motor analysis (flywheel, intake, drivetrain) loads NetworkTables fields
from the WPILog and additionally pulls per-motor signals from the matching
hoot file written during the same match. The hoot-side concerns — locating
owlet, walking the log directory for paired files, caching the converted
wpilog so retries are fast, pumping a vlogger source into the shared raw
dict, computing per-TalonFX summary stats — live here instead of being
duplicated three times.

This is the *one* exception to the "analysis scripts are self-contained, no
cross-imports" rule. Justified because:
  1. The plumbing involves filesystem walks, subprocess, owlet auto-detection,
     persistent caching, and error swallowing — all library-grade code, not
     per-analysis math.
  2. The signature is stable across analyses; each script just supplies its
     own HOOT_REGEX and CAN ID list.

Usage in an analysis script:

    from analysis import _hoot

    def load_series(log_path):
        raw = defaultdict(list)
        src = vlogger.get_source(...wpilog url..., MY_REGEX)
        _hoot.load_into_raw(raw, src)

        hoot_files_used = _hoot.attach_paired_hoots(
            raw, log_path, HOOT_REGEX, bus="canivore"  # or "rio"
        )

        for name in raw: raw[name].sort(...)
        return dict(raw), hoot_files_used

    # later, per motor:
    stats = _hoot.motor_stats(series, can_id)   # None if no hoot data

UI integration (gui/data.py):

    _hoot.set_progress_callback(lambda msg: bar.progress(...,  text=msg))
    _hoot.set_skip(skip_hoot)
    try:
        result = analyze_log(path)
    finally:
        _hoot.set_progress_callback(None)
        _hoot.set_skip(False)
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


# Default subset of Phoenix6/TalonFX signals analyses care about. Extending the
# list costs little since the regex filters at the source level.
DEFAULT_SIGNALS = ("DeviceTemp", "SupplyCurrent", "TorqueCurrent")

# Persistent cache of converted hoot.wpilog files (alongside each *.hoot file).
# Hoot → wpilog conversion takes 1-2 minutes per file via owlet; caching means
# only the first run pays that cost. Keyed on hoot mtime baked into the filename.
HOOT_CACHE_DIR_NAME = ".vlogger_hoot_cache"


# ---- Module-level toggles set by the GUI around analyze_log calls -----------

# When True, attach_paired_hoots returns immediately and no hoot data is
# merged. Used by the sidebar's "Skip hoot pairing" checkbox.
_skip: bool = False

# Optional callback that takes a single string message. Called with status
# updates as hoots convert/load so the GUI can update its progress bar text.
_progress_callback = None


def set_skip(value: bool) -> None:
    """When True, attach_paired_hoots returns immediately. Default False."""
    global _skip
    _skip = bool(value)


def set_progress_callback(fn) -> None:
    """Register a `fn(msg: str) -> None` for status updates, or None to clear."""
    global _progress_callback
    _progress_callback = fn


def _emit(msg: str) -> None:
    cb = _progress_callback
    if cb is None:
        return
    try:
        cb(msg)
    except Exception:                                       # noqa: BLE001
        # Never let a UI callback failure break analysis.
        pass


# ---- Owlet + paired-file discovery ------------------------------------------

def find_owlet():
    """Locate CTRE's owlet — first `PATH`, then `<repo_root>/tools/owlet*`.

    Returns the absolute path or `None` if no copy is found. Callers that get
    `None` should skip hoot pairing entirely; the WPI-only analysis still works.
    """
    p = shutil.which("owlet")
    if p:
        return p
    repo_root = Path(__file__).resolve().parent.parent
    tools_dir = repo_root / "tools"
    if tools_dir.is_dir():
        for f in sorted(tools_dir.iterdir()):
            if f.is_file() and f.name.lower().startswith("owlet"):
                return str(f)
    return None


def find_paired_hoots(wpilog_path, *, bus="canivore"):
    """Return `*.hoot` files in the wpilog's directory tree matching `bus`.

    Heuristic: walks the wpilog's parent dir + 1-level subdirs. CTRE writes one
    hoot per CAN bus per match; the rio bus's filename always contains `_rio_`.

    `bus`:
      - `"canivore"` (default): skip files whose name contains `_rio_`.
      - `"rio"`:                keep only files whose name contains `_rio_`.
      - `"any"`:                all `*.hoot` files in the tree.
    """
    if bus not in ("canivore", "rio", "any"):
        raise ValueError(f"unknown bus {bus!r}; expected canivore / rio / any")
    p = Path(wpilog_path)
    if not p.exists():
        return []
    search_dirs = {p.parent}
    try:
        for d in p.parent.iterdir():
            if d.is_dir():
                search_dirs.add(d)
    except OSError:
        pass
    hoots = []
    for d in search_dirs:
        for f in d.glob("*.hoot"):
            is_rio = "_rio_" in f.name.lower()
            if bus == "canivore" and is_rio:
                continue
            if bus == "rio" and not is_rio:
                continue
            hoots.append(str(f))
    return sorted(set(hoots))


# ---- Persistent cache of converted hoot.wpilog files ------------------------

def _hoot_cache_dir(hoot_path) -> Path:
    return Path(hoot_path).parent / HOOT_CACHE_DIR_NAME


def _cached_outputs(hoot_path):
    """Return cached wpilog files for a hoot, or [] if no cache hit.

    Cache key is the hoot file's mtime — if the source hoot changes the cache
    is invalidated automatically (any new conversion uses a new mtime in the
    filename). All rollover files (`.wpilog`, `.2.wpilog`, ...) come back in
    natural sort order.
    """
    p = Path(hoot_path)
    try:
        mtime_int = int(p.stat().st_mtime)
    except OSError:
        return []
    cache_dir = _hoot_cache_dir(hoot_path)
    if not cache_dir.is_dir():
        return []
    base = cache_dir / f"{p.stem}.{mtime_int}.wpilog"
    if not base.is_file():
        return []
    rollovers = sorted(cache_dir.glob(f"{p.stem}.{mtime_int}.[0-9]*.wpilog"))
    return [base, *rollovers]


def _persist_outputs(hoot_path, tmp_outputs):
    """Move owlet's temp `hoot[.N].wpilog` files into the persistent cache.

    Returns the list of cached paths in load order. Cache files are named
    `<hoot_stem>.<mtime>.wpilog`, `<hoot_stem>.<mtime>.2.wpilog`, etc. — the
    mtime baked into the filename is what invalidates the cache when the hoot
    is replaced (e.g. re-downloaded from the robot).
    """
    p = Path(hoot_path)
    try:
        mtime_int = int(p.stat().st_mtime)
    except OSError:
        return [str(t) for t in tmp_outputs]  # can't read mtime, skip caching
    cache_dir = _hoot_cache_dir(hoot_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = []
    for src in tmp_outputs:
        # owlet names: hoot.wpilog, hoot.2.wpilog, hoot.3.wpilog, ...
        # cache names: <stem>.<mtime>.wpilog, <stem>.<mtime>.2.wpilog, ...
        name = src.name
        if name == "hoot.wpilog":
            dst_name = f"{p.stem}.{mtime_int}.wpilog"
        elif name.startswith("hoot.") and name.endswith(".wpilog"):
            rollover = name[len("hoot."):-len(".wpilog")]   # "2", "3", ...
            dst_name = f"{p.stem}.{mtime_int}.{rollover}.wpilog"
        else:
            dst_name = name  # unexpected; keep as-is
        dst = cache_dir / dst_name
        try:
            shutil.move(str(src), str(dst))
            cached.append(dst)
        except OSError as e:
            sys.stderr.write(f"[hoot] couldn't cache {src.name} -> {dst}: {e}\n")
            cached.append(src)  # fall back to the temp path; caller will read it
    return cached


# ---- Source ingestion -------------------------------------------------------

def load_into_raw(raw, src):
    """Iterate a vlogger source and append entries into a shared `raw` dict.

    `raw` is a `defaultdict(list)` keyed by signal name; values are lists of
    `(timestamp_seconds, value)`. Booleans, numerics, and strings are kept as
    Python types; everything else (raw bytes, struct payloads we couldn't
    decode) is skipped.
    """
    with src:
        for entry in src:
            name = entry["name"]
            ts   = entry["timestamp"] / 1e6
            val  = entry["data"]
            if isinstance(val, bool):
                raw[name].append((ts, bool(val)))
            elif isinstance(val, (int, float)):
                raw[name].append((ts, float(val)))
            elif isinstance(val, str):
                raw[name].append((ts, val))


def _convert_hoot(owlet, hoot_path):
    """Run owlet on a single hoot, returning (output_paths, was_cached, error).

    Tolerates non-zero owlet exit when partial output exists (truncated hoots
    from mid-match disable still produce useful data). Reads all rollover files
    owlet creates (`hoot.wpilog`, `hoot.2.wpilog`, ...). On a cache hit, owlet
    is not invoked at all.

    `error` is None on success or a short string for the stderr log.
    """
    cached = _cached_outputs(hoot_path)
    if cached:
        _emit(f"cached {Path(hoot_path).name}")
        return cached, True, None

    _emit(f"converting {Path(hoot_path).name} (~1-2 min)")
    tmpdir = Path(tempfile.mkdtemp(prefix="vlogger_hoot_"))
    try:
        out_base = tmpdir / "hoot.wpilog"
        proc = subprocess.run(
            [owlet, str(hoot_path), str(out_base), "-f", "wpilog"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        outputs = sorted(tmpdir.glob("hoot*.wpilog"))

        if not outputs:
            stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
            return [], False, f"owlet rc={proc.returncode}, no output. {stderr_tail[-1]}"

        # Move owlet's outputs into the persistent cache.
        cached = _persist_outputs(hoot_path, outputs)

        err = None
        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
            err = (f"owlet rc={proc.returncode}, using partial output "
                   f"({len(cached)} file{'s' if len(cached) != 1 else ''}). "
                   f"{stderr_tail[-1]}")
        return cached, False, err
    finally:
        # tmpdir might still hold copies if persist failed; clean up either way.
        shutil.rmtree(tmpdir, ignore_errors=True)


def attach_paired_hoots(raw, wpilog_path, hoot_regex, *, bus="canivore"):
    """Best-effort: find paired hoots for `wpilog_path` and merge their data.

    Behaviour:
      - Skipped entirely when the module-level `_skip` flag is True (set by the
        GUI's "Skip hoot pairing" toggle).
      - Skipped when input isn't a `.wpilog` (a `.hoot` was passed directly).
      - Skipped when owlet can't be found.
      - Persistent cache: `<hoot_dir>/.vlogger_hoot_cache/<stem>.<mtime>.wpilog`
        (+ rollovers). Cache hits skip owlet entirely. Source hoot replaced →
        new mtime → fresh conversion.
      - Tolerates non-zero owlet exits when partial output exists.
      - Reads every rollover file owlet emits (1 GB cap → `hoot.2.wpilog`,
        `hoot.3.wpilog`, ...).

    Returns the list of source hoot files that contributed data (possibly
    empty). Per-file failures are logged to stderr and skipped.
    """
    import vlogger  # noqa: PLC0415 — lazy so this module is importable on its own

    if _skip:
        return []
    if not wpilog_path.lower().endswith(".wpilog"):
        return []
    owlet = find_owlet()
    if not owlet:
        return []

    used = []
    for hpath in find_paired_hoots(wpilog_path, bus=bus):
        try:
            outputs, was_cached, err = _convert_hoot(owlet, hpath)
            if err:
                sys.stderr.write(f"[hoot] {os.path.basename(hpath)}: {err}\n")
            if not outputs:
                continue
            _emit(f"reading {len(outputs)} wpilog{'s' if len(outputs) != 1 else ''} "
                  f"({'cached' if was_cached else 'fresh'})")
            for opath in outputs:
                wpisrc = vlogger.get_source(f"wpilog:///{opath}", hoot_regex)
                load_into_raw(raw, wpisrc)
            used.append(hpath)
        except Exception as e:                              # noqa: BLE001
            sys.stderr.write(f"[hoot] {os.path.basename(hpath)}: {e}\n")
    return used


# ---- Per-motor stat extraction ---------------------------------------------

def motor_stats(series, canid, signals=DEFAULT_SIGNALS):
    """Per-TalonFX peak/mean stats from the paired hoot.

    Returns a dict with `peak_temp_c`, `mean_temp_c`, `peak_supply_curr`,
    `mean_supply_curr`, `peak_torque_curr` keys (any of which can be `None` if
    that signal wasn't logged). Returns `None` when none of the requested
    signals appear in `series` — caller treats that as "no hoot data for this
    motor".

    Stats are computed on the hoot's *native* timestamps (no interpolation),
    preserving the high sample rate.
    """
    prefix = f"Phoenix6/TalonFX-{canid}"

    def _vals(leaf):
        if leaf not in signals:
            return None
        pts = series.get(f"{prefix}/{leaf}")
        if not pts or not isinstance(pts[0][1], (int, float)):
            return None
        return np.array([float(p[1]) for p in pts])

    temp = _vals("DeviceTemp")
    supc = _vals("SupplyCurrent")
    tqc  = _vals("TorqueCurrent")
    if temp is None and supc is None and tqc is None:
        return None

    return {
        "peak_temp_c":      float(np.max(temp))         if temp is not None else None,
        "mean_temp_c":      float(np.mean(temp))        if temp is not None else None,
        "peak_supply_curr": float(np.max(np.abs(supc))) if supc is not None else None,
        "mean_supply_curr": float(np.mean(np.abs(supc))) if supc is not None else None,
        "peak_torque_curr": float(np.max(np.abs(tqc)))  if tqc  is not None else None,
    }


def hoot_regex(can_ids, signals=DEFAULT_SIGNALS):
    """Build a `Phoenix6/TalonFX-<id>/<sig>` regex for the given CAN IDs + signals.

    Convenience wrapper so each analysis doesn't need to handcraft the regex:

        HOOT_REGEX = _hoot.hoot_regex((30, 31, 32))
    """
    if not can_ids:
        raise ValueError("can_ids must be non-empty")
    ids = "|".join(str(c) for c in can_ids)
    sigs = "|".join(signals)
    return f"Phoenix6/TalonFX-(?:{ids})/(?:{sigs})"

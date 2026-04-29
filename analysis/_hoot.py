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
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np


# Default subset of Phoenix6/TalonFX signals analyses care about. Extending the
# list costs little since the regex filters at the source level.
DEFAULT_SIGNALS = ("DeviceTemp", "SupplyCurrent", "TorqueCurrent")

# Union of every CAN ID any analysis pulls from a paired hoot. Owlet's
# converted wpilog is filtered through this regex at cache time, so the
# persistent cache only stores signals an analyzer might actually read.
# Cuts the on-disk footprint from ~1+ GB per match (owlet output, all
# devices × all signals × full sample rate) down to a few tens of MB.
#
# Adding a new analysis with new CAN IDs requires:
#   1. Append the IDs here.
#   2. Bump HOOT_CACHE_VERSION so existing pkl caches are invalidated.
UNIVERSAL_CAN_IDS = (
    *range(1, 9),   # drivetrain (4 drive + 4 azimuth, IDs 1-8 on canivore)
    12, 13,         # intake (rio bus, IDs 12-13)
    14, 15,         # hopper (rio bus, IDs 14-15)
    30, 31, 32,     # flywheel (canivore bus, IDs 30-32)
    51, 52,         # feeder (canivore bus, IDs 51-52)
)

# Bump when UNIVERSAL_CAN_IDS or DEFAULT_SIGNALS changes — older pkls are
# treated as misses and re-converted from the source hoot.
# v2: added hopper (14, 15) and feeder (51, 52) for the new feeder /
#     hopper / shot analyses.
HOOT_CACHE_VERSION = 2

# Persistent cache of filtered hoot data alongside each *.hoot file.
# Pre-v1: cache held the multi-GB wpilog rollovers verbatim.
# v1+: cache holds a single pickled `{signal_name: [(ts, val), ...]}` dict
#      filtered through UNIVERSAL_HOOT_REGEX. Conversion still costs 1-2
#      min via owlet on first run; subsequent loads read the small pkl.
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


# ---- Persistent cache of filtered hoot series dicts -------------------------

def _hoot_cache_dir(hoot_path) -> Path:
    return Path(hoot_path).parent / HOOT_CACHE_DIR_NAME


def _filtered_cache_path(hoot_path):
    """Pickle path for the filtered series dict, or None if mtime is unreadable.

    Cache key is the source hoot's mtime + HOOT_CACHE_VERSION, both baked
    into the filename. Source hoot replaced → new mtime → cache miss.
    UNIVERSAL_CAN_IDS / DEFAULT_SIGNALS changed → bumped version → cache miss.
    """
    p = Path(hoot_path)
    try:
        mtime_int = int(p.stat().st_mtime)
    except OSError:
        return None
    return _hoot_cache_dir(hoot_path) / f"{p.stem}.{mtime_int}.v{HOOT_CACHE_VERSION}.pkl"


def _load_filtered_pkl(pkl_path):
    """Read a pickled filtered series dict, returning None on miss/corrupt."""
    if pkl_path is None or not pkl_path.is_file():
        return None
    try:
        with open(pkl_path, "rb") as f:
            return pickle.load(f)
    except Exception:                                       # noqa: BLE001
        return None


def _save_filtered_pkl(pkl_path, series_dict):
    """Atomically write the filtered series dict. Failures are swallowed so a
    read-only disk doesn't break analysis."""
    if pkl_path is None:
        return
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = pkl_path.with_suffix(pkl_path.suffix + ".tmp")
    try:
        with open(tmp, "wb") as f:
            pickle.dump(series_dict, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(pkl_path)                               # atomic on POSIX + Windows
    except Exception as e:                                  # noqa: BLE001
        sys.stderr.write(f"[hoot] cache write failed: {e}\n")
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _purge_legacy_wpilog_cache(cache_dir, hoot_stem, mtime_int):
    """Delete the pre-v1 per-rollover wpilog cache files for this (stem, mtime).

    Older versions of vlogger stored owlet's raw wpilog rollovers in the
    cache (~1+ GB per match). Once the equivalent filtered pkl exists,
    those rollovers are obsolete — drop them to reclaim disk.
    """
    if not cache_dir.is_dir():
        return
    for f in cache_dir.glob(f"{hoot_stem}.{mtime_int}*.wpilog"):
        try:
            f.unlink()
        except OSError:
            pass


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
    """Convert hoot → universal-filtered pickle. Returns (pkl_path_or_None, was_cached, error).

    Cache hits skip owlet entirely. On a miss the conversion uses two
    layered filters:

        1. owlet --scan → list signal IDs whose names match
           _UNIVERSAL_SCAN_REGEX, then `owlet --signals <csv> ...` so
           owlet writes a wpilog that already contains only what we
           want. This avoids the multi-GB temp-disk + write cost of a
           full conversion when scan succeeds.

        2. After conversion, we still stream the rollovers through
           UNIVERSAL_HOOT_REGEX (Python-side) before pickling. This is
           the safety net: if scan parsing fails or we hit a future
           owlet that changes its scan format, we fall back to
           "convert everything, filter Python-side" without losing
           data.

    The pkl typically lands at 10-50 MB (vs 1+ GB raw owlet output)
    regardless of which path we took. Tolerates non-zero owlet exit
    when partial output exists (truncated hoots from mid-match
    disables still produce useful data).

    `error` is None on success or a short string for the stderr log.
    """
    import vlogger  # noqa: PLC0415 — lazy so this module is importable on its own

    pkl = _filtered_cache_path(hoot_path)
    if pkl is not None and pkl.is_file():
        _emit(f"cached {Path(hoot_path).name}")
        return pkl, True, None

    # Phase 1: scan the hoot for signal IDs we care about, so owlet can
    # narrow the conversion. None = scan failed (fall back to full); [] =
    # scan succeeded with zero matches (skip owlet entirely).
    filter_ids = _scan_signal_ids(owlet, hoot_path)

    if filter_ids == []:
        _emit(f"no relevant signals in {Path(hoot_path).name} (scan)")
        _save_filtered_pkl(pkl, {})
        try:
            mtime_int = int(Path(hoot_path).stat().st_mtime)
            _purge_legacy_wpilog_cache(_hoot_cache_dir(hoot_path),
                                        Path(hoot_path).stem, mtime_int)
        except OSError:
            pass
        return pkl, False, None

    if filter_ids:
        _emit(f"converting {Path(hoot_path).name} "
              f"({len(filter_ids)} signal{'s' if len(filter_ids) != 1 else ''})")
    else:
        _emit(f"converting {Path(hoot_path).name} (full, ~1-2 min)")

    tmpdir = Path(tempfile.mkdtemp(prefix="vlogger_hoot_"))
    try:
        out_base = tmpdir / "hoot.wpilog"
        cmd = [owlet, str(hoot_path), str(out_base), "-f", "wpilog"]
        if filter_ids:
            cmd += ["--signals", ",".join(filter_ids)]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        outputs = sorted(tmpdir.glob("hoot*.wpilog"))
        if not outputs:
            stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
            return None, False, f"owlet rc={proc.returncode}, no output. {stderr_tail[-1]}"

        # Phase 2 safety filter — if scan-time worked it's already a near-
        # subset, but the regex pass is cheap and protects us against any
        # mismatch between scan IDs and converted names.
        _emit(f"filtering {Path(hoot_path).name} "
              f"({len(outputs)} rollover{'s' if len(outputs) != 1 else ''})")
        filtered: dict[str, list] = defaultdict(list)
        for opath in outputs:
            wpisrc = vlogger.get_source(f"wpilog:///{opath}", UNIVERSAL_HOOT_REGEX)
            load_into_raw(filtered, wpisrc)
        for name in filtered:
            filtered[name].sort(key=lambda x: x[0])
        filtered = dict(filtered)

        _save_filtered_pkl(pkl, filtered)
        try:
            mtime_int = int(Path(hoot_path).stat().st_mtime)
            _purge_legacy_wpilog_cache(_hoot_cache_dir(hoot_path),
                                        Path(hoot_path).stem, mtime_int)
        except OSError:
            pass

        err = None
        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
            err = (f"owlet rc={proc.returncode}, using partial output "
                   f"({len(outputs)} rollover{'s' if len(outputs) != 1 else ''}). "
                   f"{stderr_tail[-1]}")
        return pkl, False, err
    finally:
        # tmpdir holds owlet's output rollovers; always clean up.
        shutil.rmtree(tmpdir, ignore_errors=True)


def attach_paired_hoots(raw, wpilog_path, hoot_regex, *, bus="canivore"):
    """Best-effort: find paired hoots, load filtered cache, merge what matches.

    Behaviour:
      - Skipped when the module-level `_skip` flag is True (sidebar toggle).
      - Skipped when input isn't a `.wpilog` (a `.hoot` was passed directly).
      - Skipped when owlet can't be found.
      - Persistent cache: `<hoot_dir>/.vlogger_hoot_cache/<stem>.<mtime>.vN.pkl`.
        Pre-filtered through UNIVERSAL_HOOT_REGEX at conversion time so the
        on-disk file is a few tens of MB, not the 1+ GB of raw owlet output.
        Source hoot replaced → new mtime → fresh conversion. CAN-ID list
        change → bumped HOOT_CACHE_VERSION → fresh conversion.
      - The caller's `hoot_regex` is applied as a narrower second-pass filter
        on the pkl contents, so each analysis still only merges its own CAN
        IDs into `raw`.

    Returns the list of source hoot files that contributed data (possibly
    empty). Per-file failures are logged to stderr and skipped.
    """
    if _skip:
        return []
    if not wpilog_path.lower().endswith(".wpilog"):
        return []
    owlet = find_owlet()
    if not owlet:
        return []

    pattern = re.compile(hoot_regex)
    used = []
    for hpath in find_paired_hoots(wpilog_path, bus=bus):
        try:
            pkl, was_cached, err = _convert_hoot(owlet, hpath)
            if err:
                sys.stderr.write(f"[hoot] {os.path.basename(hpath)}: {err}\n")
            if pkl is None:
                continue
            filtered = _load_filtered_pkl(pkl)
            if filtered is None:
                # Pkl write succeeded but read failed — corrupt cache?
                sys.stderr.write(f"[hoot] {os.path.basename(hpath)}: cache "
                                 f"unreadable; treating as miss\n")
                continue
            _emit(f"reading {Path(hpath).name} ({'cached' if was_cached else 'fresh'})")
            for name, pts in filtered.items():
                if pattern.search(name):
                    raw[name].extend(pts)
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


# Regex applied at cache time to narrow owlet's output down to just the
# signals any analysis might consume. Placed after hoot_regex() so it can
# call the helper directly.
UNIVERSAL_HOOT_REGEX = hoot_regex(UNIVERSAL_CAN_IDS)

# Same predicate, but matched against owlet `--scan` output names. Owlet's
# scan reports unprefixed names (e.g. "TalonFX-1/DeviceTemp"); the prefix
# "Phoenix6/" only appears once owlet writes the wpilog.
_UNIVERSAL_SCAN_REGEX = UNIVERSAL_HOOT_REGEX.replace("Phoenix6/", "", 1)


def _scan_signal_ids(owlet, hoot_path):
    """Run `owlet --scan` and return the hex signal IDs whose names match
    `_UNIVERSAL_SCAN_REGEX`.

    Returns:
        list[str]  — ordered hex IDs to pass to `owlet --signals`. Empty
                     list means "scan worked but the hoot contains no
                     signals any analysis cares about".
        None       — scan failed or its output couldn't be parsed; the
                     caller should fall back to unfiltered conversion.

    Scan output format (one line per signal):
        <signal_name>:<padding><hex_id>

    e.g. ``TalonFX-1/DeviceTemp:                              2cd0100``.
    Names may contain a colon (``DS:IsDSAttached``); the regex anchors on
    the *trailing* `:<spaces><hex>` to disambiguate.
    """
    try:
        proc = subprocess.run(
            [owlet, "--scan", str(hoot_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None

    line_re = re.compile(r"^(.+):\s+([0-9a-fA-F]+)$")
    name_re = re.compile(_UNIVERSAL_SCAN_REGEX)
    parsed_any = False
    matched: list[str] = []
    for line in proc.stdout.splitlines():
        m = line_re.match(line)
        if not m:
            continue
        parsed_any = True
        name, sig_id = m.group(1), m.group(2)
        if name_re.search(name):
            matched.append(sig_id)

    # If we couldn't parse a single line the format probably changed in
    # a future owlet version — fall back to full conversion rather than
    # silently dropping every signal.
    if not parsed_any:
        return None
    return matched

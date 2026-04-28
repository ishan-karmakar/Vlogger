# -*- coding: utf-8 -*-
"""
Shared plumbing for analyses that pair `*.hoot` files alongside the WPILog.

Each motor analysis (flywheel, intake, drivetrain) loads NetworkTables fields
from the WPILog and additionally pulls per-motor signals from the matching
hoot file written during the same match. The hoot-side concerns — locating
owlet, walking the log directory for paired files, pumping a vlogger source
into the shared raw dict, computing per-TalonFX summary stats — live here
instead of being duplicated three times.

This is the *one* exception to the "analysis scripts are self-contained, no
cross-imports" rule. Justified because:
  1. The plumbing involves filesystem walks, subprocess, owlet auto-detection,
     and error swallowing — all library-grade code, not per-analysis math.
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


def attach_paired_hoots(raw, wpilog_path, hoot_regex, *, bus="canivore"):
    """Best-effort: find paired hoots for `wpilog_path` and merge their data.

    Drives owlet directly rather than going through `vlogger.hoot`, for two
    real-world reasons:

      1. **Tolerate non-zero owlet exits when partial output exists.** Match
         hoots routinely end mid-write (robot disabled abruptly), and owlet
         reports `Could not read to end of input file: No error` and exits 1
         — but only after emitting a perfectly usable partial wpilog. The
         vlogger source uses `check_call` and raises, throwing the data away.
      2. **Read every rollover file owlet produces.** Owlet caps each output
         wpilog at 1 GB and starts `hoot.2.wpilog`, `hoot.3.wpilog`, etc. for
         long matches. `vlogger.hoot` only opens the first file, so the tail
         is silently lost on big logs.

    Imports `vlogger` lazily so this module can also be used standalone (e.g.
    from a test or REPL) without the `sys.path` setup the analysis scripts do.

    Skips silently when:
      - the input isn't a `.wpilog` (a `.hoot` was passed directly),
      - owlet isn't installed (no PATH, no `tools/owlet*` drop-in),
      - no paired hoot files match the requested bus.

    Returns the list of hoot files that were successfully merged (possibly
    empty). Per-file failures are logged to stderr and skipped — one bad hoot
    doesn't abort the whole match.
    """
    import vlogger  # noqa: PLC0415 — lazy so this module is importable on its own

    if not wpilog_path.lower().endswith(".wpilog"):
        return []
    owlet = find_owlet()
    if not owlet:
        return []

    used = []
    for hpath in find_paired_hoots(wpilog_path, bus=bus):
        tmpdir = tempfile.mkdtemp(prefix="vlogger_hoot_")
        out_base = os.path.join(tmpdir, "hoot.wpilog")
        try:
            proc = subprocess.run(
                [owlet, hpath, out_base, "-f", "wpilog"],
                stdout=subprocess.DEVNULL,    # silence owlet's progress bar
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            # owlet rolls over at 1 GB → hoot.wpilog, hoot.2.wpilog, ...
            outputs = sorted(Path(tmpdir).glob("hoot*.wpilog"))
            if not outputs:
                stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
                sys.stderr.write(
                    f"[hoot] {os.path.basename(hpath)}: owlet rc={proc.returncode}, "
                    f"no output produced. {stderr_tail[-1]}\n"
                )
                continue

            if proc.returncode != 0:
                stderr_tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
                sys.stderr.write(
                    f"[hoot] {os.path.basename(hpath)}: owlet rc={proc.returncode}, "
                    f"using partial output "
                    f"({len(outputs)} file{'s' if len(outputs) != 1 else ''}). "
                    f"{stderr_tail[-1]}\n"
                )

            for opath in outputs:
                wpisrc = vlogger.get_source(f"wpilog:///{opath}", hoot_regex)
                load_into_raw(raw, wpisrc)
            used.append(hpath)
        except Exception as e:                              # noqa: BLE001
            sys.stderr.write(f"[hoot] {os.path.basename(hpath)}: {e}\n")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    return used


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

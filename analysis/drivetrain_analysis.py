# -*- coding: utf-8 -*-
"""
Drivetrain (swerve) analysis for FRC Team Valor 6800.

Four swerve modules, each with one Drive motor and one Azimuth motor
(8 TalonFX total). Current + speed + energy are reported per motor, and
separated into AUTO vs TELEOP phases so you can compare how hard the
drivetrain works in each mode.

Module index -> CAN ID mapping (from robot Constants::CANIDs):
  Module 0 : Drive = 2,  Azimuth = 1
  Module 1 : Drive = 4,  Azimuth = 3
  Module 2 : Drive = 6,  Azimuth = 5
  Module 3 : Drive = 8,  Azimuth = 7
Module-to-corner mapping (FL/FR/BL/BR) varies by robot variant — see
robot/src/main/include/constants/Constants.h getModuleCoordsX/Y(). This
script leaves modules labeled 0-3; correlate with your robot build.

All swerve motors live on the Canivore bus, so the Canivore .hoot file
sitting next to the wpilog is the only one needed for high-fidelity
SupplyCurrent data (NT only logs Stator Current + Out Volt + Speed).

Same CLI conventions as the other analysis scripts:
    python drivetrain_analysis.py                  # default log
    python drivetrain_analysis.py logs/E1          # folder
    python drivetrain_analysis.py logs/            # season
    python drivetrain_analysis.py -j 8 logs/
    python drivetrain_analysis.py --no-file logs/
"""

import sys
import os
import glob
import io
import time
import datetime
import contextlib
import concurrent.futures
import subprocess
import tempfile
import shutil
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import vlogger  # noqa: F401 — imported for consistency w/ other scripts
from can_config import CAN_DEVICES, CAN_DEVICES_BY_LABEL, SUBSYSTEMS

# -- Configuration ---------------------------------------------------------------

DEFAULT_LOG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "logs", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")

# Module index -> (drive_can_id, azimuth_can_id). Stable across robot
# variants (only the corner mapping varies).
MODULE_CAN_IDS = {
    0: {"drive": 2, "azimuth": 1},
    1: {"drive": 4, "azimuth": 3},
    2: {"drive": 6, "azimuth": 5},
    3: {"drive": 8, "azimuth": 7},
}

# NT path base for each module's motors
def _nt_base(module_idx, role):
    """role in ('Drive', 'Azimuth') -> NT path base under SmartDashboard."""
    return f"NT:/SmartDashboard/SwerveDrive/Module {module_idx}/{role} Motor"

# Per-motor signals we read from NT
NT_SIGNALS = {
    "Speed":          "Speed",
    "Stator Current": "Stator Current",
    "Supply Current": "Supply Current",   # hoot-only
    "Out Volt":       "Out Volt",
}

# Target series names used throughout the script. Build once to avoid regex
# nesting.
def _all_signal_paths():
    paths = []
    for idx in MODULE_CAN_IDS:
        for role in ("Drive", "Azimuth"):
            for sig in NT_SIGNALS:
                paths.append(f"{_nt_base(idx, role)}/{sig}")
    return paths

# Regex covers NT signals + DS mode flags
DRIVE_REGEX = (
    r"(NT:/SmartDashboard/SwerveDrive/Module [0-3]/(Drive|Azimuth) Motor/"
    r"(Speed|Stator Current|Supply Current|Out Volt|reqSpeed|reqPosition)"
    r"|DS:(enabled|autonomous))"
)

# Which roles we analyze
ROLES = ("Drive", "Azimuth")

# Phase definitions
PHASES = ("AUTO", "TELEOP", "COMBINED")

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading (NT + hoot overlay) --------------------------------------------

def load_series(log_path):
    """NT load + optional hoot overlay. Hoot overlay REPLACES NT entries for
    the signals it covers (hoot is higher fidelity, and it fills in
    SupplyCurrent which NT doesn't publish for swerve motors)."""
    raw = defaultdict(list)
    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, DRIVE_REGEX)
    with src:
        for entry in src:
            raw[entry["name"]].append((entry["timestamp"] / 1e6, entry["data"]))
    for name in raw:
        raw[name].sort(key=lambda x: x[0])

    # Overlay every sibling hoot. Swerve lives on Canivore, so typically only
    # one hoot contains hits, but we try all sibling hoots to be safe.
    for hoot_path in _find_sibling_hoots(log_path):
        try:
            _overlay_hoot_into(raw, hoot_path)
        except Exception as ex:
            sys.stderr.write(
                f"WARNING: hoot overlay for {os.path.basename(hoot_path)} "
                f"failed ({type(ex).__name__}: {ex}); using NT currents.\n")

    return dict(raw)

def _find_sibling_hoots(log_path):
    log_dir = os.path.dirname(os.path.abspath(log_path))
    hoots = []
    for root, _, files in os.walk(log_dir):
        for f in files:
            if f.lower().endswith(".hoot"):
                hoots.append(os.path.join(root, f))
    return sorted(hoots)

def _find_owlet():
    on_path = shutil.which("owlet")
    if on_path:
        return on_path
    repo_owlet = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                               "..", "owlet.exe"))
    return repo_owlet if os.path.isfile(repo_owlet) else None

def _owlet_scan(hoot_path, owlet_exe):
    result = subprocess.run(
        [owlet_exe, hoot_path, "--scan"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        check=False, text=True)
    out = {}
    for line in (result.stdout or "").splitlines():
        if ":" not in line:
            continue
        name, _, rest = line.partition(":")
        name = name.strip()
        hex_id = rest.strip()
        if name and hex_id and all(c in "0123456789abcdefABCDEF" for c in hex_id):
            out[name] = hex_id
    return out

# Hoot signal -> NT-style signal name (same convention as intake_analysis).
HOOT_SIGNAL_MAP = {
    "StatorCurrent":  "Stator Current",
    "SupplyCurrent":  "Supply Current",
    "RotorVelocity":  "Speed",
    "MotorVoltage":   "Out Volt",
}

def _wanted_hoot_signal_names():
    """Build 'TalonFX-<id>/<SignalName>' entries for all 8 swerve motors."""
    want = set()
    for idx, ids in MODULE_CAN_IDS.items():
        for can_id in ids.values():
            for sig in HOOT_SIGNAL_MAP:
                want.add(f"TalonFX-{can_id}/{sig}")
    return want

def _decode_hoot_filtered(hoot_path, owlet_exe, signal_ids):
    if not signal_ids:
        return None
    tmp_dir = tempfile.mkdtemp(prefix="hoot_drive_")
    out_path = os.path.join(tmp_dir, "filtered.wpilog")
    cmd = [owlet_exe, hoot_path, out_path,
           "-f", "wpilog", "-s", ",".join(signal_ids)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=False)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None
    return out_path

def _read_filtered_wpilog(wpilog_path, accepted_names):
    from wpiutil.log import DataLogReader
    reader = DataLogReader(wpilog_path)
    entry_map = {}
    out = defaultdict(list)
    def match_name(entry_name):
        if entry_name in accepted_names:
            return entry_name
        for want in accepted_names:
            if entry_name.endswith(want) or entry_name.endswith("/" + want):
                return want
        return None
    for rec in reader:
        if rec.isStart():
            d = rec.getStartData()
            canon = match_name(d.name)
            if canon is not None:
                entry_map[d.entry] = canon
            continue
        if rec.isFinish():
            entry_map.pop(rec.getFinishEntry(), None)
            continue
        eid = rec.getEntry()
        if eid not in entry_map:
            continue
        try:
            val = rec.getDouble()
        except Exception:
            continue
        out[entry_map[eid]].append((rec.getTimestamp() / 1e6, float(val)))
    for name in out:
        out[name].sort(key=lambda x: x[0])
    return dict(out)

def _overlay_hoot_into(raw, hoot_path):
    """Overlay swerve motor currents + speed from a sibling hoot."""
    owlet_exe = _find_owlet()
    if not owlet_exe:
        raise RuntimeError("owlet not found on PATH or at repo root")
    wanted = _wanted_hoot_signal_names()
    if not wanted:
        return
    name_to_id = _owlet_scan(hoot_path, owlet_exe)
    signal_ids = [name_to_id[n] for n in wanted if n in name_to_id]
    if not signal_ids:
        return  # Probably a non-Canivore hoot — silent skip.
    out_wpilog = _decode_hoot_filtered(hoot_path, owlet_exe, signal_ids)
    if out_wpilog is None:
        raise RuntimeError("owlet produced no output")
    try:
        hoot_samples = _read_filtered_wpilog(out_wpilog, wanted)
    finally:
        shutil.rmtree(os.path.dirname(out_wpilog), ignore_errors=True)

    # Route hoot samples back to Module N NT keys
    can_to_module_role = {}
    for idx, ids in MODULE_CAN_IDS.items():
        can_to_module_role[ids["drive"]]   = (idx, "Drive")
        can_to_module_role[ids["azimuth"]] = (idx, "Azimuth")

    total_samples = 0
    replaced = 0
    for hoot_name, pts in hoot_samples.items():
        try:
            head, signal = hoot_name.split("/", 1)
            _, id_str = head.split("-", 1)
            can_id = int(id_str)
        except (ValueError, TypeError):
            continue
        if can_id not in can_to_module_role:
            continue
        mod_idx, role = can_to_module_role[can_id]
        nt_signal = HOOT_SIGNAL_MAP.get(signal)
        if nt_signal is None:
            continue
        nt_key = f"{_nt_base(mod_idx, role)}/{nt_signal}"
        raw[nt_key] = pts
        total_samples += len(pts)
        replaced += 1
    sys.stderr.write(
        f"[hoot] {os.path.basename(hoot_path)}: "
        f"{replaced} signals, {total_samples:,} samples\n")

# -- Interval helpers (shared with other analysis scripts' shape) ---------------

def compute_phase_intervals(enabled_pts, auto_pts, t_end):
    """
    Return a dict of phase -> intervals:
      AUTO     = enabled AND autonomous
      TELEOP   = enabled AND NOT autonomous
      COMBINED = enabled
    Walks both signals' transitions in time order to build accurate phase
    windows; same approach as limelight_analysis' FMS gating.
    """
    events = []
    for ts, v in enabled_pts:
        events.append((ts, "enabled", bool(v)))
    for ts, v in auto_pts:
        events.append((ts, "auto", bool(v)))
    events.sort(key=lambda e: e[0])

    enabled = False
    auto    = False
    auto_ints, teleop_ints, combined_ints = [], [], []
    open_auto = None
    open_tele = None
    open_en   = None

    for ts, kind, val in events:
        prev_auto   = enabled and auto
        prev_tele   = enabled and not auto
        prev_en     = enabled
        if kind == "enabled":
            enabled = val
        else:
            auto = val
        now_auto = enabled and auto
        now_tele = enabled and not auto
        now_en   = enabled

        # AUTO transitions
        if not prev_auto and now_auto:
            open_auto = ts
        elif prev_auto and not now_auto and open_auto is not None:
            auto_ints.append((open_auto, ts)); open_auto = None
        # TELEOP transitions
        if not prev_tele and now_tele:
            open_tele = ts
        elif prev_tele and not now_tele and open_tele is not None:
            teleop_ints.append((open_tele, ts)); open_tele = None
        # COMBINED (enabled)
        if not prev_en and now_en:
            open_en = ts
        elif prev_en and not now_en and open_en is not None:
            combined_ints.append((open_en, ts)); open_en = None

    if open_auto is not None: auto_ints.append((open_auto, t_end))
    if open_tele is not None: teleop_ints.append((open_tele, t_end))
    if open_en   is not None: combined_ints.append((open_en,   t_end))
    return {"AUTO": auto_ints, "TELEOP": teleop_ints, "COMBINED": combined_ints}

def intervals_total(intervals):
    return float(sum(t1 - t0 for t0, t1 in intervals))

def overlap_with_intervals(a, b, intervals):
    if b <= a:
        return 0.0
    s = 0.0
    for t0, t1 in intervals:
        ov0 = a if a > t0 else t0
        ov1 = b if b < t1 else t1
        if ov1 > ov0:
            s += ov1 - ov0
    return s

def ts_in_intervals(t, intervals):
    for t0, t1 in intervals:
        if t0 <= t <= t1:
            return True
    return False

# -- Stats ----------------------------------------------------------------------

def time_weighted_abs_stats(pts, intervals, t_end):
    """Time-weighted mean of |value| plus sample-based p50/p95/max."""
    if not pts or not intervals:
        return None
    samples = []
    integral = 0.0
    total_time = 0.0
    prev_ts = None
    prev_abs = None
    for ts, v in pts:
        if not isinstance(v, (int, float)):
            continue
        a = abs(float(v))
        if ts_in_intervals(ts, intervals):
            samples.append(a)
        if prev_ts is not None and prev_abs is not None:
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                integral   += prev_abs * ov
                total_time += ov
        prev_ts  = ts
        prev_abs = a
    if prev_ts is not None and prev_abs is not None:
        ov = overlap_with_intervals(prev_ts, t_end, intervals)
        if ov > 0:
            integral   += prev_abs * ov
            total_time += ov
    if not samples or total_time <= 0:
        return None
    arr = np.array(samples)
    return {
        "n":       len(samples),
        "mean_tw": float(integral / total_time),
        "p50":     float(np.percentile(arr, 50)),
        "p95":     float(np.percentile(arr, 95)),
        "max":     float(np.max(arr)),
    }

def energy_over_intervals(voltage_pts, current_pts, intervals, t_end):
    """Integral of |V| * |I| dt over intervals — motor electrical energy in J."""
    if not voltage_pts or not current_pts or not intervals:
        return 0.0
    ts_all = sorted(set([ts for ts, _ in voltage_pts] +
                        [ts for ts, _ in current_pts]))
    ts_all = np.array(ts_all)
    vts = np.array([ts for ts, _ in voltage_pts])
    vvs = np.array([float(v) for _, v in voltage_pts])
    cts = np.array([ts for ts, _ in current_pts])
    cvs = np.array([float(v) for _, v in current_pts])
    v_grid = np.interp(ts_all, vts, vvs, left=vvs[0], right=vvs[-1])
    c_grid = np.interp(ts_all, cts, cvs, left=cvs[0], right=cvs[-1])
    p_grid = np.abs(v_grid) * np.abs(c_grid)
    total = 0.0
    for i in range(len(ts_all) - 1):
        t0, t1 = ts_all[i], ts_all[i + 1]
        dt = t1 - t0
        if dt <= 0:
            continue
        ov = overlap_with_intervals(t0, t1, intervals)
        if ov <= 0:
            continue
        total += 0.5 * (p_grid[i] + p_grid[i + 1]) * ov
    return float(total)

# -- Per-log analysis -----------------------------------------------------------

def analyze_log(log_path):
    series = load_series(log_path)
    enabled_pts = series.get("DS:enabled", [])
    auto_pts    = series.get("DS:autonomous", [])

    # Log timespan from union of all relevant signals
    all_ts = [ts for ts, _ in enabled_pts] + [ts for ts, _ in auto_pts]
    for path in _all_signal_paths():
        for ts, _ in series.get(path, []):
            all_ts.append(ts)
    if not all_ts:
        return None

    t_end = float(max(all_ts))
    phases = compute_phase_intervals(enabled_pts, auto_pts, t_end)
    phase_secs = {p: intervals_total(phases[p]) for p in PHASES}
    if phase_secs["COMBINED"] <= 0:
        return None

    # Per-module, per-role, per-phase stats + energy
    # Structure: modules[idx][role][phase] = {"stator": stats, "supply": stats,
    #                                          "speed": stats, "energy_J": float}
    modules = {}
    for idx in MODULE_CAN_IDS:
        modules[idx] = {}
        for role in ROLES:
            base = _nt_base(idx, role)
            stator_pts = series.get(f"{base}/Stator Current", [])
            supply_pts = series.get(f"{base}/Supply Current", [])
            speed_pts  = series.get(f"{base}/Speed", [])
            volt_pts   = series.get(f"{base}/Out Volt", [])
            per_phase = {}
            for p in PHASES:
                ivs = phases[p]
                per_phase[p] = {
                    "stator":  time_weighted_abs_stats(stator_pts, ivs, t_end),
                    "supply":  time_weighted_abs_stats(supply_pts, ivs, t_end),
                    "speed":   time_weighted_abs_stats(speed_pts,  ivs, t_end),
                    "energy_J": energy_over_intervals(volt_pts, stator_pts,
                                                      ivs, t_end),
                }
            modules[idx][role] = per_phase

    result = {
        "log_path":   log_path,
        "t_end":      t_end,
        "phase_secs": phase_secs,
        "modules":    modules,
    }
    del series
    return result

# -- Report helpers -------------------------------------------------------------

def _fmt_abs(s, unit=""):
    if s is None:
        return "(no samples)"
    return (f"mean {s['mean_tw']:.1f}, p50 {s['p50']:.1f}, "
            f"p95 {s['p95']:.1f}, max {s['max']:.1f} {unit} (n={s['n']})")

def _fmt_short(s, unit=""):
    if s is None:
        return "-"
    return f"{s['mean_tw']:.1f}/{s['p95']:.1f}/{s['max']:.1f}{unit}"

def _role_phase_stats(modules, role, phase, key):
    """Return list of stat dicts for a given role+phase+metric across modules."""
    out = []
    for idx in sorted(modules):
        s = modules[idx][role][phase].get(key)
        if s is not None:
            out.append(s)
    return out

def _merge_abs_stats(stats_list):
    stats_list = [s for s in stats_list if s is not None]
    if not stats_list:
        return None
    total_n = sum(s["n"] for s in stats_list)
    if total_n == 0:
        return None
    return {
        "n":       total_n,
        "mean_tw": sum(s["mean_tw"] * s["n"] for s in stats_list) / total_n,
        "p50":     float(np.median([s["p50"] for s in stats_list])),
        "p95":     float(np.max([s["p95"] for s in stats_list])),
        "max":     float(np.max([s["max"] for s in stats_list])),
    }

def print_per_log_report(r):
    print()
    print(SEP)
    print(f"  LOG: {os.path.basename(r['log_path'])}")
    print(SEP)
    ps = r["phase_secs"]
    print(f"  Phase time: AUTO={ps['AUTO']:.1f}s, TELEOP={ps['TELEOP']:.1f}s, "
          f"COMBINED={ps['COMBINED']:.1f}s")

    for role in ROLES:
        print()
        print(f"  [{role} motors] by phase + module")
        print(f"    {'Mod':>3}  {'Phase':<8}  {'Stator (A)':<38}  "
              f"{'Supply (A)':<38}  {'|Speed|':<32}  {'Energy':>8}")
        print(f"    {'-'*3}  {'-'*8}  {'-'*38}  {'-'*38}  {'-'*32}  {'-'*8}")
        for idx in sorted(r["modules"]):
            for phase in ("AUTO", "TELEOP", "COMBINED"):
                m = r["modules"][idx][role][phase]
                print(f"    {idx:>3}  {phase:<8}  "
                      f"{_fmt_abs(m['stator']):<38}  "
                      f"{_fmt_abs(m['supply']):<38}  "
                      f"{_fmt_abs(m['speed']):<32}  "
                      f"{m['energy_J']:>6.0f} J")
            # blank line between modules for readability
            if idx != max(r["modules"]):
                print(f"    {'':<3}  {'':<8}  {'':<38}  {'':<38}  {'':<32}  {'':>8}")

    # Role totals per phase: sum energies + aggregate stats across the 4 modules
    print()
    print(f"  [Role totals per phase]")
    print(f"    {'Role':<8}  {'Phase':<8}  {'Stator (A) mean/p95/max':<28}  "
          f"{'Supply (A) mean/p95/max':<28}  {'Energy (kJ)':>11}")
    print(f"    {'-'*8}  {'-'*8}  {'-'*28}  {'-'*28}  {'-'*11}")
    for role in ROLES:
        for phase in PHASES:
            merged_st = _merge_abs_stats(_role_phase_stats(r["modules"], role, phase, "stator"))
            merged_su = _merge_abs_stats(_role_phase_stats(r["modules"], role, phase, "supply"))
            total_e = sum(r["modules"][idx][role][phase]["energy_J"]
                          for idx in r["modules"])
            print(f"    {role:<8}  {phase:<8}  "
                  f"{_fmt_short(merged_st, ' A'):<28}  "
                  f"{_fmt_short(merged_su, ' A'):<28}  "
                  f"{total_e / 1000:>9.2f}")

    # Drivetrain totals (all 8 motors) per phase
    print()
    print(f"  [Drivetrain totals — all 8 motors]")
    print(f"    {'Phase':<8}  {'Energy (kJ)':>11}  {'per sec':>8}")
    print(f"    {'-'*8}  {'-'*11}  {'-'*8}")
    for phase in PHASES:
        total_e = sum(r["modules"][idx][role][phase]["energy_J"]
                      for idx in r["modules"] for role in ROLES)
        secs = r["phase_secs"][phase]
        rate = total_e / secs if secs > 0 else 0
        print(f"    {phase:<8}  {total_e / 1000:>9.2f}  {rate:>6.1f} W")

# -- Combined analysis ----------------------------------------------------------

def print_combined_analysis(results):
    n_logs = len(results)
    print()
    print(SEP)
    print(f"  COMBINED DRIVETRAIN ANALYSIS ACROSS {n_logs} LOG{'S' if n_logs != 1 else ''}")
    print(SEP)

    total_secs = {p: sum(r["phase_secs"][p] for r in results) for p in PHASES}
    print(f"\n  Total time: AUTO={total_secs['AUTO']:.1f}s, "
          f"TELEOP={total_secs['TELEOP']:.1f}s, "
          f"COMBINED={total_secs['COMBINED']:.1f}s")

    # Per-module per-role per-phase totals (merge stats + sum energies)
    for role in ROLES:
        print()
        print(f"  [{role} motors] season totals by module + phase")
        print(f"    {'Mod':>3}  {'Phase':<8}  {'Stator (A) mean/p95/max':<28}  "
              f"{'Supply (A) mean/p95/max':<28}  {'|Speed| mean/p95/max':<28}  "
              f"{'Energy':>9}")
        print(f"    {'-'*3}  {'-'*8}  {'-'*28}  {'-'*28}  {'-'*28}  {'-'*9}")
        for idx in sorted(results[0]["modules"]):
            for phase in ("AUTO", "TELEOP", "COMBINED"):
                merged_st = _merge_abs_stats(
                    [r["modules"][idx][role][phase]["stator"] for r in results])
                merged_su = _merge_abs_stats(
                    [r["modules"][idx][role][phase]["supply"] for r in results])
                merged_sp = _merge_abs_stats(
                    [r["modules"][idx][role][phase]["speed"] for r in results])
                total_e = sum(r["modules"][idx][role][phase]["energy_J"]
                              for r in results)
                print(f"    {idx:>3}  {phase:<8}  "
                      f"{_fmt_short(merged_st, ' A'):<28}  "
                      f"{_fmt_short(merged_su, ' A'):<28}  "
                      f"{_fmt_short(merged_sp):<28}  "
                      f"{total_e / 1000:>7.2f} kJ")
            if idx != max(results[0]["modules"]):
                print(f"    {'':<3}")

    # Role totals across all modules, all matches, per phase
    print()
    print(f"  [Role totals — all modules, all matches, by phase]")
    print(f"    {'Role':<8}  {'Phase':<8}  {'Stator (A) mean/p95/max':<28}  "
          f"{'Supply (A) mean/p95/max':<28}  {'Energy':>9}  {'Per match':>10}")
    print(f"    {'-'*8}  {'-'*8}  {'-'*28}  {'-'*28}  {'-'*9}  {'-'*10}")
    for role in ROLES:
        for phase in PHASES:
            all_st = []
            all_su = []
            all_e  = 0.0
            for r in results:
                for idx in r["modules"]:
                    m = r["modules"][idx][role][phase]
                    if m["stator"] is not None: all_st.append(m["stator"])
                    if m["supply"] is not None: all_su.append(m["supply"])
                    all_e += m["energy_J"]
            merged_st = _merge_abs_stats(all_st)
            merged_su = _merge_abs_stats(all_su)
            print(f"    {role:<8}  {phase:<8}  "
                  f"{_fmt_short(merged_st, ' A'):<28}  "
                  f"{_fmt_short(merged_su, ' A'):<28}  "
                  f"{all_e / 1000:>7.2f} kJ  "
                  f"{(all_e / 1000) / n_logs:>8.2f} kJ")

    # Drivetrain grand total
    print()
    print(f"  [Drivetrain grand totals]")
    print(f"    {'Phase':<8}  {'Energy (kJ)':>12}  {'Per match (kJ)':>16}  "
          f"{'Avg power (W)':>15}")
    print(f"    {'-'*8}  {'-'*12}  {'-'*16}  {'-'*15}")
    for phase in PHASES:
        total_e = 0.0
        for r in results:
            for idx in r["modules"]:
                for role in ROLES:
                    total_e += r["modules"][idx][role][phase]["energy_J"]
        secs = total_secs[phase]
        avg_p = total_e / secs if secs > 0 else 0
        print(f"    {phase:<8}  {total_e / 1000:>10.2f}  "
              f"{(total_e / 1000) / n_logs:>14.2f}  {avg_p:>13.1f}")

    # AUTO vs TELEOP ratios — highlights how much harder we work in each mode
    print()
    print(f"  [AUTO vs TELEOP intensity — all 8 motors]")
    print(f"    {'Metric':<30}  {'AUTO':>10}  {'TELEOP':>10}  {'Ratio A/T':>10}")
    print(f"    {'-'*30}  {'-'*10}  {'-'*10}  {'-'*10}")

    def _agg(metric):
        """Return (auto_val, teleop_val) for a named aggregate metric."""
        vals = {"AUTO": [], "TELEOP": []}
        for phase in ("AUTO", "TELEOP"):
            for r in results:
                for idx in r["modules"]:
                    for role in ROLES:
                        m = r["modules"][idx][role][phase]
                        if metric == "stator_mean":
                            if m["stator"]:
                                vals[phase].append((m["stator"]["mean_tw"], m["stator"]["n"]))
                        elif metric == "stator_p95":
                            if m["stator"]:
                                vals[phase].append((m["stator"]["p95"], m["stator"]["n"]))
                        elif metric == "stator_max":
                            if m["stator"]:
                                vals[phase].append((m["stator"]["max"], 1))
                        elif metric == "speed_mean":
                            if m["speed"]:
                                vals[phase].append((m["speed"]["mean_tw"], m["speed"]["n"]))
        out = {}
        for p, pairs in vals.items():
            if metric == "stator_max":
                out[p] = max(v for v, _ in pairs) if pairs else 0.0
            else:
                tot_n = sum(n for _, n in pairs)
                out[p] = (sum(v * n for v, n in pairs) / tot_n) if tot_n else 0.0
        return out["AUTO"], out["TELEOP"]

    for label, metric, unit in (
        ("Mean stator current/motor", "stator_mean", "A"),
        ("p95 stator current/motor",  "stator_p95",  "A"),
        ("Peak stator current",       "stator_max",  "A"),
        ("Mean |speed|/motor",        "speed_mean",  ""),
    ):
        a, t = _agg(metric)
        ratio = (a / t) if t > 0 else float("inf")
        print(f"    {label:<30}  {a:>8.2f} {unit}  {t:>8.2f} {unit}  "
              f"{ratio:>10.2f}")

    # Energy ratio
    e_auto = sum(r["modules"][idx][role]["AUTO"]["energy_J"]
                 for r in results for idx in r["modules"] for role in ROLES)
    e_tele = sum(r["modules"][idx][role]["TELEOP"]["energy_J"]
                 for r in results for idx in r["modules"] for role in ROLES)
    t_auto = total_secs["AUTO"]
    t_tele = total_secs["TELEOP"]
    print(f"    {'Avg power (drivetrain)':<30}  "
          f"{(e_auto/t_auto if t_auto>0 else 0):>8.1f} W  "
          f"{(e_tele/t_tele if t_tele>0 else 0):>8.1f} W  "
          f"{((e_auto/t_auto) / (e_tele/t_tele)) if t_tele>0 and e_tele>0 else 0:>10.2f}")

    print()
    print(SEP)

# -- CLI / IO -------------------------------------------------------------------

def resolve_log_paths(args):
    if not args:
        return [DEFAULT_LOG]
    def walk_dir(d):
        found = []
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".wpilog"):
                    found.append(os.path.join(root, f))
        return sorted(found)
    paths = []
    for a in args:
        if os.path.isdir(a):
            paths.extend(walk_dir(a))
            continue
        hits = glob.glob(a) or [a]
        for h in hits:
            if os.path.isdir(h):
                paths.extend(walk_dir(h))
            elif os.path.isfile(h) and h.lower().endswith(".wpilog"):
                paths.append(h)
    seen, uniq = set(), []
    for p in paths:
        abs_p = os.path.abspath(p).replace("\\", "/")
        if abs_p not in seen:
            uniq.append(abs_p); seen.add(abs_p)
    return uniq

def parse_cli(argv):
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    summary_out = os.path.join(reports_dir, "drivetrain_summary.md")
    matches_out = os.path.join(reports_dir, "drivetrain_matches.md")
    write_file  = True
    workers     = None
    positional  = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-o", "--output", "--summary-out"):
            summary_out = argv[i + 1]; write_file = True; i += 2
        elif a == "--matches-out":
            matches_out = argv[i + 1]; write_file = True; i += 2
        elif a in ("-j", "--workers"):
            workers = max(1, int(argv[i + 1])); i += 2
        elif a == "--no-file":
            write_file = False; i += 1
        elif a == "--serial":
            workers = 1; i += 1
        else:
            positional.append(a); i += 1
    return positional, summary_out, matches_out, write_file, workers

def write_markdown_report(title, captured_text, out_path, paths, extra_note=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# {title}", "", f"_Generated: {now}_", "",
        f"## Logs analyzed ({len(paths)})", "",
    ]
    for p in paths:
        lines.append(f"- `{p}`")
    if extra_note:
        lines.extend(["", extra_note])
    lines.extend(["", "## Analysis output", "", "```", captured_text.rstrip(), "```", ""])
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def _worker(idx_path):
    import gc
    idx, p = idx_path
    t0 = time.time()
    r = analyze_log(p)
    gc.collect()
    return (idx, p, r, time.time() - t0)

def _make_pool(workers):
    kwargs = {"max_workers": workers}
    if sys.version_info >= (3, 11):
        kwargs["max_tasks_per_child"] = 1
    return concurrent.futures.ProcessPoolExecutor(**kwargs)

def load_all(paths, workers):
    n = len(paths)
    if workers is None:
        workers = min(os.cpu_count() or 4, n)
    workers = max(1, min(workers, n))
    results_by_idx = {}
    failed = []
    if workers == 1:
        progress("Loading logs serially ...")
        for i, p in enumerate(paths):
            t0 = time.time()
            progress(f"[{i+1}/{n}] {os.path.basename(p)} ...")
            r = analyze_log(p)
            dt = time.time() - t0
            if r is None:
                failed.append(p); continue
            results_by_idx[i] = r
            progress(f"  done in {dt:.1f}s")
        return [results_by_idx[i] for i in range(n) if i in results_by_idx], failed
    progress(f"Loading {n} logs in parallel ({workers} workers) ...")
    done = 0
    ex = _make_pool(workers)
    futures = {}
    try:
        futures = {ex.submit(_worker, (i, p)): i for i, p in enumerate(paths)}
        for fut in concurrent.futures.as_completed(futures):
            idx, p, r, dt = fut.result()
            done += 1
            if r is None:
                progress(f"[{done}/{n}] {os.path.basename(p)} FAILED after {dt:.1f}s")
                failed.append(p); continue
            results_by_idx[idx] = r
            progress(f"[{done}/{n}] {os.path.basename(p)} — {dt:.1f}s")
    except KeyboardInterrupt:
        progress("Interrupted — cancelling remaining workers ...")
        for f in futures: f.cancel()
        ex.shutdown(wait=True, cancel_futures=True)
        raise
    finally:
        ex.shutdown(wait=True, cancel_futures=True)
    return [results_by_idx[i] for i in range(n) if i in results_by_idx], failed

def main():
    t_overall = time.time()
    positional, summary_out, matches_out, write_file, workers = parse_cli(sys.argv[1:])
    paths = resolve_log_paths(positional)
    if not paths:
        sys.stderr.write("ERROR: no log files found.\n")
        sys.exit(1)
    progress(f"Found {len(paths)} log{'s' if len(paths) != 1 else ''} to analyze")
    results, failed = load_all(paths, workers)
    progress(f"Loaded logs ({len(results)} ok, {len(failed)} failed)")

    matches_buf = io.StringIO()
    summary_buf = io.StringIO()
    with contextlib.redirect_stdout(matches_buf):
        print(f"Analyzing {len(paths)} log{'s' if len(paths) != 1 else ''}:")
        for p in paths:
            print(f"  - {p}")
        for p in failed:
            print(f"\nWARNING: no drivetrain data in {p}.")
        for r in results:
            print_per_log_report(r)
    if results:
        with contextlib.redirect_stdout(summary_buf):
            print_combined_analysis(results)
    sys.stdout.write(matches_buf.getvalue())
    sys.stdout.write(summary_buf.getvalue())
    sys.stdout.flush()
    if write_file:
        progress(f"Writing per-match report to {matches_out} ...")
        write_markdown_report("Drivetrain Analysis — Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Drivetrain Analysis — Season Summary",
                              summary_buf.getvalue(), summary_out, paths,
                              extra_note="Per-match breakdowns are in the companion matches file.")
        sys.stdout.write(
            f"\nMarkdown reports written to:\n"
            f"  summary : {summary_out}\n"
            f"  matches : {matches_out}\n"
        )
    progress(f"Done. Total elapsed: {time.time() - t_overall:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\nAborted by user.\n")
        sys.exit(130)

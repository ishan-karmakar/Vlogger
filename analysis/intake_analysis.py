# -*- coding: utf-8 -*-
"""
Intake energy & performance analysis for FRC Team Valor 6800.

Two motors : Left Intake Motor, Right Intake Motor
Cycle model: Intake State transitions (OFF <-> INTAKING <-> SHOOTING)
Power      : |Out Volt| x |Stator Current| per motor, summed

Usage:
    python intake_analysis.py                          # default log
    python intake_analysis.py logs/                    # directory (recursive)
    python intake_analysis.py logs/*.wpilog            # glob
    python intake_analysis.py -j 8 logs/               # 8 workers
    python intake_analysis.py --no-file logs/          # terminal only
"""

import sys
import os
import glob
import io
import time
import datetime
import contextlib
import concurrent.futures
import shutil
from pathlib import Path
import numpy as np
from collections import defaultdict, Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import vlogger

# -- Configuration ---------------------------------------------------------------

DEFAULT_LOG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "logs", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")

INTAKE_REGEX = r"NT:/SmartDashboard/Intake/(Intake State|Intake Jam|(Left|Right) Intake Motor/(Speed|Stator Current|Supply Current|Out Volt|reqSpeed))"

L_SPEED    = "NT:/SmartDashboard/Intake/Left Intake Motor/Speed"
L_STATOR   = "NT:/SmartDashboard/Intake/Left Intake Motor/Stator Current"
L_SUPPLY   = "NT:/SmartDashboard/Intake/Left Intake Motor/Supply Current"
L_VOLTAGE  = "NT:/SmartDashboard/Intake/Left Intake Motor/Out Volt"
L_REQSPEED = "NT:/SmartDashboard/Intake/Left Intake Motor/reqSpeed"
R_SPEED    = "NT:/SmartDashboard/Intake/Right Intake Motor/Speed"
R_STATOR   = "NT:/SmartDashboard/Intake/Right Intake Motor/Stator Current"
R_SUPPLY   = "NT:/SmartDashboard/Intake/Right Intake Motor/Supply Current"
R_VOLTAGE  = "NT:/SmartDashboard/Intake/Right Intake Motor/Out Volt"
R_REQSPEED = "NT:/SmartDashboard/Intake/Right Intake Motor/reqSpeed"
STATE_PATH = "NT:/SmartDashboard/Intake/Intake State"
JAM_PATH   = "NT:/SmartDashboard/Intake/Intake Jam"

# Hoot CAN-ID mapping for the 2 intake motors. Both live on the **rio** bus
# (TalonFX-12 and TalonFX-13), unlike drivetrain/flywheel which are on canivore.
CAN_INTAKE = (
    ("Left",  12),
    ("Right", 13),
)
HOOT_DRIVETRAIN_SIGNALS = ("DeviceTemp", "SupplyCurrent", "TorqueCurrent")
HOOT_REGEX = (
    r"Phoenix6/TalonFX-(?:12|13)/(?:" + "|".join(HOOT_DRIVETRAIN_SIGNALS) + r")"
)

AT_SPEED_FRACTION = 0.80    # "reached commanded speed" threshold
MIN_CYCLE_SECS    = 0.10    # ignore INTAKING blips shorter than this
STALL_FRACTION    = 0.30    # below this fraction of reqSpeed -> stalled / jammed
MIN_REQ_SPEED     = 1.0

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading ----------------------------------------------------------------

def _find_owlet():
    """Locate CTRE's owlet — first PATH, then `<repo_root>/tools/`. None if missing."""
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


def _find_paired_hoots(wpilog_path):
    """Return rio-bus *.hoot files near a .wpilog (intake motors live on rio).

    Heuristic: walk the wpilog's parent dir + 1-level subdirs; keep ONLY files
    with `_rio_` in name (canivore-bus hoots don't have intake motors 12/13).
    """
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
            if "_rio_" not in f.name.lower():
                continue
            hoots.append(str(f))
    return sorted(set(hoots))


def _load_into_raw(raw, src):
    """Iterate a vlogger source and append entries into the shared raw dict."""
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


def load_series(log_path):
    """Load WPI series + (optionally) any paired-hoot motor signals.

    Returns (series_dict, hoot_files_used). Hoot pairing is best-effort — if
    owlet is missing or no paired files exist, hoot_files_used is empty.
    """
    raw = defaultdict(list)

    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, INTAKE_REGEX)
    _load_into_raw(raw, src)

    hoot_files_used = []
    if log_path.lower().endswith(".wpilog"):
        owlet = _find_owlet()
        if owlet:
            for hpath in _find_paired_hoots(log_path):
                try:
                    hsrc = vlogger.get_source(f"hoot:///{hpath}", HOOT_REGEX, owlet=owlet)
                    _load_into_raw(raw, hsrc)
                    hoot_files_used.append(hpath)
                except Exception as e:                          # noqa: BLE001
                    sys.stderr.write(f"[hoot] couldn't open {hpath}: {e}\n")

    for name in raw:
        raw[name].sort(key=lambda x: x[0])
    return dict(raw), hoot_files_used


def _hoot_motor_stats(series, canid):
    """Per-TalonFX peak/mean stats from the paired hoot. None if no hoot data."""
    prefix = f"Phoenix6/TalonFX-{canid}"
    _, temp = to_np(series, f"{prefix}/DeviceTemp")
    _, supc = to_np(series, f"{prefix}/SupplyCurrent")
    _, tqc  = to_np(series, f"{prefix}/TorqueCurrent")
    if temp is None and supc is None and tqc is None:
        return None
    return {
        "peak_temp_c":      float(np.max(temp))         if temp is not None else None,
        "mean_temp_c":      float(np.mean(temp))        if temp is not None else None,
        "peak_supply_curr": float(np.max(np.abs(supc))) if supc is not None else None,
        "mean_supply_curr": float(np.mean(np.abs(supc))) if supc is not None else None,
        "peak_torque_curr": float(np.max(np.abs(tqc)))  if tqc  is not None else None,
    }

# -- Helpers ---------------------------------------------------------------------

def to_np(series, name):
    pts = series.get(name)
    if not pts or not isinstance(pts[0][1], (float, int)):
        return None, None
    return np.array([p[0] for p in pts]), np.array([float(p[1]) for p in pts])

def interp_at(ts_target, ts_src, vals_src):
    if ts_src is None or len(ts_src) < 2:
        return np.zeros_like(ts_target, dtype=float)
    return np.interp(ts_target, ts_src, vals_src,
                     left=vals_src[0], right=vals_src[-1])

def energy_in_window(ts_grid, power, t_start, t_end):
    mask = (ts_grid >= t_start) & (ts_grid <= t_end)
    if mask.sum() < 2:
        return 0.0
    return float(np.trapezoid(power[mask], ts_grid[mask]))

def mean_in_window(ts_grid, signal, t_start, t_end):
    mask = (ts_grid >= t_start) & (ts_grid <= t_end)
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(signal[mask]))

def peak_in_window(ts_grid, signal, t_start, t_end):
    mask = (ts_grid >= t_start) & (ts_grid <= t_end)
    if mask.sum() == 0:
        return 0.0
    return float(np.max(signal[mask]))

# -- State-based cycle detection -------------------------------------------------

def find_state_windows(state_pts, target_state):
    """Find contiguous windows where state == target_state."""
    windows = []
    in_win  = False
    t_start = None
    for ts, val in state_pts:
        if not in_win and val == target_state:
            in_win  = True
            t_start = ts
        elif in_win and val != target_state:
            in_win = False
            if ts - t_start >= MIN_CYCLE_SECS:
                windows.append((t_start, ts))
            t_start = None
    if in_win and t_start is not None:
        windows.append((t_start, state_pts[-1][0]))
    return windows

def count_jams_in_window(jam_pts, t_start, t_end):
    """Count rising edges of the jam signal within the window."""
    count    = 0
    prev_val = None
    for ts, val in jam_pts:
        if ts < t_start:
            prev_val = bool(val)
            continue
        if ts > t_end:
            break
        v = bool(val)
        if prev_val is not None and (not prev_val) and v:
            count += 1
        prev_val = v
    return count

# -- Per-log analysis ------------------------------------------------------------

def analyze_log(log_path):
    """Run per-log intake analysis and return a result dict, or None if required signals missing."""
    series, hoot_files_used = load_series(log_path)

    ts_ls,  l_speed    = to_np(series, L_SPEED)
    ts_lsc, l_stator   = to_np(series, L_STATOR)
    ts_lsp, l_supply   = to_np(series, L_SUPPLY)
    ts_lv,  l_voltage  = to_np(series, L_VOLTAGE)
    ts_lq,  l_req      = to_np(series, L_REQSPEED)
    ts_rs,  r_speed    = to_np(series, R_SPEED)
    ts_rsc, r_stator   = to_np(series, R_STATOR)
    ts_rsp, r_supply   = to_np(series, R_SUPPLY)
    ts_rv,  r_voltage  = to_np(series, R_VOLTAGE)
    ts_rq,  r_req      = to_np(series, R_REQSPEED)
    state_pts          = series.get(STATE_PATH, [])
    jam_pts            = series.get(JAM_PATH, [])

    if ts_ls is None or ts_rs is None or not state_pts:
        return None

    # -- Common time grid from all speed channels
    ts_grid = np.unique(np.concatenate([ts_ls, ts_rs]))

    ls_g    = interp_at(ts_grid, ts_ls,  l_speed)
    lsc_g   = interp_at(ts_grid, ts_lsc, l_stator)  if ts_lsc is not None else np.zeros_like(ts_grid)
    lsp_g   = interp_at(ts_grid, ts_lsp, l_supply)  if ts_lsp is not None else np.zeros_like(ts_grid)
    lv_g    = interp_at(ts_grid, ts_lv,  l_voltage) if ts_lv  is not None else np.zeros_like(ts_grid)
    lq_g    = interp_at(ts_grid, ts_lq,  l_req)     if ts_lq  is not None else np.zeros_like(ts_grid)
    rs_g    = interp_at(ts_grid, ts_rs,  r_speed)
    rsc_g   = interp_at(ts_grid, ts_rsc, r_stator)  if ts_rsc is not None else np.zeros_like(ts_grid)
    rsp_g   = interp_at(ts_grid, ts_rsp, r_supply)  if ts_rsp is not None else np.zeros_like(ts_grid)
    rv_g    = interp_at(ts_grid, ts_rv,  r_voltage) if ts_rv  is not None else np.zeros_like(ts_grid)
    rq_g    = interp_at(ts_grid, ts_rq,  r_req)     if ts_rq  is not None else np.zeros_like(ts_grid)

    # Power per motor = |V| * |I_stator|, then sum
    power_L   = np.abs(lv_g) * np.abs(lsc_g)
    power_R   = np.abs(rv_g) * np.abs(rsc_g)
    power_tot = power_L + power_R

    stator_tot = np.abs(lsc_g) + np.abs(rsc_g)
    supply_tot = np.abs(lsp_g) + np.abs(rsp_g)

    t0 = ts_grid[0]

    # -- Session totals
    session_len    = float(ts_grid[-1] - t0)
    total_energy_J = float(np.trapezoid(power_tot, ts_grid))
    max_speed_L    = float(np.max(np.abs(ls_g)))
    max_speed_R    = float(np.max(np.abs(rs_g)))

    # -- State distribution (time in each state)
    state_time = Counter()
    for i in range(len(state_pts) - 1):
        ts, val = state_pts[i]
        nxt     = state_pts[i + 1][0]
        state_time[val] += (nxt - ts)
    if state_pts:
        last_ts, last_val = state_pts[-1]
        state_time[last_val] += max(0.0, ts_grid[-1] - last_ts)

    # -- INTAKING / SHOOTING windows
    intaking_windows = find_state_windows(state_pts, "INTAKING")
    shooting_windows = find_state_windows(state_pts, "SHOOTING")

    cycles = []
    for t_start, t_end in intaking_windows:
        dur     = t_end - t_start
        E_cyc   = energy_in_window(ts_grid, power_tot, t_start, t_end)
        I_stat_avg = mean_in_window(ts_grid, stator_tot, t_start, t_end)
        I_stat_pk  = peak_in_window(ts_grid, stator_tot, t_start, t_end)
        I_sup_avg  = mean_in_window(ts_grid, supply_tot, t_start, t_end)
        I_sup_pk   = peak_in_window(ts_grid, supply_tot, t_start, t_end)

        # Did motors actually reach target speed?
        mask = (ts_grid >= t_start) & (ts_grid <= t_end)
        if mask.sum() > 1:
            req_median = float(np.median(lq_g[mask][lq_g[mask] > 0])) if np.any(lq_g[mask] > 0) else 0.0
            actual_L_avg = float(np.mean(np.abs(ls_g[mask])))
            actual_R_avg = float(np.mean(np.abs(rs_g[mask])))
            reached = (req_median > 0 and
                       actual_L_avg >= AT_SPEED_FRACTION * abs(req_median) and
                       actual_R_avg >= AT_SPEED_FRACTION * abs(req_median))
            stalled = (req_median > 0 and
                       (actual_L_avg < STALL_FRACTION * abs(req_median) or
                        actual_R_avg < STALL_FRACTION * abs(req_median)))
        else:
            req_median = 0.0
            actual_L_avg = 0.0
            actual_R_avg = 0.0
            reached = False
            stalled = False

        jam_count = count_jams_in_window(jam_pts, t_start, t_end)

        cycles.append({
            "t_start":    t_start,
            "t_end":      t_end,
            "dur":        dur,
            "req_rps":    req_median,
            "act_L":      actual_L_avg,
            "act_R":      actual_R_avg,
            "E_J":        E_cyc,
            "I_stat_avg": I_stat_avg,
            "I_stat_pk":  I_stat_pk,
            "I_sup_avg":  I_sup_avg,
            "I_sup_pk":   I_sup_pk,
            "reached":    reached,
            "stalled":    stalled,
            "jams":       jam_count,
        })

    # -- SHOOTING windows: per-window data
    shooting_cycles = []
    for t_start, t_end in shooting_windows:
        shooting_cycles.append({
            "t_start":    t_start,
            "t_end":      t_end,
            "dur":        t_end - t_start,
            "E_J":        energy_in_window(ts_grid, power_tot, t_start, t_end),
            "I_stat_avg": mean_in_window(ts_grid, stator_tot, t_start, t_end),
        })

    # -- Total jam events (rising edges across whole log) + jam time
    total_jams = 0
    jam_time   = 0.0
    jam_edges  = []
    prev_ts    = None
    prev_val   = None
    for ts, val in jam_pts:
        v = bool(val)
        if prev_val is True and prev_ts is not None:
            jam_time += (ts - prev_ts)
        if prev_val is not True and v:
            jam_edges.append(ts)
            total_jams += 1
        prev_ts  = ts
        prev_val = v

    jam_events = []
    for t_jam in jam_edges:
        cyc_idx = next((i + 1 for i, c in enumerate(cycles)
                        if c["t_start"] <= t_jam <= c["t_end"]), None)
        st = next((v for (ts, v) in reversed(state_pts) if ts <= t_jam), "?")
        jam_events.append({"time": t_jam, "cycle_idx": cyc_idx, "state": st})

    # -- Current draw summary table rows
    current_stats = [
        {"label": "Left  stator",    "mean": float(np.mean(np.abs(lsc_g))), "peak": float(np.max(np.abs(lsc_g)))},
        {"label": "Right stator",    "mean": float(np.mean(np.abs(rsc_g))), "peak": float(np.max(np.abs(rsc_g)))},
        {"label": "Combined stator", "mean": float(np.mean(stator_tot)),    "peak": float(np.max(stator_tot))},
        {"label": "Left  supply",    "mean": float(np.mean(np.abs(lsp_g))), "peak": float(np.max(np.abs(lsp_g)))},
        {"label": "Right supply",    "mean": float(np.mean(np.abs(rsp_g))), "peak": float(np.max(np.abs(rsp_g)))},
        {"label": "Combined supply", "mean": float(np.mean(supply_tot)),    "peak": float(np.max(supply_tot))},
    ]

    # Hoot per-motor telemetry. Each entry is None when no hoot data was paired.
    hoot_motors = [
        {"label": label, "can_id": cid, "stats": _hoot_motor_stats(series, cid)}
        for (label, cid) in CAN_INTAKE
    ]
    hoot_temps = [m["stats"]["peak_temp_c"] for m in hoot_motors
                  if m["stats"] and m["stats"].get("peak_temp_c") is not None]
    max_motor_temp_c = max(hoot_temps) if hoot_temps else None

    return {
        "log_path":        log_path,
        "session_len":     session_len,
        "max_speed_L":     max_speed_L,
        "max_speed_R":     max_speed_R,
        "total_energy_J":  total_energy_J,
        "total_jams":      total_jams,
        "jam_time":        jam_time,
        "n_intaking":      len(intaking_windows),
        "n_shooting":      len(shooting_windows),
        "state_time":      dict(state_time),
        "current_stats":   current_stats,
        "cycles":          cycles,
        "shooting_cycles": shooting_cycles,
        "jam_events":      jam_events,
        "hoot_motors":      hoot_motors,
        "hoot_files_used":  hoot_files_used,
        "max_motor_temp_c": max_motor_temp_c,
    }

# -- Per-log report --------------------------------------------------------------

def print_per_log_report(r):
    log_name = os.path.basename(r["log_path"])
    session_len = r["session_len"]
    cycles      = r["cycles"]
    state_time  = r["state_time"]

    print()
    print(SEP)
    print(f"  INTAKE ANALYSIS  --  {log_name}")
    print(SEP)
    print(f"\n  Log duration            : {session_len:.1f} s  ({session_len/60:.2f} min)")
    print(f"  Peak speed (Left/Right) : {r['max_speed_L']:.1f} / {r['max_speed_R']:.1f} RPS")
    print(f"  Total intake energy     : {r['total_energy_J']/1000:.2f} kJ")
    print(f"  Total jam events        : {r['total_jams']}  (rising edges of Intake Jam)")
    print(f"  INTAKING cycles         : {r['n_intaking']}")
    print(f"  SHOOTING cycles         : {r['n_shooting']}")
    if r.get("max_motor_temp_c") is not None:
        print(f"  Peak motor temp         : {r['max_motor_temp_c']:.1f} °C  "
              f"(across both intake motors, from hoot)")
    if r.get("hoot_files_used"):
        print(f"  Hoot data merged from   : {len(r['hoot_files_used'])} file(s)")
        for hp in r["hoot_files_used"]:
            print(f"      - {os.path.basename(hp)}")

    # -- Per-motor hoot telemetry (only when hoot data is present)
    if any(m["stats"] for m in r.get("hoot_motors", [])):
        print()
        print(f"  Per-motor telemetry (from hoot):")
        print(f"  {'Motor':<8}  {'CAN':>3}  {'°C pk':>6}  {'°C avg':>7}  "
              f"{'I_sup pk':>9}  {'I_torq pk':>10}")
        print(f"  {'-'*8}  {'-'*3}  {'-'*6}  {'-'*7}  "
              f"{'-'*9}  {'-'*10}")
        def _f(d, k, fmt):
            v = d.get(k) if d else None
            return fmt.format(v) if v is not None else "  -- "
        for m in r["hoot_motors"]:
            s = m["stats"]
            print(f"  {m['label']:<8}  {m['can_id']:>3}  "
                  f"{_f(s, 'peak_temp_c',      '{:>4.1f}°'):>6}  "
                  f"{_f(s, 'mean_temp_c',      '{:>5.1f}°'):>7}  "
                  f"{_f(s, 'peak_supply_curr', '{:>7.1f}A'):>9}  "
                  f"{_f(s, 'peak_torque_curr', '{:>8.1f}A'):>10}")

    # -- Time distribution in each state
    print()
    print(f"  Time in each Intake State:")
    print(f"  {'State':>12}  {'Time (s)':>10}  {'% of log':>8}")
    print(f"  {'-'*12}  {'-'*10}  {'-'*8}")
    for st in ("OFF", "INTAKING", "SHOOTING"):
        t = state_time.get(st, 0.0)
        pct = (100 * t / session_len) if session_len > 0 else 0.0
        print(f"  {st:>12}  {t:>10.1f}  {pct:>7.1f}%")

    # -- Overall current draw
    print()
    print(f"  {'Current draw':35s}  {'Mean (A)':>9}  {'Peak (A)':>9}")
    print(f"  {'-'*35}  {'-'*9}  {'-'*9}")
    for row in r["current_stats"]:
        print(f"  {row['label']:35s}  {row['mean']:>9.1f}  {row['peak']:>9.1f}")

    # -- Per-cycle INTAKING table
    print()
    print(f"  INTAKING cycles (state=INTAKING):")
    print()
    print(f"  {'#':>2}  {'Start':>7}  {'End':>7}  {'Dur':>5}  "
          f"{'Req':>5}  {'ActL':>5}  {'ActR':>5}  {'OK?':>4}  "
          f"{'Is_avg':>7}  {'Is_pk':>6}  {'Ip_avg':>7}  {'Ip_pk':>6}  "
          f"{'E (J)':>6}  {'Jam':>3}")
    print(f"  {'-'*2}  {'-'*7}  {'-'*7}  {'-'*5}  "
          f"{'-'*5}  {'-'*5}  {'-'*5}  {'-'*4}  "
          f"{'-'*7}  {'-'*6}  {'-'*7}  {'-'*6}  "
          f"{'-'*6}  {'-'*3}")

    for i, c in enumerate(cycles):
        if c["stalled"]:
            ok = "STAL"
        elif c["reached"]:
            ok = "YES"
        elif c["req_rps"] == 0:
            ok = "n/a"
        else:
            ok = "no"
        print(f"  {i+1:>2}  {c['t_start']:>7.1f}  {c['t_end']:>7.1f}  "
              f"{c['dur']:>4.2f}s  "
              f"{c['req_rps']:>5.1f}  {c['act_L']:>5.1f}  {c['act_R']:>5.1f}  {ok:>4}  "
              f"{c['I_stat_avg']:>7.1f}  {c['I_stat_pk']:>6.1f}  "
              f"{c['I_sup_avg']:>7.1f}  {c['I_sup_pk']:>6.1f}  "
              f"{c['E_J']:>6.1f}  {c['jams']:>3d}")

    # -- Aggregated cycle stats
    print()
    if cycles:
        dur_arr   = np.array([c["dur"] for c in cycles])
        E_arr     = np.array([c["E_J"] for c in cycles])
        Istat_avg = np.array([c["I_stat_avg"] for c in cycles])
        Istat_pk  = np.array([c["I_stat_pk"]  for c in cycles])
        Isup_avg  = np.array([c["I_sup_avg"]  for c in cycles])
        Isup_pk   = np.array([c["I_sup_pk"]   for c in cycles])
        n_reached = sum(1 for c in cycles if c["reached"])
        n_stalled = sum(1 for c in cycles if c["stalled"])
        n_jammed  = sum(1 for c in cycles if c["jams"] > 0)

        print(f"  Cycles reaching {int(AT_SPEED_FRACTION*100)}% of reqSpeed: {n_reached} / {len(cycles)}")
        print(f"  Cycles with stall (<{int(STALL_FRACTION*100)}% reqSpeed): {n_stalled}")
        print(f"  Cycles with at least one jam event: {n_jammed}")
        print()
        print(f"  Avg INTAKING duration  : {np.mean(dur_arr):.2f} s  "
              f"(min {np.min(dur_arr):.2f}, max {np.max(dur_arr):.2f})")
        print(f"  Avg energy per intake  : {np.mean(E_arr):.1f} J  "
              f"(min {np.min(E_arr):.1f}, max {np.max(E_arr):.1f})")
        print(f"  Avg stator current     : {np.mean(Istat_avg):.1f} A  "
              f"(peak up to {np.max(Istat_pk):.1f} A)")
        print(f"  Avg supply current     : {np.mean(Isup_avg):.1f} A  "
              f"(peak up to {np.max(Isup_pk):.1f} A)")

    # -- Jam analysis
    print()
    print(SEP)
    print("  JAM ANALYSIS")
    print(SEP)

    jam_events = r["jam_events"]
    jam_time   = r["jam_time"]
    if jam_events or jam_time > 0:
        pct = (100 * jam_time / session_len) if session_len > 0 else 0.0
        print(f"\n  Total jam events (rising edges): {len(jam_events)}")
        print(f"  Total time in jammed state     : {jam_time:.1f} s  ({pct:.1f}% of log)")
        if jam_events:
            print(f"  Jam events (timestamp / intake cycle #):")
            print(f"  {'Time (s)':>9}  {'During Cycle':>13}  {'State at t':>11}")
            print(f"  {'-'*9}  {'-'*13}  {'-'*11}")
            for ev in jam_events:
                cyc_str = f"#{ev['cycle_idx']}" if ev["cycle_idx"] else "-"
                print(f"  {ev['time']:>9.2f}  {cyc_str:>13}  {ev['state']:>11}")
    else:
        print("\n  No Intake Jam data found.")

    # -- SHOOTING state analysis
    print()
    print(SEP)
    print("  SHOOTING STATE (feeder running into flywheel)")
    print(SEP)

    shooting_cycles = r["shooting_cycles"]
    if shooting_cycles:
        shoot_dur = np.array([s["dur"]        for s in shooting_cycles])
        shoot_E   = np.array([s["E_J"]        for s in shooting_cycles])
        shoot_I   = np.array([s["I_stat_avg"] for s in shooting_cycles])

        print(f"\n  SHOOTING windows     : {len(shooting_cycles)}")
        print(f"  Avg duration         : {np.mean(shoot_dur):.2f} s  "
              f"(min {np.min(shoot_dur):.2f}, max {np.max(shoot_dur):.2f})")
        print(f"  Avg energy (intake)  : {np.mean(shoot_E):.1f} J  "
              f"(min {np.min(shoot_E):.1f}, max {np.max(shoot_E):.1f})")
        print(f"  Avg stator current   : {np.mean(shoot_I):.1f} A")
    else:
        print("\n  No SHOOTING windows in this log.")

    print()
    print(SEP)

# -- Combined / season report ----------------------------------------------------

def print_combined_analysis(results):
    n_matches = len(results)
    if n_matches == 0:
        return

    print()
    print(SEP)
    print(f"  INTAKE ANALYSIS  --  SEASON SUMMARY  ({n_matches} match{'es' if n_matches != 1 else ''})")
    print(SEP)

    # -- Per-match summary table
    print()
    print(f"  {'#':>2}  {'Match':<38}  {'Dur(s)':>7}  {'Intk':>4}  {'Shot':>4}  {'Jams':>4}  {'kJ':>6}")
    print(f"  {'-'*2}  {'-'*38}  {'-'*7}  {'-'*4}  {'-'*4}  {'-'*4}  {'-'*6}")
    for i, r in enumerate(results):
        name = os.path.basename(r["log_path"])
        if len(name) > 38:
            name = name[:35] + "..."
        print(f"  {i+1:>2}  {name:<38}  {r['session_len']:>7.1f}  "
              f"{r['n_intaking']:>4d}  {r['n_shooting']:>4d}  "
              f"{r['total_jams']:>4d}  {r['total_energy_J']/1000:>6.2f}")

    # -- Aggregate cycle-level stats
    all_cycles = [c for r in results for c in r["cycles"]]
    all_shoots = [s for r in results for s in r["shooting_cycles"]]
    total_intaking = sum(r["n_intaking"] for r in results)
    total_shooting = sum(r["n_shooting"] for r in results)
    total_jams     = sum(r["total_jams"] for r in results)
    total_energy_J = sum(r["total_energy_J"] for r in results)
    total_session  = sum(r["session_len"] for r in results)

    print()
    print(f"  Totals across all matches:")
    print(f"    INTAKING cycles      : {total_intaking}")
    print(f"    SHOOTING cycles      : {total_shooting}")
    print(f"    Jam events           : {total_jams}")
    print(f"    Intake energy        : {total_energy_J/1000:.2f} kJ")
    print(f"    Combined log time    : {total_session:.1f} s  ({total_session/60:.2f} min)")

    print()
    print(f"  Per-match averages:")
    print(f"    INTAKING cycles/match: {total_intaking / n_matches:.1f}")
    print(f"    SHOOTING cycles/match: {total_shooting / n_matches:.1f}")
    print(f"    Jams/match           : {total_jams / n_matches:.2f}")
    print(f"    Intake energy/match  : {(total_energy_J / n_matches) / 1000:.2f} kJ")

    # -- Cycle-level stats across season
    if all_cycles:
        dur_arr   = np.array([c["dur"]        for c in all_cycles])
        E_arr     = np.array([c["E_J"]        for c in all_cycles])
        Istat_avg = np.array([c["I_stat_avg"] for c in all_cycles])
        Istat_pk  = np.array([c["I_stat_pk"]  for c in all_cycles])
        Isup_avg  = np.array([c["I_sup_avg"]  for c in all_cycles])
        n_reached = sum(1 for c in all_cycles if c["reached"])
        n_stalled = sum(1 for c in all_cycles if c["stalled"])
        n_jammed  = sum(1 for c in all_cycles if c["jams"] > 0)

        print()
        print(f"  INTAKING cycle stats ({len(all_cycles)} cycles total):")
        print(f"    Reached {int(AT_SPEED_FRACTION*100)}% of reqSpeed : {n_reached} / {len(all_cycles)}  "
              f"({100*n_reached/len(all_cycles):.1f}%)")
        print(f"    Stalled (<{int(STALL_FRACTION*100)}% reqSpeed) : {n_stalled}  "
              f"({100*n_stalled/len(all_cycles):.1f}%)")
        print(f"    Cycles with jam event       : {n_jammed}  "
              f"({100*n_jammed/len(all_cycles):.1f}%)")
        print()
        print(f"    Avg duration         : {np.mean(dur_arr):.2f} s  "
              f"(min {np.min(dur_arr):.2f}, max {np.max(dur_arr):.2f})")
        print(f"    Avg energy / cycle   : {np.mean(E_arr):.1f} J  "
              f"(min {np.min(E_arr):.1f}, max {np.max(E_arr):.1f})")
        print(f"    Avg stator current   : {np.mean(Istat_avg):.1f} A  "
              f"(peak up to {np.max(Istat_pk):.1f} A)")
        print(f"    Avg supply current   : {np.mean(Isup_avg):.1f} A")

    # -- SHOOTING state aggregate
    if all_shoots:
        sdur = np.array([s["dur"] for s in all_shoots])
        sE   = np.array([s["E_J"] for s in all_shoots])
        sI   = np.array([s["I_stat_avg"] for s in all_shoots])
        print()
        print(f"  SHOOTING window stats ({len(all_shoots)} windows total):")
        print(f"    Avg duration         : {np.mean(sdur):.2f} s")
        print(f"    Avg energy (intake)  : {np.mean(sE):.1f} J")
        print(f"    Avg stator current   : {np.mean(sI):.1f} A")

    # -- State-time distribution averaged across matches
    state_totals = Counter()
    for r in results:
        for st, t in r["state_time"].items():
            state_totals[st] += t
    print()
    print(f"  Time distribution across all matches:")
    print(f"    {'State':>12}  {'Total (s)':>10}  {'% of all logs':>14}")
    print(f"    {'-'*12}  {'-'*10}  {'-'*14}")
    for st in ("OFF", "INTAKING", "SHOOTING"):
        t = state_totals.get(st, 0.0)
        pct = (100 * t / total_session) if total_session > 0 else 0.0
        print(f"    {st:>12}  {t:>10.1f}  {pct:>13.1f}%")

    print()
    print(SEP)

# -- CLI / parallel infrastructure -----------------------------------------------

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
            uniq.append(abs_p)
            seen.add(abs_p)
    return uniq

def parse_cli(argv):
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    summary_out = os.path.join(reports_dir, "intake_summary.md")
    matches_out = os.path.join(reports_dir, "intake_matches.md")
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
        f"# {title}",
        "",
        f"_Generated: {now}_",
        "",
        f"## Logs analyzed ({len(paths)})",
        "",
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
    r  = analyze_log(p)
    gc.collect()
    return (idx, p, r, time.time() - t0)

def _make_pool(workers):
    """Recycle workers after each task to bound peak memory (see flywheel script)."""
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
            progress(f"[{done}/{n}] {os.path.basename(p)} - {dt:.1f}s")
    except KeyboardInterrupt:
        progress("Interrupted - cancelling remaining workers ...")
        for f in futures:
            f.cancel()
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
            print(f"\nWARNING: required intake signals missing in {p}.")
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
        write_markdown_report("Intake Analysis - Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Intake Analysis - Season Summary",
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

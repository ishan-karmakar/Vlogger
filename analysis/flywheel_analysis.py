# -*- coding: utf-8 -*-
"""
Flywheel energy & performance analysis for FRC Team Valor 6800.

Usage:
    python flywheel_analysis.py                       # default log
    python flywheel_analysis.py path/to/log.wpilog    # single log
    python flywheel_analysis.py logs/                 # directory (recursive)
    python flywheel_analysis.py logs/*.wpilog         # glob (multiple logs)
    python flywheel_analysis.py a.wpilog b.wpilog ... # list
    python flywheel_analysis.py -o summary.md logs/             # set summary path
    python flywheel_analysis.py --matches-out matches.md logs/  # set per-match path
    python flywheel_analysis.py --no-file logs/                 # terminal only
    python flywheel_analysis.py -j 8 logs/                      # 8 parallel workers
    python flywheel_analysis.py --serial logs/                  # force single-process

By default writes two markdown files into analysis/reports/:
  analysis/reports/flywheel_summary.md    season-wide / combined analysis
  analysis/reports/flywheel_matches.md    per-match breakdown

Log parsing runs in a ProcessPoolExecutor (default workers = min(cpu_count, n_logs)).

Cycle detection : Flywheel State (DISABLE->SHOOT transitions)
At-speed        : actual speed >= AT_SPEED_FRACTION * reqSpeed for that cycle
Power per motor : |Out Volt| x |Stator Current|  (each motor has its own voltage)
Cruise power    : speed within CRUISE_TOLERANCE of reqSpeed AND feeders idle
"""

import sys
import os
import glob
import io
import time
import datetime
import contextlib
import concurrent.futures
import numpy as np
from collections import defaultdict

def progress(msg):
    """Write a progress line to stderr (not captured by redirect_stdout)."""
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import vlogger

# Sibling helper modules. Supports both `python analysis/foo.py`
# (script-mode → `__package__` empty) and `from analysis import foo` (package-mode).
try:
    from . import _hoot, _cycles
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _hoot
    import _cycles

# -- Configuration ---------------------------------------------------------------

DEFAULT_LOG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "logs", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")

FLYWHEEL_REGEX  = (
    r"(NT:/SmartDashboard/(Shooter/(Flywheel|Projectile Aiming Mode)|Intake/.*Feeder"
    r"|SwerveDrive/(Gyro Yaw|Rotation Target|Driver Rotation State))"
    r"|DS:enabled)"
)
F_AIMING_MODE   = "NT:/SmartDashboard/Shooter/Projectile Aiming Mode"
F_GYRO_YAW      = "NT:/SmartDashboard/SwerveDrive/Gyro Yaw"          # degrees, unwrapped
F_ROT_TARGET    = "NT:/SmartDashboard/SwerveDrive/Rotation Target"   # radians, wrapped
F_DRIVE_STATE   = "NT:/SmartDashboard/SwerveDrive/Driver Rotation State"
DS_ENABLED      = "DS:enabled"

ALIGN_TOL_RAD   = 0.05   # ~2.9 deg — "aligned" when |heading error| <= this

F_LEFT_SPEED    = "NT:/SmartDashboard/Shooter/Flywheel Left Motor/Speed"
F_LEFT_CURRENT  = "NT:/SmartDashboard/Shooter/Flywheel Left Motor/Stator Current"
F_LEFT_VOLTAGE  = "NT:/SmartDashboard/Shooter/Flywheel Left Motor/Out Volt"
F_LEFT_REQSPEED = "NT:/SmartDashboard/Shooter/Flywheel Left Motor/reqSpeed"
F_R1_SPEED      = "NT:/SmartDashboard/Shooter/Flywheel Right One Motor/Speed"
F_R1_CURRENT    = "NT:/SmartDashboard/Shooter/Flywheel Right One Motor/Stator Current"
F_R1_VOLTAGE    = "NT:/SmartDashboard/Shooter/Flywheel Right One Motor/Out Volt"
F_R2_SPEED      = "NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/Speed"
F_R2_CURRENT    = "NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/Stator Current"
F_R2_VOLTAGE    = "NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/Out Volt"
F_STATE         = "NT:/SmartDashboard/Shooter/Flywheel State"
F_FEEDER_L      = "NT:/SmartDashboard/Intake/Left Feeder Motor/Speed"
F_FEEDER_R      = "NT:/SmartDashboard/Intake/Right Feeder Motor/Speed"

# Hoot CAN-ID mapping for the 3 flywheel motors. Phoenix6 logs label devices as
# `Phoenix6/TalonFX-<id>/...`. Edit if your wiring changes.
CAN_FLYWHEEL = (
    ("Left",      30),
    ("Right One", 31),
    ("Right Two", 32),
)
HOOT_REGEX = _hoot.hoot_regex(cid for (_, cid) in CAN_FLYWHEEL)

AT_SPEED_FRACTION = 0.90
CRUISE_TOLERANCE  = 0.5
FEEDER_IDLE_RPS   = 1.0
MIN_REQ_SPEED     = 1.0
MIN_CYCLE_SECS    = 0.20
COAST_DOWN_SECS   = 2.0

SEP = "-" * 72

# -- Data loading ----------------------------------------------------------------

def load_series(log_path):
    """Load WPI series + (optionally) any paired-hoot motor signals.

    Returns (series_dict, hoot_files_used). Hoot pairing is best-effort — if
    owlet is missing or no paired files exist, hoot_files_used is empty and
    only the WPI fields are populated.
    """
    raw = defaultdict(list)

    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, FLYWHEEL_REGEX)
    _hoot.load_into_raw(raw, src)
    hoot_files_used = _hoot.attach_paired_hoots(raw, log_path, HOOT_REGEX, bus="canivore")

    for name in raw:
        raw[name].sort(key=lambda x: x[0])
    return dict(raw), hoot_files_used

# -- Helpers ---------------------------------------------------------------------

def to_np(series, name):
    pts = series.get(name)
    if not pts or not isinstance(pts[0][1], float):
        return None, None
    return np.array([p[0] for p in pts]), np.array([p[1] for p in pts])

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

def find_shoot_windows(state_pts):
    """Flywheel SHOOT windows. Closes on DISABLE specifically (transient
    intermediate states stay inside the window). Thin wrapper around the
    shared helper; kept for cross-module callers (e.g. shot_analysis)."""
    return _cycles.find_state_windows(
        state_pts, "SHOOT",
        min_cycle_secs=MIN_CYCLE_SECS,
        end_state="DISABLE",
    )

def angular_error(yaw_rad, target_rad):
    """Shortest-path angular error wrapped to [-pi, pi]."""
    return np.arctan2(np.sin(yaw_rad - target_rad), np.cos(yaw_rad - target_rad))

def compute_xmode_metrics(drive_state_pts, t_start, t_end):
    """
    Return:
      t_xmode_first_s: seconds from t_start until drive state became X_MODE (or None)
      time_in_xmode_s: total seconds spent in X_MODE during the cycle window
    """
    if not drive_state_pts:
        return {"t_xmode_first_s": None, "time_in_xmode_s": 0.0}

    # Gather state transitions within the window, bracketed by the latest state before t_start
    segments = []  # list of (start_ts, state)
    prior_state = "UNKNOWN"
    for ts, val in drive_state_pts:
        if ts < t_start:
            prior_state = val
        else:
            break
    segments.append((t_start, prior_state))
    for ts, val in drive_state_pts:
        if t_start <= ts <= t_end:
            segments.append((ts, val))

    t_first = None
    time_in = 0.0
    for i, (ts, val) in enumerate(segments):
        seg_end = segments[i + 1][0] if i + 1 < len(segments) else t_end
        if val == "X_MODE":
            if t_first is None:
                t_first = ts - t_start
            time_in += max(0.0, seg_end - ts)
    return {
        "t_xmode_first_s": t_first,
        "time_in_xmode_s": float(time_in),
    }

def compute_align_metrics(ts_yaw, yaw_deg, ts_tgt, tgt_rad, t_start, t_end):
    """
    For a cycle window, return:
      - t_align_s: time (from t_start) until |heading error| <= ALIGN_TOL_RAD, or None if never
      - err_start_rad: |heading error| at t_start
      - err_end_rad: |heading error| at t_end
    Returns None if signals missing.
    """
    if ts_yaw is None or ts_tgt is None:
        return None
    # Convert unwrapped yaw degrees to wrapped radians
    yaw_rad_wrapped = np.deg2rad(((yaw_deg + 180) % 360) - 180)
    # Resample target onto yaw timestamps within the cycle window
    mask = (ts_yaw >= t_start) & (ts_yaw <= t_end)
    if mask.sum() < 2:
        return None
    ts_win   = ts_yaw[mask]
    yaw_win  = yaw_rad_wrapped[mask]
    tgt_win  = np.interp(ts_win, ts_tgt, tgt_rad,
                         left=tgt_rad[0], right=tgt_rad[-1])
    err_abs  = np.abs(angular_error(yaw_win, tgt_win))

    # Find first index where error drops to tolerance
    hits = np.where(err_abs <= ALIGN_TOL_RAD)[0]
    t_align = float(ts_win[hits[0]] - t_start) if len(hits) else None
    return {
        "t_align_s":     t_align,
        "err_start_rad": float(err_abs[0]),
        "err_end_rad":   float(err_abs[-1]),
    }

def total_true_time(bool_pts, t_end):
    """Sum the duration the boolean signal was True, up to t_end."""
    if not bool_pts:
        return 0.0
    total     = 0.0
    prev_ts   = None
    prev_val  = None
    for ts, val in bool_pts:
        if prev_val is True and prev_ts is not None:
            total += min(ts, t_end) - prev_ts
        prev_ts  = ts
        prev_val = bool(val)
    # Trailing segment up to t_end
    if prev_val is True and prev_ts is not None and prev_ts < t_end:
        total += t_end - prev_ts
    return float(total)

def state_at_time(state_pts, t, default="?"):
    """Return the latest state value at or before time t."""
    latest = default
    for ts, val in state_pts:
        if ts > t:
            break
        latest = val
    return latest

def spinup_end_time(ts_speed, speed, t_start, t_end, req_speed):
    if req_speed <= 0:
        return None
    target = AT_SPEED_FRACTION * req_speed
    mask   = (ts_speed >= t_start) & (ts_speed <= t_end)
    hits   = np.where(speed[mask] >= target)[0]
    if len(hits) == 0:
        return None
    return float(ts_speed[mask][hits[0]])

# -- Per-log analysis ------------------------------------------------------------

def analyze_log(log_path):
    """Run the per-log analysis and return a result dict. Prints a compact summary."""
    series, hoot_files_used = load_series(log_path)

    ts_ls,  left_speed   = to_np(series, F_LEFT_SPEED)
    ts_lc,  left_current = to_np(series, F_LEFT_CURRENT)
    ts_lv,  left_voltage = to_np(series, F_LEFT_VOLTAGE)
    ts_lq,  left_req     = to_np(series, F_LEFT_REQSPEED)
    ts_r1s, r1_speed     = to_np(series, F_R1_SPEED)
    ts_r1c, r1_current   = to_np(series, F_R1_CURRENT)
    ts_r1v, r1_voltage   = to_np(series, F_R1_VOLTAGE)
    ts_r2s, r2_speed     = to_np(series, F_R2_SPEED)
    ts_r2c, r2_current   = to_np(series, F_R2_CURRENT)
    ts_r2v, r2_voltage   = to_np(series, F_R2_VOLTAGE)
    ts_fl,  fl_speed     = to_np(series, F_FEEDER_L)
    ts_fr,  fr_speed     = to_np(series, F_FEEDER_R)
    state_pts            = series.get(F_STATE, [])
    aiming_pts           = series.get(F_AIMING_MODE, [])
    enabled_pts          = series.get(DS_ENABLED, [])
    drive_state_pts      = series.get(F_DRIVE_STATE, [])
    ts_yaw, yaw_deg      = to_np(series, F_GYRO_YAW)
    ts_tgt, tgt_rad      = to_np(series, F_ROT_TARGET)

    if ts_ls is None or not state_pts:
        return None

    all_ts = [ts_ls]
    for ts in [ts_r1s, ts_r2s]:
        if ts is not None:
            all_ts.append(ts)
    ts_grid = np.unique(np.concatenate(all_ts))

    ls_g  = interp_at(ts_grid, ts_ls,  left_speed)
    lc_g  = interp_at(ts_grid, ts_lc,  left_current)
    lv_g  = interp_at(ts_grid, ts_lv,  left_voltage)
    lq_g  = interp_at(ts_grid, ts_lq,  left_req)
    r1c_g = interp_at(ts_grid, ts_r1c, r1_current) if ts_r1c is not None else np.zeros_like(ts_grid)
    r1v_g = interp_at(ts_grid, ts_r1v, r1_voltage) if ts_r1v is not None else lv_g.copy()
    r2c_g = interp_at(ts_grid, ts_r2c, r2_current) if ts_r2c is not None else np.zeros_like(ts_grid)
    r2v_g = interp_at(ts_grid, ts_r2v, r2_voltage) if ts_r2v is not None else lv_g.copy()
    fl_g  = interp_at(ts_grid, ts_fl,  fl_speed)   if ts_fl  is not None else np.zeros_like(ts_grid)
    fr_g  = interp_at(ts_grid, ts_fr,  fr_speed)   if ts_fr  is not None else np.zeros_like(ts_grid)

    power_total   = (np.abs(lv_g)  * np.abs(lc_g)  +
                     np.abs(r1v_g) * np.abs(r1c_g) +
                     np.abs(r2v_g) * np.abs(r2c_g))
    current_total = np.abs(lc_g) + np.abs(r1c_g) + np.abs(r2c_g)

    feeder_idle = (np.abs(fl_g) < FEEDER_IDLE_RPS) & (np.abs(fr_g) < FEEDER_IDLE_RPS)
    cruise_mask = (
        (lq_g > MIN_REQ_SPEED) &
        (np.abs(ls_g - lq_g) <= CRUISE_TOLERANCE) &
        feeder_idle
    )

    cycles = []
    for t_start, t_end in find_shoot_windows(state_pts):
        if ts_lq is not None:
            m = (ts_lq >= t_start) & (ts_lq <= t_end)
            vals = left_req[m]
            req_in_window = float(np.median(vals[vals > 0])) if np.any(vals > 0) else 0.0
        else:
            req_in_window = 0.0

        t_at_speed = spinup_end_time(ts_ls, left_speed, t_start, t_end, req_in_window)
        spinup_end   = t_at_speed if t_at_speed else t_end
        # Classify cycle using Projectile Aiming Mode at cycle start
        aim_mode = state_at_time(aiming_pts, t_start, default="UNKNOWN")
        drive_state = state_at_time(drive_state_pts, t_start, default="UNKNOWN")
        align = compute_align_metrics(ts_yaw, yaw_deg, ts_tgt, tgt_rad, t_start, t_end)
        xmode = compute_xmode_metrics(drive_state_pts, t_start, t_end)
        cycles.append({
            "t_start":      t_start,
            "t_end":        t_end,
            "req_rps":      req_in_window,
            "spinup_s":     spinup_end - t_start,
            "spinup_E_J":   energy_in_window(ts_grid, power_total, t_start, spinup_end),
            "spinup_avg_I": mean_in_window(ts_grid, current_total, t_start, spinup_end),
            "spinup_pk_I":  peak_in_window(ts_grid, current_total, t_start, spinup_end),
            "total_E_J":    energy_in_window(ts_grid, power_total, t_start, t_end),
            "at_speed":     t_at_speed is not None,
            "aim_mode":     aim_mode,
            "drive_state":  drive_state,
            "align_t_s":    align["t_align_s"]     if align else None,
            "err_start":    align["err_start_rad"] if align else None,
            "err_end":      align["err_end_rad"]   if align else None,
            "t_xmode_s":    xmode["t_xmode_first_s"],
            "time_in_xmode_s": xmode["time_in_xmode_s"],
        })

    enabled_s = total_true_time(enabled_pts, float(ts_grid[-1]))

    # Build the result dict containing ONLY the small numpy arrays / scalars we
    # need downstream. Done before we drop the big intermediates so any view
    # references get materialized via .copy().
    # Hoot per-motor telemetry. Each entry is None when no hoot data was paired.
    hoot_motors = [
        {"label": label, "can_id": cid, "stats": _hoot.motor_stats(series, cid)}
        for (label, cid) in CAN_FLYWHEEL
    ]
    hoot_temps = [m["stats"]["peak_temp_c"] for m in hoot_motors
                  if m["stats"] and m["stats"].get("peak_temp_c") is not None]
    max_motor_temp_c = max(hoot_temps) if hoot_temps else None

    result = {
        "log_path":       log_path,
        "session_len":    float(ts_grid[-1] - ts_grid[0]),
        "enabled_s":      enabled_s,
        "total_energy_J": float(np.trapezoid(power_total, ts_grid)),
        "max_speed":      float(np.max(np.abs(ls_g))),
        "cycles":         cycles,
        "cruise_reqs":    lq_g[cruise_mask].copy(),
        "cruise_power":   power_total[cruise_mask].copy(),
        "cruise_n":       int(cruise_mask.sum()),
        "mean_I_L":       float(np.mean(np.abs(lc_g))),
        "peak_I_L":       float(np.max(np.abs(lc_g))),
        "mean_I_R1":      float(np.mean(np.abs(r1c_g))),
        "peak_I_R1":      float(np.max(np.abs(r1c_g))),
        "mean_I_R2":      float(np.mean(np.abs(r2c_g))),
        "peak_I_R2":      float(np.max(np.abs(r2c_g))),
        "mean_I_tot":     float(np.mean(current_total)),
        "peak_I_tot":     float(np.max(current_total)),
        "hoot_motors":      hoot_motors,
        "hoot_files_used":  hoot_files_used,
        "max_motor_temp_c": max_motor_temp_c,
    }

    # Drop the heavy local references so the worker's RSS shrinks before the
    # caller pickles the result back to the parent.
    del series, ts_grid, power_total, current_total
    del ls_g, lc_g, lv_g, lq_g, r1c_g, r1v_g, r2c_g, r2v_g, fl_g, fr_g
    del left_speed, left_current, left_voltage, left_req
    if r1_speed   is not None: del r1_speed
    if r1_current is not None: del r1_current
    if r1_voltage is not None: del r1_voltage
    if r2_speed   is not None: del r2_speed
    if r2_current is not None: del r2_current
    if r2_voltage is not None: del r2_voltage

    return result

# -- Per-log report --------------------------------------------------------------

def print_per_log_report(r):
    print()
    print(SEP)
    print(f"  LOG: {os.path.basename(r['log_path'])}")
    print(SEP)
    n_score = sum(1 for c in r["cycles"] if c["aim_mode"] == "SCORING")
    n_shutl = sum(1 for c in r["cycles"] if c["aim_mode"] == "SHUTTLING")
    n_other = len(r["cycles"]) - n_score - n_shutl
    print(f"  Duration             : {r['session_len']:.1f} s  ({r['session_len']/60:.2f} min)")
    print(f"  Enabled time         : {r['enabled_s']:.1f} s  "
          f"({100*r['enabled_s']/r['session_len']:.1f}% of log)")
    print(f"  Peak speed           : {r['max_speed']:.1f} RPS  (~{r['max_speed']*60:.0f} RPM)")
    print(f"  Total flywheel energy: {r['total_energy_J']/1000:.2f} kJ")
    print(f"  Cruise samples       : {r['cruise_n']}")
    print(f"  Shoot cycles         : {len(r['cycles'])}  "
          f"(SCORING={n_score}, SHUTTLING={n_shutl}"
          + (f", other={n_other}" if n_other else "") + ")")
    if r.get("max_motor_temp_c") is not None:
        print(f"  Peak motor temp      : {r['max_motor_temp_c']:.1f} °C  "
              f"(across all 3 flywheel motors, from hoot)")
    if r.get("hoot_files_used"):
        print(f"  Hoot data merged from: {len(r['hoot_files_used'])} file(s)")
        for hp in r["hoot_files_used"]:
            print(f"      - {os.path.basename(hp)}")

    # Per-log alignment and X-mode aggregates
    scoring = [c for c in r["cycles"] if c["aim_mode"] == "SCORING"]
    for label, lst in (("Scoring cycles", scoring), ("All cycles", r["cycles"])):
        if not lst:
            continue
        converged   = [c["align_t_s"] for c in lst if c["align_t_s"] is not None]
        errs        = [c["err_start"] for c in lst if c["err_start"] is not None]
        entered_x   = [c["t_xmode_s"] for c in lst if c["t_xmode_s"] is not None]
        time_in_x   = [c["time_in_xmode_s"] for c in lst]
        print(f"  {label:20s} | align: {len(converged)}/{len(lst)} converged"
              + (f", median {np.median(converged):.2f}s, max {np.max(converged):.2f}s"
                 if converged else "")
              + (f" | median init err {np.rad2deg(np.median(errs)):.1f} deg"
                 if errs else "")
              + f" | X_MODE: {len(entered_x)}/{len(lst)}"
              + (f", median entry {np.median(entered_x):.2f}s" if entered_x else "")
              + f", total {np.sum(time_in_x):.1f}s in X")
    print()
    print(f"  {'Current draw':35s}  {'Mean (A)':>9}  {'Peak (A)':>9}")
    print(f"  {'-'*35}  {'-'*9}  {'-'*9}")
    print(f"  {'Left motor (stator)':35s}  {r['mean_I_L']:>9.1f}  {r['peak_I_L']:>9.1f}")
    print(f"  {'Right 1 motor (stator)':35s}  {r['mean_I_R1']:>9.1f}  {r['peak_I_R1']:>9.1f}")
    print(f"  {'Right 2 motor (stator)':35s}  {r['mean_I_R2']:>9.1f}  {r['peak_I_R2']:>9.1f}")
    print(f"  {'Combined (all 3)':35s}  {r['mean_I_tot']:>9.1f}  {r['peak_I_tot']:>9.1f}")

    # Hoot-derived per-motor telemetry (only when present)
    if any(m["stats"] for m in r.get("hoot_motors", [])):
        print()
        print(f"  Per-motor telemetry (from hoot):")
        print(f"  {'Motor':<14}  {'CAN':>3}  {'°C pk':>6}  {'°C avg':>7}  "
              f"{'I_sup pk':>9}  {'I_torq pk':>10}")
        print(f"  {'-'*14}  {'-'*3}  {'-'*6}  {'-'*7}  "
              f"{'-'*9}  {'-'*10}")
        def _f(d, k, fmt):
            v = d.get(k) if d else None
            return fmt.format(v) if v is not None else "  -- "
        for m in r["hoot_motors"]:
            s = m["stats"]
            print(f"  {m['label']:<14}  {m['can_id']:>3}  "
                  f"{_f(s, 'peak_temp_c',      '{:>4.1f}°'):>6}  "
                  f"{_f(s, 'mean_temp_c',      '{:>5.1f}°'):>7}  "
                  f"{_f(s, 'peak_supply_curr', '{:>7.1f}A'):>9}  "
                  f"{_f(s, 'peak_torque_curr', '{:>8.1f}A'):>10}")

    cycles = r["cycles"]
    if not cycles:
        return
    print()
    print(f"  {'#':>2}  {'Start':>8}  {'End':>8}  {'Mode':>9}  {'ReqRPS':>7}  "
          f"{'SpinUp':>7}  {'AtSpd?':>6}  {'Align':>7}  {'ErrI':>5}  "
          f"{'Iavg':>6}  {'Ipk':>5}  {'E_spn':>7}  {'E_tot':>7}")
    print(f"  {'-'*2}  {'-'*8}  {'-'*8}  {'-'*9}  {'-'*7}  "
          f"{'-'*7}  {'-'*6}  {'-'*7}  {'-'*5}  "
          f"{'-'*6}  {'-'*5}  {'-'*7}  {'-'*7}")
    for i, c in enumerate(cycles):
        ok = "YES" if c["at_speed"] else "no"
        mode_short = (c["aim_mode"][:9]) if c["aim_mode"] else "?"
        if c["align_t_s"] is None and c["err_start"] is None:
            align_str = "   -   "
        elif c["align_t_s"] is None:
            align_str = " never "
        else:
            align_str = f"{c['align_t_s']:>5.2f}s "
        err_str = f"{np.rad2deg(c['err_start']):>4.1f}d" if c["err_start"] is not None else "  -  "
        print(f"  {i+1:>2}  {c['t_start']:>8.2f}  {c['t_end']:>8.2f}  "
              f"{mode_short:>9}  {c['req_rps']:>7.1f}  "
              f"{c['spinup_s']:>6.2f}s  {ok:>6}  "
              f"{align_str:>7}  {err_str:>5}  "
              f"{c['spinup_avg_I']:>6.1f}  {c['spinup_pk_I']:>5.1f}  "
              f"{c['spinup_E_J']:>6.1f}J  {c['total_E_J']:>6.1f}J")

# -- Combined analysis across all logs -------------------------------------------

def print_combined_analysis(results):
    n_logs = len(results)
    print()
    print(SEP)
    print(f"  COMBINED ANALYSIS ACROSS {n_logs} LOG{'S' if n_logs != 1 else ''}")
    print(SEP)

    # Aggregate cross-log session totals
    total_session = sum(r["session_len"]    for r in results)
    total_enabled = sum(r["enabled_s"]      for r in results)
    total_energy  = sum(r["total_energy_J"] for r in results)
    max_speed_all = max(r["max_speed"]      for r in results)

    # Merge all cycles, cruise samples
    all_cycles = [c for r in results for c in r["cycles"]]
    reached    = [c for c in all_cycles if c["at_speed"]]

    cruise_reqs  = np.concatenate([r["cruise_reqs"]  for r in results]) \
                   if results else np.array([])
    cruise_power = np.concatenate([r["cruise_power"] for r in results]) \
                   if results else np.array([])

    # Shoot cycle aggregates (all cycles, not just reached)
    cycle_durs   = np.array([c["t_end"] - c["t_start"] for c in all_cycles]) \
                   if all_cycles else np.array([])
    total_shoot  = float(np.sum(cycle_durs)) if len(cycle_durs) else 0.0
    avg_shoot    = float(np.mean(cycle_durs)) if len(cycle_durs) else 0.0
    avg_per_match = len(all_cycles) / n_logs if n_logs else 0.0

    # Spin-up times across cycles that reached target
    spinup_durs  = np.array([c["spinup_s"] for c in reached]) \
                   if reached else np.array([])
    avg_spinup   = float(np.mean(spinup_durs)) if len(spinup_durs) else 0.0

    # Cycle counts by aiming mode
    scoring_cycles  = [c for c in all_cycles if c["aim_mode"] == "SCORING"]
    shuttle_cycles  = [c for c in all_cycles if c["aim_mode"] == "SHUTTLING"]
    other_cycles    = [c for c in all_cycles
                       if c["aim_mode"] not in ("SCORING", "SHUTTLING")]

    # Use enabled time as denominator for % (avoids disabled/pit time)
    denom_s = total_enabled if total_enabled > 0 else total_session
    denom_lbl = "enabled time" if total_enabled > 0 else "log time"

    print(f"\n  Total duration across logs : {total_session:.1f} s  "
          f"({total_session/60:.2f} min)")
    print(f"  Total enabled time         : {total_enabled:.1f} s  "
          f"({total_enabled/60:.2f} min, {100*total_enabled/total_session:.1f}% of log)")
    print(f"  Total flywheel energy      : {total_energy/1000:.2f} kJ")
    print(f"  Peak speed across logs     : {max_speed_all:.1f} RPS  "
          f"(~{max_speed_all*60:.0f} RPM)")
    print(f"  Shoot cycles (all logs)    : {len(all_cycles)}  "
          f"(SCORING={len(scoring_cycles)}, SHUTTLING={len(shuttle_cycles)}"
          + (f", other={len(other_cycles)}" if other_cycles else "") + ")")
    print(f"  Avg shoot cycles per match : {avg_per_match:.1f}  "
          f"(across {n_logs} match{'es' if n_logs != 1 else ''})")
    print(f"  Total time spent shooting  : {total_shoot:.1f} s  "
          f"({100*total_shoot/denom_s:.1f}% of {denom_lbl})")
    print(f"  Avg shoot cycle duration   : {avg_shoot:.2f} s")
    print(f"  Avg spin-up time           : {avg_spinup:.2f} s  "
          f"(cycles reaching target)")
    print(f"  Cycles reaching target     : {len(reached)} / {len(all_cycles)}")
    print(f"  Cruise samples (all logs)  : {len(cruise_power)}")

    # Three-way breakdown: SCORING | SHUTTLING | COMBINED
    def _metrics(cat_cycles):
        """Compute all metrics for a given cycle list. Returns dict of strings."""
        if not cat_cycles:
            return None
        reached_cat = [c for c in cat_cycles if c["at_speed"]]
        dur   = np.array([c["t_end"] - c["t_start"] for c in cat_cycles])
        req   = np.array([c["req_rps"]    for c in cat_cycles if c["req_rps"] > 0])
        E_tot = np.array([c["total_E_J"]  for c in cat_cycles])
        spn   = np.array([c["spinup_s"]      for c in reached_cat]) if reached_cat else np.array([])
        E_spn = np.array([c["spinup_E_J"]    for c in reached_cat]) if reached_cat else np.array([])
        I_spn = np.array([c["spinup_avg_I"]  for c in reached_cat]) if reached_cat else np.array([])
        Ipk   = np.array([c["spinup_pk_I"]   for c in reached_cat]) if reached_cat else np.array([])

        # Alignment metrics (only cycles with valid align data)
        with_align = [c for c in cat_cycles if c["err_start"] is not None]
        converged  = [c for c in with_align if c["align_t_s"] is not None]
        err_start  = np.array([c["err_start"] for c in with_align]) if with_align else np.array([])
        t_align    = np.array([c["align_t_s"] for c in converged])  if converged  else np.array([])
        # ALIGN_TO_TARGET usage rate: cycles where driver put drivetrain in align-to-target mode
        aligned_drive = sum(1 for c in cat_cycles if c["drive_state"] == "ALIGN_TO_TARGET")

        # X_MODE metrics
        entered_xmode   = [c for c in cat_cycles if c["t_xmode_s"] is not None]
        t_xmode_first   = np.array([c["t_xmode_s"] for c in entered_xmode])
        t_in_xmode      = np.array([c["time_in_xmode_s"] for c in cat_cycles])
        # Time from aligned to X_MODE (positive = aligned first, then xmode)
        aligned_then_x  = [c for c in cat_cycles
                           if c["align_t_s"] is not None and c["t_xmode_s"] is not None]
        dt_align_to_x   = np.array([c["t_xmode_s"] - c["align_t_s"] for c in aligned_then_x])

        return {
            "n":             len(cat_cycles),
            "per_match":     len(cat_cycles) / n_logs,
            "reached":       len(reached_cat),
            "total_time":    float(np.sum(dur)),
            "avg_dur":       float(np.mean(dur)),
            "pct_enabled":   100 * float(np.sum(dur)) / denom_s if denom_s > 0 else 0.0,
            "median_req":    float(np.median(req)) if len(req) else 0.0,
            "req_min":       float(np.min(req))    if len(req) else 0.0,
            "req_max":       float(np.max(req))    if len(req) else 0.0,
            "avg_spinup":    float(np.mean(spn))   if len(spn) else 0.0,
            "avg_spinup_I":  float(np.mean(I_spn)) if len(I_spn) else 0.0,
            "peak_spinup_I": float(np.max(Ipk))    if len(Ipk) else 0.0,
            "avg_spinup_E":  float(np.mean(E_spn)) if len(E_spn) else 0.0,
            "avg_total_E":   float(np.mean(E_tot)),
            "sum_total_E":   float(np.sum(E_tot)),
            # Drivetrain alignment
            "aligned_drive":  aligned_drive,
            "align_n":        len(with_align),
            "align_converged":len(converged),
            "avg_err_start":  float(np.rad2deg(np.mean(err_start))) if len(err_start) else 0.0,
            "median_err_start":float(np.rad2deg(np.median(err_start))) if len(err_start) else 0.0,
            "max_err_start":  float(np.rad2deg(np.max(err_start)))  if len(err_start) else 0.0,
            "avg_align_t":    float(np.mean(t_align))   if len(t_align) else 0.0,
            "median_align_t": float(np.median(t_align)) if len(t_align) else 0.0,
            "max_align_t":    float(np.max(t_align))    if len(t_align) else 0.0,
            # X_MODE
            "xmode_entered":  len(entered_xmode),
            "avg_t_xmode":    float(np.mean(t_xmode_first))   if len(t_xmode_first) else 0.0,
            "median_t_xmode": float(np.median(t_xmode_first)) if len(t_xmode_first) else 0.0,
            "avg_align_to_x": float(np.mean(dt_align_to_x))   if len(dt_align_to_x) else 0.0,
            "avg_time_in_xmode":   float(np.mean(t_in_xmode)),
            "total_time_in_xmode": float(np.sum(t_in_xmode)),
        }

    score_m = _metrics(scoring_cycles)
    shutl_m = _metrics(shuttle_cycles)
    combo_m = _metrics(all_cycles)

    print()
    print(SEP)
    print("  BREAKDOWN: SCORING vs SHUTTLING vs COMBINED")
    print(SEP)

    rows = [
        ("Cycle count",             "n",            "{:.0f}",      ""),
        ("Cycles per match",        "per_match",    "{:.1f}",      ""),
        ("Reached target speed",    "reached",      "{:.0f}",      ""),
        ("Total time",              "total_time",   "{:.1f}",      "s"),
        ("% of enabled time",       "pct_enabled",  "{:.1f}",      "%"),
        ("Avg cycle duration",      "avg_dur",      "{:.2f}",      "s"),
        ("Median reqSpeed",         "median_req",   "{:.1f}",      "RPS"),
        ("reqSpeed min",            "req_min",      "{:.1f}",      "RPS"),
        ("reqSpeed max",            "req_max",      "{:.1f}",      "RPS"),
        ("Avg spin-up time",        "avg_spinup",   "{:.2f}",      "s"),
        ("Avg spin-up current",     "avg_spinup_I", "{:.1f}",      "A"),
        ("Peak spin-up current",    "peak_spinup_I","{:.1f}",      "A"),
        ("Avg spin-up energy",      "avg_spinup_E", "{:.1f}",      "J"),
        ("Avg total energy/cycle",  "avg_total_E",  "{:.1f}",      "J"),
        ("Total energy",            "sum_total_E",  "{:.0f}",      "J"),
        # Drivetrain alignment
        ("--- Drivetrain align ---","",             "",            ""),
        ("Cycles in ALIGN_TO_TARGET","aligned_drive","{:.0f}",     ""),
        ("Cycles w/ align data",    "align_n",      "{:.0f}",      ""),
        ("Cycles converged in tol", "align_converged","{:.0f}",    ""),
        ("Median initial heading err","median_err_start","{:.1f}", "deg"),
        ("Max initial heading err", "max_err_start","{:.1f}",      "deg"),
        ("Avg time to align",       "avg_align_t",  "{:.2f}",      "s"),
        ("Median time to align",    "median_align_t","{:.2f}",     "s"),
        ("Max time to align",       "max_align_t",  "{:.2f}",      "s"),
        # X_MODE
        ("--- X-mode ---",          "",             "",            ""),
        ("Cycles entering X_MODE",  "xmode_entered","{:.0f}",      ""),
        ("Avg time to X_MODE",      "avg_t_xmode",  "{:.2f}",      "s"),
        ("Median time to X_MODE",   "median_t_xmode","{:.2f}",     "s"),
        ("Avg align->X_MODE gap",   "avg_align_to_x","{:.2f}",     "s"),
        ("Avg time IN X_MODE/cyc",  "avg_time_in_xmode","{:.2f}",  "s"),
        ("Total time in X_MODE",    "total_time_in_xmode","{:.1f}","s"),
    ]

    def fmt_cell(m, key, fmt, unit):
        if m is None or not key:
            return ""
        val = m.get(key)
        if val is None:
            return "-"
        s = fmt.format(val)
        return f"{s} {unit}" if unit else s

    col_w = 18
    hdr_w = 28
    print()
    print(f"  {'Metric':<{hdr_w}}  {'SCORING':>{col_w}}  {'SHUTTLING':>{col_w}}  {'COMBINED':>{col_w}}")
    print(f"  {'-'*hdr_w}  {'-'*col_w}  {'-'*col_w}  {'-'*col_w}")
    for label, key, fmt, unit in rows:
        if not key:  # section separator
            print(f"  {label:<{hdr_w}}")
            continue
        s = fmt_cell(score_m, key, fmt, unit)
        h = fmt_cell(shutl_m, key, fmt, unit)
        c = fmt_cell(combo_m, key, fmt, unit)
        print(f"  {label:<{hdr_w}}  {s:>{col_w}}  {h:>{col_w}}  {c:>{col_w}}")

    if other_cycles:
        other_m = _metrics(other_cycles)
        print()
        print(f"  Note: {len(other_cycles)} cycle(s) had mode='{other_cycles[0]['aim_mode']}' "
              f"(not counted in SCORING/SHUTTLING above)")
        if other_m:
            print(f"    total time: {other_m['total_time']:.1f}s  "
                  f"avg dur: {other_m['avg_dur']:.2f}s  "
                  f"avg E/cyc: {other_m['avg_total_E']:.1f}J")

    if not reached or len(cruise_power) == 0:
        print("\n  Insufficient data for break-even analysis.")
        return

    # Aggregated spin-up stats
    dur_arr = np.array([c["spinup_s"]   for c in reached])
    ien_arr = np.array([c["spinup_E_J"] for c in reached])
    iav_arr = np.array([c["spinup_avg_I"] for c in reached])
    ipk_arr = np.array([c["spinup_pk_I"]  for c in reached])

    P_cruise_W = float(np.mean(cruise_power))
    E_spinup_J = float(np.mean(ien_arr))

    print()
    print(f"  Average spin-up time    : {np.mean(dur_arr):.2f} s  "
          f"(min {np.min(dur_arr):.2f} s, max {np.max(dur_arr):.2f} s)")
    print(f"  Average spin-up current : {np.mean(iav_arr):.1f} A  "
          f"(peak up to {np.max(ipk_arr):.1f} A)")
    print(f"  Average spin-up energy  : {np.mean(ien_arr):.1f} J  "
          f"(min {np.min(ien_arr):.1f} J, max {np.max(ien_arr):.1f} J)")
    print(f"  Cruise (no-load hold) power  : {P_cruise_W:.1f} W")

    # -- Break-even: spin-up-per-shot vs keep-spinning
    print()
    print(SEP)
    print("  ENERGY COMPARISON: spin-up-per-shot vs keep-spinning")
    print(SEP)
    print(f"\n  Cruise (no-load hold) power : {P_cruise_W:.1f} W")
    print(f"  Avg spin-up energy          : {E_spinup_J:.1f} J")
    breakeven_s = E_spinup_J / P_cruise_W
    print(f"\n  Break-even gap between shots: {breakeven_s:.2f} s")
    print(f"  Gap < {breakeven_s:.2f} s  ->  keep spinning is cheaper")
    print(f"  Gap > {breakeven_s:.2f} s  ->  spin-up per shot is cheaper")

    print()
    print(f"  {'Gap (s)':>8}  {'Keep-spinning (J)':>18}  "
          f"{'Spin-up-per-shot (J)':>20}  {'Cheaper':>10}")
    print(f"  {'-'*8}  {'-'*18}  {'-'*20}  {'-'*10}")
    for gap in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 10.0]:
        e_keep = P_cruise_W * gap
        winner = "keep-spin" if e_keep < E_spinup_J else "spin-up"
        print(f"  {gap:>8.1f}  {e_keep:>18.1f}  {E_spinup_J:>20.1f}  {winner:>10}")

    # -- Low-speed idle + higher-target + coast-aware analyses
    print()
    print(SEP)
    print("  LOW-SPEED IDLE ANALYSIS: what if we hold at a lower speed?")
    print(SEP)

    if len(cruise_power) <= 20:
        print("\n  Not enough cruise samples to fit a P(speed) curve.")
        return

    bin_size = 2.0
    bins = {}
    for rq, p in zip(cruise_reqs, cruise_power):
        key = round(float(rq) / bin_size) * bin_size
        bins.setdefault(key, []).append(float(p))
    bin_centers = sorted(bins.keys())
    bin_means   = np.array([np.mean(bins[b]) for b in bin_centers])
    bin_speeds  = np.array(bin_centers)

    print("\n  Measured cruise power vs reqSpeed (feeders idle, all logs combined):")
    print(f"  {'ReqSpeed (RPS)':>16}  {'Power (W)':>10}  {'Samples':>8}")
    print(f"  {'-'*16}  {'-'*10}  {'-'*8}")
    for b in bin_centers:
        print(f"  {b:>16.1f}  {np.mean(bins[b]):>10.1f}  {len(bins[b]):>8d}")

    A = np.vstack([bin_speeds, bin_speeds**2]).T
    coef, *_ = np.linalg.lstsq(A, bin_means, rcond=None)
    a_coef, b_coef = coef
    P_model = lambda w: a_coef * w + b_coef * (w ** 2)
    print(f"\n  Fitted model: P(w) = {a_coef:.3f}*w + {b_coef:.4f}*w^2  W")

    req_typical = float(np.median([c["req_rps"] for c in reached]))
    print(f"  Typical target speed        : {req_typical:.1f} RPS")
    print(f"  Measured spin-up energy     : {E_spinup_J:.1f} J (from 0 -> {req_typical:.0f} RPS)")

    print()
    print("  Per-shot cost for each idle strategy, at various gaps between shots:")
    print(f"    Target spin-up energy (from 0):  {E_spinup_J:.1f} J")
    print(f"    Typical target speed           :  {req_typical:.1f} RPS")
    print()
    print(f"  {'IdleSpd':>7}  {'IdleP':>7}  {'E_saved':>8}  {'vs-stop':>9}  "
          f"{'Cost @':>7}  {'Cost @':>7}  {'Cost @':>7}  {'Cost @':>7}")
    print(f"  {'(RPS)':>7}  {'(W)':>7}  {'(J)':>8}  {'breakev':>9}  "
          f"{'0.5s':>7}  {'1.0s':>7}  {'2.0s':>7}  {'5.0s':>7}")
    print(f"  {'-'*7}  {'-'*7}  {'-'*8}  {'-'*9}  "
          f"{'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}")

    test_gaps = [0.5, 1.0, 2.0, 5.0]
    for idle_w in [0, 5, 10, 15, 20, 25, 30, req_typical]:
        P_idle_est = max(0.0, P_model(idle_w)) if idle_w > 0 else 0.0
        ke_ratio   = min(1.0, (idle_w ** 2) / (req_typical ** 2))
        E_saved    = E_spinup_J * ke_ratio
        E_from_idle = E_spinup_J - E_saved
        if P_idle_est > 0 and E_saved > 0:
            be_str = f"{E_saved / P_idle_est:.2f}s"
        elif idle_w == 0:
            be_str = "baseline"
        else:
            be_str = "n/a"
        costs = [f"{P_idle_est * gap + E_from_idle:>7.1f}" for gap in test_gaps]
        lbl = f"{idle_w:>7.1f}" if idle_w == req_typical else f"{idle_w:>7.0f}"
        print(f"  {lbl}  {P_idle_est:>7.1f}  {E_saved:>8.1f}  {be_str:>9}  "
              f"{costs[0]}  {costs[1]}  {costs[2]}  {costs[3]}")

    print()
    print("  Caveat: idle speeds below the lowest measured bin are heavy extrapolation.")
    print(f"  Lowest measured cruise speed bin: {min(bin_centers):.1f} RPS")

    # -- Higher target speeds
    print()
    print(SEP)
    print("  HIGHER TARGET SPEEDS: what if we shoot at 40/45/50 TPS?")
    print(SEP)
    t_spinup_typical = float(np.mean(dur_arr))
    print(f"\n  Baseline (measured)         : {req_typical:.1f} RPS")
    print(f"    Spin-up energy            : {E_spinup_J:.1f} J")
    print(f"    Spin-up time              : {t_spinup_typical:.2f} s")
    print(f"    Cruise (hold) power       : {P_cruise_W:.1f} W")
    print(f"    Break-even gap            : {E_spinup_J / P_cruise_W:.2f} s")

    print()
    print(f"  {'TgtSpd':>7}  {'SpinUp':>7}  {'SpinUp':>8}  {'Cruise':>7}  "
          f"{'Break':>7}  {'Ratio vs':>9}")
    print(f"  {'(RPS)':>7}  {'time(s)':>7}  {'E (J)':>8}  {'P (W)':>7}  "
          f"{'even(s)':>7}  {'baseline':>9}")
    print(f"  {'-'*7}  {'-'*7}  {'-'*8}  {'-'*7}  "
          f"{'-'*7}  {'-'*9}")
    for tgt in [req_typical, 40.0, 45.0, 50.0]:
        w_ratio = tgt / req_typical
        E_tgt   = E_spinup_J * (w_ratio ** 2)
        t_tgt   = t_spinup_typical * w_ratio
        P_hold  = max(0.0, P_model(tgt))
        be_tgt  = E_tgt / P_hold if P_hold > 0 else float("inf")
        print(f"  {tgt:>7.1f}  {t_tgt:>7.2f}  {E_tgt:>8.1f}  {P_hold:>7.1f}  "
              f"{be_tgt:>6.2f}s  {E_tgt / E_spinup_J:>8.2f}x")

    # -- Coast-aware
    print()
    print(SEP)
    print(f"  COAST-AWARE: flywheel coasts to 0 in ~{COAST_DOWN_SECS:.1f}s (motor off)")
    print(SEP)

    KE_full   = P_cruise_W * COAST_DOWN_SECS / 2.0
    Loss_full = max(0.0, E_spinup_J - KE_full)
    print(f"\n  Decomposing measured spin-up energy ({E_spinup_J:.1f} J):")
    print(f"    Estimated KE at {req_typical:.1f} RPS : {KE_full:.1f} J")
    print(f"    Spin-up losses (I^2R etc.) : {Loss_full:.1f} J")

    k_star = 2.0 - (P_cruise_W * COAST_DOWN_SECS - Loss_full) / KE_full if KE_full > 0 else None
    T_star = k_star * COAST_DOWN_SECS if k_star and 0 < k_star <= 1 else None

    print(f"\n  Break-even HOLD vs COAST-AND-RESPIN (target {req_typical:.1f} RPS):")
    if T_star:
        print(f"    T* = {T_star:.2f} s "
              f"(was {E_spinup_J/P_cruise_W:.2f} s without coast accounting)")

    print()
    print(f"  Per-shot cost at {req_typical:.1f} RPS target:")
    print(f"  {'Gap':>5}  {'w_end':>6}  {'Hold':>7}  {'Coast+':>8}  {'Winner':>8}  {'Save':>7}")
    print(f"  {'(s)':>5}  {'(RPS)':>6}  {'(J)':>7}  {'respin':>8}  {'':>8}  {'(J)':>7}")
    print(f"  {'-'*5}  {'-'*6}  {'-'*7}  {'-'*8}  {'-'*8}  {'-'*7}")
    for T in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]:
        w_end = req_typical * max(0.0, 1 - T / COAST_DOWN_SECS)
        h = P_cruise_W * T
        k = min(1.0, T / COAST_DOWN_SECS)
        c = KE_full * (2*k - k*k) + Loss_full * k
        winner = "HOLD" if h < c else "COAST"
        print(f"  {T:>5.1f}  {w_end:>6.1f}  {h:>7.1f}  {c:>8.1f}  {winner:>8}  {abs(h-c):>7.1f}")

    print()
    print(SEP)

# -- CLI entry -------------------------------------------------------------------

def resolve_log_paths(args):
    """
    Expand CLI args into a list of .wpilog files. Accepts:
      - Files: passed through as-is
      - Directories: walked recursively for *.wpilog
      - Globs: expanded; any dir hits are also walked recursively
    Paths are normalized to forward slashes (required by vlogger's URL scheme).
    """
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

    # Normalize to forward-slash absolute paths, dedupe preserving order
    seen = set()
    uniq = []
    for p in paths:
        abs_p = os.path.abspath(p).replace("\\", "/")
        if abs_p not in seen:
            uniq.append(abs_p)
            seen.add(abs_p)
    return uniq

def parse_cli(argv):
    """
    Separate CLI flags from positional log args.

    Flags:
      -o / --output / --summary-out PATH   overall/combined analysis file
      --matches-out PATH                   per-match breakdown file
      --no-file                            don't write either file
    """
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    summary_out = os.path.join(reports_dir, "flywheel_summary.md")
    matches_out = os.path.join(reports_dir, "flywheel_matches.md")
    write_file  = True
    workers     = None  # None -> auto
    positional  = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-o", "--output", "--summary-out"):
            if i + 1 >= len(argv):
                print(f"ERROR: {a} requires a path argument")
                sys.exit(2)
            summary_out = argv[i + 1]
            write_file = True
            i += 2
        elif a == "--matches-out":
            if i + 1 >= len(argv):
                print(f"ERROR: {a} requires a path argument")
                sys.exit(2)
            matches_out = argv[i + 1]
            write_file = True
            i += 2
        elif a in ("-j", "--workers"):
            if i + 1 >= len(argv):
                print(f"ERROR: {a} requires a count argument")
                sys.exit(2)
            workers = max(1, int(argv[i + 1]))
            i += 2
        elif a == "--no-file":
            write_file = False
            i += 1
        elif a == "--serial":
            workers = 1
            i += 1
        else:
            positional.append(a)
            i += 1
    return positional, summary_out, matches_out, write_file, workers

def write_markdown_report(title, captured_text, out_path, paths, extra_note=None):
    """Wrap captured analysis output in a markdown file with a header."""
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
    lines.extend([
        "",
        "## Analysis output",
        "",
        "```",
        captured_text.rstrip(),
        "```",
        "",
    ])
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def _worker_analyze(idx_path):
    """Worker for process pool: returns (idx, path, result, elapsed_s)."""
    import gc
    idx, p = idx_path
    t0 = time.time()
    r  = analyze_log(p)
    gc.collect()  # free large intermediates before returning
    return (idx, p, r, time.time() - t0)

def _make_pool(workers):
    """Create a ProcessPoolExecutor that recycles workers after each task.

    `max_tasks_per_child=1` is critical here: vlogger / pyntcore / numpy hold
    onto memory in C-extension state that Python's GC can't reclaim. Without
    recycling, peak memory grows without bound as a single worker chews through
    multiple logs. With recycling each worker is killed after one log and the
    OS reclaims everything cleanly.
    """
    kwargs = {"max_workers": workers}
    # max_tasks_per_child added in Python 3.11; older interpreters fall back
    # to non-recycling pools.
    if sys.version_info >= (3, 11):
        kwargs["max_tasks_per_child"] = 1
    return concurrent.futures.ProcessPoolExecutor(**kwargs)

def load_all(paths, workers):
    """Run analyze_log across paths, possibly in parallel. Returns list of results in input order."""
    n = len(paths)
    if workers is None:
        workers = min(os.cpu_count() or 4, n)
    workers = max(1, min(workers, n))

    results_by_idx = {}
    failed = []

    if workers == 1:
        progress(f"Loading logs serially ...")
        for i, p in enumerate(paths):
            t0 = time.time()
            progress(f"[{i+1}/{n}] Loading {os.path.basename(p)} ...")
            r = analyze_log(p)
            dt = time.time() - t0
            if r is None:
                progress(f"  WARNING: skipped (missing data)")
                failed.append(p)
                continue
            results_by_idx[i] = r
            progress(f"  done in {dt:.1f}s — {len(r['cycles'])} cycles, {r['cruise_n']} cruise, {r['enabled_s']:.0f}s enabled")
        return [results_by_idx[i] for i in range(n) if i in results_by_idx], failed

    progress(f"Loading {n} logs in parallel ({workers} workers) ...")
    completed = 0
    ex = _make_pool(workers)
    futures = {}
    try:
        futures = {ex.submit(_worker_analyze, (i, p)): i for i, p in enumerate(paths)}
        for fut in concurrent.futures.as_completed(futures):
            idx, p, r, dt = fut.result()
            completed += 1
            if r is None:
                progress(f"[{completed}/{n}] {os.path.basename(p)} FAILED (missing data) after {dt:.1f}s")
                failed.append(p)
                continue
            results_by_idx[idx] = r
            progress(f"[{completed}/{n}] {os.path.basename(p)} — {dt:.1f}s, {len(r['cycles'])} cycles, {r['cruise_n']} cruise, {r['enabled_s']:.0f}s enabled")
    except KeyboardInterrupt:
        progress("Interrupted — cancelling remaining workers ...")
        for f in futures:
            f.cancel()
        ex.shutdown(wait=True, cancel_futures=True)
        raise
    finally:
        # Always force a clean shutdown so no worker processes are left behind.
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

    t_load = time.time()
    results, failed = load_all(paths, workers)
    progress(f"Loaded all logs in {time.time() - t_load:.1f}s  "
             f"({len(results)} ok, {len(failed)} failed)")

    # Two separate buffers: per-match breakdown, and overall summary.
    matches_buf = io.StringIO()
    summary_buf = io.StringIO()

    with contextlib.redirect_stdout(matches_buf):
        print(f"Analyzing {len(paths)} log{'s' if len(paths) != 1 else ''}:")
        for p in paths:
            print(f"  - {p}")
        for p in failed:
            print(f"\nWARNING: could not analyze {p} (missing speed or state data).")
        for r in results:
            print_per_log_report(r)

    if results:
        with contextlib.redirect_stdout(summary_buf):
            progress(f"Computing combined analysis across {len(results)} log{'s' if len(results) != 1 else ''} ...")
            print_combined_analysis(results)

    matches_text = matches_buf.getvalue()
    summary_text = summary_buf.getvalue()

    progress(f"Writing output to terminal ...")
    sys.stdout.write(matches_text)
    sys.stdout.write(summary_text)
    sys.stdout.flush()

    if write_file:
        progress(f"Writing per-match report to {matches_out} ...")
        write_markdown_report(
            "Flywheel Analysis — Per-Match Breakdown",
            matches_text, matches_out, paths,
            extra_note="Combined/overall analysis is in the companion summary file."
        )
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report(
            "Flywheel Analysis — Season Summary",
            summary_text, summary_out, paths,
            extra_note="Per-match breakdowns are in the companion matches file."
        )
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
        # _make_pool's finally block already cleans up workers; just exit.
        sys.stderr.write("\nAborted by user.\n")
        sys.exit(130)

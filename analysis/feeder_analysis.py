# -*- coding: utf-8 -*-
"""
Feeder energy & performance analysis for FRC Team Valor 6800.

Two motors: Left Feeder Motor, Right Feeder Motor (TalonFX 51 + 52, canivore).
Cycle model: Feeder State transitions (DISABLED <-> SHOOTING / OUTTAKING).
Power     : |Out Volt| * |Stator Current| per motor, summed.

Note: NT publishes Stator Current but NOT Supply Current for feeder motors;
supply current is only available from the paired hoot file (Phoenix6 logs
SupplyCurrent for every TalonFX). Energy math uses Stator (which is the
useful one for joule integration anyway).

Usage:
    python feeder_analysis.py                          # default log
    python feeder_analysis.py logs/                    # directory (recursive)
    python feeder_analysis.py logs/*.wpilog            # glob
    python feeder_analysis.py -j 8 logs/               # 8 workers
    python feeder_analysis.py --no-file logs/          # terminal only
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
from collections import defaultdict, Counter

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
    os.path.dirname(__file__), "..", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")

# Note: no `Supply Current` in this regex — feeder motors don't publish it on NT
# (they would log it via hoot, which we read separately).
FEEDER_REGEX = (
    r"NT:/SmartDashboard/Intake/("
    r"Feeder State"
    r"|(Left|Right) Feeder Motor/(Speed|Stator Current|Out Volt|reqSpeed)"
    r")"
)
REGEX = FEEDER_REGEX  # canonical alias

L_SPEED    = "NT:/SmartDashboard/Intake/Left Feeder Motor/Speed"
L_STATOR   = "NT:/SmartDashboard/Intake/Left Feeder Motor/Stator Current"
L_VOLTAGE  = "NT:/SmartDashboard/Intake/Left Feeder Motor/Out Volt"
L_REQSPEED = "NT:/SmartDashboard/Intake/Left Feeder Motor/reqSpeed"
R_SPEED    = "NT:/SmartDashboard/Intake/Right Feeder Motor/Speed"
R_STATOR   = "NT:/SmartDashboard/Intake/Right Feeder Motor/Stator Current"
R_VOLTAGE  = "NT:/SmartDashboard/Intake/Right Feeder Motor/Out Volt"
R_REQSPEED = "NT:/SmartDashboard/Intake/Right Feeder Motor/reqSpeed"
STATE_PATH = "NT:/SmartDashboard/Intake/Feeder State"

# Hoot CAN-ID mapping for the 2 feeder motors. They live on the **canivore**
# bus alongside drivetrain + flywheel (despite being part of the C++ Intake
# subsystem with the rio-bus intake/hopper motors). The robot code calls
# this bus "baseCAN"; CTRE / vlogger convention is "canivore".
CAN_FEEDER = (
    ("Left",  51),
    ("Right", 52),
)
HOOT_REGEX = _hoot.hoot_regex(cid for (_, cid) in CAN_FEEDER)

AT_SPEED_FRACTION = 0.80
MIN_CYCLE_SECS    = 0.10
STALL_FRACTION    = 0.30
MIN_REQ_SPEED     = 1.0

# State-machine values published as `Intake/Feeder State`. Anything that isn't
# one of these is treated as "DISABLED" / idle for the time-distribution table.
STATES = ("DISABLED", "SHOOTING", "OUTTAKING")

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading ----------------------------------------------------------------

def load_series(log_path):
    """Load WPI series + (optionally) any paired-hoot motor signals.

    Returns ``(series_dict, hoot_files_used)``. Hoot pairing is best-effort —
    if owlet is missing or no paired files exist, hoot_files_used is empty.
    """
    raw = defaultdict(list)
    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, FEEDER_REGEX)
    _hoot.load_into_raw(raw, src)
    hoot_files_used = _hoot.attach_paired_hoots(raw, log_path, HOOT_REGEX, bus="canivore")

    for name in raw:
        raw[name].sort(key=lambda x: x[0])
    return dict(raw), hoot_files_used

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

def find_state_windows(state_pts, target_state):
    """Find contiguous windows where state == target_state. Thin wrapper
    around the shared helper using feeder's MIN_CYCLE_SECS and the
    "close on any non-target" convention (intake / feeder / hopper share)."""
    return _cycles.find_state_windows(
        state_pts, target_state, min_cycle_secs=MIN_CYCLE_SECS,
    )

# -- Per-log analysis ------------------------------------------------------------

def analyze_log(log_path):
    """Run per-log feeder analysis, returning a result dict or None when
    required signals are missing (typically: motor speed series, or no
    Feeder State logged at all)."""
    series, hoot_files_used = load_series(log_path)

    ts_ls,  l_speed    = to_np(series, L_SPEED)
    ts_lsc, l_stator   = to_np(series, L_STATOR)
    ts_lv,  l_voltage  = to_np(series, L_VOLTAGE)
    ts_lq,  l_req      = to_np(series, L_REQSPEED)
    ts_rs,  r_speed    = to_np(series, R_SPEED)
    ts_rsc, r_stator   = to_np(series, R_STATOR)
    ts_rv,  r_voltage  = to_np(series, R_VOLTAGE)
    ts_rq,  r_req      = to_np(series, R_REQSPEED)
    state_pts          = series.get(STATE_PATH, [])

    if ts_ls is None or ts_rs is None or not state_pts:
        return None

    ts_grid = np.unique(np.concatenate([ts_ls, ts_rs]))

    ls_g    = interp_at(ts_grid, ts_ls,  l_speed)
    lsc_g   = interp_at(ts_grid, ts_lsc, l_stator)  if ts_lsc is not None else np.zeros_like(ts_grid)
    lv_g    = interp_at(ts_grid, ts_lv,  l_voltage) if ts_lv  is not None else np.zeros_like(ts_grid)
    lq_g    = interp_at(ts_grid, ts_lq,  l_req)     if ts_lq  is not None else np.zeros_like(ts_grid)
    rs_g    = interp_at(ts_grid, ts_rs,  r_speed)
    rsc_g   = interp_at(ts_grid, ts_rsc, r_stator)  if ts_rsc is not None else np.zeros_like(ts_grid)
    rv_g    = interp_at(ts_grid, ts_rv,  r_voltage) if ts_rv  is not None else np.zeros_like(ts_grid)
    rq_g    = interp_at(ts_grid, ts_rq,  r_req)     if ts_rq  is not None else np.zeros_like(ts_grid)

    power_L   = np.abs(lv_g) * np.abs(lsc_g)
    power_R   = np.abs(rv_g) * np.abs(rsc_g)
    power_tot = power_L + power_R

    stator_tot = np.abs(lsc_g) + np.abs(rsc_g)

    t0 = ts_grid[0]
    session_len    = float(ts_grid[-1] - t0)
    total_energy_J = float(np.trapezoid(power_tot, ts_grid))
    max_speed_L    = float(np.max(np.abs(ls_g)))
    max_speed_R    = float(np.max(np.abs(rs_g)))

    state_time = Counter()
    for i in range(len(state_pts) - 1):
        ts, val = state_pts[i]
        nxt     = state_pts[i + 1][0]
        state_time[val] += (nxt - ts)
    if state_pts:
        last_ts, last_val = state_pts[-1]
        state_time[last_val] += max(0.0, ts_grid[-1] - last_ts)

    shooting_windows  = find_state_windows(state_pts, "SHOOTING")
    outtaking_windows = find_state_windows(state_pts, "OUTTAKING")

    def _build_cycle(t_start, t_end):
        dur     = t_end - t_start
        E_cyc   = energy_in_window(ts_grid, power_tot, t_start, t_end)
        I_avg   = mean_in_window(ts_grid, stator_tot, t_start, t_end)
        I_pk    = peak_in_window(ts_grid, stator_tot, t_start, t_end)

        mask = (ts_grid >= t_start) & (ts_grid <= t_end)
        if mask.sum() > 1:
            req_median = (float(np.median(lq_g[mask][lq_g[mask] != 0]))
                          if np.any(lq_g[mask] != 0) else 0.0)
            actual_L_avg = float(np.mean(np.abs(ls_g[mask])))
            actual_R_avg = float(np.mean(np.abs(rs_g[mask])))
            req_abs = abs(req_median)
            reached = (req_abs > MIN_REQ_SPEED and
                       actual_L_avg >= AT_SPEED_FRACTION * req_abs and
                       actual_R_avg >= AT_SPEED_FRACTION * req_abs)
            stalled = (req_abs > MIN_REQ_SPEED and
                       (actual_L_avg < STALL_FRACTION * req_abs or
                        actual_R_avg < STALL_FRACTION * req_abs))
        else:
            req_median   = 0.0
            actual_L_avg = 0.0
            actual_R_avg = 0.0
            reached = stalled = False
        return {
            "t_start":    t_start,
            "t_end":      t_end,
            "dur":        dur,
            "req_rps":    req_median,
            "act_L":      actual_L_avg,
            "act_R":      actual_R_avg,
            "E_J":        E_cyc,
            "I_stat_avg": I_avg,
            "I_stat_pk":  I_pk,
            "reached":    reached,
            "stalled":    stalled,
        }

    shoot_cycles    = [_build_cycle(s, e) for (s, e) in shooting_windows]
    outtake_cycles  = [_build_cycle(s, e) for (s, e) in outtaking_windows]

    current_stats = [
        {"label": "Left  stator",    "mean": float(np.mean(np.abs(lsc_g))), "peak": float(np.max(np.abs(lsc_g)))},
        {"label": "Right stator",    "mean": float(np.mean(np.abs(rsc_g))), "peak": float(np.max(np.abs(rsc_g)))},
        {"label": "Combined stator", "mean": float(np.mean(stator_tot)),    "peak": float(np.max(stator_tot))},
    ]

    hoot_motors = [
        {"label": label, "can_id": cid, "stats": _hoot.motor_stats(series, cid)}
        for (label, cid) in CAN_FEEDER
    ]
    hoot_temps = [m["stats"]["peak_temp_c"] for m in hoot_motors
                  if m["stats"] and m["stats"].get("peak_temp_c") is not None]
    max_motor_temp_c = max(hoot_temps) if hoot_temps else None

    return {
        "log_path":         log_path,
        "session_len":      session_len,
        "max_speed_L":      max_speed_L,
        "max_speed_R":      max_speed_R,
        "total_energy_J":   total_energy_J,
        "n_shooting":       len(shoot_cycles),
        "n_outtaking":      len(outtake_cycles),
        "state_time":       dict(state_time),
        "current_stats":    current_stats,
        "shoot_cycles":     shoot_cycles,
        "outtake_cycles":   outtake_cycles,
        "hoot_motors":      hoot_motors,
        "hoot_files_used":  hoot_files_used,
        "max_motor_temp_c": max_motor_temp_c,
    }

# -- Per-log report --------------------------------------------------------------

def _print_cycle_table(label, cycles):
    if not cycles:
        print(f"\n  {label}: (none)")
        return
    print()
    print(f"  {label} ({len(cycles)}):")
    print()
    print(f"  {'#':>2}  {'Start':>7}  {'End':>7}  {'Dur':>5}  "
          f"{'Req':>6}  {'ActL':>6}  {'ActR':>6}  {'OK?':>4}  "
          f"{'Is_avg':>7}  {'Is_pk':>6}  {'E (J)':>6}")
    print(f"  {'-'*2}  {'-'*7}  {'-'*7}  {'-'*5}  "
          f"{'-'*6}  {'-'*6}  {'-'*6}  {'-'*4}  "
          f"{'-'*7}  {'-'*6}  {'-'*6}")
    for i, c in enumerate(cycles):
        if c["stalled"]:
            ok = "STAL"
        elif c["reached"]:
            ok = "YES"
        elif abs(c["req_rps"]) < MIN_REQ_SPEED:
            ok = "n/a"
        else:
            ok = "no"
        print(f"  {i+1:>2}  {c['t_start']:>7.1f}  {c['t_end']:>7.1f}  "
              f"{c['dur']:>4.2f}s  "
              f"{c['req_rps']:>6.1f}  {c['act_L']:>6.1f}  {c['act_R']:>6.1f}  {ok:>4}  "
              f"{c['I_stat_avg']:>7.1f}  {c['I_stat_pk']:>6.1f}  "
              f"{c['E_J']:>6.1f}")

def print_per_log_report(r):
    log_name = os.path.basename(r["log_path"])
    session_len = r["session_len"]

    print()
    print(SEP)
    print(f"  FEEDER ANALYSIS  --  {log_name}")
    print(SEP)
    print(f"\n  Log duration            : {session_len:.1f} s  ({session_len/60:.2f} min)")
    print(f"  Peak speed (Left/Right) : {r['max_speed_L']:.1f} / {r['max_speed_R']:.1f} RPS")
    print(f"  Total feeder energy     : {r['total_energy_J']/1000:.2f} kJ")
    print(f"  SHOOTING cycles         : {r['n_shooting']}")
    print(f"  OUTTAKING cycles        : {r['n_outtaking']}")
    if r.get("max_motor_temp_c") is not None:
        print(f"  Peak motor temp         : {r['max_motor_temp_c']:.1f} °C  "
              f"(across both feeder motors, from hoot)")
    if r.get("hoot_files_used"):
        print(f"  Hoot data merged from   : {len(r['hoot_files_used'])} file(s)")
        for hp in r["hoot_files_used"]:
            print(f"      - {os.path.basename(hp)}")

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

    print()
    print(f"  Time in each Feeder State:")
    print(f"  {'State':>12}  {'Time (s)':>10}  {'% of log':>8}")
    print(f"  {'-'*12}  {'-'*10}  {'-'*8}")
    for st in STATES:
        t = r["state_time"].get(st, 0.0)
        pct = (100 * t / session_len) if session_len > 0 else 0.0
        print(f"  {st:>12}  {t:>10.1f}  {pct:>7.1f}%")

    print()
    print(f"  {'Current draw':35s}  {'Mean (A)':>9}  {'Peak (A)':>9}")
    print(f"  {'-'*35}  {'-'*9}  {'-'*9}")
    for row in r["current_stats"]:
        print(f"  {row['label']:35s}  {row['mean']:>9.1f}  {row['peak']:>9.1f}")

    _print_cycle_table("SHOOTING cycles",  r["shoot_cycles"])
    _print_cycle_table("OUTTAKING cycles", r["outtake_cycles"])

    cycles = r["shoot_cycles"]
    if cycles:
        dur_arr = np.array([c["dur"]        for c in cycles])
        E_arr   = np.array([c["E_J"]        for c in cycles])
        I_avg   = np.array([c["I_stat_avg"] for c in cycles])
        I_pk    = np.array([c["I_stat_pk"]  for c in cycles])
        n_reached = sum(1 for c in cycles if c["reached"])
        n_stalled = sum(1 for c in cycles if c["stalled"])
        print()
        print(f"  Shoot cycle stats:")
        print(f"    Reached {int(AT_SPEED_FRACTION*100)}% of reqSpeed : {n_reached} / {len(cycles)}")
        print(f"    Stalled (<{int(STALL_FRACTION*100)}% reqSpeed) : {n_stalled}")
        print(f"    Avg duration         : {np.mean(dur_arr):.2f} s  "
              f"(min {np.min(dur_arr):.2f}, max {np.max(dur_arr):.2f})")
        print(f"    Avg energy / cycle   : {np.mean(E_arr):.1f} J  "
              f"(min {np.min(E_arr):.1f}, max {np.max(E_arr):.1f})")
        print(f"    Avg stator current   : {np.mean(I_avg):.1f} A  "
              f"(peak up to {np.max(I_pk):.1f} A)")

    print()
    print(SEP)

# -- Combined / season report ----------------------------------------------------

def print_combined_analysis(results):
    n_matches = len(results)
    if n_matches == 0:
        return

    print()
    print(SEP)
    print(f"  FEEDER ANALYSIS  --  SEASON SUMMARY  ({n_matches} match{'es' if n_matches != 1 else ''})")
    print(SEP)

    print()
    print(f"  {'#':>2}  {'Match':<38}  {'Dur(s)':>7}  {'Shoot':>5}  {'Outtk':>5}  {'kJ':>6}")
    print(f"  {'-'*2}  {'-'*38}  {'-'*7}  {'-'*5}  {'-'*5}  {'-'*6}")
    for i, r in enumerate(results):
        name = os.path.basename(r["log_path"])
        if len(name) > 38:
            name = name[:35] + "..."
        print(f"  {i+1:>2}  {name:<38}  {r['session_len']:>7.1f}  "
              f"{r['n_shooting']:>5d}  {r['n_outtaking']:>5d}  "
              f"{r['total_energy_J']/1000:>6.2f}")

    all_shoots   = [c for r in results for c in r["shoot_cycles"]]
    all_outtakes = [c for r in results for c in r["outtake_cycles"]]
    total_shooting  = sum(r["n_shooting"]  for r in results)
    total_outtaking = sum(r["n_outtaking"] for r in results)
    total_energy_J  = sum(r["total_energy_J"] for r in results)
    total_session   = sum(r["session_len"] for r in results)

    print()
    print(f"  Totals across all matches:")
    print(f"    SHOOTING cycles      : {total_shooting}")
    print(f"    OUTTAKING cycles     : {total_outtaking}")
    print(f"    Feeder energy        : {total_energy_J/1000:.2f} kJ")
    print(f"    Combined log time    : {total_session:.1f} s  ({total_session/60:.2f} min)")

    print()
    print(f"  Per-match averages:")
    print(f"    SHOOTING cycles/match: {total_shooting / n_matches:.1f}")
    print(f"    Energy/match         : {(total_energy_J / n_matches) / 1000:.2f} kJ")

    if all_shoots:
        dur_arr = np.array([c["dur"]        for c in all_shoots])
        E_arr   = np.array([c["E_J"]        for c in all_shoots])
        I_avg   = np.array([c["I_stat_avg"] for c in all_shoots])
        I_pk    = np.array([c["I_stat_pk"]  for c in all_shoots])
        print()
        print(f"  SHOOTING cycle stats ({len(all_shoots)} cycles total):")
        print(f"    Avg duration         : {np.mean(dur_arr):.2f} s  "
              f"(min {np.min(dur_arr):.2f}, max {np.max(dur_arr):.2f})")
        print(f"    Avg energy / cycle   : {np.mean(E_arr):.1f} J  "
              f"(min {np.min(E_arr):.1f}, max {np.max(E_arr):.1f})")
        print(f"    Avg stator current   : {np.mean(I_avg):.1f} A  "
              f"(peak up to {np.max(I_pk):.1f} A)")

    if all_outtakes:
        dur = np.array([c["dur"] for c in all_outtakes])
        E   = np.array([c["E_J"] for c in all_outtakes])
        print()
        print(f"  OUTTAKING cycle stats ({len(all_outtakes)} cycles total):")
        print(f"    Avg duration         : {np.mean(dur):.2f} s")
        print(f"    Avg energy / cycle   : {np.mean(E):.1f} J")

    state_totals = Counter()
    for r in results:
        for st, t in r["state_time"].items():
            state_totals[st] += t
    print()
    print(f"  Time distribution across all matches:")
    print(f"    {'State':>12}  {'Total (s)':>10}  {'% of all logs':>14}")
    print(f"    {'-'*12}  {'-'*10}  {'-'*14}")
    for st in STATES:
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
            uniq.append(abs_p); seen.add(abs_p)
    return uniq

def parse_cli(argv):
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    summary_out = os.path.join(reports_dir, "feeder_summary.md")
    matches_out = os.path.join(reports_dir, "feeder_matches.md")
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
        f"# {title}", "",
        f"_Generated: {now}_", "",
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
            print(f"\nWARNING: required feeder signals missing in {p}.")
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
        write_markdown_report("Feeder Analysis - Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Feeder Analysis - Season Summary",
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

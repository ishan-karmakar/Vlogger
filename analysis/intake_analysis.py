# -*- coding: utf-8 -*-
"""
Intake energy & performance analysis for FRC Team Valor 6800.

Two motors : Left Intake Motor, Right Intake Motor
Cycle model: Intake State transitions (OFF <-> INTAKING)
Power      : |Out Volt| x |Stator Current| per motor, summed
"""

import sys
import os
import numpy as np
from collections import defaultdict, Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import vlogger

# -- Configuration ---------------------------------------------------------------

_log_abs = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "logs", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")
LOG_PATH = f"wpilog:///{_log_abs}"

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

AT_SPEED_FRACTION = 0.80    # "reached commanded speed" threshold
MIN_CYCLE_SECS    = 0.10    # ignore INTAKING blips shorter than this
STALL_FRACTION    = 0.30    # below this fraction of reqSpeed -> stalled / jammed
MIN_REQ_SPEED     = 1.0

# -- Data loading ----------------------------------------------------------------

def load_series():
    raw = defaultdict(list)
    print("Loading log ...")
    src = vlogger.get_source(LOG_PATH, INTAKE_REGEX)
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
    for name in raw:
        raw[name].sort(key=lambda x: x[0])
    return dict(raw)

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

# -- Main ------------------------------------------------------------------------

def main():
    series = load_series()

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

    if ts_ls is None or ts_rs is None:
        print("ERROR: Intake motor speed data not found.")
        sys.exit(1)
    if not state_pts:
        print("ERROR: Intake State data not found.")
        sys.exit(1)

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
    session_len    = ts_grid[-1] - t0
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

    # -- INTAKING cycles
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

    # -- Total jam events (rising edges across whole log)
    total_jams = 0
    prev       = None
    for ts, val in jam_pts:
        v = bool(val)
        if prev is not None and (not prev) and v:
            total_jams += 1
        prev = v

    # -- Report ------------------------------------------------------------------
    SEP = "-" * 72

    print()
    print(SEP)
    print("  INTAKE ANALYSIS  --  FRC Team Valor 6800")
    print(SEP)
    print(f"\n  Log duration            : {session_len:.1f} s  ({session_len/60:.2f} min)")
    print(f"  Peak speed (Left/Right) : {max_speed_L:.1f} / {max_speed_R:.1f} RPS")
    print(f"  Total intake energy     : {total_energy_J/1000:.2f} kJ")
    print(f"  Total jam events        : {total_jams}  (rising edges of Intake Jam)")
    print(f"  INTAKING cycles         : {len(intaking_windows)}")
    print(f"  SHOOTING cycles         : {len(shooting_windows)}")

    # -- Time distribution in each state
    print()
    print(f"  Time in each Intake State:")
    print(f"  {'State':>12}  {'Time (s)':>10}  {'% of log':>8}")
    print(f"  {'-'*12}  {'-'*10}  {'-'*8}")
    for st in ("OFF", "INTAKING", "SHOOTING"):
        t = state_time.get(st, 0.0)
        print(f"  {st:>12}  {t:>10.1f}  {100*t/session_len:>7.1f}%")

    # -- Overall current draw
    print()
    print(f"  {'Current draw':35s}  {'Mean (A)':>9}  {'Peak (A)':>9}")
    print(f"  {'-'*35}  {'-'*9}  {'-'*9}")
    print(f"  {'Left  stator':35s}  {np.mean(np.abs(lsc_g)):>9.1f}  {np.max(np.abs(lsc_g)):>9.1f}")
    print(f"  {'Right stator':35s}  {np.mean(np.abs(rsc_g)):>9.1f}  {np.max(np.abs(rsc_g)):>9.1f}")
    print(f"  {'Combined stator':35s}  {np.mean(stator_tot):>9.1f}  {np.max(stator_tot):>9.1f}")
    print(f"  {'Left  supply':35s}  {np.mean(np.abs(lsp_g)):>9.1f}  {np.max(np.abs(lsp_g)):>9.1f}")
    print(f"  {'Right supply':35s}  {np.mean(np.abs(rsp_g)):>9.1f}  {np.max(np.abs(rsp_g)):>9.1f}")
    print(f"  {'Combined supply':35s}  {np.mean(supply_tot):>9.1f}  {np.max(supply_tot):>9.1f}")

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

    # -- Jam analysis section ---------------------------------------------------
    print()
    print(SEP)
    print("  JAM ANALYSIS")
    print(SEP)

    if jam_pts:
        # Compute time spent in jammed state
        jam_time  = 0.0
        jam_edges = []
        prev_ts   = None
        prev_val  = None
        for ts, val in jam_pts:
            if prev_val is True and prev_ts is not None:
                jam_time += (ts - prev_ts)
            if prev_val is not True and val is True:
                jam_edges.append(ts)
            prev_ts  = ts
            prev_val = bool(val)

        print(f"\n  Total jam events (rising edges): {len(jam_edges)}")
        print(f"  Total time in jammed state     : {jam_time:.1f} s  "
              f"({100*jam_time/session_len:.1f}% of log)")
        if jam_edges:
            print(f"  Jam events (timestamp / intake cycle #):")
            print(f"  {'Time (s)':>9}  {'During Cycle':>13}  {'State at t':>11}")
            print(f"  {'-'*9}  {'-'*13}  {'-'*11}")
            for t_jam in jam_edges:
                # Locate which cycle (if any) we're in at this moment
                cyc_idx = next((i + 1 for i, c in enumerate(cycles)
                                if c["t_start"] <= t_jam <= c["t_end"]), None)
                # State at that time
                st = next((v for (ts, v) in reversed(state_pts) if ts <= t_jam), "?")
                cyc_str = f"#{cyc_idx}" if cyc_idx else "-"
                print(f"  {t_jam:>9.2f}  {cyc_str:>13}  {st:>11}")
    else:
        print("\n  No Intake Jam data found.")

    # -- SHOOTING state analysis ------------------------------------------------
    print()
    print(SEP)
    print("  SHOOTING STATE (feeder running into flywheel)")
    print(SEP)

    if shooting_windows:
        shoot_E    = []
        shoot_dur  = []
        shoot_I    = []
        for ts, te in shooting_windows:
            shoot_dur.append(te - ts)
            shoot_E.append(energy_in_window(ts_grid, power_tot, ts, te))
            shoot_I.append(mean_in_window(ts_grid, stator_tot, ts, te))

        shoot_dur = np.array(shoot_dur)
        shoot_E   = np.array(shoot_E)
        shoot_I   = np.array(shoot_I)

        print(f"\n  SHOOTING windows     : {len(shooting_windows)}")
        print(f"  Avg duration         : {np.mean(shoot_dur):.2f} s  "
              f"(min {np.min(shoot_dur):.2f}, max {np.max(shoot_dur):.2f})")
        print(f"  Avg energy (intake)  : {np.mean(shoot_E):.1f} J  "
              f"(min {np.min(shoot_E):.1f}, max {np.max(shoot_E):.1f})")
        print(f"  Avg stator current   : {np.mean(shoot_I):.1f} A")

    print()
    print(SEP)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\nAborted by user.\n")
        sys.exit(130)

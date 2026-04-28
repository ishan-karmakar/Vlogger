# -*- coding: utf-8 -*-
"""
Joystick / gamepad input analysis for FRC Team Valor 6800.

Two gamepads are assumed:
  joystick0 = Driver
  joystick1 = Operator

Per-match and season-wide stats are produced for:
  - Axis activity (min / max / mean |value| / active fraction)
  - Button press counts (rising edges per button)
  - POV / D-pad presses (per direction)

Usage:
    python joystick_analysis.py                          # default log
    python joystick_analysis.py logs/                    # directory (recursive)
    python joystick_analysis.py logs/*.wpilog            # glob
    python joystick_analysis.py -j 8 logs/               # 8 workers
    python joystick_analysis.py --no-file logs/          # terminal only
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import vlogger

# -- Configuration ---------------------------------------------------------------

DEFAULT_LOG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "logs", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")

JS_REGEX = r"(DS:joystick[0-9]+/(axes|buttons|povs)|DS:(enabled|autonomous))"
REGEX = JS_REGEX  # canonical name for the GUI's combined-decode path

# Which joysticks to analyze, plus human-readable role labels.
# Based on the season logs: joystick1 is the active driver controller (heavy
# stick usage for swerve driving); joystick0 is the operator (buttons for
# mechanism triggers). Adjust if the DS slot assignment changes.
JOYSTICK_ROLES = {
    1: "Driver",
    0: "Operator",
}

# Standard Xbox controller mapping. Axes are 0-indexed; buttons are 0-indexed in the
# raw log (WPILib APIs treat buttons as 1-indexed, so we display both).
AXIS_LABELS = {
    0: "Left X",
    1: "Left Y",
    2: "Left Trigger",
    3: "Right Trigger",
    4: "Right X",
    5: "Right Y",
}
BUTTON_LABELS = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "LB",
    5: "RB",
    6: "Back",
    7: "Start",
    8: "LStick",
    9: "RStick",
    # Synthetic keys for trigger-as-button (index 100 + axis index)
    102: "LT>thresh",
    103: "RT>thresh",
}

# Triggers behave like buttons: count rising edges through TRIGGER_THRESHOLD.
# Synthetic button key = 100 + axis index, so they don't collide with 0-9.
TRIGGER_THRESHOLD = 0.8
TRIGGER_AS_BUTTON = {
    2: 102,   # LT
    3: 103,   # RT
}
POV_DIRECTIONS = {
    0:   "Up",
    45:  "UpRight",
    90:  "Right",
    135: "DownRight",
    180: "Down",
    225: "DownLeft",
    270: "Left",
    315: "UpLeft",
}

# (label, x_axis_index, y_axis_index) pairs used for stick-magnitude analysis.
STICK_PAIRS = [
    ("Left Stick",  0, 1),
    ("Right Stick", 4, 5),
]

AXIS_DEADBAND = 0.1    # |value| above this counts as "active"

# -------------------------------------------------------------------------------
# ACTION MAPPINGS — fill these in with what each button/axis/POV does on your
# robot. The summary report prints a mapping table from these dicts so readers
# know what each input controls. Leave a value as "" or omit the key for an
# unmapped input (it will render as "--").
# Structure: {joystick_id: {index/degrees: "action description"}}
# -------------------------------------------------------------------------------
# Mapping scraped from C:\Users\Jan\code\valor\robot (OIConstants + RobotContainer):
#   Driver   = CommandXboxController on port 1
#   Operator = CommandXboxController on port 0
# Button index is 0-based (log-array index); WPI button number is index+1.
BUTTON_ACTIONS = {
    1: {  # Driver (joystick1)
        0: "Setpoint rotation (A)",
        1: "(unused)",
        2: "Outtake (X)",
        3: "(unused)",
        4: "Vision aim (LB, held)",
        5: "Shoot (RB)",
        6: "Gyro reset / TOAST rotation (Back)",
        7: "(unused)",
        8: "(unused - LStick click)",
        9: "(unused - RStick click)",
        102: "Vision aim + flywheel spin-up (LT)",
        103: "Full shoot sequence (RT)",
    },
    0: {  # Operator (joystick0)
        0: "(unused)",
        1: "Intake OFF (B)",
        2: "(unused)",
        3: "(unused)",
        4: "(unused)",
        5: "(unused)",
        6: "(unused)",
        7: "(unused)",
        8: "(unused)",
        9: "(unused)",
        102: "(unused)",
        103: "Manual pivot override (RT)",
    },
}
POV_ACTIONS = {
    1: {  # Driver (joystick1)
        0:   "Rotation setpoint 0 deg (face forward)",
        90:  "Rotation setpoint toward alliance station",
        180: "Retract intake pivot",
        270: "Speed limit mode (1.0 m/s cap)",
    },
    0: {},  # Operator (joystick0) — no POV bindings
}
AXIS_ACTIONS = {
    1: {  # Driver (joystick1)
        0: "Drive translation X (strafe)",
        1: "Drive translation Y (fwd/back)",
        2: "Vision aim + flywheel spin-up (LT)",
        3: "Full shoot sequence (RT)",
        4: "Drive rotation (manual)",
        5: "(unused)",
    },
    0: {  # Operator (joystick0)
        0: "(unused)",
        1: "(unused)",
        2: "(unused)",
        3: "Manual pivot override (RT)",
        4: "(unused)",
        5: "(unused)",
    },
}

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading ----------------------------------------------------------------

def coerce_value(val):
    """Per-module value coercion used by load_series and the GUI's combined decoder.
    Joystick analysis preserves all values (axes/buttons/POVs are lists)."""
    return val

def load_series(log_path):
    """Return dict: name -> list[(ts_s, value)]. Preserves list values as-is."""
    raw = defaultdict(list)
    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, JS_REGEX)
    with src:
        for entry in src:
            name = entry["name"]
            ts   = entry["timestamp"] / 1e6
            raw[name].append((ts, coerce_value(entry["data"])))
    for name in raw:
        raw[name].sort(key=lambda x: x[0])
    return dict(raw)

# -- Helpers ---------------------------------------------------------------------

def compute_teleop_intervals(enabled_pts, auto_pts, t_end):
    """
    Return a list of (t_start, t_end) intervals where DS:enabled is True AND
    DS:autonomous is False — i.e. teleop time only. If auto_pts is empty, assume
    autonomous was False throughout.
    """
    # Merge-sort the two event streams into state changes we care about.
    events = []
    for ts, v in enabled_pts:
        events.append((ts, "enabled", bool(v)))
    for ts, v in auto_pts:
        events.append((ts, "auto", bool(v)))
    events.sort(key=lambda e: e[0])

    enabled   = False
    auto      = False
    intervals = []
    cur_start = None

    def in_teleop():
        return enabled and not auto

    for ts, kind, val in events:
        was = in_teleop()
        if kind == "enabled":
            enabled = val
        else:
            auto = val
        now = in_teleop()
        if not was and now:
            cur_start = ts
        elif was and not now and cur_start is not None:
            intervals.append((cur_start, ts))
            cur_start = None
    # Close open interval at t_end
    if cur_start is not None and in_teleop():
        intervals.append((cur_start, t_end))
    return intervals

def intervals_total(intervals):
    return float(sum(t1 - t0 for t0, t1 in intervals))

def overlap_with_intervals(a, b, intervals):
    """Return the total duration of overlap of [a, b] with the interval list."""
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

def total_true_time(bool_pts, t_end):
    """Sum seconds where a bool signal was True, bounded by t_end."""
    if not bool_pts:
        return 0.0
    total    = 0.0
    prev_ts  = None
    prev_val = None
    for ts, val in bool_pts:
        if prev_val is True and prev_ts is not None:
            total += min(ts, t_end) - prev_ts
        prev_ts  = ts
        prev_val = bool(val)
    if prev_val is True and prev_ts is not None and prev_ts < t_end:
        total += t_end - prev_ts
    return float(total)

def compute_axis_stats(axis_pts, intervals):
    """
    Given a list of (ts, [axis values]) samples and a list of teleop intervals,
    return a dict keyed by axis index with time-weighted stats over the union of
    the teleop intervals:
      - n_samples (samples whose timestamp falls inside teleop)
      - min, max, mean_abs (of samples inside teleop)
      - active_s: time spent with |value| > AXIS_DEADBAND (during teleop)
      - active_frac: active_s / total teleop duration
    """
    if not axis_pts or not intervals:
        return {}

    max_axes = 0
    for _, v in axis_pts:
        if isinstance(v, list):
            max_axes = max(max_axes, len(v))
    if max_axes == 0:
        return {}

    per_axis = {i: {"vals": [], "active_time": 0.0} for i in range(max_axes)}
    prev_ts  = None
    prev_vec = None
    t_last   = max(t1 for _, t1 in intervals)

    for ts, v in axis_pts:
        if ts > t_last:
            break
        if prev_vec is not None and prev_ts is not None:
            # Credit the PRIOR sample across any teleop overlap with [prev_ts, ts]
            for i, pv in enumerate(prev_vec):
                if abs(pv) > AXIS_DEADBAND:
                    per_axis[i]["active_time"] += overlap_with_intervals(prev_ts, ts, intervals)
        if isinstance(v, list):
            prev_vec = v
            if ts_in_intervals(ts, intervals):
                for i, pv in enumerate(v):
                    per_axis[i]["vals"].append(float(pv))
        prev_ts = ts

    # Trailing segment held until t_last
    if prev_vec is not None and prev_ts is not None:
        for i, pv in enumerate(prev_vec):
            if abs(pv) > AXIS_DEADBAND:
                per_axis[i]["active_time"] += overlap_with_intervals(prev_ts, t_last, intervals)

    duration = max(1e-9, intervals_total(intervals))
    out = {}
    for i, d in per_axis.items():
        vs = np.array(d["vals"]) if d["vals"] else np.array([0.0])
        out[i] = {
            "n":           len(d["vals"]),
            "min":         float(np.min(vs)),
            "max":         float(np.max(vs)),
            "mean_abs":    float(np.mean(np.abs(vs))),
            "active_frac": float(d["active_time"] / duration),
            "active_s":    float(d["active_time"]),
        }
    return out

def compute_stick_magnitude_stats(axes_pts, x_idx, y_idx, intervals):
    """
    Given axis samples and a teleop-interval list, return time-weighted magnitude
    statistics for a stick: mag = sqrt(x^2 + y^2).

    Samples are "held" until the next sample; integrals clip to the teleop
    intervals so the mean and active time exclude disabled/auto periods.
    Percentiles are taken across samples whose timestamp falls in teleop.
    """
    if not axes_pts or not intervals:
        return None

    mags          = []
    mag_integral  = 0.0
    active_time   = 0.0
    total_time    = 0.0
    peak          = 0.0
    prev_ts       = None
    prev_mag      = None
    t_last        = max(t1 for _, t1 in intervals)

    for ts, v in axes_pts:
        if ts > t_last:
            break
        if not isinstance(v, list) or len(v) <= max(x_idx, y_idx):
            continue
        x = float(v[x_idx])
        y = float(v[y_idx])
        mag = (x * x + y * y) ** 0.5
        if ts_in_intervals(ts, intervals):
            mags.append(mag)
            if mag > peak:
                peak = mag
        if prev_ts is not None and prev_mag is not None:
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                mag_integral += prev_mag * ov
                total_time   += ov
                if prev_mag > AXIS_DEADBAND:
                    active_time += ov
        prev_ts  = ts
        prev_mag = mag

    # Trailing held segment until end of the last teleop interval
    if prev_mag is not None and prev_ts is not None:
        ov = overlap_with_intervals(prev_ts, t_last, intervals)
        if ov > 0:
            mag_integral += prev_mag * ov
            total_time   += ov
            if prev_mag > AXIS_DEADBAND:
                active_time += ov

    if not mags or total_time <= 0:
        return None

    mags_np  = np.array(mags)
    duration = max(1e-9, intervals_total(intervals))
    return {
        "n":            len(mags),
        "mean_tw":      float(mag_integral / total_time),
        "mean_sample":  float(np.mean(mags_np)),
        "peak":         float(peak),
        "p50":          float(np.percentile(mags_np, 50)),
        "p90":          float(np.percentile(mags_np, 90)),
        "p95":          float(np.percentile(mags_np, 95)),
        "active_s":     float(active_time),
        "active_frac":  float(active_time / duration),
    }

def compute_button_presses(button_pts, intervals):
    """
    Count rising edges per button index that occur within a teleop interval.
    State is tracked across the full log so a press held from auto into teleop
    is NOT counted (no rising edge within teleop), but any fresh press during
    teleop is.
    """
    counts = defaultdict(int)
    prev   = None
    for ts, v in button_pts:
        if not isinstance(v, list):
            continue
        if prev is not None and ts_in_intervals(ts, intervals):
            n = max(len(prev), len(v))
            for i in range(n):
                prev_b = bool(prev[i]) if i < len(prev) else False
                cur_b  = bool(v[i])    if i < len(v)    else False
                if not prev_b and cur_b:
                    counts[i] += 1
        prev = v
    return dict(counts)

def compute_trigger_presses(axes_pts, intervals, threshold=TRIGGER_THRESHOLD):
    """
    Count rising edges through `threshold` for each trigger axis listed in
    TRIGGER_AS_BUTTON, only within teleop intervals. Returns a dict with the
    same shape as compute_button_presses, keyed by the synthetic button index
    (100+axis_index) so results can be merged into the button-press dict.
    """
    counts = defaultdict(int)
    prev   = None
    for ts, v in axes_pts:
        if not isinstance(v, list):
            continue
        if prev is not None and ts_in_intervals(ts, intervals):
            for axis_i, btn_key in TRIGGER_AS_BUTTON.items():
                if axis_i >= len(prev) or axis_i >= len(v):
                    continue
                prev_v = float(prev[axis_i])
                cur_v  = float(v[axis_i])
                if prev_v < threshold <= cur_v:
                    counts[btn_key] += 1
        prev = v
    return dict(counts)

def compute_pov_presses(pov_pts, intervals):
    """Count POV transitions into a new direction that occur during teleop."""
    counts = defaultdict(int)
    prev   = -1
    for ts, v in pov_pts:
        cur = v[0] if isinstance(v, list) and v else -1
        if cur != prev and cur != -1 and ts_in_intervals(ts, intervals):
            counts[int(cur)] += 1
        prev = cur
    return dict(counts)

# -- Per-log analysis ------------------------------------------------------------

def analyze_log(log_path):
    """Decode the log and run the analysis. Thin wrapper over analyze_from_series."""
    return analyze_from_series(load_series(log_path), log_path)

def analyze_from_series(series, log_path):
    """Run the joystick analysis on an already-decoded series dict. Returns a
    result dict, or None if no input data was logged.

    Split out so the GUI can decode a wpilog once and run multiple analyses
    against the same series dict (see gui/data.py:load_combined_series)."""
    enabled_pts = series.get("DS:enabled", [])
    auto_pts    = series.get("DS:autonomous", [])

    # Timespan: union of all joystick timestamps
    all_ts = []
    for role_id in JOYSTICK_ROLES:
        for field in ("axes", "buttons", "povs"):
            for ts, _ in series.get(f"DS:joystick{role_id}/{field}", []):
                all_ts.append(ts)
    if enabled_pts:
        all_ts.extend(ts for ts, _ in enabled_pts)
    if not all_ts:
        return None

    t_start = float(min(all_ts))
    t_end   = float(max(all_ts))

    enabled_s        = total_true_time(enabled_pts, t_end)
    teleop_intervals = compute_teleop_intervals(enabled_pts, auto_pts, t_end)
    teleop_s         = intervals_total(teleop_intervals)

    per_joy = {}
    for role_id, role_name in JOYSTICK_ROLES.items():
        axes_pts    = series.get(f"DS:joystick{role_id}/axes",    [])
        buttons_pts = series.get(f"DS:joystick{role_id}/buttons", [])
        povs_pts    = series.get(f"DS:joystick{role_id}/povs",    [])
        sticks = {}
        for name, xi, yi in STICK_PAIRS:
            s = compute_stick_magnitude_stats(axes_pts, xi, yi, teleop_intervals)
            if s is not None:
                sticks[name] = s
        # Regular button presses + trigger-as-button edges merged into one dict
        buttons = compute_button_presses(buttons_pts, teleop_intervals)
        for k, v in compute_trigger_presses(axes_pts, teleop_intervals).items():
            buttons[k] = buttons.get(k, 0) + v

        per_joy[role_id] = {
            "role":     role_name,
            "axes":     compute_axis_stats(axes_pts, teleop_intervals),
            "sticks":   sticks,
            "buttons":  buttons,
            "povs":     compute_pov_presses(povs_pts, teleop_intervals),
            "has_data": any(isinstance(v, list) and v for _, v in axes_pts),
        }

    result = {
        "log_path":     log_path,
        "session_len":  t_end - t_start,
        "enabled_s":    enabled_s,
        "teleop_s":     teleop_s,
        "joysticks":    per_joy,
    }
    # Drop the raw series dict before returning to keep the worker's RSS small.
    del series
    return result

# -- Per-log report --------------------------------------------------------------

def print_joystick_block(role_id, jdata):
    role = jdata["role"]
    if not jdata["has_data"]:
        print(f"\n  [{role} (joystick{role_id})]  (no data)")
        return

    print(f"\n  [{role} (joystick{role_id})]")

    # Axes
    axes = jdata["axes"]
    if axes:
        print(f"    Axis activity (|value| > {AXIS_DEADBAND}, teleop only):")
        print(f"    {'Ax':>3}  {'Label':<16}  {'Min':>6}  {'Max':>6}  "
              f"{'Mean|v|':>7}  {'Active':>7}  {'Active_s':>9}")
        print(f"    {'-'*3}  {'-'*16}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*7}  {'-'*9}")
        for i in sorted(axes):
            label = AXIS_LABELS.get(i, f"Axis{i}")
            s = axes[i]
            print(f"    {i:>3}  {label:<16}  {s['min']:>+6.2f}  {s['max']:>+6.2f}  "
                  f"{s['mean_abs']:>7.3f}  {100*s['active_frac']:>6.1f}%  "
                  f"{s['active_s']:>8.1f}s")

    # Stick magnitudes
    sticks = jdata.get("sticks", {})
    if sticks:
        print(f"    Stick magnitude (sqrt(x^2 + y^2), teleop only):")
        print(f"    {'Stick':<12}  {'Mean':>6}  {'p50':>5}  {'p90':>5}  "
              f"{'p95':>5}  {'Peak':>5}  {'Active':>7}  {'Active_s':>9}")
        print(f"    {'-'*12}  {'-'*6}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*5}  "
              f"{'-'*7}  {'-'*9}")
        for name in sticks:
            s = sticks[name]
            print(f"    {name:<12}  {s['mean_tw']:>6.3f}  {s['p50']:>5.2f}  "
                  f"{s['p90']:>5.2f}  {s['p95']:>5.2f}  {s['peak']:>5.2f}  "
                  f"{100*s['active_frac']:>6.1f}%  {s['active_s']:>8.1f}s")

    # Buttons (includes synthetic trigger-as-button edges at keys >= 100)
    btns = jdata["buttons"]
    if btns:
        total = sum(btns.values())
        actions = BUTTON_ACTIONS.get(role_id, {})
        print(f"    Button presses (total = {total}, teleop only, "
              f"triggers count edges through {TRIGGER_THRESHOLD:.1f}):")
        print(f"    {'Idx':>3}  {'WPI':>3}  {'Label':<10}  {'Count':>5}  {'Action':<32}")
        print(f"    {'-'*3}  {'-'*3}  {'-'*10}  {'-'*5}  {'-'*32}")
        for i in sorted(btns):
            label  = BUTTON_LABELS.get(i, f"B{i}")
            action = actions.get(i) or "--"
            wpi    = "-" if i >= 100 else str(i + 1)
            idx_s  = "t2" if i == 102 else "t3" if i == 103 else str(i)
            print(f"    {idx_s:>3}  {wpi:>3}  {label:<10}  {btns[i]:>5d}  {action:<32}")

    # POVs
    povs = jdata["povs"]
    if povs:
        total = sum(povs.values())
        actions = POV_ACTIONS.get(role_id, {})
        print(f"    POV/D-pad presses (total = {total}, teleop only):")
        print(f"    {'Direction':<10}  {'Count':>5}  {'Action':<28}")
        print(f"    {'-'*10}  {'-'*5}  {'-'*28}")
        for deg in sorted(povs):
            label  = POV_DIRECTIONS.get(deg, f"{deg} deg")
            action = actions.get(deg) or "--"
            print(f"    {label:<10}  {povs[deg]:>5d}  {action:<28}")

def print_per_log_report(r):
    print()
    print(SEP)
    print(f"  LOG: {os.path.basename(r['log_path'])}")
    print(SEP)
    print(f"  Duration     : {r['session_len']:.1f} s  ({r['session_len']/60:.2f} min)")
    print(f"  Enabled time : {r['enabled_s']:.1f} s  "
          f"({100*r['enabled_s']/r['session_len']:.1f}% of log)")
    tele_note = (f", {100*r['teleop_s']/r['enabled_s']:.1f}% of enabled"
                 if r['enabled_s'] > 0 else "")
    print(f"  Teleop time  : {r['teleop_s']:.1f} s  "
          f"({100*r['teleop_s']/r['session_len']:.1f}% of log{tele_note})")
    for role_id in sorted(JOYSTICK_ROLES):
        print_joystick_block(role_id, r["joysticks"][role_id])

# -- Combined analysis -----------------------------------------------------------

def print_combined_analysis(results):
    n_logs = len(results)
    print()
    print(SEP)
    print(f"  COMBINED JOYSTICK ANALYSIS ACROSS {n_logs} LOG{'S' if n_logs != 1 else ''}")
    print(SEP)

    total_session = sum(r["session_len"] for r in results)
    total_enabled = sum(r["enabled_s"]   for r in results)
    total_teleop  = sum(r["teleop_s"]    for r in results)
    print(f"\n  Total duration   : {total_session:.1f} s  ({total_session/60:.2f} min)")
    print(f"  Total enabled    : {total_enabled:.1f} s  ({total_enabled/60:.2f} min)")
    print(f"  Total teleop     : {total_teleop:.1f} s  ({total_teleop/60:.2f} min)")
    print(f"  (All per-joystick metrics below are measured during TELEOP only)")

    for role_id, role_name in JOYSTICK_ROLES.items():
        print()
        print(SEP)
        print(f"  [{role_name}] (joystick{role_id}) -- season summary")
        print(SEP)

        # Aggregate button presses across logs
        btn_totals = defaultdict(int)
        btn_counts_per_log = defaultdict(list)
        for r in results:
            for i, c in r["joysticks"][role_id]["buttons"].items():
                btn_totals[i] += c
                btn_counts_per_log[i].append(c)

        btn_actions = BUTTON_ACTIONS.get(role_id, {})
        if btn_totals:
            grand_total = sum(btn_totals.values())
            print(f"\n  Button presses (total across all matches = {grand_total}, "
                  f"triggers count edges through {TRIGGER_THRESHOLD:.1f}):")
            print(f"  {'Idx':>3}  {'WPI':>3}  {'Label':<10}  "
                  f"{'Total':>6}  {'Per-match':>9}  {'Max':>4}  {'Action':<32}")
            print(f"  {'-'*3}  {'-'*3}  {'-'*10}  "
                  f"{'-'*6}  {'-'*9}  {'-'*4}  {'-'*32}")
            for i in sorted(btn_totals, key=lambda k: -btn_totals[k]):
                label   = BUTTON_LABELS.get(i, f"B{i}")
                action  = btn_actions.get(i) or "--"
                counts  = btn_counts_per_log[i]
                per_mat = btn_totals[i] / n_logs
                mx      = max(counts) if counts else 0
                wpi     = "-" if i >= 100 else str(i + 1)
                idx_s   = "t2" if i == 102 else "t3" if i == 103 else str(i)
                print(f"  {idx_s:>3}  {wpi:>3}  {label:<10}  "
                      f"{btn_totals[i]:>6d}  {per_mat:>9.1f}  {mx:>4d}  {action:<32}")

        # POV totals
        pov_totals = defaultdict(int)
        for r in results:
            for deg, c in r["joysticks"][role_id]["povs"].items():
                pov_totals[deg] += c
        pov_actions = POV_ACTIONS.get(role_id, {})
        if pov_totals:
            grand_total = sum(pov_totals.values())
            print(f"\n  POV/D-pad presses (total = {grand_total}, "
                  f"per-match avg = {grand_total/n_logs:.1f}):")
            print(f"    {'Direction':<10}  {'Total':>5}  {'Per-match':>9}  {'Action':<28}")
            print(f"    {'-'*10}  {'-'*5}  {'-'*9}  {'-'*28}")
            for deg in sorted(pov_totals):
                label  = POV_DIRECTIONS.get(deg, f"{deg} deg")
                action = pov_actions.get(deg) or "--"
                per_m  = pov_totals[deg] / n_logs
                print(f"    {label:<10}  {pov_totals[deg]:>5d}  {per_m:>9.1f}  {action:<28}")

        # Axis aggregates: combine min/max/mean weighted by sample count
        axis_agg = defaultdict(lambda: {"n":0, "min":+1e9, "max":-1e9,
                                         "mean_abs_wsum":0.0, "active_s":0.0})
        for r in results:
            for i, s in r["joysticks"][role_id]["axes"].items():
                a = axis_agg[i]
                a["n"]             += s["n"]
                a["min"]            = min(a["min"], s["min"])
                a["max"]            = max(a["max"], s["max"])
                a["mean_abs_wsum"] += s["mean_abs"] * s["n"]
                a["active_s"]      += s["active_s"]
        axis_actions = AXIS_ACTIONS.get(role_id, {})
        if axis_agg:
            print(f"\n  Axis activity (season totals, teleop only):")
            print(f"  {'Ax':>3}  {'Label':<16}  {'Min':>6}  {'Max':>6}  "
                  f"{'Mean|v|':>7}  {'Active_s':>9}  {'Active':>7}  {'Action':<28}")
            print(f"  {'-'*3}  {'-'*16}  {'-'*6}  {'-'*6}  "
                  f"{'-'*7}  {'-'*9}  {'-'*7}  {'-'*28}")
            for i in sorted(axis_agg):
                a           = axis_agg[i]
                label       = AXIS_LABELS.get(i, f"Axis{i}")
                action      = axis_actions.get(i) or "--"
                mean_ab     = a["mean_abs_wsum"] / a["n"] if a["n"] else 0.0
                active_frac = a["active_s"] / total_teleop if total_teleop else 0.0
                print(f"  {i:>3}  {label:<16}  {a['min']:>+6.2f}  {a['max']:>+6.2f}  "
                      f"{mean_ab:>7.3f}  {a['active_s']:>8.1f}s  "
                      f"{100*active_frac:>6.1f}%  {action:<28}")

        # Stick magnitude aggregates across matches (time-weighted means)
        stick_agg = defaultdict(lambda: {"mean_wsum": 0.0, "wsum": 0.0,
                                          "peak": 0.0, "active_s": 0.0})
        for r in results:
            for name, s in r["joysticks"][role_id].get("sticks", {}).items():
                w = s["n"]  # weight means by sample count within each match
                stick_agg[name]["mean_wsum"] += s["mean_tw"] * w
                stick_agg[name]["wsum"]     += w
                stick_agg[name]["peak"]      = max(stick_agg[name]["peak"], s["peak"])
                stick_agg[name]["active_s"] += s["active_s"]
        if stick_agg:
            print(f"\n  Stick magnitude (season, teleop only):")
            print(f"  {'Stick':<12}  {'Mean':>6}  {'Peak':>5}  "
                  f"{'Active_s':>9}  {'Active':>7}")
            print(f"  {'-'*12}  {'-'*6}  {'-'*5}  {'-'*9}  {'-'*7}")
            for name in stick_agg:
                a   = stick_agg[name]
                m   = a["mean_wsum"] / a["wsum"] if a["wsum"] else 0.0
                af  = a["active_s"] / total_teleop if total_teleop else 0.0
                print(f"  {name:<12}  {m:>6.3f}  {a['peak']:>5.2f}  "
                      f"{a['active_s']:>8.1f}s  {100*af:>6.1f}%")

    # Cross-gamepad summary: total actions per match
    print()
    print(SEP)
    print("  BUSY-NESS SUMMARY (actions per match)")
    print(SEP)
    print(f"\n  {'Role':<10}  {'Avg btns':>9}  {'Avg POV':>8}  {'Avg total':>10}")
    print(f"  {'-'*10}  {'-'*9}  {'-'*8}  {'-'*10}")
    for role_id, role_name in JOYSTICK_ROLES.items():
        btn_per = []
        pov_per = []
        for r in results:
            btn_per.append(sum(r["joysticks"][role_id]["buttons"].values()))
            pov_per.append(sum(r["joysticks"][role_id]["povs"].values()))
        a_b = np.mean(btn_per) if btn_per else 0.0
        a_p = np.mean(pov_per) if pov_per else 0.0
        print(f"  {role_name:<10}  {a_b:>9.1f}  {a_p:>8.1f}  {a_b + a_p:>10.1f}")

    print()
    print(SEP)

# -- CLI / IO --------------------------------------------------------------------

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
    summary_out = os.path.join(reports_dir, "joystick_summary.md")
    matches_out = os.path.join(reports_dir, "joystick_matches.md")
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
            progress(f"[{done}/{n}] {os.path.basename(p)} — {dt:.1f}s")
    except KeyboardInterrupt:
        progress("Interrupted — cancelling remaining workers ...")
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
            print(f"\nWARNING: no joystick data in {p}.")
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
        write_markdown_report("Joystick Analysis — Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Joystick Analysis — Season Summary",
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

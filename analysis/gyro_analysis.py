# -*- coding: utf-8 -*-
"""
Pigeon2 gyro + accelerometer analysis for FRC Team Valor 6800.

Metrics:
  - Yaw / pitch / roll during enabled time (range, max deflection, tilt events)
  - Angular velocity (mean / p95 / max magnitude)
  - Per-axis acceleration (x, y, z) during enabled time
  - Acceleration MAGNITUDE: time-weighted mean, percentiles, peak
  - G-shock event detection: crossings through HIGH_G_THRESHOLD (in g), with
    timestamps + peak magnitude so the driver can go review the moment
  - Tilt events: time where |pitch| or |roll| > TILT_THRESHOLD_DEG
  - Alliance (from FMS when connected + enabled, same three-tier logic as
    limelight_analysis.py) for cross-tagging shock events

Units:
  - Yaw/pitch/roll: degrees (yaw is unwrapped — accumulates across full spins)
  - Acceleration: m/s^2 as logged; converted to g for "shock" thresholds
    (1 g = 9.80665 m/s^2)
  - Angular velocity: as-logged (source signal may be deg/s or rad/s; the
    script reports values unchanged — investigate robot code for units if
    the numbers look wrong)

Same CLI conventions as the other analysis scripts:
    python gyro_analysis.py                       # default log
    python gyro_analysis.py logs/                 # recursive directory scan
    python gyro_analysis.py -j 8 logs/            # 8 workers
    python gyro_analysis.py --no-file logs/       # terminal only
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

# Signal paths — Pigeon yaw/pitch/roll + angular velocity + accel are all
# republished under SmartDashboard/SwerveDrive/.
F_YAW    = "NT:/SmartDashboard/SwerveDrive/Gyro Yaw"
F_PITCH  = "NT:/SmartDashboard/SwerveDrive/Gyro Pitch"
F_ROLL   = "NT:/SmartDashboard/SwerveDrive/Gyro Roll"
F_ANGVEL = "NT:/SmartDashboard/SwerveDrive/Angular Velocity"
F_ACCEL  = "NT:/SmartDashboard/SwerveDrive/Acceleration"   # double[3]: [x, y, z] m/s^2

LIMELIGHTS = ["limelight-center", "limelight-left", "limelight-right"]

GYRO_REGEX = (
    r"(NT:/SmartDashboard/SwerveDrive/(Gyro (Yaw|Pitch|Roll)|Angular Velocity|Acceleration)"
    r"|NT:/limelight-(center|left|right)/imu"
    r"|NT:/FMSInfo/(IsRedAlliance|FMSControlData)"
    r"|DS:(enabled|autonomous))"
)

# Limelight IMU array layout — index into NT:/limelight-<cam>/imu
# (from official Limelight 4 docs):
#   [0]=robotYaw_set, [1]=roll(deg), [2]=pitch(deg), [3]=yaw(deg)
#   [4..6]=gyroX/Y/Z (deg/s)
#   [7..9]=accelX/Y/Z (g)
LL_IMU_ROLL, LL_IMU_PITCH, LL_IMU_YAW        = 1, 2, 3
LL_IMU_GX,   LL_IMU_GY,    LL_IMU_GZ         = 4, 5, 6
LL_IMU_AX,   LL_IMU_AY,    LL_IMU_AZ         = 7, 8, 9

# Physical + analysis constants
G_MS2 = 9.80665            # 1 g in m/s^2

# Threshold (in g) for flagging a "shock" event. Normal matchplay bumps are
# 1-2 g; hard contact / bumper crashes hit 3+ g. Tune to taste.
HIGH_G_THRESHOLD_G = 3.0

# Degrees — |pitch| or |roll| above this counts as a "tilt" event. A flat field
# should stay within a few degrees; 10+ degrees usually means tipping or
# driving onto a ramp/edge.
TILT_THRESHOLD_DEG = 10.0

# Used to fuse near-simultaneous shock peaks into one event so a single bumper
# hit doesn't register 20 times in a row.
SHOCK_DEBOUNCE_S = 0.25

# FMS bit (matches limelight_analysis.py)
FMS_ATTACHED_BIT = 1 << 4

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading ----------------------------------------------------------------

def load_series(log_path):
    raw = defaultdict(list)
    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, GYRO_REGEX)
    with src:
        for entry in src:
            name = entry["name"]
            ts   = entry["timestamp"] / 1e6
            raw[name].append((ts, entry["data"]))
    for name in raw:
        raw[name].sort(key=lambda x: x[0])
    return dict(raw)

# -- Interval + lookup helpers (mirror limelight_analysis.py) --------------------

def compute_enabled_intervals(enabled_pts, t_end):
    intervals = []
    cur_start = None
    for ts, val in enabled_pts:
        if bool(val) and cur_start is None:
            cur_start = ts
        elif not bool(val) and cur_start is not None:
            intervals.append((cur_start, ts))
            cur_start = None
    if cur_start is not None:
        intervals.append((cur_start, t_end))
    return intervals

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

def _build_searchable(pts, value_fn=lambda v: v):
    if not pts:
        return np.array([]), []
    ts_arr = np.array([ts for ts, _ in pts])
    vals   = [value_fn(v) for _, v in pts]
    return ts_arr, vals

def _lookup_at(ts, ts_arr, vals, default=None):
    if len(ts_arr) == 0:
        return default
    idx = int(np.searchsorted(ts_arr, ts, side="right")) - 1
    return vals[idx] if idx >= 0 else default

# -- Alliance detection (copied + trimmed from limelight_analysis.py) ------------

def detect_alliance(series):
    red_pts  = series.get("NT:/FMSInfo/IsRedAlliance", [])
    ctrl_pts = series.get("NT:/FMSInfo/FMSControlData", [])
    en_pts   = series.get("DS:enabled", [])
    fms_ts, fms_v = _build_searchable(ctrl_pts,
                                       lambda v: bool(int(v) & FMS_ATTACHED_BIT))
    en_ts,  en_v  = _build_searchable(en_pts, lambda v: bool(v))
    red_ts, red_v = _build_searchable(red_pts, lambda v: bool(v))
    transitions = sorted(set(list(fms_ts) + list(en_ts)))
    for ts in transitions:
        if (_lookup_at(ts, fms_ts, fms_v, default=False) and
            _lookup_at(ts, en_ts,  en_v,  default=False)):
            val = _lookup_at(ts, red_ts, red_v, default=None)
            if val is not None:
                return "red" if val else "blue"
    return None

# -- Signal aggregators ----------------------------------------------------------

def time_weighted_stats(pts, intervals, t_end, take_abs=False):
    """
    Time-weighted mean + sample-based min / p50 / p95 / max over enabled
    intervals. Non-finite values are dropped from stats but counted in
    n_invalid so 'inf' flags (e.g. sensor saturation) don't silently skew.

    If take_abs=True, use |value| for both the integral and the samples
    (useful for yaw-rate / angular-velocity where sign flips are symmetric).
    """
    if not pts or not intervals:
        return None
    samples = []
    integral = 0.0
    total_time = 0.0
    n_invalid = 0
    prev_ts = None
    prev_val = None
    for ts, v in pts:
        if not isinstance(v, (int, float)):
            continue
        fv = float(v)
        if take_abs:
            fv = abs(fv)
        finite = np.isfinite(fv)
        if ts_in_intervals(ts, intervals):
            if finite:
                samples.append(fv)
            else:
                n_invalid += 1
        if prev_ts is not None and prev_val is not None and np.isfinite(prev_val):
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                integral += prev_val * ov
                total_time += ov
        prev_ts = ts
        prev_val = fv
    if prev_ts is not None and prev_val is not None and np.isfinite(prev_val):
        ov = overlap_with_intervals(prev_ts, t_end, intervals)
        if ov > 0:
            integral += prev_val * ov
            total_time += ov
    if not samples or total_time <= 0:
        return None
    arr = np.array(samples)
    return {
        "n":         len(samples),
        "n_invalid": n_invalid,
        "mean":      float(integral / total_time),
        "min":       float(np.min(arr)),
        "p50":       float(np.percentile(arr, 50)),
        "p95":       float(np.percentile(arr, 95)),
        "max":       float(np.max(arr)),
    }

def time_fraction_above(pts, threshold_abs, intervals, t_end):
    """Fraction of enabled time where |value| > threshold_abs."""
    if not pts or not intervals:
        return 0.0
    cross_time = 0.0
    prev_ts = None
    prev_val = None
    for ts, v in pts:
        if not isinstance(v, (int, float)):
            continue
        if prev_ts is not None and prev_val is not None and abs(prev_val) > threshold_abs:
            cross_time += overlap_with_intervals(prev_ts, ts, intervals)
        prev_ts = ts
        prev_val = float(v)
    if prev_ts is not None and prev_val is not None and abs(prev_val) > threshold_abs:
        cross_time += overlap_with_intervals(prev_ts, t_end, intervals)
    total = intervals_total(intervals)
    return cross_time / total if total > 0 else 0.0

def analyze_acceleration(accel_pts, intervals, t_end):
    """
    Parse [ax, ay, az] samples, compute per-axis time-weighted stats, magnitude
    stats, and a debounced list of G-shock events (peak-|mag|/timestamp pairs).
    """
    if not accel_pts or not intervals:
        return None

    samples_by_axis = [[], [], []]
    mag_samples     = []
    integrals       = [0.0, 0.0, 0.0]
    mag_integral    = 0.0
    total_time      = 0.0
    prev_ts         = None
    prev_vec        = None
    prev_mag        = None

    # For shock-event detection we walk samples in order, track whether we're
    # currently above threshold, and record peaks on the way down.
    threshold_ms2 = HIGH_G_THRESHOLD_G * G_MS2
    shock_events  = []     # list of dicts {"ts", "peak_ms2", "peak_g"}
    in_event      = False
    event_peak    = 0.0
    event_peak_ts = 0.0
    last_shock_ts = -1e9

    for ts, v in accel_pts:
        if not isinstance(v, list) or len(v) < 3:
            continue
        try:
            ax = float(v[0]); ay = float(v[1]); az = float(v[2])
        except (TypeError, ValueError):
            continue
        mag = (ax*ax + ay*ay + az*az) ** 0.5

        in_window = ts_in_intervals(ts, intervals)
        if in_window:
            samples_by_axis[0].append(ax)
            samples_by_axis[1].append(ay)
            samples_by_axis[2].append(az)
            mag_samples.append(mag)

        # Time-weighted integration using PRIOR sample held over the gap
        if prev_ts is not None and prev_vec is not None:
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                integrals[0] += prev_vec[0] * ov
                integrals[1] += prev_vec[1] * ov
                integrals[2] += prev_vec[2] * ov
                mag_integral += prev_mag     * ov
                total_time   += ov

        # Shock-event state machine — only fires inside enabled intervals
        if in_window:
            if mag >= threshold_ms2:
                if not in_event:
                    in_event   = True
                    event_peak = mag
                    event_peak_ts = ts
                elif mag > event_peak:
                    event_peak    = mag
                    event_peak_ts = ts
            else:
                if in_event:
                    # Closed out an event — debounce against previous
                    if event_peak_ts - last_shock_ts >= SHOCK_DEBOUNCE_S:
                        shock_events.append({
                            "ts":       event_peak_ts,
                            "peak_ms2": event_peak,
                            "peak_g":   event_peak / G_MS2,
                        })
                        last_shock_ts = event_peak_ts
                    in_event = False
                    event_peak = 0.0

        prev_ts  = ts
        prev_vec = (ax, ay, az)
        prev_mag = mag

    # Close trailing event if log ends mid-shock
    if in_event and (event_peak_ts - last_shock_ts >= SHOCK_DEBOUNCE_S):
        shock_events.append({
            "ts":       event_peak_ts,
            "peak_ms2": event_peak,
            "peak_g":   event_peak / G_MS2,
        })

    # Trailing held segment for time-weighted integrals
    if prev_ts is not None and prev_vec is not None:
        ov = overlap_with_intervals(prev_ts, t_end, intervals)
        if ov > 0:
            integrals[0] += prev_vec[0] * ov
            integrals[1] += prev_vec[1] * ov
            integrals[2] += prev_vec[2] * ov
            mag_integral += prev_mag     * ov
            total_time   += ov

    if not mag_samples or total_time <= 0:
        return None

    def axis_summary(arr, integral):
        a = np.array(arr)
        return {
            "mean_tw":    integral / total_time,
            "mean_samp":  float(np.mean(a)),
            "min":        float(np.min(a)),
            "max":        float(np.max(a)),
            "abs_max":    float(np.max(np.abs(a))),
        }

    mag_arr = np.array(mag_samples)
    return {
        "n":              len(mag_samples),
        "axes":           {
            "x": axis_summary(samples_by_axis[0], integrals[0]),
            "y": axis_summary(samples_by_axis[1], integrals[1]),
            "z": axis_summary(samples_by_axis[2], integrals[2]),
        },
        "mag_mean_tw":    float(mag_integral / total_time),
        "mag_mean_samp":  float(np.mean(mag_arr)),
        "mag_p50":        float(np.percentile(mag_arr, 50)),
        "mag_p95":        float(np.percentile(mag_arr, 95)),
        "mag_max":        float(np.max(mag_arr)),
        "mag_max_g":      float(np.max(mag_arr) / G_MS2),
        "shock_events":   shock_events,
        "shock_count":    len(shock_events),
    }

def analyze_ll_imu(imu_pts, intervals, t_end):
    """
    Pull roll/pitch/yaw + accel (in g) from a Limelight IMU series. Gyro fields
    are skipped for now — the Pigeon is the authoritative body-rate source.

    Returns None if no usable samples. Accel threshold uses HIGH_G_THRESHOLD_G
    directly (already in g).
    """
    if not imu_pts or not intervals:
        return None

    # Build per-field (ts, value) sublists on-the-fly; some samples may be
    # shorter than 10 values if the LL publisher was caught mid-update.
    roll_pts, pitch_pts, yaw_pts = [], [], []
    # Accel tracking analogous to analyze_acceleration (but in g already)
    mag_samples  = []
    mag_integral = 0.0
    total_time   = 0.0
    prev_ts      = None
    prev_vec     = None
    prev_mag     = None
    shock_events  = []
    in_event      = False
    event_peak    = 0.0
    event_peak_ts = 0.0
    last_shock_ts = -1e9

    for ts, v in imu_pts:
        if not isinstance(v, list) or len(v) < 10:
            continue
        try:
            ax = float(v[LL_IMU_AX]); ay = float(v[LL_IMU_AY]); az = float(v[LL_IMU_AZ])
            roll  = float(v[LL_IMU_ROLL])
            pitch = float(v[LL_IMU_PITCH])
            yaw   = float(v[LL_IMU_YAW])
        except (TypeError, ValueError):
            continue
        mag_g = (ax*ax + ay*ay + az*az) ** 0.5

        in_win = ts_in_intervals(ts, intervals)
        if in_win:
            roll_pts.append((ts, roll))
            pitch_pts.append((ts, pitch))
            yaw_pts.append((ts, yaw))
            mag_samples.append(mag_g)

        if prev_ts is not None and prev_mag is not None:
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                mag_integral += prev_mag * ov
                total_time   += ov

        if in_win:
            if mag_g >= HIGH_G_THRESHOLD_G:
                if not in_event:
                    in_event     = True
                    event_peak   = mag_g
                    event_peak_ts = ts
                elif mag_g > event_peak:
                    event_peak    = mag_g
                    event_peak_ts = ts
            else:
                if in_event:
                    if event_peak_ts - last_shock_ts >= SHOCK_DEBOUNCE_S:
                        shock_events.append({
                            "ts":     event_peak_ts,
                            "peak_g": event_peak,
                        })
                        last_shock_ts = event_peak_ts
                    in_event = False
                    event_peak = 0.0

        prev_ts  = ts
        prev_vec = (ax, ay, az)
        prev_mag = mag_g

    if in_event and (event_peak_ts - last_shock_ts >= SHOCK_DEBOUNCE_S):
        shock_events.append({"ts": event_peak_ts, "peak_g": event_peak})

    if prev_ts is not None and prev_mag is not None:
        ov = overlap_with_intervals(prev_ts, t_end, intervals)
        if ov > 0:
            mag_integral += prev_mag * ov
            total_time   += ov

    if not mag_samples or total_time <= 0:
        return None

    mag_arr = np.array(mag_samples)
    return {
        "n":               len(mag_samples),
        "roll":            time_weighted_stats(roll_pts,  intervals, t_end),
        "pitch":           time_weighted_stats(pitch_pts, intervals, t_end),
        "yaw":             time_weighted_stats(yaw_pts,   intervals, t_end),
        "mag_mean_tw":     float(mag_integral / total_time),
        "mag_p50":         float(np.percentile(mag_arr, 50)),
        "mag_p95":         float(np.percentile(mag_arr, 95)),
        "mag_max":         float(np.max(mag_arr)),
        "shock_events":    shock_events,
        "shock_count":     len(shock_events),
    }

# -- Per-log analysis ------------------------------------------------------------

def analyze_log(log_path):
    series = load_series(log_path)
    enabled_pts = series.get("DS:enabled", [])

    # Union of all signal timestamps for log span
    all_ts = [ts for ts, _ in enabled_pts]
    for key in (F_YAW, F_PITCH, F_ROLL, F_ANGVEL, F_ACCEL):
        for ts, _ in series.get(key, []):
            all_ts.append(ts)
    if not all_ts:
        return None

    t_end = float(max(all_ts))
    enabled_intervals = compute_enabled_intervals(enabled_pts, t_end)
    enabled_s         = intervals_total(enabled_intervals)
    if enabled_s <= 0:
        return None

    yaw_pts   = series.get(F_YAW,    [])
    pitch_pts = series.get(F_PITCH,  [])
    roll_pts  = series.get(F_ROLL,   [])
    angv_pts  = series.get(F_ANGVEL, [])
    acc_pts   = series.get(F_ACCEL,  [])

    # Yaw: we want NET rotation (unwrapped final - initial during enabled) plus
    # min/max/range. Use raw samples within enabled windows.
    yaw_samples = [float(v) for ts, v in yaw_pts
                   if isinstance(v, (int, float)) and ts_in_intervals(ts, enabled_intervals)]
    yaw_info = None
    if yaw_samples:
        yaw_arr = np.array(yaw_samples)
        yaw_info = {
            "n":        len(yaw_arr),
            "min":      float(np.min(yaw_arr)),
            "max":      float(np.max(yaw_arr)),
            "first":    float(yaw_arr[0]),
            "last":     float(yaw_arr[-1]),
            "net":      float(yaw_arr[-1] - yaw_arr[0]),   # total rotation (deg)
            "range":    float(np.max(yaw_arr) - np.min(yaw_arr)),
        }

    pitch_stats = time_weighted_stats(pitch_pts, enabled_intervals, t_end)
    roll_stats  = time_weighted_stats(roll_pts,  enabled_intervals, t_end)
    pitch_tilt  = time_fraction_above(pitch_pts, TILT_THRESHOLD_DEG,
                                       enabled_intervals, t_end)
    roll_tilt   = time_fraction_above(roll_pts,  TILT_THRESHOLD_DEG,
                                       enabled_intervals, t_end)

    angv_abs_stats = time_weighted_stats(angv_pts, enabled_intervals, t_end,
                                          take_abs=True)

    accel = analyze_acceleration(acc_pts, enabled_intervals, t_end)

    # Per-Limelight IMU
    ll_imus = {}
    for cam in LIMELIGHTS:
        imu_pts = series.get(f"NT:/{cam}/imu", [])
        ll_imus[cam] = analyze_ll_imu(imu_pts, enabled_intervals, t_end)

    alliance = detect_alliance(series)

    result = {
        "log_path":     log_path,
        "session_len":  t_end,
        "enabled_s":    enabled_s,
        "alliance":     alliance,
        "yaw":          yaw_info,
        "pitch":        pitch_stats,
        "roll":         roll_stats,
        "pitch_tilt":   pitch_tilt,   # fraction of enabled time |pitch| > tilt threshold
        "roll_tilt":    roll_tilt,
        "angv_abs":     angv_abs_stats,
        "accel":        accel,
        "ll_imus":      ll_imus,
    }
    del series
    return result

# -- Report helpers --------------------------------------------------------------

def _fmt_stat(s, unit="", decimals=2):
    if s is None:
        return "(no samples)"
    f = f"{{:.{decimals}f}}"
    return (f"mean {f.format(s['mean'])}, p50 {f.format(s['p50'])}, "
            f"p95 {f.format(s['p95'])}, max {f.format(s['max'])} "
            f"{unit}(n={s['n']})").strip()

def print_per_log_report(r):
    print()
    print(SEP)
    print(f"  LOG: {os.path.basename(r['log_path'])}")
    print(SEP)
    ally = r.get("alliance")
    ally_str = ally.upper() if ally else "(unknown)"
    print(f"  Enabled time : {r['enabled_s']:.1f} s")
    print(f"  Our alliance : {ally_str}")

    # Yaw
    y = r.get("yaw")
    if y:
        full_spins = y["range"] / 360.0
        print(f"\n  [Yaw]  (Gyro Yaw, unwrapped degrees)")
        print(f"    Range            : {y['min']:+.1f} to {y['max']:+.1f} deg  "
              f"(span {y['range']:.1f} deg = {full_spins:.2f} full turns)")
        print(f"    Net rotation     : {y['net']:+.1f} deg  "
              f"(final {y['last']:+.1f} - first {y['first']:+.1f})")

    # Pitch / Roll
    for label, stat, tilt_frac in (("Pitch", r["pitch"], r["pitch_tilt"]),
                                     ("Roll",  r["roll"],  r["roll_tilt"])):
        if stat is None:
            continue
        print(f"\n  [{label}]  (degrees, time-weighted)")
        print(f"    {_fmt_stat(stat, unit='deg ')}")
        print(f"    Max |deflection| : {max(abs(stat['min']), abs(stat['max'])):.2f} deg")
        print(f"    Time > {TILT_THRESHOLD_DEG:.0f} deg     : "
              f"{100 * tilt_frac:.2f}% of enabled time")

    # Angular velocity
    av = r.get("angv_abs")
    if av:
        print(f"\n  [Angular velocity]  (absolute value, time-weighted)")
        print(f"    {_fmt_stat(av, decimals=3)}")
        print(f"    (units as-logged; verify against robot code for deg/s vs rad/s)")

    # Acceleration
    a = r.get("accel")
    if a:
        print(f"\n  [Acceleration]  ({a['n']} samples, m/s^2 unless noted)")
        for axis in ("x", "y", "z"):
            s = a["axes"][axis]
            print(f"    {axis.upper()} axis  : mean_tw {s['mean_tw']:+6.3f}, "
                  f"range [{s['min']:+6.2f}, {s['max']:+6.2f}], "
                  f"abs max {s['abs_max']:6.2f} m/s^2")
        print(f"    Magnitude      : mean_tw {a['mag_mean_tw']:.2f}, "
              f"p50 {a['mag_p50']:.2f}, p95 {a['mag_p95']:.2f} m/s^2")
        print(f"    Peak magnitude : {a['mag_max']:.2f} m/s^2  "
              f"(= {a['mag_max_g']:.2f} g)")
        print(f"    G-shock events >{HIGH_G_THRESHOLD_G:.1f} g : "
              f"{a['shock_count']}")
        if a["shock_events"]:
            top = sorted(a["shock_events"], key=lambda e: -e["peak_g"])[:5]
            print(f"    Top {len(top)} shock events:")
            print(f"    {'t (s)':>8}  {'peak g':>7}  {'peak m/s^2':>11}")
            print(f"    {'-'*8}  {'-'*7}  {'-'*11}")
            for e in top:
                print(f"    {e['ts']:>8.2f}  {e['peak_g']:>7.2f}  "
                      f"{e['peak_ms2']:>11.2f}")

    # Limelight IMUs (separate from Pigeon — each LL has its own onboard IMU)
    ll_imus = r.get("ll_imus", {})
    for cam in LIMELIGHTS:
        ll = ll_imus.get(cam)
        if ll is None:
            print(f"\n  [LL IMU: {cam}]  (no samples)")
            continue
        print(f"\n  [LL IMU: {cam}]  ({ll['n']} samples)")
        for label, stat in (("Roll",  ll["roll"]),
                             ("Pitch", ll["pitch"]),
                             ("Yaw",   ll["yaw"])):
            if stat is None:
                continue
            print(f"    {label:<6s}: {_fmt_stat(stat, unit='deg ')}")
        print(f"    Accel mag (g)  : mean_tw {ll['mag_mean_tw']:.2f}, "
              f"p50 {ll['mag_p50']:.2f}, p95 {ll['mag_p95']:.2f}, max {ll['mag_max']:.2f}")
        print(f"    Shock events >{HIGH_G_THRESHOLD_G:.1f} g : {ll['shock_count']}")
        if ll["shock_events"]:
            top = sorted(ll["shock_events"], key=lambda e: -e["peak_g"])[:3]
            for e in top:
                print(f"      t={e['ts']:>7.2f}s  peak {e['peak_g']:.2f} g")

# -- Combined analysis -----------------------------------------------------------

def _merge_tw_stats(stat_list):
    """Merge a list of time_weighted_stats dicts (weight means by n)."""
    stat_list = [s for s in stat_list if s is not None]
    if not stat_list:
        return None
    total_n = sum(s["n"] for s in stat_list)
    if total_n == 0:
        return None
    return {
        "n":    total_n,
        "mean": sum(s["mean"] * s["n"] for s in stat_list) / total_n,
        "min":  float(np.min([s["min"] for s in stat_list])),
        "p50":  float(np.median([s["p50"] for s in stat_list])),
        "p95":  float(np.max([s["p95"] for s in stat_list])),
        "max":  float(np.max([s["max"] for s in stat_list])),
    }

def print_combined_analysis(results):
    n_logs = len(results)
    print()
    print(SEP)
    print(f"  COMBINED GYRO ANALYSIS ACROSS {n_logs} LOG{'S' if n_logs != 1 else ''}")
    print(SEP)

    total_enabled = sum(r["enabled_s"] for r in results)
    red  = sum(1 for r in results if r["alliance"] == "red")
    blue = sum(1 for r in results if r["alliance"] == "blue")
    unknown = n_logs - red - blue
    print(f"\n  Total enabled time across logs : {total_enabled:.1f} s  "
          f"({total_enabled/60:.2f} min)")
    print(f"  Alliance distribution          : RED={red}, BLUE={blue}"
          + (f", unknown={unknown}" if unknown else ""))

    # Yaw / orientation
    yaws = [r["yaw"] for r in results if r["yaw"]]
    if yaws:
        nets     = [y["net"] for y in yaws]
        ranges   = [y["range"] for y in yaws]
        print(f"\n  [Yaw] aggregate across matches:")
        print(f"    Avg |net rotation| / match : {np.mean(np.abs(nets)):.1f} deg")
        print(f"    Max |net rotation|         : {np.max(np.abs(nets)):.1f} deg")
        print(f"    Avg range / match          : {np.mean(ranges):.1f} deg  "
              f"({np.mean(ranges)/360:.2f} turns)")
        print(f"    Max range                  : {np.max(ranges):.1f} deg  "
              f"({np.max(ranges)/360:.2f} turns)")

    # Pitch / Roll aggregate
    for label, key, tilt_key in (("Pitch", "pitch", "pitch_tilt"),
                                   ("Roll",  "roll",  "roll_tilt")):
        merged = _merge_tw_stats([r[key] for r in results])
        if merged is None:
            continue
        max_abs = np.max([max(abs(r[key]["min"]), abs(r[key]["max"]))
                           for r in results if r[key]])
        tilt_frac_w = sum(r[tilt_key] * r["enabled_s"] for r in results) / total_enabled
        print(f"\n  [{label}] season totals:")
        print(f"    {_fmt_stat(merged, unit='deg ')}")
        print(f"    Worst |deflection|  : {max_abs:.2f} deg")
        print(f"    Time > {TILT_THRESHOLD_DEG:.0f} deg      : "
              f"{100 * tilt_frac_w:.2f}% of enabled time")

    # Angular velocity
    av_merged = _merge_tw_stats([r["angv_abs"] for r in results])
    if av_merged:
        print(f"\n  [Angular velocity] season (|value|):")
        print(f"    {_fmt_stat(av_merged, decimals=3)}")

    # Acceleration + G-shock aggregate
    accels = [r["accel"] for r in results if r["accel"]]
    if accels:
        print(f"\n  [Acceleration] season totals:")
        total_n = sum(a["n"] for a in accels)
        for axis in ("x", "y", "z"):
            mean_tw = (sum(a["axes"][axis]["mean_tw"] * a["n"] for a in accels) /
                       total_n) if total_n else 0.0
            axis_abs_max = max(a["axes"][axis]["abs_max"] for a in accels)
            axis_min = min(a["axes"][axis]["min"] for a in accels)
            axis_max = max(a["axes"][axis]["max"] for a in accels)
            print(f"    {axis.upper()} axis  : mean_tw {mean_tw:+6.3f}, "
                  f"range [{axis_min:+6.2f}, {axis_max:+6.2f}], "
                  f"abs max {axis_abs_max:6.2f} m/s^2")
        mag_mean_tw = sum(a["mag_mean_tw"] * a["n"] for a in accels) / total_n
        mag_max_g   = max(a["mag_max_g"] for a in accels)
        mag_max_ms2 = max(a["mag_max"]   for a in accels)
        print(f"    Magnitude      : mean_tw {mag_mean_tw:.2f} m/s^2")
        print(f"    Season peak    : {mag_max_ms2:.2f} m/s^2 = {mag_max_g:.2f} g")

        total_shocks = sum(a["shock_count"] for a in accels)
        print(f"    G-shock events >{HIGH_G_THRESHOLD_G:.1f} g : {total_shocks}  "
              f"(avg {total_shocks/n_logs:.1f} per match)")

        # Top shock events across the season, tagged with log + alliance
        all_shocks = []
        for r in results:
            if not r["accel"]:
                continue
            match = os.path.basename(r["log_path"])
            ally  = r.get("alliance") or "?"
            for e in r["accel"]["shock_events"]:
                all_shocks.append({**e, "match": match, "alliance": ally})
        if all_shocks:
            top = sorted(all_shocks, key=lambda e: -e["peak_g"])[:15]
            print(f"\n  Top {len(top)} shock events (season):")
            print(f"  {'peak g':>7}  {'peak m/s^2':>11}  {'t (s)':>8}  "
                  f"{'Ally':>4}  {'Match':<45}")
            print(f"  {'-'*7}  {'-'*11}  {'-'*8}  {'-'*4}  {'-'*45}")
            for e in top:
                print(f"  {e['peak_g']:>7.2f}  {e['peak_ms2']:>11.2f}  "
                      f"{e['ts']:>8.2f}  {e['alliance']:>4}  {e['match']:<45}")

    # Per-Limelight IMU summary across matches (keep separate from Pigeon so
    # you can cross-check sensors and spot any LL mounted weirdly)
    print()
    print(SEP)
    print("  LIMELIGHT IMU SEASON SUMMARY (each LL's onboard IMU)")
    print(SEP)
    for cam in LIMELIGHTS:
        cam_data = [r["ll_imus"].get(cam) for r in results
                    if r.get("ll_imus") and r["ll_imus"].get(cam)]
        if not cam_data:
            print(f"\n  [{cam}]  (no usable samples across season)")
            continue
        print(f"\n  [{cam}]  ({sum(d['n'] for d in cam_data)} samples total)")
        for label, key in (("Roll",  "roll"),
                            ("Pitch", "pitch"),
                            ("Yaw",   "yaw")):
            merged = _merge_tw_stats([d[key] for d in cam_data])
            if merged is None:
                continue
            print(f"    {label:<6s}: {_fmt_stat(merged, unit='deg ')}")
        total_n     = sum(d["n"] for d in cam_data)
        mag_mean_tw = sum(d["mag_mean_tw"] * d["n"] for d in cam_data) / total_n
        mag_max     = max(d["mag_max"] for d in cam_data)
        total_sh    = sum(d["shock_count"] for d in cam_data)
        print(f"    Accel mag (g)  : mean_tw {mag_mean_tw:.2f}, "
              f"season peak {mag_max:.2f}")
        print(f"    Shock events   : {total_sh}  "
              f"(avg {total_sh/n_logs:.1f} per match)")
        # Top shocks across season for this camera
        all_cam_shocks = []
        for r in results:
            d = r.get("ll_imus", {}).get(cam)
            if not d:
                continue
            match = os.path.basename(r["log_path"])
            ally  = r.get("alliance") or "?"
            for e in d["shock_events"]:
                all_cam_shocks.append({**e, "match": match, "alliance": ally})
        if all_cam_shocks:
            top = sorted(all_cam_shocks, key=lambda e: -e["peak_g"])[:5]
            print(f"    Top {len(top)} shock events:")
            print(f"    {'peak g':>7}  {'t (s)':>7}  {'Ally':>4}  {'Match':<45}")
            print(f"    {'-'*7}  {'-'*7}  {'-'*4}  {'-'*45}")
            for e in top:
                print(f"    {e['peak_g']:>7.2f}  {e['ts']:>7.2f}  "
                      f"{e['alliance']:>4}  {e['match']:<45}")

    print()
    print(SEP)

# -- CLI / IO (mirrors the other analysis scripts) -------------------------------

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
    summary_out = os.path.join(reports_dir, "gyro_summary.md")
    matches_out = os.path.join(reports_dir, "gyro_matches.md")
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
    r  = analyze_log(p)
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
            print(f"\nWARNING: no gyro data in {p}.")
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
        write_markdown_report("Gyro / Pigeon IMU — Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Gyro / Pigeon IMU — Season Summary",
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

# -*- coding: utf-8 -*-
"""
Intake motor + jam analysis for FRC Team Valor 6800.

Two intake motors (Left / Right) and two feeder motors (Left / Right).
The robot publishes "Intake State" (OFF / INTAKING / SHOOTING) plus a
boolean "Intake Jam" that we cross-check with our own detector.

Metrics per match and across the season:
  - Per motor, per state: mean / p95 / max stator + supply current, |speed|
  - Time spent in each state; total time on + total energy (intake motors)
  - Robot-reported "Intake Jam" event count (rising edges of the bool)
  - Custom jam detector events — see JAM DETECTION section below

-------------------------------------------------------------------------------
ROBOT-SIDE JAM DETECTION (as of repo snapshot, src/main/cpp/subsystems/Intake.cpp)

One-sentence summary: "Intake Jam" = true iff
    (7-tap moving average of LEFT intake stator current >= 50 A)
    AND (LEFT intake motor speed < 1 TPS).

  - Only the LEFT intake motor is monitored; the right is ignored.
  - Only STATOR current is checked (not supply).
  - No debounce / hysteresis — the flag can toggle cycle-to-cycle (~20 ms).
  - No cooldown — a single physical jam typically re-triggers across
    many cycles as the motor briefly recovers speed.
  - On detect: rumble on the driver gamepad (0.1) and write the bool to
    NT. No automatic reversal, no state change, shooting still allowed.

Implications for our analysis:
  - The robot's rising-edge count under-reports physical jams because one
    stall can rumble continuously without a clean edge, or re-trigger
    many times for the same jam.
  - Right-side or feeder-side issues are invisible to the robot detector.

-------------------------------------------------------------------------------
CUSTOM JAM DETECTOR

  Per intake motor:
    stalled(motor, t) = (|stator_current(t)| >= CUSTOM_STALL_CURRENT_A)
                         AND (|speed(t)|          <  CUSTOM_STALL_SPEED_TPS)
                         AND (|reqSpeed(t)|       >= CUSTOM_MIN_REQ_SPEED)

  An event fires when ANY motor (left or right intake) has been stalled
  continuously for >= CUSTOM_MIN_DURATION_S. Event stays active until the
  motor recovers (current drops OR speed picks up) for at least
  CUSTOM_CLEAR_DURATION_S. A JAM_COOLDOWN_S window between events prevents
  the same physical jam from being counted multiple times.

  Each event is classified:
    LEFT_ONLY / RIGHT_ONLY / BOTH   (which motors were stalled)
    state                           (OFF / INTAKING / SHOOTING at event start)
    peak stator current, min speed during the stall, and duration

  Rationale vs the robot detector:
    - Both motors watched — catches right-side issues.
    - reqSpeed gate eliminates false positives when the intake is
      actively commanded OFF.
    - Debounce + cooldown collapses runs of re-triggers into single
      "jam events" that match what a driver would subjectively call one
      jam.
    - Slightly lower current threshold catches the onset of a stall
      before the motor fully hits the current limit.
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
import vlogger
# Shared CAN ID -> motor label config (edit analysis/can_config.py to update
# mappings when the robot CAN IDs change).
from can_config import CAN_DEVICES, CAN_DEVICES_BY_LABEL, SUBSYSTEMS

# -- Configuration ---------------------------------------------------------------

DEFAULT_LOG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "logs", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")

# Motors we track. Keyed by a short label used in output.
INTAKE_MOTORS = {
    "Left Intake":  "NT:/SmartDashboard/Intake/Left Intake Motor",
    "Right Intake": "NT:/SmartDashboard/Intake/Right Intake Motor",
}
FEEDER_MOTORS = {
    "Left Feeder":  "NT:/SmartDashboard/Intake/Left Feeder Motor",
    "Right Feeder": "NT:/SmartDashboard/Intake/Right Feeder Motor",
}
# Pivot is position-controlled (not speed-controlled like the others), so it
# gets analyzed in its own block with closed-loop error + position metrics.
PIVOT_MOTOR_BASE = "NT:/SmartDashboard/Intake/Pivot Motor"
PIVOT_STATE_PATH = "NT:/SmartDashboard/Intake/Pivot State"
# Pivot state values published by the robot (Intake.cpp PIVOT_STATE enum):
PIVOT_STATES = ["OFF", "RETRACTED", "DEPLOYED", "SHIMMY_IN", "SHIMMY_OUT"]

# |error| <= this (in native position units, typically rotations) counts as
# "at setpoint". Tune after observing actual error distributions.
PIVOT_AT_SETPOINT_TOLERANCE = 0.05

# Per motor we need: Speed, Stator Current, Supply Current, Out Volt, reqSpeed.
# Feeders don't publish Supply Current (handled gracefully by load_series).
SIGNALS_PER_MOTOR = ["Speed", "Stator Current", "Supply Current", "Out Volt", "reqSpeed"]

STATE_PATH = "NT:/SmartDashboard/Intake/Intake State"
JAM_PATH   = "NT:/SmartDashboard/Intake/Intake Jam"

INTAKE_REGEX = (
    r"(NT:/SmartDashboard/Intake/(Intake State|Intake Jam|Pivot State|"
    r"(Left|Right) (Intake|Feeder|Hopper) Motor/"
    r"(Speed|Stator Current|Supply Current|Out Volt|reqSpeed)|"
    r"Pivot Motor/(Speed|Stator Current|Supply Current|Out Volt|Position|reqPosition))"
    r"|DS:(enabled|autonomous))"
)

# Custom jam detector parameters — tune here if the physical intake changes.
CUSTOM_STALL_CURRENT_A   = 45.0   # |stator current| above this = stalled
CUSTOM_STALL_SPEED_TPS   = 2.0    # |speed| below this = stalled
CUSTOM_MIN_REQ_SPEED     = 1.0    # only count if we're actually commanding motion
CUSTOM_MIN_DURATION_S    = 0.15   # stall must persist this long to count
CUSTOM_CLEAR_DURATION_S  = 0.20   # recovery must persist this long before event ends
CUSTOM_COOLDOWN_S        = 0.50   # min gap between distinct jam events

# For reference / comparison in the report — these are the robot's thresholds.
ROBOT_JAM_CURRENT_A      = 50.0
ROBOT_JAM_SPEED_TPS      = 1.0

# --- Hoot integration (optional, higher-fidelity current + speed) -------------
# The intake + hopper motors are on the RIO CAN bus; feeder motors on the
# Canivore bus. A season's TXCMP log folder typically contains:
#   <match>_rio_<date>.hoot               -> intake, hopper
#   <match>_<canivore-serial>_<date>.hoot -> flywheel, feeder, swerve
# Both are scanned and merged via the shared can_config.CAN_DEVICES map.
# Only labels we actually want to overlay from hoot (the analyzer's motors).
HOOT_LABELS_TO_OVERLAY = (
    SUBSYSTEMS["intake"] + SUBSYSTEMS["hopper"] + SUBSYSTEMS["feeder"]
    + SUBSYSTEMS["intake_pivot"]
)

# CAN device label (from can_config.CAN_DEVICES) -> the NT path base used in
# the wpilog for that motor. Used by the hoot overlay to route hoot samples
# back to the same NT-style keys the rest of the analyzer expects. Most
# labels match directly (e.g. "Left Intake" -> "Left Intake Motor"), but a
# few need explicit translation — the pivot's NT path is just "Pivot Motor",
# not "Intake Pivot Motor".
HOOT_LABEL_TO_NT_BASE = {
    "Left Intake":  "NT:/SmartDashboard/Intake/Left Intake Motor",
    "Right Intake": "NT:/SmartDashboard/Intake/Right Intake Motor",
    "Left Hopper":  "NT:/SmartDashboard/Intake/Left Hopper Motor",
    "Right Hopper": "NT:/SmartDashboard/Intake/Right Hopper Motor",
    "Left Feeder":  "NT:/SmartDashboard/Intake/Left Feeder Motor",
    "Right Feeder": "NT:/SmartDashboard/Intake/Right Feeder Motor",
    "Intake Pivot": PIVOT_MOTOR_BASE,
}
# Hoot signal -> NT-style signal name. Hoot RotorVelocity is rotations/sec at
# the motor (matches the "TPS" semantics of NT Speed for our purposes — the
# jam detector uses ratios, not absolute speeds).
HOOT_SIGNAL_MAP = {
    "StatorCurrent":  "Stator Current",
    "SupplyCurrent":  "Supply Current",
    "RotorVelocity":  "Speed",
    "MotorVoltage":   "Out Volt",
}

# Signal-grouping helpers
INTAKE_STATES = ["OFF", "INTAKING", "SHOOTING"]

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading ----------------------------------------------------------------

def load_series(log_path):
    """
    Load NT series from a WPILog and (if a sibling .hoot log is found) overlay
    high-fidelity Phoenix signals for intake / feeder motor currents + speeds.
    The hoot overlay REPLACES the corresponding low-rate NT series on overlap
    (higher sample rate + more accurate during transients), but the NT series
    are still loaded so non-hoot signals (state, jam bool, reqSpeed) work
    unchanged.
    """
    raw = defaultdict(list)
    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, INTAKE_REGEX)
    with src:
        for entry in src:
            name = entry["name"]
            ts   = entry["timestamp"] / 1e6
            val  = entry["data"]
            raw[name].append((ts, val))
    for name in raw:
        raw[name].sort(key=lambda x: x[0])

    # Try to overlay hoot data when available. Tolerates missing owlet.
    # Walk every sibling hoot (both RIO + Canivore buses) since intake motors
    # live on RIO and feeders live on Canivore.
    for hoot_path in _find_sibling_hoots(log_path):
        try:
            _overlay_hoot_into(raw, hoot_path)
        except Exception as ex:
            sys.stderr.write(
                f"WARNING: hoot overlay for {os.path.basename(hoot_path)} "
                f"failed ({type(ex).__name__}: {ex}); using NT currents.\n")

    return dict(raw)

def _find_sibling_hoots(log_path):
    """
    Find every .hoot log in the same folder tree as the wpilog. We return
    ALL of them (not just one), because a season folder typically has both
    a RIO-bus hoot and a Canivore hoot — each with different motors — and
    we want to merge from both.
    """
    log_dir = os.path.dirname(os.path.abspath(log_path))
    hoots = []
    for root, _, files in os.walk(log_dir):
        for f in files:
            if f.lower().endswith(".hoot"):
                hoots.append(os.path.join(root, f))
    return sorted(hoots)

def _find_owlet():
    """Return path to owlet.exe — PATH first, then repo root fallback."""
    on_path = shutil.which("owlet")
    if on_path:
        return on_path
    repo_owlet = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                               "..", "owlet.exe"))
    return repo_owlet if os.path.isfile(repo_owlet) else None

def _owlet_scan(hoot_path, owlet_exe):
    """
    Run `owlet <hoot> --scan` and return a dict of signal_name -> hex_id.
    Scan is cheap (sub-second even for large hoots) because it just indexes
    the file without decoding values.

    Example input line:
        TalonFX-12/StatorCurrent:                                 6f30c00
    """
    result = subprocess.run(
        [owlet_exe, hoot_path, "--scan"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        check=False, text=True,
    )
    out = {}
    for line in (result.stdout or "").splitlines():
        # Lines look like "NAME:<spaces>HEXID" — split on ':' once and strip
        if ":" not in line:
            continue
        name, _, rest = line.partition(":")
        name = name.strip()
        hex_id = rest.strip()
        if name and hex_id and all(c in "0123456789abcdefABCDEF" for c in hex_id):
            out[name] = hex_id
    return out

def _wanted_hoot_signal_names():
    """Build the set of 'TalonFX-<id>/<SignalName>' entries we want from hoots."""
    names = set()
    for label in HOOT_LABELS_TO_OVERLAY:
        entry = CAN_DEVICES_BY_LABEL.get(label)
        if not entry:
            continue
        kind, can_id = entry
        if kind != "TalonFX":
            continue
        for hoot_sig in HOOT_SIGNAL_MAP.keys():
            names.add(f"{kind}-{can_id}/{hoot_sig}")
    return names

def _decode_hoot_filtered(hoot_path, owlet_exe, signal_ids):
    """
    Run `owlet <hoot> <tmp.wpilog> -f wpilog -s <ids>` to decode ONLY the
    signals we care about. Returns path to the output wpilog, or None if
    nothing usable was produced. Tolerates rc=1 from owlet when the output
    file is still valid (owlet emits "Could not read to end of input file"
    as a non-fatal warning at EOF).
    """
    if not signal_ids:
        return None
    tmp_dir = tempfile.mkdtemp(prefix="hoot_overlay_")
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
    """
    Stream a (small) filtered wpilog via wpiutil and return a dict of
    signal_name -> [(ts_seconds, float_value), ...] for signals in
    accepted_names. Matches names either exactly or by suffix (owlet often
    prefixes entries with "/CTRELogger/" or similar when writing wpilog —
    we match on the tail so configuration is easier).
    """
    from wpiutil.log import DataLogReader
    reader = DataLogReader(wpilog_path)
    entry_map = {}    # entry_id -> canonical signal name (key in accepted_names)
    out = defaultdict(list)

    # Build a lookup from suffix match
    def match_name(entry_name):
        if entry_name in accepted_names:
            return entry_name
        # Try matching by "<device>-<id>/<signal>" suffix anywhere in the entry
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
        canon = entry_map[eid]
        # All targets are doubles (stator/supply/voltage/velocity)
        try:
            val = rec.getDouble()
        except Exception:
            continue
        out[canon].append((rec.getTimestamp() / 1e6, float(val)))
    for name in out:
        out[name].sort(key=lambda x: x[0])
    return dict(out)

def _overlay_hoot_into(raw, hoot_path):
    """
    Overlay high-fidelity Phoenix current/speed samples from a hoot file onto
    the NT-sampled `raw` dict. Steps:
      1. owlet --scan (fast) -> build signal-name -> hex-ID map
      2. filter to the signals we care about
      3. owlet -s <ids> -f wpilog (filtered decode, fast)
      4. read the filtered wpilog and convert TalonFX-N/SignalName keys
         back to NT-style analyzer keys
      5. REPLACE the corresponding NT series in `raw`

    Bypasses vlogger.Hoot because check_call doesn't tolerate owlet's
    non-zero EOF warning, and we want the -s filter which vlogger doesn't
    currently pass through.
    """
    owlet_exe = _find_owlet()
    if not owlet_exe:
        raise RuntimeError("owlet not found on PATH or at repo root")

    wanted_names = _wanted_hoot_signal_names()
    if not wanted_names:
        return

    # Scan to get hex signal IDs for filter.
    name_to_id = _owlet_scan(hoot_path, owlet_exe)
    signal_ids = [name_to_id[n] for n in wanted_names if n in name_to_id]
    if not signal_ids:
        # No matching devices in this hoot (probably wrong bus) — silent skip.
        return

    # Decode only the signals we want.
    out_wpilog = _decode_hoot_filtered(hoot_path, owlet_exe, signal_ids)
    if out_wpilog is None:
        raise RuntimeError("owlet produced no output")

    try:
        hoot_samples = _read_filtered_wpilog(out_wpilog, wanted_names)
    finally:
        shutil.rmtree(os.path.dirname(out_wpilog), ignore_errors=True)

    # Convert hoot signal names (Phoenix6/TalonFX-<id>/<signal>, canonicalized
    # by _read_filtered_wpilog's suffix match to TalonFX-<id>/<signal>) to the
    # analyzer's NT-style keys and REPLACE in the series dict — hoot is higher
    # fidelity than NT-logged currents (event-driven at the Phoenix signal
    # level, typically 10-100x the sample count during motor activity).
    total_samples = 0
    replaced_keys = 0
    for hoot_name, pts in hoot_samples.items():
        try:
            head, signal = hoot_name.split("/", 1)
            kind, id_str = head.split("-", 1)
            can_id = int(id_str)
        except (ValueError, TypeError):
            continue
        motor_label = CAN_DEVICES.get((kind, can_id))
        nt_signal   = HOOT_SIGNAL_MAP.get(signal)
        if motor_label is None or nt_signal is None:
            continue
        # Route hoot samples back to the NT path the robot uses. The pivot's
        # NT base is "Pivot Motor" not "Intake Pivot Motor", hence the explicit
        # translation table.
        nt_base = HOOT_LABEL_TO_NT_BASE.get(motor_label)
        if nt_base is None:
            continue
        # Hoot RotorVelocity is motor-shaft TPS but the pivot NT key for
        # velocity is named "Speed". For the pivot we also want the *position*
        # overlaid, but hoot's RotorPosition is not in our signal list yet
        # (it'd need to be added to HOOT_SIGNAL_MAP). Leaving pivot position
        # from NT for now — it updates frequently enough to be usable.
        nt_key = f"{nt_base}/{nt_signal}"
        raw[nt_key] = pts
        total_samples += len(pts)
        replaced_keys += 1
    # One-line summary per hoot — useful to confirm overlay actually landed
    # without spamming the log.
    sys.stderr.write(
        f"[hoot] {os.path.basename(hoot_path)}: "
        f"{replaced_keys} signals, {total_samples:,} samples\n")

# -- Interval helpers (mirrors the other analysis scripts) -----------------------

def compute_state_intervals(state_pts, target_states, t_end):
    """
    Return a dict: state_name -> list of (t_start, t_end) intervals for each
    of target_states. Any unrecognized state values are ignored.
    """
    out = {s: [] for s in target_states}
    cur_state = None
    cur_start = None
    for ts, val in state_pts:
        s = val if isinstance(val, str) else None
        if s == cur_state:
            continue
        if cur_state is not None and cur_state in out and cur_start is not None:
            out[cur_state].append((cur_start, ts))
        cur_state = s
        cur_start = ts
    if cur_state is not None and cur_state in out and cur_start is not None:
        out[cur_state].append((cur_start, t_end))
    return out

def intersect_intervals(a, b):
    """Return intersection of two lists of (start,end) intervals."""
    out = []
    for (a0, a1) in a:
        for (b0, b1) in b:
            lo = max(a0, b0)
            hi = min(a1, b1)
            if hi > lo:
                out.append((lo, hi))
    return out

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

# -- Stats ---------------------------------------------------------------------

def time_weighted_abs_stats(pts, intervals, t_end):
    """
    Time-weighted mean of |value| plus sample-based p50/p95/max. Returns None
    if no samples. Used for current + speed (both are magnitudes we care about).
    """
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
        prev_ts = ts
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
    """
    Energy = integral of |V| * |I| dt over the union of intervals. Uses the
    common-grid interpolation approach so we don't need the signals to be
    sampled at the same points.
    """
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

    # Integrate only over portions of the grid inside the intervals
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

# -- Pivot analysis -------------------------------------------------------------

def _interp_signal(ts_arr, vals, target_ts):
    """Step-hold interpolation: for each ts in target_ts, return the last
    value at or before that ts (or None if before the first sample)."""
    if len(ts_arr) == 0:
        return [None] * len(target_ts)
    idx = np.searchsorted(ts_arr, target_ts, side="right") - 1
    out = []
    for i in idx:
        out.append(vals[i] if i >= 0 else None)
    return out

def analyze_pivot(series, enabled_intervals, t_end):
    """
    Pivot motor analysis: per Pivot State, report stator/supply current
    stats, position + reqPosition stats, and closed-loop error stats.
    Includes a "time at setpoint" metric (|error| <= PIVOT_AT_SETPOINT_TOLERANCE).

    Returns None if the pivot isn't logged in this match.
    """
    pos_pts  = series.get(f"{PIVOT_MOTOR_BASE}/Position", [])
    req_pts  = series.get(f"{PIVOT_MOTOR_BASE}/reqPosition", [])
    cst_pts  = series.get(f"{PIVOT_MOTOR_BASE}/Stator Current", [])
    sup_pts  = series.get(f"{PIVOT_MOTOR_BASE}/Supply Current", [])
    vlt_pts  = series.get(f"{PIVOT_MOTOR_BASE}/Out Volt", [])
    spd_pts  = series.get(f"{PIVOT_MOTOR_BASE}/Speed", [])
    state_pts = series.get(PIVOT_STATE_PATH, [])

    if not pos_pts and not cst_pts:
        return None

    # Per-state intervals (intersected with enabled, same approach as the
    # Intake State breakdown)
    raw_pivot_state_intervals = compute_state_intervals(state_pts, PIVOT_STATES, t_end)
    pivot_state_intervals = {
        s: intersect_intervals(raw_pivot_state_intervals[s], enabled_intervals)
        for s in PIVOT_STATES
    }
    pivot_state_secs = {s: intervals_total(pivot_state_intervals[s]) for s in PIVOT_STATES}

    # Closed-loop error: computed at each Position sample as
    #   error(t) = Position(t) - reqPosition_lookup(t)
    # reqPosition is held until next update, so step-hold interpolation is
    # the right semantic.
    error_pts = []
    if pos_pts and req_pts:
        pos_ts   = np.array([ts for ts, _ in pos_pts])
        pos_vals = np.array([float(v) for _, v in pos_pts])
        req_ts   = np.array([ts for ts, _ in req_pts])
        req_vals = [float(v) for _, v in req_pts]
        req_lookup = _interp_signal(req_ts, req_vals, pos_ts)
        for ts, pos, req in zip(pos_ts.tolist(), pos_vals.tolist(), req_lookup):
            if req is None:
                continue
            error_pts.append((ts, pos - req))

    # Time at setpoint per state (and overall enabled)
    def _time_at_setpoint(intervals):
        if not error_pts or not intervals:
            return 0.0
        t_in = 0.0
        prev_ts  = None
        prev_err = None
        for ts, err in error_pts:
            if prev_ts is not None and prev_err is not None:
                if abs(prev_err) <= PIVOT_AT_SETPOINT_TOLERANCE:
                    t_in += overlap_with_intervals(prev_ts, ts, intervals)
            prev_ts = ts
            prev_err = err
        # Trailing segment
        if prev_ts is not None and prev_err is not None:
            if abs(prev_err) <= PIVOT_AT_SETPOINT_TOLERANCE:
                t_last = max(t for t, _ in error_pts)
                t_in += overlap_with_intervals(prev_ts, t_last, intervals)
        return float(t_in)

    # Per-state metrics: stator, supply, |speed|, position, reqPosition,
    # |error|, and at-setpoint time
    per_state = {}
    for s in PIVOT_STATES + ["ENABLED"]:   # "ENABLED" = overall enabled time
        ivs = pivot_state_intervals[s] if s in pivot_state_intervals else enabled_intervals
        per_state[s] = {
            "seconds":    intervals_total(ivs),
            "stator":     time_weighted_abs_stats(cst_pts, ivs, t_end),
            "supply":     time_weighted_abs_stats(sup_pts, ivs, t_end),
            "speed":      time_weighted_abs_stats(spd_pts, ivs, t_end),
            # Position is signed, so report raw samples (not abs) for range
            "position":   _signed_stats(pos_pts, ivs, t_end),
            "reqPosition":_signed_stats(req_pts, ivs, t_end),
            "abs_error":  time_weighted_abs_stats(error_pts, ivs, t_end),
            "at_setpoint_s": _time_at_setpoint(ivs),
        }

    # Energy consumed by pivot over enabled time
    energy = energy_over_intervals(vlt_pts, cst_pts, enabled_intervals, t_end)

    return {
        "state_secs":    pivot_state_secs,
        "per_state":     per_state,
        "energy_J":      energy,
        "n_position":    len(pos_pts),
        "n_req":         len(req_pts),
        "n_error":       len(error_pts),
    }

def _signed_stats(pts, intervals, t_end):
    """Time-weighted mean + min/p5/p95/max on signed values (for position,
    where the sign matters — pivot retracted vs deployed)."""
    if not pts or not intervals:
        return None
    samples = []
    integral = 0.0
    total_time = 0.0
    prev_ts = None
    prev_v  = None
    for ts, v in pts:
        if not isinstance(v, (int, float)):
            continue
        fv = float(v)
        if ts_in_intervals(ts, intervals):
            samples.append(fv)
        if prev_ts is not None and prev_v is not None:
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                integral   += prev_v * ov
                total_time += ov
        prev_ts = ts
        prev_v  = fv
    if prev_ts is not None and prev_v is not None:
        ov = overlap_with_intervals(prev_ts, t_end, intervals)
        if ov > 0:
            integral   += prev_v * ov
            total_time += ov
    if not samples or total_time <= 0:
        return None
    arr = np.array(samples)
    return {
        "n":       len(samples),
        "mean_tw": float(integral / total_time),
        "min":     float(np.min(arr)),
        "p5":      float(np.percentile(arr, 5)),
        "p50":     float(np.percentile(arr, 50)),
        "p95":     float(np.percentile(arr, 95)),
        "max":     float(np.max(arr)),
    }

# -- Jam detection -------------------------------------------------------------

def count_rising_edges(bool_pts, intervals):
    """Count False -> True transitions within the given intervals."""
    if not bool_pts:
        return 0
    count = 0
    prev = None
    for ts, v in bool_pts:
        cur = bool(v)
        if prev is not None and not prev and cur and ts_in_intervals(ts, intervals):
            count += 1
        prev = cur
    return count

def build_per_motor_searchables(series, base_path):
    """Return (ts_arr, v_arr) tuples for speed / stator / reqSpeed under base_path."""
    out = {}
    for sig in ("Speed", "Stator Current", "reqSpeed"):
        key = f"{base_path}/{sig}"
        pts = series.get(key, [])
        ts_arr, vals = _build_searchable(pts, lambda v: float(v) if isinstance(v, (int, float)) else 0.0)
        out[sig] = (ts_arr, vals)
    return out

def detect_custom_jams(series, state_pts, intervals, t_end):
    """
    Custom jam detector: walks common-time grid, tracks whether each intake
    motor is in a stall condition, and emits debounced + cooldown-gated jam
    events.

    Returns list of dicts:
      {"t_start", "t_end", "duration", "state",
       "motors": ["Left Intake", ...], "peak_current_A", "min_speed_TPS"}
    """
    # Gather searchable arrays for each intake motor
    motor_data = {}
    all_ts = set()
    for label, base in INTAKE_MOTORS.items():
        motor_data[label] = build_per_motor_searchables(series, base)
        for sig in ("Speed", "Stator Current", "reqSpeed"):
            for ts in motor_data[label][sig][0].tolist():
                all_ts.add(ts)

    # State lookup
    state_ts, state_v = _build_searchable(state_pts, lambda v: v if isinstance(v, str) else "UNKNOWN")

    if not all_ts:
        return []

    ts_grid = np.array(sorted(all_ts))

    def stalled_at(motor, t):
        cur_ts, cur_v = motor_data[motor]["Stator Current"]
        spd_ts, spd_v = motor_data[motor]["Speed"]
        req_ts, req_v = motor_data[motor]["reqSpeed"]
        cur = _lookup_at(t, cur_ts, cur_v, default=0.0)
        spd = _lookup_at(t, spd_ts, spd_v, default=0.0)
        req = _lookup_at(t, req_ts, req_v, default=0.0)
        return (abs(cur) >= CUSTOM_STALL_CURRENT_A
                and abs(spd) <  CUSTOM_STALL_SPEED_TPS
                and abs(req) >= CUSTOM_MIN_REQ_SPEED), cur, spd

    events = []
    in_event = False
    event_start = None
    event_first_clear = None
    event_motors = set()
    event_peak_current = 0.0
    event_min_speed = float("inf")
    last_event_end = -1e9

    for t in ts_grid:
        if not ts_in_intervals(t, intervals):
            continue

        # Which motors are stalled right now?
        stalled_now = set()
        max_current_now = 0.0
        min_speed_now = float("inf")
        for motor in INTAKE_MOTORS:
            is_stall, cur, spd = stalled_at(motor, t)
            if is_stall:
                stalled_now.add(motor)
                max_current_now = max(max_current_now, abs(cur))
                min_speed_now = min(min_speed_now, abs(spd))

        if stalled_now:
            # Check cooldown gate before opening a new event
            if not in_event:
                if t - last_event_end < CUSTOM_COOLDOWN_S:
                    continue
                in_event = True
                event_start = t
                event_first_clear = None
                event_motors = set(stalled_now)
                event_peak_current = max_current_now
                event_min_speed = min_speed_now
            else:
                event_motors.update(stalled_now)
                event_peak_current = max(event_peak_current, max_current_now)
                event_min_speed    = min(event_min_speed,    min_speed_now)
                event_first_clear = None  # reset — we're still stalling
        else:
            if in_event:
                if event_first_clear is None:
                    event_first_clear = t
                elif (t - event_first_clear) >= CUSTOM_CLEAR_DURATION_S:
                    # Close out event — but only if it persisted long enough
                    duration = event_first_clear - event_start
                    if duration >= CUSTOM_MIN_DURATION_S:
                        state = _lookup_at(event_start, state_ts, state_v,
                                            default="UNKNOWN")
                        events.append({
                            "t_start":         float(event_start),
                            "t_end":           float(event_first_clear),
                            "duration":        float(duration),
                            "state":           state,
                            "motors":          sorted(event_motors),
                            "peak_current_A":  float(event_peak_current),
                            "min_speed_TPS":   float(event_min_speed),
                        })
                        last_event_end = event_first_clear
                    in_event = False
                    event_start = None
                    event_first_clear = None
                    event_motors = set()
                    event_peak_current = 0.0
                    event_min_speed = float("inf")

    # Flush trailing event if log ends mid-stall
    if in_event and event_start is not None:
        end_ts = event_first_clear if event_first_clear is not None else float(ts_grid[-1])
        duration = end_ts - event_start
        if duration >= CUSTOM_MIN_DURATION_S:
            state = _lookup_at(event_start, state_ts, state_v, default="UNKNOWN")
            events.append({
                "t_start":         float(event_start),
                "t_end":           float(end_ts),
                "duration":        float(duration),
                "state":           state,
                "motors":          sorted(event_motors),
                "peak_current_A":  float(event_peak_current),
                "min_speed_TPS":   float(event_min_speed),
            })

    return events

def classify_jam(event):
    """Turn the motor-set into a short event type label."""
    m = set(event["motors"])
    if m == {"Left Intake", "Right Intake"}:
        return "BOTH"
    if m == {"Left Intake"}:
        return "LEFT_ONLY"
    if m == {"Right Intake"}:
        return "RIGHT_ONLY"
    return "OTHER"

# -- Per-log analysis ------------------------------------------------------------

def analyze_log(log_path):
    series = load_series(log_path)
    state_pts   = series.get(STATE_PATH, [])
    jam_pts     = series.get(JAM_PATH, [])
    enabled_pts = series.get("DS:enabled", [])

    # Timespan
    all_ts = [ts for ts, _ in enabled_pts] + [ts for ts, _ in state_pts]
    for motor_base in list(INTAKE_MOTORS.values()) + list(FEEDER_MOTORS.values()):
        for sig in SIGNALS_PER_MOTOR:
            for ts, _ in series.get(f"{motor_base}/{sig}", []):
                all_ts.append(ts)
    if not all_ts:
        return None

    t_end = float(max(all_ts))
    enabled_intervals = compute_enabled_intervals(enabled_pts, t_end)
    enabled_s = intervals_total(enabled_intervals)
    if enabled_s <= 0:
        return None

    # State intervals, intersected with enabled so we only count time the robot
    # was actually running (state signal keeps publishing pre-match too).
    raw_state_intervals = compute_state_intervals(state_pts, INTAKE_STATES, t_end)
    state_intervals = {s: intersect_intervals(raw_state_intervals[s], enabled_intervals)
                        for s in INTAKE_STATES}
    state_secs = {s: intervals_total(state_intervals[s]) for s in INTAKE_STATES}

    # Per-motor, per-state stats. For each motor we compute:
    #   stator_abs, supply_abs, speed_abs stats restricted to each state's
    #   intervals (and a separate "all enabled" bucket).
    motor_stats = {}
    motor_totals = {}  # overall enabled-time stats per motor
    motor_energy = {}
    for label, base in {**INTAKE_MOTORS, **FEEDER_MOTORS}.items():
        spd_pts = series.get(f"{base}/Speed", [])
        cst_pts = series.get(f"{base}/Stator Current", [])
        sup_pts = series.get(f"{base}/Supply Current", [])
        vlt_pts = series.get(f"{base}/Out Volt", [])

        per_state = {}
        for s in INTAKE_STATES:
            ivs = state_intervals[s]
            per_state[s] = {
                "stator": time_weighted_abs_stats(cst_pts, ivs, t_end),
                "supply": time_weighted_abs_stats(sup_pts, ivs, t_end),
                "speed":  time_weighted_abs_stats(spd_pts, ivs, t_end),
            }
        motor_stats[label] = per_state
        motor_totals[label] = {
            "stator": time_weighted_abs_stats(cst_pts, enabled_intervals, t_end),
            "supply": time_weighted_abs_stats(sup_pts, enabled_intervals, t_end),
            "speed":  time_weighted_abs_stats(spd_pts, enabled_intervals, t_end),
        }
        motor_energy[label] = energy_over_intervals(vlt_pts, cst_pts,
                                                     enabled_intervals, t_end)

    # Robot jam count (rising edges of Intake Jam within enabled time)
    robot_jam_edges = count_rising_edges(jam_pts, enabled_intervals)

    # Total seconds the robot's Intake Jam bool was True (during enabled)
    robot_jam_time = 0.0
    prev_ts = None
    prev_val = None
    for ts, v in jam_pts:
        if prev_ts is not None and prev_val:
            robot_jam_time += overlap_with_intervals(prev_ts, ts, enabled_intervals)
        prev_ts = ts
        prev_val = bool(v)
    if prev_ts is not None and prev_val:
        robot_jam_time += overlap_with_intervals(prev_ts, t_end, enabled_intervals)

    # Custom jam events
    custom_jams = detect_custom_jams(series, state_pts, enabled_intervals, t_end)

    # Pivot (position-controlled motor, analyzed separately)
    pivot = analyze_pivot(series, enabled_intervals, t_end)

    result = {
        "log_path":         log_path,
        "session_len":      t_end,
        "enabled_s":        enabled_s,
        "state_secs":       state_secs,
        "motor_stats":      motor_stats,
        "motor_totals":     motor_totals,
        "motor_energy_J":   motor_energy,
        "robot_jam_edges":  robot_jam_edges,
        "robot_jam_time":   float(robot_jam_time),
        "custom_jams":      custom_jams,
        "pivot":            pivot,
    }
    del series
    return result

# -- Report helpers --------------------------------------------------------------

def _fmt_abs(s, unit=""):
    if s is None:
        return "(no samples)"
    return (f"mean {s['mean_tw']:.1f}, p50 {s['p50']:.1f}, "
            f"p95 {s['p95']:.1f}, max {s['max']:.1f} {unit} (n={s['n']})")

def print_per_log_report(r):
    print()
    print(SEP)
    print(f"  LOG: {os.path.basename(r['log_path'])}")
    print(SEP)
    print(f"  Enabled time : {r['enabled_s']:.1f} s")

    # Time in each state
    ss = r["state_secs"]
    total = r["enabled_s"]
    print(f"  State time   : "
          + ", ".join(f"{s}={ss[s]:.1f}s ({100*ss[s]/total:.1f}%)"
                       for s in INTAKE_STATES))

    # Per-motor overall (all enabled time)
    print()
    print(f"  [Per-motor, all enabled time]")
    print(f"  {'Motor':<14}  {'Stator (A)':<38}  {'Supply (A)':<38}  {'Speed (TPS)':<38}  {'Energy':>8}")
    print(f"  {'-'*14}  {'-'*38}  {'-'*38}  {'-'*38}  {'-'*8}")
    for label in list(INTAKE_MOTORS) + list(FEEDER_MOTORS):
        t = r["motor_totals"][label]
        e = r["motor_energy_J"][label]
        st = _fmt_abs(t["stator"])
        su = _fmt_abs(t["supply"])
        sp = _fmt_abs(t["speed"])
        print(f"  {label:<14}  {st:<38}  {su:<38}  {sp:<38}  {e:>6.0f} J")

    # Per-motor per-state breakdown for intake motors only (most interesting)
    for label in INTAKE_MOTORS:
        print()
        print(f"  [{label}] by state:")
        print(f"    {'State':<10}  {'Stator (A)':<38}  {'Supply (A)':<38}  {'Speed (TPS)':<38}")
        print(f"    {'-'*10}  {'-'*38}  {'-'*38}  {'-'*38}")
        for s in INTAKE_STATES:
            row = r["motor_stats"][label][s]
            st = _fmt_abs(row["stator"])
            su = _fmt_abs(row["supply"])
            sp = _fmt_abs(row["speed"])
            print(f"    {s:<10}  {st:<38}  {su:<38}  {sp:<38}")

    # Pivot (position-controlled — separate block)
    p = r.get("pivot")
    if p is not None:
        print()
        print(f"  [Intake Pivot]  energy {p['energy_J']:.0f} J  "
              f"(Position n={p['n_position']}, error samples n={p['n_error']})")
        if p["state_secs"]:
            parts = [f"{s}={p['state_secs'][s]:.1f}s"
                     for s in PIVOT_STATES if p['state_secs'][s] > 0]
            print(f"    Pivot-state time : " + ", ".join(parts) if parts else
                  "    Pivot-state time : (no state samples)")
        # Table header
        print(f"    {'State':<11}  {'Secs':>5}  {'Stator (A)':<24}  "
              f"{'Supply (A)':<24}  {'|Error| (rot)':<24}  {'At setpt':>8}")
        print(f"    {'-'*11}  {'-'*5}  {'-'*24}  {'-'*24}  {'-'*24}  {'-'*8}")
        for s in PIVOT_STATES + ["ENABLED"]:
            row = p["per_state"][s]
            secs = row["seconds"]
            if secs <= 0:
                continue
            def _fmt_short_stat(stat, unit=""):
                if stat is None:
                    return "-"
                return (f"{stat['mean_tw']:.1f}/{stat['p95']:.1f}/"
                        f"{stat['max']:.1f}{unit}")
            at_pct = (100 * row["at_setpoint_s"] / secs) if secs > 0 else 0.0
            print(f"    {s:<11}  {secs:>4.1f}s  "
                  f"{_fmt_short_stat(row['stator'], ' A'):<24}  "
                  f"{_fmt_short_stat(row['supply'], ' A'):<24}  "
                  f"{_fmt_short_stat(row['abs_error']):<24}  "
                  f"{at_pct:>6.1f}%")

        # Position range, signed, for enabled time
        pos = p["per_state"]["ENABLED"]["position"]
        req = p["per_state"]["ENABLED"]["reqPosition"]
        if pos is not None:
            print(f"    Position (enabled) : mean {pos['mean_tw']:+.3f}, "
                  f"range [{pos['min']:+.3f}, {pos['max']:+.3f}] rot")
        if req is not None:
            print(f"    reqPosition        : mean {req['mean_tw']:+.3f}, "
                  f"range [{req['min']:+.3f}, {req['max']:+.3f}] rot")
        print(f"    At-setpoint threshold: |error| <= "
              f"{PIVOT_AT_SETPOINT_TOLERANCE} (native units, typically rotations)")

    # Jam comparison
    print()
    print(f"  [Jam detection]")
    print(f"    Robot 'Intake Jam' rising edges : {r['robot_jam_edges']}  "
          f"(True for {r['robot_jam_time']:.2f}s total)")
    print(f"    Custom detector events          : {len(r['custom_jams'])}")
    if r["custom_jams"]:
        print(f"    {'#':>2}  {'t (s)':>7}  {'dur':>5}  {'type':<11}  "
              f"{'state':<9}  {'peak I':>6}  {'min spd':>7}")
        print(f"    {'-'*2}  {'-'*7}  {'-'*5}  {'-'*11}  "
              f"{'-'*9}  {'-'*6}  {'-'*7}")
        for i, e in enumerate(r["custom_jams"][:20], 1):
            print(f"    {i:>2}  {e['t_start']:>7.2f}  {e['duration']:>4.2f}s  "
                  f"{classify_jam(e):<11}  {e['state']:<9}  "
                  f"{e['peak_current_A']:>5.1f}A  {e['min_speed_TPS']:>5.2f} TPS")
        if len(r["custom_jams"]) > 20:
            print(f"    ... {len(r['custom_jams']) - 20} more")

# -- Combined analysis -----------------------------------------------------------

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

def print_combined_analysis(results):
    n_logs = len(results)
    print()
    print(SEP)
    print(f"  COMBINED INTAKE ANALYSIS ACROSS {n_logs} LOG{'S' if n_logs != 1 else ''}")
    print(SEP)

    total_enabled = sum(r["enabled_s"] for r in results)
    print(f"\n  Total enabled time  : {total_enabled:.1f} s  "
          f"({total_enabled/60:.2f} min)")

    # State-time aggregates
    state_totals = {s: sum(r["state_secs"].get(s, 0.0) for r in results)
                    for s in INTAKE_STATES}
    print(f"  State time totals   : "
          + ", ".join(f"{s}={state_totals[s]:.1f}s "
                       f"({100*state_totals[s]/total_enabled:.1f}%)"
                       for s in INTAKE_STATES))

    # Per-motor season totals (all enabled time)
    print()
    print(f"  [Per-motor season totals, all enabled time]")
    print(f"  {'Motor':<14}  {'Stator mean/p95/max':<28}  "
          f"{'Supply mean/p95/max':<28}  {'|Speed| mean/p95/max':<28}  {'Energy':>9}")
    print(f"  {'-'*14}  {'-'*28}  {'-'*28}  {'-'*28}  {'-'*9}")
    for label in list(INTAKE_MOTORS) + list(FEEDER_MOTORS):
        s_st = _merge_abs_stats([r["motor_totals"][label]["stator"] for r in results])
        s_su = _merge_abs_stats([r["motor_totals"][label]["supply"] for r in results])
        s_sp = _merge_abs_stats([r["motor_totals"][label]["speed"]  for r in results])
        def _short(s, unit=""):
            return (f"{s['mean_tw']:.1f}/{s['p95']:.1f}/{s['max']:.1f}{unit}"
                    if s else "-")
        total_e = sum(r["motor_energy_J"][label] for r in results)
        print(f"  {label:<14}  {_short(s_st, ' A'):<28}  "
              f"{_short(s_su, ' A'):<28}  {_short(s_sp):<28}  {total_e/1000:>7.2f} kJ")

    # Per-motor, per-state breakdown for INTAKE motors
    for label in INTAKE_MOTORS:
        print()
        print(f"  [{label}] by state (season):")
        print(f"    {'State':<10}  {'Stator (A)':<30}  "
              f"{'Supply (A)':<30}  {'|Speed|':<30}")
        print(f"    {'-'*10}  {'-'*30}  {'-'*30}  {'-'*30}")
        for s in INTAKE_STATES:
            st = _merge_abs_stats([r["motor_stats"][label][s]["stator"] for r in results])
            su = _merge_abs_stats([r["motor_stats"][label][s]["supply"] for r in results])
            sp = _merge_abs_stats([r["motor_stats"][label][s]["speed"]  for r in results])
            def _short(s):
                return (f"mean {s['mean_tw']:.1f}, p95 {s['p95']:.1f}, max {s['max']:.1f}"
                        if s else "-")
            print(f"    {s:<10}  {_short(st):<30}  {_short(su):<30}  {_short(sp):<30}")

    # Pivot season summary
    pivot_results = [r["pivot"] for r in results if r.get("pivot")]
    if pivot_results:
        print()
        print(SEP)
        print("  INTAKE PIVOT — season summary")
        print(SEP)

        total_energy = sum(p["energy_J"] for p in pivot_results)
        print(f"\n  Total pivot energy (enabled) : {total_energy/1000:.2f} kJ  "
              f"(avg {total_energy/n_logs/1000:.2f} kJ/match)")

        # Per-pivot-state aggregate
        state_secs_total = defaultdict(float)
        for p in pivot_results:
            for s, secs in p["state_secs"].items():
                state_secs_total[s] += secs
        nonzero = {s: v for s, v in state_secs_total.items() if v > 0}
        if nonzero:
            print(f"  Total pivot-state time       : "
                  + ", ".join(f"{s}={nonzero[s]:.1f}s" for s in PIVOT_STATES
                               if nonzero.get(s)))

        print()
        print(f"  {'State':<11}  {'Secs':>7}  {'Stator (A) mean/p95/max':<28}  "
              f"{'Supply (A) mean/p95/max':<28}  {'|Error| mean/p95/max':<28}  {'At setpt':>8}")
        print(f"  {'-'*11}  {'-'*7}  {'-'*28}  {'-'*28}  {'-'*28}  {'-'*8}")
        for s in PIVOT_STATES + ["ENABLED"]:
            stator_list = [p["per_state"][s]["stator"] for p in pivot_results]
            supply_list = [p["per_state"][s]["supply"] for p in pivot_results]
            error_list  = [p["per_state"][s]["abs_error"] for p in pivot_results]
            total_secs  = sum(p["per_state"][s]["seconds"] for p in pivot_results)
            total_at    = sum(p["per_state"][s]["at_setpoint_s"] for p in pivot_results)
            if total_secs <= 0:
                continue
            merged_st = _merge_abs_stats(stator_list)
            merged_su = _merge_abs_stats(supply_list)
            merged_er = _merge_abs_stats(error_list)
            def _short(stat, unit=""):
                if stat is None:
                    return "-"
                return f"{stat['mean_tw']:.2f}/{stat['p95']:.2f}/{stat['max']:.2f}{unit}"
            at_pct = 100 * total_at / total_secs if total_secs > 0 else 0.0
            print(f"  {s:<11}  {total_secs:>6.1f}s  "
                  f"{_short(merged_st, ' A'):<28}  "
                  f"{_short(merged_su, ' A'):<28}  "
                  f"{_short(merged_er):<28}  "
                  f"{at_pct:>6.1f}%")

    # Jam detection summary
    print()
    print(SEP)
    print("  JAM DETECTION — robot vs custom")
    print(SEP)
    robot_total = sum(r["robot_jam_edges"] for r in results)
    robot_time  = sum(r["robot_jam_time"]  for r in results)
    print(f"\n  Robot 'Intake Jam' rising edges (season) : {robot_total}  "
          f"(avg {robot_total/n_logs:.1f}/match)")
    print(f"  Robot jam bool True time (season)        : {robot_time:.2f}s  "
          f"({100*robot_time/total_enabled:.2f}% of enabled)")
    print(f"  Robot detector: current >= {ROBOT_JAM_CURRENT_A:.0f}A AND "
          f"speed < {ROBOT_JAM_SPEED_TPS:.0f} TPS on LEFT INTAKE only; "
          f"no debounce, no cooldown")

    all_custom = []
    for r in results:
        match = os.path.basename(r["log_path"])
        for e in r["custom_jams"]:
            all_custom.append({**e, "match": match})
    print(f"\n  Custom detector events (season) : {len(all_custom)}  "
          f"(avg {len(all_custom)/n_logs:.1f}/match)")
    print(f"  Custom detector: |stator| >= {CUSTOM_STALL_CURRENT_A:.0f}A AND "
          f"|speed| < {CUSTOM_STALL_SPEED_TPS:.1f} TPS AND "
          f"|reqSpeed| >= {CUSTOM_MIN_REQ_SPEED:.1f} TPS,")
    print(f"                  held for {CUSTOM_MIN_DURATION_S:.2f}s min, "
          f"cleared after {CUSTOM_CLEAR_DURATION_S:.2f}s recovery, "
          f"{CUSTOM_COOLDOWN_S:.2f}s cooldown")

    # Breakdown by type + state
    if all_custom:
        by_type = defaultdict(int)
        by_state = defaultdict(int)
        by_type_state = defaultdict(int)
        for e in all_custom:
            t = classify_jam(e); s = e["state"]
            by_type[t]  += 1
            by_state[s] += 1
            by_type_state[(t, s)] += 1
        print()
        print(f"  Custom jam events by motor(s):")
        for t in ("LEFT_ONLY", "RIGHT_ONLY", "BOTH", "OTHER"):
            if by_type[t]:
                print(f"    {t:<10}  {by_type[t]:>4d}  ({100*by_type[t]/len(all_custom):.1f}%)")
        print(f"\n  Custom jam events by state:")
        for s in INTAKE_STATES + ["UNKNOWN"]:
            if by_state[s]:
                print(f"    {s:<10}  {by_state[s]:>4d}  ({100*by_state[s]/len(all_custom):.1f}%)")

        # Longest / most-intense events
        top = sorted(all_custom, key=lambda e: -e["duration"])[:10]
        print(f"\n  Top {len(top)} longest jam events (season):")
        print(f"  {'dur':>5}  {'peak I':>6}  {'min spd':>7}  {'type':<11}  "
              f"{'state':<9}  {'t (s)':>7}  {'Match':<45}")
        print(f"  {'-'*5}  {'-'*6}  {'-'*7}  {'-'*11}  {'-'*9}  {'-'*7}  {'-'*45}")
        for e in top:
            print(f"  {e['duration']:>4.2f}s  "
                  f"{e['peak_current_A']:>5.1f}A  "
                  f"{e['min_speed_TPS']:>5.2f}   "
                  f"{classify_jam(e):<11}  {e['state']:<9}  "
                  f"{e['t_start']:>7.2f}  {e['match']:<45}")

    print()
    print(SEP)

# -- CLI / IO (same shape as other analysis scripts) -----------------------------

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
            progress(f"  done in {dt:.1f}s — {len(r['custom_jams'])} custom jams")
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
            progress(f"[{done}/{n}] {os.path.basename(p)} — {dt:.1f}s, "
                     f"{len(r['custom_jams'])} custom jams")
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
            print(f"\nWARNING: no intake data in {p}.")
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
        write_markdown_report("Intake Analysis — Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Intake Analysis — Season Summary",
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

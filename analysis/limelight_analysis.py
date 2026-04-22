# -*- coding: utf-8 -*-
"""
Limelight vision analysis for FRC Team Valor 6800.

Analyzes all three Limelights (limelight-center / -left / -right) across:
  - Capture + targeting + end-to-end latency
  - Target visibility (team-filter hasTarget vs raw Limelight tv)
  - Number of AprilTags visible per frame (from rawfiducials)
  - Distance to primary target (from rawfiducials and team-published
    "Field Calibration/Distance to Tag")
  - Per-tag summary (ambiguity, distance, frame count) aggregated across
    cameras so each AprilTag ID gets a unified row

All metrics are measured during DS:enabled time only (auto + teleop,
since vision runs in both). Time-based stats (visibility fraction,
latency average) are time-weighted with samples held between updates
and clipped to enabled intervals.

Usage: same CLI conventions as the other analysis scripts.
    python limelight_analysis.py                        # default log
    python limelight_analysis.py logs/                  # recursive scan
    python limelight_analysis.py -j 8 logs/             # 8 workers
    python limelight_analysis.py --no-file logs/        # terminal only

Default output:
  analysis/reports/limelight_summary.md
  analysis/reports/limelight_matches.md

Limelight rawfiducials format (per tag, 7 doubles per tag entry):
  [id, txnc, tync, ta, distToCamera, distToRobot, ambiguity]
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

CAMERAS = ["limelight-center", "limelight-left", "limelight-right"]

# rawfiducials values are packed in groups of 7
RAWFID_STRIDE = 7

# ------------------------------------------------------------------------------
# Filter thresholds, taken from the robot code
# (valkyrie/src/main/cpp/sensors/AprilTagsSensor.cpp + Drivetrain.cpp).
#   - All cameras run the MT1 solver (Robot.cpp sets Solver::MT1 for every cam)
#   - AprilTagsSensor::Config defaults come from the header except where
#     overridden in Drivetrain.cpp:118 via setConfig(...)
# ------------------------------------------------------------------------------
AMBIGUITY_THRESHOLD = 0.2    # Drivetrain.cpp:118 (overrides header default of 0.4)
MAX_LATENCY_MS      = 2000.0 # default AprilTagsSensor::Config.maxMeasurementAge
FIELD_BORDER_M      = 0.5    # default AprilTagsSensor::Config.fieldBorderMargin
MAX_VISION_DIST_M   = 5.0    # Drivetrain.cpp: MAX_VISION_MEASUREMENT
# Field dimensions sourced from robot constants
# (src/main/include/constants/Constants.h -> Constants::GameSpecific)
FIELD_LENGTH_M      = 16.54
FIELD_WIDTH_M       = 8.07

# botpose array indices (both botpose_wpiblue and botpose_orb_wpiblue)
BP_X = 0; BP_Y = 1; BP_YAW = 5; BP_LATENCY_MS = 6; BP_TAG_COUNT = 7; BP_AVG_DIST = 9

REJECTION_REASONS = [
    "PASS",
    "NOT_ACTIVE",      # Active Camera == false
    "NO_TARGET",       # tv == 0  (hasTarget() returns false)
    "MALFORMED",       # botpose_wpiblue array shorter than 11
    "NO_TAGS",         # tagCount < 1
    "STALE",           # total latency > 2000ms
    "OUT_OF_FIELD",    # pose X/Y outside field bounds + border margin
    "HIGH_AMBIGUITY",  # single-tag, MT1, ambiguity > 0.2
    "TOO_FAR",         # avg tag distance >= 5.0m
]

# -------------------------------------------------------------------------------
# Tag -> field zone mapping (2026 season, k2026RebuiltAndyMark).
#
# Canonical team mapping provided by driver/operator — keep this as the single
# source of truth so analysis labels match what the drive team calls each
# structure.  Update here when the mapping changes season-to-season.
#
# Each entry is: tag_id -> (zone_name, owning_alliance)
#   zone_name:  "Tower" / "Outpost" / "Left Trench" / "Right Trench" / "Hub"
#   alliance:   "red" / "blue"  (which alliance the tag belongs to, NOT our
#               alliance this match — use `alliance_is_red` to find that)
# -------------------------------------------------------------------------------
TAG_ZONES = {
    # --- RED alliance tags ---
    15: ("Tower",       "red"),
    16: ("Tower",       "red"),
    13: ("Outpost",     "red"),
    14: ("Outpost",     "red"),
    6:  ("Left Trench", "red"),
    7:  ("Left Trench", "red"),
    12: ("Right Trench","red"),
    1:  ("Right Trench","red"),
    9:  ("Hub",         "red"),
    10: ("Hub",         "red"),
    8:  ("Hub",         "red"),
    5:  ("Hub",         "red"),
    11: ("Hub",         "red"),
    2:  ("Hub",         "red"),
    4:  ("Hub",         "red"),
    3:  ("Hub",         "red"),
    # --- BLUE alliance tags ---
    31: ("Tower",       "blue"),
    32: ("Tower",       "blue"),
    29: ("Outpost",     "blue"),
    30: ("Outpost",     "blue"),
    22: ("Left Trench", "blue"),
    23: ("Left Trench", "blue"),
    17: ("Right Trench","blue"),
    28: ("Right Trench","blue"),
    25: ("Hub",         "blue"),
    26: ("Hub",         "blue"),
    18: ("Hub",         "blue"),
    27: ("Hub",         "blue"),
    21: ("Hub",         "blue"),
    24: ("Hub",         "blue"),
    19: ("Hub",         "blue"),
    20: ("Hub",         "blue"),
}

# Ordered list used for zone-summary tables (consistent column ordering)
ZONE_ORDER = ["Hub", "Tower", "Outpost", "Left Trench", "Right Trench", "UNKNOWN"]

def zone_for(tag_id):
    """Return ('ZONE_NAME', 'alliance') or ('UNKNOWN', '-') if not mapped."""
    return TAG_ZONES.get(int(tag_id), ("UNKNOWN", "-"))

# -------------------------------------------------------------------------------
# Zone-only tags — these AprilTags are positioned such that they're only ever
# within line-of-sight while the robot is physically in its own alliance half.
# If we see any of these, we can infer which alliance we were on even when FMS
# data is absent/unreliable (pre-match boot, unsynced logs, practice matches).
# -------------------------------------------------------------------------------
ZONE_ONLY_TAGS = {
    "red":  {7, 9, 10, 12},
    "blue": {23, 25, 26, 28},
}

# Regex pulls only the fields we need (raw LL keys + team SmartDashboard keys)
JS_REGEX_PARTS = []
for cam in CAMERAS:
    # Raw Limelight keys (including botpose_wpiblue for filter simulation)
    JS_REGEX_PARTS.append(rf"NT:/{cam}/(cl|tl|tv|tid|rawfiducials|ta|botpose_wpiblue)")
    # Team-published keys under SmartDashboard/SwerveDrive/<cam>/
    JS_REGEX_PARTS.append(
        rf"NT:/SmartDashboard/SwerveDrive/{cam}/"
        rf"(Active Camera|hasTarget|totalLatency|Vision Filter Pass|"
        rf"Doubts/(Rotational|Translational)|"
        rf"Field Calibration/Distance to Tag|tid)"
    )
# Add FMS alliance + control-data (for FMS-attached bit) + DS mode signals
JS_REGEX_PARTS.append(r"NT:/FMSInfo/(IsRedAlliance|FMSControlData)")
LL_REGEX = r"(" + "|".join(JS_REGEX_PARTS) + r"|DS:(enabled|autonomous))"

# Bit positions in NT:/FMSInfo/FMSControlData (from WPILib DriverStation).
# Layout: bit0=enabled, bit1=autonomous, bit2=test, bit3=emergencyStop,
#         bit4=FMSAttached, bit5=DSAttached
FMS_ATTACHED_BIT = 1 << 4

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading ----------------------------------------------------------------

def load_series(log_path):
    raw = defaultdict(list)
    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, LL_REGEX)
    with src:
        for entry in src:
            name = entry["name"]
            ts   = entry["timestamp"] / 1e6
            raw[name].append((ts, entry["data"]))
    for name in raw:
        raw[name].sort(key=lambda x: x[0])
    return dict(raw)

# -- Interval helpers (mirrors joystick_analysis.py) -----------------------------

def compute_enabled_intervals(enabled_pts, t_end):
    """Return (t_start, t_end) intervals where DS:enabled is True."""
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

# -- Per-signal time-weighted aggregators ----------------------------------------

def time_weighted_stats(pts, intervals, t_end):
    """
    Return dict with time-weighted mean, plus sample-based min/max/p50/p95,
    taking only samples whose timestamps (or held intervals) overlap enabled
    intervals.

    Non-finite values (inf / nan) are dropped from the integral + percentile
    computation but counted via n_invalid. For Limelight doubts, inf means
    "pose rejected" — so we want the descriptive stats to reflect the valid
    samples only, with n_invalid giving the separate rejection count.
    """
    if not pts or not intervals:
        return None
    samples    = []
    integral   = 0.0
    total_time = 0.0
    prev_ts    = None
    prev_val   = None
    n_invalid  = 0
    for ts, v in pts:
        if not isinstance(v, (int, float)):
            continue
        fv = float(v)
        finite = np.isfinite(fv)
        if ts_in_intervals(ts, intervals):
            if finite:
                samples.append(fv)
            else:
                n_invalid += 1
        if prev_ts is not None and prev_val is not None and np.isfinite(prev_val):
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                integral   += prev_val * ov
                total_time += ov
        prev_ts  = ts
        prev_val = fv
    # Trailing held segment
    if prev_ts is not None and prev_val is not None and np.isfinite(prev_val):
        ov = overlap_with_intervals(prev_ts, t_end, intervals)
        if ov > 0:
            integral   += prev_val * ov
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

def time_fraction_true(bool_pts, intervals, t_end):
    """Fraction of enabled time a bool signal was True."""
    if not intervals:
        return 0.0
    true_time = 0.0
    prev_ts   = None
    prev_val  = None
    for ts, v in bool_pts:
        if prev_ts is not None and prev_val:
            true_time += overlap_with_intervals(prev_ts, ts, intervals)
        prev_ts  = ts
        prev_val = bool(v)
    if prev_ts is not None and prev_val:
        true_time += overlap_with_intervals(prev_ts, t_end, intervals)
    total = intervals_total(intervals)
    return true_time / total if total > 0 else 0.0

# -- rawfiducials aggregation ----------------------------------------------------

def aggregate_rawfiducials(rawfid_pts, intervals, t_end):
    """
    Walk rawfiducials samples; for each sample whose timestamp is in an enabled
    interval, unpack its (id, txnc, tync, ta, distC, distR, amb) groups.

    Returns:
      frame_stats: time-weighted stats for tag-count-per-frame
      per_tag: {tag_id: {"frames": n, "dists": [...], "ambs": [...]}}
    """
    per_tag = defaultdict(lambda: {"frames": 0, "dists": [], "ambs": [],
                                    "primary_frames": 0})
    count_samples      = []    # counts seen in enabled frames
    count_integral     = 0.0
    total_time         = 0.0
    prev_ts            = None
    prev_count         = None

    for ts, v in rawfid_pts:
        if not isinstance(v, list):
            continue
        # Unpack groups; tolerate ragged/truncated lists just in case.
        n_tags = len(v) // RAWFID_STRIDE

        if prev_ts is not None and prev_count is not None:
            ov = overlap_with_intervals(prev_ts, ts, intervals)
            if ov > 0:
                count_integral += prev_count * ov
                total_time     += ov

        if ts_in_intervals(ts, intervals):
            count_samples.append(n_tags)
            for g in range(n_tags):
                off = g * RAWFID_STRIDE
                try:
                    tag_id = int(v[off + 0])
                    dist   = float(v[off + 5])   # distToRobot
                    amb    = float(v[off + 6])
                except (TypeError, ValueError, IndexError):
                    continue
                per_tag[tag_id]["frames"] += 1
                per_tag[tag_id]["dists"].append(dist)
                per_tag[tag_id]["ambs"].append(amb)
                if g == 0:
                    per_tag[tag_id]["primary_frames"] += 1

        prev_ts    = ts
        prev_count = n_tags

    if prev_ts is not None and prev_count is not None:
        ov = overlap_with_intervals(prev_ts, t_end, intervals)
        if ov > 0:
            count_integral += prev_count * ov
            total_time     += ov

    if count_samples:
        arr = np.array(count_samples)
        frames_with_tag = int((arr > 0).sum())
        frame_stats = {
            "n_samples":     len(count_samples),
            "mean_tw":       float(count_integral / total_time) if total_time > 0 else 0.0,
            "mean_sample":   float(np.mean(arr)),
            "max":           int(np.max(arr)),
            "frames_with_tag": frames_with_tag,
            "frame_with_tag_frac": frames_with_tag / len(count_samples),
        }
    else:
        frame_stats = None

    # Collapse per-tag arrays into summary stats
    tag_summary = {}
    for tag_id, d in per_tag.items():
        ds = np.array(d["dists"])  if d["dists"] else np.array([])
        am = np.array(d["ambs"])   if d["ambs"]  else np.array([])
        tag_summary[tag_id] = {
            "frames":         d["frames"],
            "primary_frames": d["primary_frames"],
            "dist_mean":      float(np.mean(ds)) if len(ds) else 0.0,
            "dist_min":       float(np.min(ds))  if len(ds) else 0.0,
            "dist_max":       float(np.max(ds))  if len(ds) else 0.0,
            "amb_mean":       float(np.mean(am)) if len(am) else 0.0,
            "amb_p95":        float(np.percentile(am, 95)) if len(am) else 0.0,
            "amb_max":        float(np.max(am))  if len(am) else 0.0,
        }
    return frame_stats, tag_summary

# -- Rejection classification ----------------------------------------------------

def _build_searchable(pts, value_fn=lambda v: v):
    """Split a (ts, value) list into parallel sorted arrays for bisect lookups."""
    if not pts:
        return np.array([]), []
    ts_arr  = np.array([ts for ts, _ in pts])
    vals    = [value_fn(v) for _, v in pts]
    return ts_arr, vals

def _lookup_at(ts, ts_arr, vals, default=None):
    """Return the last value whose timestamp <= ts, else default."""
    if len(ts_arr) == 0:
        return default
    idx = int(np.searchsorted(ts_arr, ts, side="right")) - 1
    return vals[idx] if idx >= 0 else default

def classify_rejections(botpose_pts, rawfid_pts, active_pts, tv_pts, intervals):
    """
    Walk each vision frame (one per botpose_wpiblue publish) during the enabled
    intervals and classify it against the robot's pose-filter gates in the same
    order as AprilTagsSensor::applyVisionMeasurement() + Drivetrain.cpp's
    distance wrapper.

    Returns (counts, accepted) where:
      counts   -> dict keyed by reason (PASS / NOT_ACTIVE / NO_TARGET / ...)
      accepted -> dict of parallel lists collected only for PASS frames:
                    tag_counts[], distances[], latencies[],
                    amb_means[]  (mean ambiguity across all tags in frame),
                    amb_maxes[]  (max ambiguity across all tags in frame)
    """
    counts   = defaultdict(int)
    accepted = {
        "tag_counts": [],
        "distances":  [],
        "latencies":  [],
        "amb_means":  [],
        "amb_maxes":  [],
    }
    if not botpose_pts:
        return dict(counts), accepted

    active_ts, active_v = _build_searchable(active_pts, lambda v: bool(v))
    tv_ts,     tv_v     = _build_searchable(tv_pts,     lambda v: bool(v))
    raw_ts,    raw_v    = _build_searchable(rawfid_pts, lambda v: v)

    for ts, bp in botpose_pts:
        if not ts_in_intervals(ts, intervals):
            continue

        # Gate 0: camera actively selected as a pose source
        if not _lookup_at(ts, active_ts, active_v, default=True):
            counts["NOT_ACTIVE"] += 1
            continue
        # Gate 1: hasTarget() == (tv == 1)
        if not _lookup_at(ts, tv_ts, tv_v, default=False):
            counts["NO_TARGET"] += 1
            continue
        # Gate 2: botpose array shape
        if not isinstance(bp, list) or len(bp) < 11:
            counts["MALFORMED"] += 1
            continue
        try:
            tag_count  = int(bp[BP_TAG_COUNT])
            latency_ms = float(bp[BP_LATENCY_MS])
            px         = float(bp[BP_X])
            py         = float(bp[BP_Y])
            avg_dist   = float(bp[BP_AVG_DIST])
        except (TypeError, ValueError):
            counts["MALFORMED"] += 1
            continue
        # Gate 3: tagCount < 1
        if tag_count < 1:
            counts["NO_TAGS"] += 1
            continue
        # Gate 4: stale frame
        if latency_ms > MAX_LATENCY_MS:
            counts["STALE"] += 1
            continue
        # Gate 5: pose outside field bounds + border margin
        if (px < -FIELD_BORDER_M or px > FIELD_LENGTH_M + FIELD_BORDER_M or
            py < -FIELD_BORDER_M or py > FIELD_WIDTH_M  + FIELD_BORDER_M):
            counts["OUT_OF_FIELD"] += 1
            continue
        # Gate 6: MT1 single-tag ambiguity rejection
        raw = _lookup_at(ts, raw_ts, raw_v, default=None)
        if tag_count == 1:
            if isinstance(raw, list) and len(raw) >= RAWFID_STRIDE:
                try:
                    amb = float(raw[6])
                except (TypeError, ValueError):
                    amb = 0.0
                if amb > AMBIGUITY_THRESHOLD:
                    counts["HIGH_AMBIGUITY"] += 1
                    continue
        # Gate 7: avg distance too far (Drivetrain.cpp wrapper)
        if avg_dist >= MAX_VISION_DIST_M:
            counts["TOO_FAR"] += 1
            continue

        # PASS — collect per-frame stats for the "accepted measurements" summary.
        counts["PASS"] += 1
        accepted["tag_counts"].append(tag_count)
        accepted["distances"].append(avg_dist)
        accepted["latencies"].append(latency_ms)
        # Pull ambiguities from rawfiducials groups-of-7 for the full frame
        if isinstance(raw, list) and len(raw) >= RAWFID_STRIDE:
            ambs = []
            for g in range(len(raw) // RAWFID_STRIDE):
                try:
                    ambs.append(float(raw[g * RAWFID_STRIDE + 6]))
                except (TypeError, ValueError):
                    pass
            if ambs:
                accepted["amb_means"].append(float(np.mean(ambs)))
                accepted["amb_maxes"].append(float(np.max(ambs)))

    return dict(counts), accepted

# -- Per-log analysis ------------------------------------------------------------

def detect_alliance(series, tag_summary):
    """
    Determine our alliance with a three-tier strategy:

    1. FMS-gated IsRedAlliance -- only samples taken while BOTH the FMS
       was attached (FMSControlData bit 4 set) AND the robot was enabled
       (DS:enabled == True) are considered valid. FMSInfo/IsRedAlliance
       defaults to False pre-connect and may revert to False post-connect,
       so ungated sampling is unreliable.
    2. Zone-only tags -- count frame-sightings of tags only visible from
       a specific alliance zone. Side with 3x the opposing hits wins.
    3. None if neither is conclusive.

    Returns ('red' | 'blue' | None, source_label) where source_label is
    'fms' / 'zone-tags' / 'none'.
    """
    red_pts   = series.get("NT:/FMSInfo/IsRedAlliance", [])
    ctrl_pts  = series.get("NT:/FMSInfo/FMSControlData", [])
    en_pts    = series.get("DS:enabled", [])

    # Build step functions for the three signals. IsRedAlliance only changes
    # when FMS writes a new alliance (so typically logged once early in the
    # match, even before enable). Looking up at sample time is wrong — we
    # need to snapshot the alliance at the first moment BOTH FMS is attached
    # AND the robot is enabled.
    fms_ts,  fms_v  = _build_searchable(
        ctrl_pts, lambda v: bool(int(v) & FMS_ATTACHED_BIT))
    en_ts,   en_v   = _build_searchable(en_pts,  lambda v: bool(v))
    red_ts,  red_v  = _build_searchable(red_pts, lambda v: bool(v))

    # Walk the union of transition timestamps and find the first where both
    # are True. Alliance doesn't change mid-match, so one sample is enough.
    transitions = sorted(set(list(fms_ts) + list(en_ts)))
    for ts in transitions:
        fms_on = _lookup_at(ts, fms_ts, fms_v, default=False)
        ena    = _lookup_at(ts, en_ts,  en_v,  default=False)
        if fms_on and ena:
            # Snapshot IsRedAlliance at this moment
            red = _lookup_at(ts, red_ts, red_v, default=None)
            if red is not None:
                return ("red" if red else "blue"), "fms"
            break  # No IsRedAlliance logged yet at this point — fall through

    # FMS/enabled gate didn't yield samples — fall back to tag-based inference.
    red_hits  = sum(tag_summary.get(t, {}).get("frames", 0)
                    for t in ZONE_ONLY_TAGS["red"])
    blue_hits = sum(tag_summary.get(t, {}).get("frames", 0)
                    for t in ZONE_ONLY_TAGS["blue"])
    if red_hits > 3 * max(1, blue_hits):
        return "red", "zone-tags"
    if blue_hits > 3 * max(1, red_hits):
        return "blue", "zone-tags"

    return None, "none"

def analyze_log(log_path):
    series = load_series(log_path)
    enabled_pts = series.get("DS:enabled", [])

    # Find timespan
    all_ts = []
    for ts, _ in enabled_pts:
        all_ts.append(ts)
    for cam in CAMERAS:
        for key in ("cl", "tl", "tv", "rawfiducials"):
            for ts, _ in series.get(f"NT:/{cam}/{key}", []):
                all_ts.append(ts)
    if not all_ts:
        return None

    t_end = float(max(all_ts))
    enabled_intervals = compute_enabled_intervals(enabled_pts, t_end)
    enabled_s         = intervals_total(enabled_intervals)

    if enabled_s <= 0:
        return None

    per_cam = {}
    per_tag_all = defaultdict(lambda: {"frames": 0, "dists": [], "ambs": [],
                                        "cameras": set()})

    for cam in CAMERAS:
        cl_pts    = series.get(f"NT:/{cam}/cl", [])
        tl_pts    = series.get(f"NT:/{cam}/tl", [])
        tv_pts    = series.get(f"NT:/{cam}/tv", [])
        raw_pts   = series.get(f"NT:/{cam}/rawfiducials", [])
        sd_prefix = f"NT:/SmartDashboard/SwerveDrive/{cam}"
        total_pts = series.get(f"{sd_prefix}/totalLatency", [])
        has_pts   = series.get(f"{sd_prefix}/hasTarget", [])
        vfp_pts   = series.get(f"{sd_prefix}/Vision Filter Pass", [])
        dist_pts  = series.get(f"{sd_prefix}/Field Calibration/Distance to Tag", [])
        drot_pts  = series.get(f"{sd_prefix}/Doubts/Rotational", [])
        dtra_pts  = series.get(f"{sd_prefix}/Doubts/Translational", [])
        active_pts = series.get(f"{sd_prefix}/Active Camera", [])

        # Raw tv is logged as 0/1 double; convert on the fly
        tv_bool_pts = [(ts, bool(v)) for ts, v in tv_pts]

        # Classify every vision frame against the team's filter gates
        botpose_pts = series.get(f"NT:/{cam}/botpose_wpiblue", [])
        rejections, accepted = classify_rejections(
            botpose_pts, raw_pts, active_pts, tv_bool_pts, enabled_intervals
        )

        frame_stats, per_tag_cam = aggregate_rawfiducials(raw_pts, enabled_intervals, t_end)

        # Merge per-tag into global aggregates
        for tag_id, d in per_tag_cam.items():
            g = per_tag_all[tag_id]
            g["frames"] += d["frames"]
            # Keep full arrays to recompute mean/min/max across cameras
            # We stored only summaries above — but we need raw distances to
            # average properly. Re-aggregate from each camera's raw lists.
            # (Cheaper: time-weighted by frame count on the per-cam summary.)
            g["dists"].append((d["frames"], d["dist_mean"], d["dist_min"], d["dist_max"]))
            g["ambs"].append((d["frames"], d["amb_mean"], d["amb_p95"], d["amb_max"]))
            g["cameras"].add(cam)

        per_cam[cam] = {
            "cl":              time_weighted_stats(cl_pts,    enabled_intervals, t_end),
            "tl":              time_weighted_stats(tl_pts,    enabled_intervals, t_end),
            "totalLatency":    time_weighted_stats(total_pts, enabled_intervals, t_end),
            "distance_to_tag": time_weighted_stats(dist_pts,  enabled_intervals, t_end),
            "doubts_rot":      time_weighted_stats(drot_pts,  enabled_intervals, t_end),
            "doubts_tra":      time_weighted_stats(dtra_pts,  enabled_intervals, t_end),
            "frames":          frame_stats,
            "tv_frac":         time_fraction_true(tv_bool_pts, enabled_intervals, t_end),
            "has_target_frac": time_fraction_true(has_pts,     enabled_intervals, t_end),
            "vfp_frac":        time_fraction_true(vfp_pts,     enabled_intervals, t_end),
            "active_frac":     time_fraction_true(active_pts,  enabled_intervals, t_end),
            "per_tag":         per_tag_cam,
            "rejections":      rejections,
            "accepted":        accepted,
        }

    # Collapse per-tag aggregates: weight by frame count
    tag_summary = {}
    for tag_id, g in per_tag_all.items():
        total_frames = g["frames"]
        if total_frames == 0:
            continue
        # Weighted mean distance / ambiguity across cameras that saw this tag
        w_dist = sum(n * d_mean for (n, d_mean, *_rest) in g["dists"])
        w_amb  = sum(n * a_mean for (n, a_mean, *_rest) in g["ambs"])
        min_dist = min(d_min  for (_, _, d_min, _) in g["dists"])
        max_dist = max(d_max  for (_, _, _, d_max) in g["dists"])
        max_amb  = max(a_max  for (_, _, _, a_max) in g["ambs"])
        tag_summary[tag_id] = {
            "frames":    total_frames,
            "dist_mean": w_dist / total_frames,
            "dist_min":  min_dist,
            "dist_max":  max_dist,
            "amb_mean":  w_amb / total_frames,
            "amb_max":   max_amb,
            "cameras":   sorted(g["cameras"]),
        }

    # Detect alliance AFTER tag_summary is built, so we can fall back to
    # zone-only tag inference if FMS data is missing/unreliable.
    alliance, alliance_source = detect_alliance(series, tag_summary)

    result = {
        "log_path":         log_path,
        "session_len":      t_end,
        "enabled_s":        enabled_s,
        "alliance":         alliance,          # 'red' / 'blue' / None
        "alliance_source":  alliance_source,   # 'fms' / 'zone-tags' / 'none'
        "cameras":          per_cam,
        "tags":             tag_summary,
    }
    del series
    return result

# -- Per-log report --------------------------------------------------------------

def _summarize_accepted(accepted):
    """Turn the per-accepted-frame lists into a small dict of summary stats."""
    n = len(accepted["tag_counts"])
    if n == 0:
        return None
    tc    = np.array(accepted["tag_counts"])
    dist  = np.array(accepted["distances"])
    lat   = np.array(accepted["latencies"])
    a_mean = np.array(accepted["amb_means"]) if accepted["amb_means"] else np.array([])
    a_max  = np.array(accepted["amb_maxes"]) if accepted["amb_maxes"] else np.array([])
    return {
        "n":             n,
        "single_tag":    int((tc == 1).sum()),
        "multi_tag":     int((tc >  1).sum()),
        "max_tag_count": int(tc.max()),
        "dist_mean":     float(dist.mean()),
        "dist_p50":      float(np.percentile(dist, 50)),
        "dist_p95":      float(np.percentile(dist, 95)),
        "dist_max":      float(dist.max()),
        "lat_mean":      float(lat.mean()),
        "lat_p50":       float(np.percentile(lat, 50)),
        "lat_p95":       float(np.percentile(lat, 95)),
        "lat_max":       float(lat.max()),
        "amb_mean":      float(a_mean.mean()) if len(a_mean) else None,
        "amb_p95":       float(np.percentile(a_mean, 95)) if len(a_mean) else None,
        "amb_max":       float(a_max.max())   if len(a_max)  else None,
    }

def _print_accepted_block(a, indent="    "):
    """Print the 'accepted measurements' summary block given summarize output."""
    if a is None:
        print(f"{indent}Accepted measurements : (none)")
        return
    pct_single = 100.0 * a["single_tag"] / a["n"]
    pct_multi  = 100.0 * a["multi_tag"]  / a["n"]
    print(f"{indent}Accepted measurements : n={a['n']}  "
          f"(single-tag {a['single_tag']}/{pct_single:.1f}%, "
          f"multi-tag {a['multi_tag']}/{pct_multi:.1f}%, "
          f"max tags {a['max_tag_count']})")
    print(f"{indent}  Distance (m)        : mean {a['dist_mean']:.2f}, "
          f"p50 {a['dist_p50']:.2f}, p95 {a['dist_p95']:.2f}, max {a['dist_max']:.2f}")
    print(f"{indent}  Latency (ms)        : mean {a['lat_mean']:.1f}, "
          f"p50 {a['lat_p50']:.1f}, p95 {a['lat_p95']:.1f}, max {a['lat_max']:.1f}")
    if a["amb_mean"] is not None:
        print(f"{indent}  Ambiguity (frame)   : mean {a['amb_mean']:.3f}, "
              f"p95 {a['amb_p95']:.3f}, max-tag {a['amb_max']:.3f}")

def _fmt_lat(s, suffix=" ms"):
    if s is None:
        return "(no samples)"
    return (f"mean {s['mean']:.1f}{suffix}, p50 {s['p50']:.1f}, "
            f"p95 {s['p95']:.1f}, max {s['max']:.1f} (n={s['n']})")

def print_camera_block(cam, cdata, enabled_s):
    print(f"\n  [{cam}]")
    af = cdata.get("active_frac", 0.0)
    print(f"    Active as pose source : {100*af:.1f}% of enabled time")
    print(f"    Raw tv == 1           : {100*cdata['tv_frac']:.1f}% "
          f"(LL thinks it has a target)")
    print(f"    Team hasTarget == 1   : {100*cdata['has_target_frac']:.1f}% "
          f"(post-filter team decision)")
    print(f"    Vision Filter Pass    : {100*cdata['vfp_frac']:.1f}% "
          f"(pose accepted into estimator)")

    print(f"    Capture latency  (cl) : {_fmt_lat(cdata['cl'])}")
    print(f"    Target latency   (tl) : {_fmt_lat(cdata['tl'])}")
    print(f"    End-to-end latency    : {_fmt_lat(cdata['totalLatency'])}")

    fs = cdata["frames"]
    if fs is None:
        print(f"    Targets per frame     : (no rawfiducials samples)")
    else:
        print(f"    Frames w/ any tag     : {fs['frames_with_tag']}/{fs['n_samples']}  "
              f"({100*fs['frame_with_tag_frac']:.1f}%)")
        print(f"    Avg tags / frame      : {fs['mean_tw']:.2f} time-weighted, "
              f"{fs['mean_sample']:.2f} per sample, max {fs['max']}")

    dt = cdata.get("distance_to_tag")
    if dt is not None:
        print(f"    Distance to primary   : mean {dt['mean']:.2f} m, "
              f"p95 {dt['p95']:.2f}, max {dt['max']:.2f} (n={dt['n']})")

    dr = cdata.get("doubts_rot")
    dtra = cdata.get("doubts_tra")
    if dr is not None or dtra is not None:
        def _short(s):
            if s is None:
                return "-"
            total = s["n"] + s["n_invalid"]
            rej = (100 * s["n_invalid"] / total) if total else 0.0
            return f"{s['mean']:.3f} ({rej:.0f}% rejected as inf)"
        print(f"    Doubts Rotational     : {_short(dr)}")
        print(f"    Doubts Translational  : {_short(dtra)}")

    # Filter rejection breakdown (from classify_rejections)
    rej = cdata.get("rejections", {})
    total = sum(rej.values())
    if total > 0:
        passed = rej.get("PASS", 0)
        rejected = total - passed
        print(f"    Filter outcome        : {passed}/{total} pass "
              f"({100*passed/total:.1f}%), {rejected} rejected "
              f"({100*rejected/total:.1f}%)")
        print(f"    Rejection reasons:")
        print(f"    {'Reason':<18}  {'Count':>6}  {'% of frames':>11}  {'% of rejects':>12}")
        print(f"    {'-'*18}  {'-'*6}  {'-'*11}  {'-'*12}")
        for reason in REJECTION_REASONS:
            if reason == "PASS":
                continue
            c = rej.get(reason, 0)
            if c == 0:
                continue
            print(f"    {reason:<18}  {c:>6d}  {100*c/total:>10.1f}%  "
                  f"{100*c/rejected if rejected else 0:>11.1f}%")

    # Accepted-only summary (what the pose estimator actually consumed)
    _print_accepted_block(_summarize_accepted(cdata.get("accepted", {})),
                          indent="    ")

def _alliance_str(alliance, source=None):
    if alliance is None:
        return "(unknown — no FMS + no zone-tag hits)"
    src = f" (source: {source})" if source else ""
    return f"{alliance.upper()}{src}"

def _side_str(tag_alliance, our_alliance):
    """Return 'ours' / 'theirs' / '-' based on tag ownership vs our alliance."""
    if our_alliance is None or tag_alliance == "-":
        return "-"
    return "ours" if tag_alliance == our_alliance else "theirs"

def print_per_log_report(r):
    print()
    print(SEP)
    print(f"  LOG: {os.path.basename(r['log_path'])}")
    print(SEP)
    print(f"  Enabled time : {r['enabled_s']:.1f} s")
    print(f"  Our alliance : {_alliance_str(r['alliance'], r.get('alliance_source'))}")
    for cam in CAMERAS:
        print_camera_block(cam, r["cameras"][cam], r["enabled_s"])

    # Top tags seen this match
    tags = r["tags"]
    our = r.get("alliance")
    if tags:
        print(f"\n  Top AprilTags seen this match (across all 3 cameras):")
        print(f"  {'Tag':>4}  {'Zone':<13}  {'Owns':<5}  {'Side':<6}  "
              f"{'Frames':>7}  {'Dist(m)':>14}  {'Ambig':>14}  {'Cameras':<20}")
        print(f"  {'-'*4}  {'-'*13}  {'-'*5}  {'-'*6}  "
              f"{'-'*7}  {'-'*14}  {'-'*14}  {'-'*20}")
        ordered = sorted(tags.items(), key=lambda kv: -kv[1]["frames"])
        for tid, t in ordered[:15]:
            zone, ally = zone_for(tid)
            side = _side_str(ally, our)
            cams_str = ",".join(c.replace("limelight-", "") for c in t["cameras"])
            d = f"{t['dist_mean']:.2f} ({t['dist_min']:.1f}-{t['dist_max']:.1f})"
            a = f"{t['amb_mean']:.3f}/{t['amb_max']:.3f}"
            print(f"  {tid:>4}  {zone:<13}  {ally:<5}  {side:<6}  "
                  f"{t['frames']:>7d}  {d:>14}  {a:>14}  {cams_str:<20}")

# -- Combined analysis -----------------------------------------------------------

def print_combined_analysis(results):
    n_logs = len(results)
    print()
    print(SEP)
    print(f"  COMBINED LIMELIGHT ANALYSIS ACROSS {n_logs} LOG{'S' if n_logs != 1 else ''}")
    print(SEP)
    total_enabled = sum(r["enabled_s"] for r in results)
    red_matches   = sum(1 for r in results if r.get("alliance") == "red")
    blue_matches  = sum(1 for r in results if r.get("alliance") == "blue")
    unknown       = n_logs - red_matches - blue_matches
    by_source     = defaultdict(int)
    for r in results:
        by_source[r.get("alliance_source", "none")] += 1
    print(f"\n  Total enabled time across logs : {total_enabled:.1f} s  "
          f"({total_enabled/60:.2f} min)")
    print(f"  Alliance distribution          : "
          f"RED={red_matches}, BLUE={blue_matches}"
          + (f", unknown={unknown}" if unknown else ""))
    src_parts = [f"{k}={v}" for k, v in sorted(by_source.items())]
    print(f"  Alliance detection sources     : {', '.join(src_parts)}")

    # Per-camera season aggregates (weight stats by enabled time per log)
    for cam in CAMERAS:
        print()
        print(SEP)
        print(f"  [{cam}] -- season summary")
        print(SEP)

        # Time-weighted fractions
        active_w = sum(r["cameras"][cam]["active_frac"]     * r["enabled_s"] for r in results)
        tv_w     = sum(r["cameras"][cam]["tv_frac"]         * r["enabled_s"] for r in results)
        has_w    = sum(r["cameras"][cam]["has_target_frac"] * r["enabled_s"] for r in results)
        vfp_w    = sum(r["cameras"][cam]["vfp_frac"]        * r["enabled_s"] for r in results)
        print(f"\n  Active as pose source : {100 * active_w/total_enabled:.1f}%")
        print(f"  Raw tv == 1           : {100 * tv_w/total_enabled:.1f}%")
        print(f"  Team hasTarget == 1   : {100 * has_w/total_enabled:.1f}%")
        print(f"  Vision Filter Pass    : {100 * vfp_w/total_enabled:.1f}%")

        def _combine_tw(key):
            """Weighted mean + min/max of time-weighted stat across logs."""
            present = [r["cameras"][cam][key] for r in results if r["cameras"][cam][key] is not None]
            if not present:
                return None
            # Weight each log by its sample count
            total_n = sum(s["n"] for s in present)
            if total_n == 0:
                return None
            mean = sum(s["mean"] * s["n"] for s in present) / total_n
            return {
                "n":    total_n,
                "mean": mean,
                "p50":  float(np.median([s["p50"] for s in present])),
                "p95":  float(np.max([s["p95"] for s in present])),
                "max":  float(np.max([s["max"] for s in present])),
                "min":  float(np.min([s["min"] for s in present])),
            }

        cl  = _combine_tw("cl")
        tl  = _combine_tw("tl")
        tot = _combine_tw("totalLatency")
        print(f"  Capture latency  (cl) : {_fmt_lat(cl)}")
        print(f"  Target latency   (tl) : {_fmt_lat(tl)}")
        print(f"  End-to-end latency    : {_fmt_lat(tot)}")

        dist = _combine_tw("distance_to_tag")
        if dist is not None:
            print(f"  Distance to primary   : mean {dist['mean']:.2f} m, "
                  f"p95 {dist['p95']:.2f}, max {dist['max']:.2f} (n={dist['n']})")

        # Targets per frame
        fs = [r["cameras"][cam]["frames"] for r in results if r["cameras"][cam]["frames"]]
        if fs:
            total_samples = sum(f["n_samples"] for f in fs)
            total_hits    = sum(f["frames_with_tag"] for f in fs)
            mean_tags     = sum(f["mean_tw"] * f["n_samples"] for f in fs) / total_samples if total_samples else 0.0
            max_tags      = max(f["max"] for f in fs)
            print(f"  Frames w/ any tag     : {total_hits}/{total_samples}  "
                  f"({100*total_hits/total_samples:.1f}%)")
            print(f"  Avg tags / frame      : {mean_tags:.2f} time-weighted, "
                  f"max {max_tags}")

        # Season-wide rejection breakdown
        agg_rej = defaultdict(int)
        for r in results:
            for reason, c in r["cameras"][cam].get("rejections", {}).items():
                agg_rej[reason] += c
        total_r = sum(agg_rej.values())
        if total_r > 0:
            passed   = agg_rej.get("PASS", 0)
            rejected = total_r - passed
            print(f"\n  Filter outcome        : {passed}/{total_r} pass "
                  f"({100*passed/total_r:.1f}%), {rejected} rejected "
                  f"({100*rejected/total_r:.1f}%)")
            print(f"  Rejection reasons (season):")
            print(f"  {'Reason':<18}  {'Count':>8}  {'% frames':>9}  {'% rejects':>10}  {'Per match':>9}")
            print(f"  {'-'*18}  {'-'*8}  {'-'*9}  {'-'*10}  {'-'*9}")
            for reason in REJECTION_REASONS:
                if reason == "PASS":
                    continue
                c = agg_rej.get(reason, 0)
                if c == 0:
                    continue
                print(f"  {reason:<18}  {c:>8d}  {100*c/total_r:>8.1f}%  "
                      f"{100*c/rejected if rejected else 0:>9.1f}%  "
                      f"{c / n_logs:>9.1f}")

        # Accepted-only summary pooled across all logs (season)
        season_accepted = {"tag_counts": [], "distances": [], "latencies": [],
                            "amb_means": [], "amb_maxes": []}
        for r in results:
            a = r["cameras"][cam].get("accepted", {})
            for k in season_accepted:
                season_accepted[k].extend(a.get(k, []))
        _print_accepted_block(_summarize_accepted(season_accepted), indent="  ")

    # Season-wide per-tag table (merge all logs + cameras)
    print()
    print(SEP)
    print("  PER-TAG SUMMARY (all cameras, all matches)")
    print(SEP)

    tag_agg = defaultdict(lambda: {"frames": 0, "dist_sum": 0.0, "amb_sum": 0.0,
                                     "dist_min": float("inf"), "dist_max": 0.0,
                                     "amb_max": 0.0, "cameras": set()})
    for r in results:
        for tid, t in r["tags"].items():
            a = tag_agg[tid]
            a["frames"]   += t["frames"]
            a["dist_sum"] += t["dist_mean"] * t["frames"]
            a["amb_sum"]  += t["amb_mean"]  * t["frames"]
            a["dist_min"]  = min(a["dist_min"], t["dist_min"])
            a["dist_max"]  = max(a["dist_max"], t["dist_max"])
            a["amb_max"]   = max(a["amb_max"],  t["amb_max"])
            a["cameras"].update(t["cameras"])

    if not tag_agg:
        print("\n  (no AprilTags seen in any log)")
    else:
        print(f"\n  {'Tag':>4}  {'Zone':<13}  {'Owns':<5}  {'Frames':>8}  "
              f"{'Dist mean':>9}  {'Dist range':>12}  {'Amb mean':>8}  "
              f"{'Amb max':>7}  {'Cams':>4}  {'Per match':>9}")
        print(f"  {'-'*4}  {'-'*13}  {'-'*5}  {'-'*8}  {'-'*9}  {'-'*12}  "
              f"{'-'*8}  {'-'*7}  {'-'*4}  {'-'*9}")
        ordered = sorted(tag_agg.items(), key=lambda kv: -kv[1]["frames"])
        for tid, a in ordered:
            zone, ally = zone_for(tid)
            dm = a["dist_sum"] / a["frames"] if a["frames"] else 0.0
            am = a["amb_sum"]  / a["frames"] if a["frames"] else 0.0
            dr = f"{a['dist_min']:.1f}-{a['dist_max']:.1f}"
            per_m = a["frames"] / n_logs
            print(f"  {tid:>4}  {zone:<13}  {ally:<5}  {a['frames']:>8d}  "
                  f"{dm:>7.2f} m  {dr:>12}  {am:>8.3f}  {a['amb_max']:>7.3f}  "
                  f"{len(a['cameras']):>4d}  {per_m:>9.1f}")

        # Per-zone totals + 'ours' vs 'theirs' breakdown. Uses the alliance
        # recorded in each match to credit tag sightings correctly even when
        # the season has matches on both alliances.
        # Structure: zone_agg[zone] = {"tags": set, "total": int,
        #                              "ours": int, "theirs": int}
        zone_agg = defaultdict(lambda: {"tags": set(), "total": 0,
                                          "ours": 0, "theirs": 0})
        for r in results:
            our = r.get("alliance")
            for tid, t in r["tags"].items():
                zone, ally = zone_for(tid)
                za = zone_agg[zone]
                za["tags"].add(tid)
                za["total"] += t["frames"]
                if our is not None and ally != "-":
                    if ally == our:
                        za["ours"] += t["frames"]
                    else:
                        za["theirs"] += t["frames"]
        total_frames = sum(z["total"] for z in zone_agg.values())
        print(f"\n  Zone summary (all cameras, all matches):")
        print(f"  {'Zone':<13}  {'Tags':>4}  {'Frames':>8}  {'% frames':>9}  "
              f"{'Per match':>9}  {'Ours':>7}  {'Theirs':>7}")
        print(f"  {'-'*13}  {'-'*4}  {'-'*8}  {'-'*9}  {'-'*9}  "
              f"{'-'*7}  {'-'*7}")
        # Order rows by ZONE_ORDER first, any unexpected zones sorted afterwards
        seen_zones = list(zone_agg.keys())
        ordered_zones = ([z for z in ZONE_ORDER if z in zone_agg] +
                         [z for z in seen_zones if z not in ZONE_ORDER])
        for zone in ordered_zones:
            z = zone_agg[zone]
            pct = 100 * z["total"] / total_frames if total_frames else 0.0
            per_m = z["total"] / n_logs
            print(f"  {zone:<13}  {len(z['tags']):>4d}  {z['total']:>8d}  "
                  f"{pct:>8.1f}%  {per_m:>9.1f}  "
                  f"{z['ours']:>7d}  {z['theirs']:>7d}")

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
            uniq.append(abs_p); seen.add(abs_p)
    return uniq

def parse_cli(argv):
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    summary_out = os.path.join(reports_dir, "limelight_summary.md")
    matches_out = os.path.join(reports_dir, "limelight_matches.md")
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
            print(f"\nWARNING: no Limelight data in {p}.")
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
        write_markdown_report("Limelight Analysis — Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Limelight Analysis — Season Summary",
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

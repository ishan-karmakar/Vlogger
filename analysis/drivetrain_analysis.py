# -*- coding: utf-8 -*-
"""
Drivetrain energy & performance analysis for FRC Team Valor 6800.

Per-module: Drive Motor (CAN IDs 1-4) + Azimuth Motor (CAN IDs 5-8) for
the 4 swerve modules (indexed 0-3 in the WPILog under SmartDashboard/SwerveDrive).

Inputs:
- WPILog (required): NetworkTables fields under SmartDashboard/SwerveDrive/* —
  per-module Drive/Azimuth Motor signals, gyro, driver state strings.
- *.hoot file paired in the wpilog's directory tree (optional, canivore bus
  only — files with `_rio_` in the name are skipped). Provides higher-fidelity
  Phoenix6/TalonFX-1..8 telemetry: DeviceTemp, SupplyCurrent, TorqueCurrent.
  Hoot reading needs CTRE's `owlet` — auto-detected on PATH or in `tools/`
  next to the repo root. If owlet is missing, hoot fields come back None and
  the WPI-only analysis still runs.

Power model    : |Out Volt| * |Stator Current| per motor, per axis (WPI)
Energy         : trapezoidal integration of instantaneous power over time
Tracking error : drive   = |reqSpeed - actual| (RPS)
                 azimuth = wrapped angular distance from reqPosition (deg)
Cycles         : ALIGN_TO_TARGET  windows from Driver Rotation State
                 X_MODE           windows from Driver Translation State

Hoot inputs alone (.hoot CLI arg) are accepted but the required Driver
Rotation State / Gyro Yaw / etc. only live in WPILogs — pass the wpilog and
the matching hoot is auto-paired.

Usage:
    python drivetrain_analysis.py                       # default log
    python drivetrain_analysis.py logs/                 # directory (recursive)
    python drivetrain_analysis.py -j 8 logs/            # 8 workers
    python drivetrain_analysis.py --no-file logs/       # terminal only
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

NUM_MODULES = 4
MODULE_LABELS = {0: "Module 0", 1: "Module 1", 2: "Module 2", 3: "Module 3"}

# Hoot CAN-ID mapping. Phoenix6 logs label devices as `Phoenix6/TalonFX-<id>/...`
# Layout for Valor's Downpour chassis (interleaved azim/drive per module):
#   module 0: azim=1, drive=2  | module 1: azim=3, drive=4
#   module 2: azim=5, drive=6  | module 3: azim=7, drive=8
# CANcoders 20..23 (one per module, in module order) and Pigeon-61 are on the
# same bus but aren't used by this analysis yet.
CAN_AZIMUTH_BY_MODULE = (1, 3, 5, 7)
CAN_DRIVE_BY_MODULE   = (2, 4, 6, 8)
CAN_CANCODER_BY_MODULE = (20, 21, 22, 23)
CAN_PIGEON             = 61

# Signals we want from each TalonFX in the paired hoot. Cheap subset of the
# ~112 signals per device; extending costs little since the regex filters at
# the source level.
HOOT_DRIVETRAIN_SIGNALS = ("DeviceTemp", "SupplyCurrent", "TorqueCurrent")
HOOT_REGEX = (
    r"Phoenix6/TalonFX-(?:[1-8])/(?:" + "|".join(HOOT_DRIVETRAIN_SIGNALS) + r")"
)

DRIVETRAIN_REGEX = (
    r"NT:/SmartDashboard/SwerveDrive/("
    r"Module [0-3]/(Drive|Azimuth) Motor/(Speed|Out Volt|Stator Current|Position|Absolute Position|reqSpeed|reqPosition)"
    r"|Gyro Yaw|Angular Velocity|Driver Rotation State|Driver Translation State|Rotation Target|Max Rotational Velocity"
    r")"
    r"|DS:enabled|DS:autonomous"
)


def _drive(i, leaf):  return f"NT:/SmartDashboard/SwerveDrive/Module {i}/Drive Motor/{leaf}"
def _azim(i, leaf):   return f"NT:/SmartDashboard/SwerveDrive/Module {i}/Azimuth Motor/{leaf}"

GYRO_YAW       = "NT:/SmartDashboard/SwerveDrive/Gyro Yaw"
ANG_VEL        = "NT:/SmartDashboard/SwerveDrive/Angular Velocity"
ROT_STATE      = "NT:/SmartDashboard/SwerveDrive/Driver Rotation State"
TRANS_STATE    = "NT:/SmartDashboard/SwerveDrive/Driver Translation State"
ROT_TARGET     = "NT:/SmartDashboard/SwerveDrive/Rotation Target"
MAX_ROT_VEL    = "NT:/SmartDashboard/SwerveDrive/Max Rotational Velocity"
DS_ENABLED     = "DS:enabled"
DS_AUTO        = "DS:autonomous"

ROT_STATES   = ("ALIGN_TO_TARGET", "DRIVER_ROTATION", "LOCKING_ROTATION", "X_MODE")
TRANS_STATES = ("DRIVER_TRANSLATION", "OFF", "X_MODE")

MIN_REQ_SPEED       = 1.0    # RPS — below this the drive setpoint is "idle" and skipped from tracking-error stats
ALIGN_TOL_RAD       = 0.05   # ~2.9 deg — same as flywheel.py's ALIGN_TOL_RAD
MIN_CYCLE_SECS      = 0.10   # ignore state windows shorter than this

SEP = "-" * 72


def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()


# -- Data loading ----------------------------------------------------------------

def _make_url(log_path):
    """Wrap a path as a vlogger URL. Both .wpilog and .hoot extensions are accepted."""
    if log_path.startswith(("wpilog:", "hoot:")):
        return log_path
    if log_path.lower().endswith(".hoot"):
        return f"hoot:///{log_path}"
    return f"wpilog:///{log_path}"


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
    """Return canivore-bus *.hoot files near a .wpilog (likely contain TalonFX-1..8).

    Heuristic: walk the wpilog's parent dir + 1-level subdirs; skip files with
    `_rio_` in name (rio-bus hoots don't have the swerve drivetrain). Sorting
    keeps the pairing deterministic across runs.
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
            if "_rio_" in f.name.lower():
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
    """Load WPI series + (optionally) any paired-hoot drivetrain signals.

    Returns (series_dict, hoot_files_used). Hoot pairing is best-effort — if
    owlet is missing or no paired files exist, hoot_files_used is empty and
    only the WPI fields are populated.
    """
    raw = defaultdict(list)

    src = vlogger.get_source(_make_url(log_path), DRIVETRAIN_REGEX)
    _load_into_raw(raw, src)

    hoot_files_used = []
    # Only pair hoots when the primary input is a wpilog — passing a .hoot
    # alone means the user explicitly opted in to that single source.
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


# -- Helpers ---------------------------------------------------------------------

def to_np(series, name):
    pts = series.get(name)
    if not pts or not isinstance(pts[0][1], (float, int)):
        return None, None
    return (np.array([p[0] for p in pts]),
            np.array([float(p[1]) for p in pts]))


def interp_at(ts_target, ts_src, vals_src):
    if ts_src is None or len(ts_src) < 2:
        return np.zeros_like(ts_target, dtype=float)
    return np.interp(ts_target, ts_src, vals_src,
                     left=vals_src[0], right=vals_src[-1])


def trapz_integral(ts, y, t_start=None, t_end=None):
    if t_start is None and t_end is None:
        if len(ts) < 2:
            return 0.0
        return float(np.trapezoid(y, ts))
    mask = np.ones_like(ts, dtype=bool)
    if t_start is not None: mask &= (ts >= t_start)
    if t_end   is not None: mask &= (ts <= t_end)
    if mask.sum() < 2:
        return 0.0
    return float(np.trapezoid(y[mask], ts[mask]))


def find_state_windows(state_pts, target_state, t_grid_end):
    """Contiguous windows where state == target_state. Returns [(t_start, t_end), ...]."""
    windows = []
    in_win  = False
    t_start = None
    for ts, val in state_pts:
        if not in_win and val == target_state:
            in_win, t_start = True, ts
        elif in_win and val != target_state:
            if ts - t_start >= MIN_CYCLE_SECS:
                windows.append((t_start, ts))
            in_win, t_start = False, None
    if in_win and t_start is not None:
        windows.append((t_start, t_grid_end))
    return windows


def state_time_distribution(state_pts, t_end):
    """Returns Counter of {state: total_seconds}."""
    out = Counter()
    if not state_pts:
        return out
    for i in range(len(state_pts) - 1):
        ts, val = state_pts[i]
        nxt     = state_pts[i + 1][0]
        out[val] += max(0.0, nxt - ts)
    last_ts, last_val = state_pts[-1]
    out[last_val] += max(0.0, t_end - last_ts)
    return out


def wrap_angle_rotations(x):
    """Wrap an angle expressed in rotations to [-0.5, 0.5)."""
    return (x + 0.5) % 1.0 - 0.5


def bool_at_grid(ts_grid, pts):
    """Step-interpolate a boolean event series onto a regular ts_grid.

    DS:enabled / DS:autonomous arrive as transitions, not samples — each entry
    is the new value at that timestamp. We hold the previous value forward
    until the next transition.
    """
    if not pts:
        return np.zeros_like(ts_grid, dtype=bool)
    ts_p  = np.array([p[0] for p in pts])
    val_p = np.array([bool(p[1]) for p in pts])
    idx = np.searchsorted(ts_p, ts_grid, side="right") - 1
    idx = np.clip(idx, 0, len(val_p) - 1)
    return val_p[idx]


def integrate_bool(ts_grid, mask):
    """Trapezoidal integral of a boolean indicator → total True-time in seconds."""
    if len(ts_grid) < 2:
        return 0.0
    return float(np.trapezoid(mask.astype(float), ts_grid))


# -- Per-log analysis ------------------------------------------------------------

def _hoot_motor_stats(series, canid):
    """Per-TalonFX peak/mean stats from the paired hoot. None if no hoot data.

    No interpolation: peaks/means are computed on the hoot's native timestamps,
    which preserves the high sample rate.
    """
    prefix = f"Phoenix6/TalonFX-{canid}"
    _, temp = to_np(series, f"{prefix}/DeviceTemp")
    _, supc = to_np(series, f"{prefix}/SupplyCurrent")
    _, tqc  = to_np(series, f"{prefix}/TorqueCurrent")
    if temp is None and supc is None and tqc is None:
        return None
    return {
        "peak_temp_c":      float(np.max(temp))       if temp is not None else None,
        "mean_temp_c":      float(np.mean(temp))      if temp is not None else None,
        "peak_supply_curr": float(np.max(np.abs(supc))) if supc is not None else None,
        "mean_supply_curr": float(np.mean(np.abs(supc))) if supc is not None else None,
        "peak_torque_curr": float(np.max(np.abs(tqc)))  if tqc  is not None else None,
    }


def _module_block(i, ts_grid, series):
    """Build the per-module result block. Returns dict + (drive_power_grid, azim_power_grid)."""
    ts_ds, drive_speed   = to_np(series, _drive(i, "Speed"))
    ts_dv, drive_volt    = to_np(series, _drive(i, "Out Volt"))
    ts_di, drive_curr    = to_np(series, _drive(i, "Stator Current"))
    ts_dp, drive_pos     = to_np(series, _drive(i, "Position"))
    ts_dq, drive_req     = to_np(series, _drive(i, "reqSpeed"))

    ts_as, azim_speed    = to_np(series, _azim(i, "Speed"))
    ts_av, azim_volt     = to_np(series, _azim(i, "Out Volt"))
    ts_ai, azim_curr     = to_np(series, _azim(i, "Stator Current"))
    ts_ap, azim_pos      = to_np(series, _azim(i, "Position"))
    ts_aq, azim_req      = to_np(series, _azim(i, "reqPosition"))

    ds  = interp_at(ts_grid, ts_ds, drive_speed) if ts_ds is not None else np.zeros_like(ts_grid)
    dv  = interp_at(ts_grid, ts_dv, drive_volt)  if ts_dv is not None else np.zeros_like(ts_grid)
    di  = interp_at(ts_grid, ts_di, drive_curr)  if ts_di is not None else np.zeros_like(ts_grid)
    dq  = interp_at(ts_grid, ts_dq, drive_req)   if ts_dq is not None else np.zeros_like(ts_grid)

    azs = interp_at(ts_grid, ts_as, azim_speed)  if ts_as is not None else np.zeros_like(ts_grid)
    azv = interp_at(ts_grid, ts_av, azim_volt)   if ts_av is not None else np.zeros_like(ts_grid)
    azi = interp_at(ts_grid, ts_ai, azim_curr)   if ts_ai is not None else np.zeros_like(ts_grid)
    azp = interp_at(ts_grid, ts_ap, azim_pos)    if ts_ap is not None else np.zeros_like(ts_grid)
    azq = interp_at(ts_grid, ts_aq, azim_req)    if ts_aq is not None else np.zeros_like(ts_grid)

    drive_power = np.abs(dv)  * np.abs(di)
    azim_power  = np.abs(azv) * np.abs(azi)

    drive_E_J     = trapz_integral(ts_grid, drive_power)
    azim_E_J      = trapz_integral(ts_grid, azim_power)
    rotations     = trapz_integral(ts_grid, np.abs(ds))   # ∫|speed| dt = total motor revolutions

    # Drive setpoint tracking — only count when commanded > MIN_REQ_SPEED.
    cmd_mask = np.abs(dq) >= MIN_REQ_SPEED
    if cmd_mask.any():
        drive_err = np.abs(dq[cmd_mask] - ds[cmd_mask])
        drive_err_avg = float(np.mean(drive_err))
        drive_err_pk  = float(np.max(drive_err))
    else:
        drive_err_avg = drive_err_pk = 0.0

    # Azimuth setpoint tracking — wrap to [-0.5, 0.5) rotations, convert to degrees.
    azim_err_rot = wrap_angle_rotations(azq - azp)
    azim_err_deg = np.abs(azim_err_rot) * 360.0
    azim_err_avg = float(np.mean(azim_err_deg))
    azim_err_pk  = float(np.max(azim_err_deg))

    # Distance-from-origin sanity: drive position is cumulative motor rotations
    if ts_dp is not None and len(drive_pos) > 1:
        drive_pos_range = float(drive_pos.max() - drive_pos.min())
    else:
        drive_pos_range = 0.0

    return {
        "idx":               i,
        "label":             MODULE_LABELS[i],
        "drive_can_id":      CAN_DRIVE_BY_MODULE[i],
        "azimuth_can_id":    CAN_AZIMUTH_BY_MODULE[i],
        "drive": {
            "peak_speed":         float(np.max(np.abs(ds))),
            "mean_abs_current":   float(np.mean(np.abs(di))),
            "peak_current":       float(np.max(np.abs(di))),
            "energy_J":           drive_E_J,
            "rotations":          rotations,
            "pos_span":           drive_pos_range,
            "tracking_err_avg":   drive_err_avg,
            "tracking_err_pk":    drive_err_pk,
            "hoot":               _hoot_motor_stats(series, CAN_DRIVE_BY_MODULE[i]),
        },
        "azimuth": {
            "mean_abs_current":   float(np.mean(np.abs(azi))),
            "peak_current":       float(np.max(np.abs(azi))),
            "energy_J":           azim_E_J,
            "tracking_err_deg_avg": azim_err_avg,
            "tracking_err_deg_pk":  azim_err_pk,
            "hoot":               _hoot_motor_stats(series, CAN_AZIMUTH_BY_MODULE[i]),
        },
    }, drive_power, azim_power


def analyze_log(log_path):
    """Run per-log drivetrain analysis. Returns dict, or None if required signals missing."""
    series, hoot_files_used = load_series(log_path)

    rot_pts   = series.get(ROT_STATE,    [])
    trans_pts = series.get(TRANS_STATE,  [])
    ts_yaw, gyro_yaw    = to_np(series, GYRO_YAW)
    ts_av,  ang_vel     = to_np(series, ANG_VEL)
    ts_rt,  rot_target  = to_np(series, ROT_TARGET)
    ds_enabled = series.get(DS_ENABLED, [])
    ds_auto    = series.get(DS_AUTO, [])

    # We need at least Module 0 drive speed + a state series to do anything useful.
    ts_m0_drive, _ = to_np(series, _drive(0, "Speed"))
    if ts_m0_drive is None or not rot_pts:
        return None

    # Build a common timebase from all the per-module drive/azimuth speed streams.
    ts_seeds = [ts_m0_drive]
    for i in range(1, NUM_MODULES):
        t, _ = to_np(series, _drive(i, "Speed"))
        if t is not None: ts_seeds.append(t)
        t, _ = to_np(series, _azim(i, "Speed"))
        if t is not None: ts_seeds.append(t)
    ts_grid = np.unique(np.concatenate(ts_seeds))
    t0, t_end = float(ts_grid[0]), float(ts_grid[-1])
    session_len = t_end - t0

    # Per-module blocks + cumulative drive / azimuth power.
    modules = []
    drive_power_tot = np.zeros_like(ts_grid)
    azim_power_tot  = np.zeros_like(ts_grid)
    for i in range(NUM_MODULES):
        m, dp, ap = _module_block(i, ts_grid, series)
        modules.append(m)
        drive_power_tot += dp
        azim_power_tot  += ap
    chassis_power_tot = drive_power_tot + azim_power_tot

    total_drive_E = trapz_integral(ts_grid, drive_power_tot)
    total_azim_E  = trapz_integral(ts_grid, azim_power_tot)
    total_E       = total_drive_E + total_azim_E

    # State distributions.
    rot_time   = state_time_distribution(rot_pts,   t_end)
    trans_time = state_time_distribution(trans_pts, t_end)

    # Chassis kinematics.
    if ts_av is not None:
        peak_yaw_rate_deg_s = float(np.max(np.abs(ang_vel)))
        mean_abs_yaw_rate   = float(np.mean(np.abs(ang_vel)))
    else:
        peak_yaw_rate_deg_s = mean_abs_yaw_rate = 0.0
    if ts_yaw is not None and len(gyro_yaw) >= 2:
        # Gyro yaw arrives unwrapped (degrees) — net rotation is just last - first.
        net_yaw_deg   = float(gyro_yaw[-1] - gyro_yaw[0])
        total_yaw_revs = abs(net_yaw_deg) / 360.0
    else:
        net_yaw_deg = total_yaw_revs = 0.0

    # ALIGN_TO_TARGET cycles — entry-to-settle latency.
    align_cycles = []
    if ts_yaw is not None and ts_rt is not None:
        for t_start, t_e in find_state_windows(rot_pts, "ALIGN_TO_TARGET", t_end):
            yaw_in_win    = interp_at(ts_grid, ts_yaw, gyro_yaw)
            target_in_win = interp_at(ts_grid, ts_rt,  rot_target)
            mask = (ts_grid >= t_start) & (ts_grid <= t_e)
            if mask.sum() < 2:
                continue
            # Heading error: convert unwrapped yaw (deg) to wrapped radians, diff vs target (rad), wrap.
            yaw_rad = np.deg2rad(yaw_in_win[mask])
            err_rad = (yaw_rad - target_in_win[mask] + np.pi) % (2*np.pi) - np.pi
            settled_idx = np.where(np.abs(err_rad) <= ALIGN_TOL_RAD)[0]
            settle_t = float(ts_grid[mask][settled_idx[0]] - t_start) if len(settled_idx) else float("inf")
            E_cyc = trapz_integral(ts_grid, chassis_power_tot, t_start, t_e)
            align_cycles.append({
                "t_start":  t_start,
                "t_end":    t_e,
                "dur":      t_e - t_start,
                "settle_t": settle_t,
                "E_J":      E_cyc,
                "n_samples": int(mask.sum()),
            })

    # X_MODE windows — total time spent fighting the wheels in an X.
    x_windows = []
    for t_start, t_e in find_state_windows(trans_pts, "X_MODE", t_end):
        x_windows.append({
            "t_start": t_start,
            "t_end":   t_e,
            "dur":     t_e - t_start,
            "E_J":     trapz_integral(ts_grid, chassis_power_tot, t_start, t_e),
        })

    # DS time accounting. DS:autonomous reflects the *selected* mode (true even
    # while the robot is disabled in the pit), so "auto seconds" must be
    # (enabled AND autonomous), not the raw DS:autonomous duration.
    en_g = bool_at_grid(ts_grid, ds_enabled)
    au_g = bool_at_grid(ts_grid, ds_auto)
    enabled_s = integrate_bool(ts_grid, en_g)
    auto_s    = integrate_bool(ts_grid, en_g & au_g)
    teleop_s  = max(0.0, enabled_s - auto_s)

    # Chassis-wide hoot rollup: peak temperature across all 8 motors, and the
    # peak sum of supply currents (worst-case battery draw if all spike together).
    all_temps = []
    sum_supply_pk = 0.0
    for m in modules:
        for axis in ("drive", "azimuth"):
            h = m[axis].get("hoot")
            if not h:
                continue
            if h.get("peak_temp_c") is not None:
                all_temps.append(h["peak_temp_c"])
            if h.get("peak_supply_curr") is not None:
                sum_supply_pk += h["peak_supply_curr"]
    max_motor_temp_c = max(all_temps) if all_temps else None
    # sum_supply_pk is conservative (sum of per-motor peaks, not peak of sum) —
    # the true peak-of-sum needs joint timestamps; leave that for a future pass.

    return {
        "log_path":      log_path,
        "session_len":   session_len,
        "enabled_s":     enabled_s,
        "auto_s":        auto_s,
        "teleop_s":      teleop_s,
        "modules":       modules,
        "chassis": {
            "drive_energy_J":         total_drive_E,
            "azim_energy_J":          total_azim_E,
            "total_energy_J":         total_E,
            "peak_yaw_rate_deg_s":    peak_yaw_rate_deg_s,
            "mean_abs_yaw_rate":      mean_abs_yaw_rate,
            "net_yaw_deg":            net_yaw_deg,
            "total_yaw_revs":         total_yaw_revs,
            "max_motor_temp_c":       max_motor_temp_c,
            "sum_motor_supply_pk":    sum_supply_pk if sum_supply_pk > 0 else None,
        },
        "hoot_files_used":        hoot_files_used,
        "rotation_state_time":    dict(rot_time),
        "translation_state_time": dict(trans_time),
        "align_cycles":           align_cycles,
        "x_mode_windows":         x_windows,
    }


# -- Per-log report --------------------------------------------------------------

def print_per_log_report(r):
    log_name = os.path.basename(r["log_path"])

    print()
    print(SEP)
    print(f"  DRIVETRAIN ANALYSIS  --  {log_name}")
    print(SEP)
    print(f"\n  Log duration            : {r['session_len']:.1f} s  ({r['session_len']/60:.2f} min)")
    if r['enabled_s'] > 0:
        print(f"  Enabled time            : {r['enabled_s']:.1f} s  "
              f"(auto {r['auto_s']:.1f}s + teleop {r['teleop_s']:.1f}s)")
    print(f"  Total drive energy      : {r['chassis']['drive_energy_J']/1000:.2f} kJ")
    print(f"  Total azimuth energy    : {r['chassis']['azim_energy_J']/1000:.2f} kJ")
    print(f"  Total chassis energy    : {r['chassis']['total_energy_J']/1000:.2f} kJ")
    print(f"  Peak yaw rate           : {r['chassis']['peak_yaw_rate_deg_s']:.0f} deg/s")
    print(f"  Net heading change      : {r['chassis']['net_yaw_deg']:>+.1f} deg "
          f"({r['chassis']['total_yaw_revs']:.2f} full revolutions)")
    if r["chassis"].get("max_motor_temp_c") is not None:
        print(f"  Peak motor temp         : {r['chassis']['max_motor_temp_c']:.1f} °C  "
              f"(across all 8 drivetrain motors)")
    if r["chassis"].get("sum_motor_supply_pk") is not None:
        print(f"  Sum of peak supply Is   : {r['chassis']['sum_motor_supply_pk']:.1f} A  "
              f"(conservative worst-case battery draw)")
    if r.get("hoot_files_used"):
        print(f"  Hoot data merged from   : {len(r['hoot_files_used'])} file(s)")
        for hp in r["hoot_files_used"]:
            print(f"      - {os.path.basename(hp)}")

    # -- Per-module table
    print()
    print(f"  Per-module (Drive/Azimuth):")
    print()
    print(f"  {'#':>2}  {'Pk Spd':>7}  {'Drv Iavg':>8}  {'Drv Ipk':>8}  "
          f"{'Drv kJ':>7}  {'Drv ErrAvg':>10}  {'Drv ErrPk':>9}  "
          f"{'Azm Iavg':>8}  {'Azm Ipk':>8}  {'Azm kJ':>7}  "
          f"{'Azm ErrAvg':>10}  {'Azm ErrPk':>9}")
    print(f"  {'-'*2}  {'-'*7}  {'-'*8}  {'-'*8}  "
          f"{'-'*7}  {'-'*10}  {'-'*9}  "
          f"{'-'*8}  {'-'*8}  {'-'*7}  "
          f"{'-'*10}  {'-'*9}")
    for m in r["modules"]:
        d = m["drive"]; a = m["azimuth"]
        print(f"  {m['idx']:>2}  "
              f"{d['peak_speed']:>6.1f}R  "
              f"{d['mean_abs_current']:>7.1f}A  {d['peak_current']:>7.1f}A  "
              f"{d['energy_J']/1000:>6.2f}k  "
              f"{d['tracking_err_avg']:>9.2f}R  {d['tracking_err_pk']:>8.2f}R  "
              f"{a['mean_abs_current']:>7.1f}A  {a['peak_current']:>7.1f}A  "
              f"{a['energy_J']/1000:>6.2f}k  "
              f"{a['tracking_err_deg_avg']:>9.1f}d  {a['tracking_err_deg_pk']:>8.1f}d")

    # -- Hoot-derived per-motor telemetry (only printed if any module has it)
    if any(m["drive"].get("hoot") or m["azimuth"].get("hoot") for m in r["modules"]):
        print()
        print(f"  Per-motor telemetry (from hoot):")
        print()
        print(f"  {'#':>2}  {'Drv °C pk':>9}  {'Drv °C avg':>10}  {'Drv I_sup pk':>13}  {'Drv I_torq pk':>14}  "
              f"{'Azm °C pk':>9}  {'Azm I_sup pk':>13}")
        print(f"  {'-'*2}  {'-'*9}  {'-'*10}  {'-'*13}  {'-'*14}  "
              f"{'-'*9}  {'-'*13}")
        for m in r["modules"]:
            dh = m["drive"].get("hoot")  or {}
            ah = m["azimuth"].get("hoot") or {}
            def _f(d, k, fmt):
                v = d.get(k)
                return fmt.format(v) if v is not None else "  --   "
            print(f"  {m['idx']:>2}  "
                  f"{_f(dh, 'peak_temp_c',      '{:>7.1f}°'):>9}  "
                  f"{_f(dh, 'mean_temp_c',      '{:>8.1f}°'):>10}  "
                  f"{_f(dh, 'peak_supply_curr', '{:>11.1f}A'):>13}  "
                  f"{_f(dh, 'peak_torque_curr', '{:>12.1f}A'):>14}  "
                  f"{_f(ah, 'peak_temp_c',      '{:>7.1f}°'):>9}  "
                  f"{_f(ah, 'peak_supply_curr', '{:>11.1f}A'):>13}")

    # -- Drive energy balance: are all 4 modules pulling roughly the same?
    drive_E = np.array([m["drive"]["energy_J"] for m in r["modules"]])
    if drive_E.sum() > 0:
        share = 100.0 * drive_E / drive_E.sum()
        print()
        print(f"  Drive energy share      : "
              + " | ".join(f"M{i}={share[i]:.1f}%" for i in range(NUM_MODULES)))
        spread = float(share.max() - share.min())
        print(f"  Module imbalance        : max-min spread = {spread:.1f}% "
              f"({'>' if spread > 10 else '<='}10% threshold)")

    # -- Rotation state distribution
    print()
    print(f"  Time in each Driver Rotation State:")
    print(f"  {'State':>20}  {'Time (s)':>10}  {'% of log':>8}")
    print(f"  {'-'*20}  {'-'*10}  {'-'*8}")
    for st in ROT_STATES:
        t = r["rotation_state_time"].get(st, 0.0)
        pct = (100 * t / r["session_len"]) if r["session_len"] > 0 else 0.0
        print(f"  {st:>20}  {t:>10.1f}  {pct:>7.1f}%")

    # -- Translation state distribution
    print()
    print(f"  Time in each Driver Translation State:")
    print(f"  {'State':>20}  {'Time (s)':>10}  {'% of log':>8}")
    print(f"  {'-'*20}  {'-'*10}  {'-'*8}")
    for st in TRANS_STATES:
        t = r["translation_state_time"].get(st, 0.0)
        pct = (100 * t / r["session_len"]) if r["session_len"] > 0 else 0.0
        print(f"  {st:>20}  {t:>10.1f}  {pct:>7.1f}%")

    # -- ALIGN_TO_TARGET cycles
    print()
    print(SEP)
    print("  ALIGN_TO_TARGET CYCLES")
    print(SEP)
    cycles = r["align_cycles"]
    if cycles:
        print(f"\n  {'#':>2}  {'Start':>7}  {'Dur (s)':>7}  {'Settle (s)':>10}  {'E (J)':>7}")
        print(f"  {'-'*2}  {'-'*7}  {'-'*7}  {'-'*10}  {'-'*7}")
        for i, c in enumerate(cycles):
            settle = "no-settle" if c["settle_t"] == float("inf") else f"{c['settle_t']:.2f}"
            print(f"  {i+1:>2}  {c['t_start']:>7.1f}  {c['dur']:>7.2f}  {settle:>10}  {c['E_J']:>7.0f}")
        print()
        durs    = np.array([c["dur"] for c in cycles])
        settled = np.array([c["settle_t"] for c in cycles if c["settle_t"] != float("inf")])
        print(f"  Total align cycles      : {len(cycles)}")
        print(f"  Cycles that settled     : {len(settled)} / {len(cycles)}  "
              f"(within {np.rad2deg(ALIGN_TOL_RAD):.1f} deg)")
        if len(settled):
            print(f"  Avg settle time         : {np.mean(settled):.2f} s  "
                  f"(min {np.min(settled):.2f}, max {np.max(settled):.2f})")
        print(f"  Avg cycle duration      : {np.mean(durs):.2f} s")
    else:
        print("\n  No ALIGN_TO_TARGET windows in this log.")

    # -- X_MODE windows
    print()
    print(SEP)
    print("  X_MODE WINDOWS  (Driver Translation State)")
    print(SEP)
    xw = r["x_mode_windows"]
    if xw:
        durs = np.array([w["dur"] for w in xw])
        Es   = np.array([w["E_J"] for w in xw])
        print(f"\n  X_MODE windows          : {len(xw)}")
        print(f"  Total time in X_MODE    : {np.sum(durs):.1f} s")
        print(f"  Avg duration            : {np.mean(durs):.2f} s")
        print(f"  Energy in X_MODE        : {np.sum(Es)/1000:.2f} kJ  "
              f"(avg {np.mean(Es):.0f} J / window)")
    else:
        print("\n  No X_MODE windows in this log.")

    print()
    print(SEP)


# -- Combined / season report ----------------------------------------------------

def print_combined_analysis(results):
    n_matches = len(results)
    if n_matches == 0:
        return

    print()
    print(SEP)
    print(f"  DRIVETRAIN ANALYSIS  --  SEASON SUMMARY  ({n_matches} match{'es' if n_matches != 1 else ''})")
    print(SEP)

    # -- Per-match summary table
    print()
    print(f"  {'#':>2}  {'Match':<38}  {'Dur(s)':>7}  {'Drv kJ':>7}  {'Azm kJ':>7}  "
          f"{'PkYaw':>6}  {'Aligns':>6}  {'X-Md':>4}")
    print(f"  {'-'*2}  {'-'*38}  {'-'*7}  {'-'*7}  {'-'*7}  "
          f"{'-'*6}  {'-'*6}  {'-'*4}")
    for i, r in enumerate(results):
        name = os.path.basename(r["log_path"])
        if len(name) > 38:
            name = name[:35] + "..."
        print(f"  {i+1:>2}  {name:<38}  {r['session_len']:>7.1f}  "
              f"{r['chassis']['drive_energy_J']/1000:>7.2f}  "
              f"{r['chassis']['azim_energy_J']/1000:>7.2f}  "
              f"{r['chassis']['peak_yaw_rate_deg_s']:>6.0f}  "
              f"{len(r['align_cycles']):>6d}  "
              f"{len(r['x_mode_windows']):>4d}")

    total_drive_E   = sum(r["chassis"]["drive_energy_J"] for r in results)
    total_azim_E    = sum(r["chassis"]["azim_energy_J"]  for r in results)
    total_session   = sum(r["session_len"] for r in results)
    total_enabled   = sum(r["enabled_s"]   for r in results)
    total_aligns    = sum(len(r["align_cycles"])    for r in results)
    total_xmode     = sum(len(r["x_mode_windows"])  for r in results)

    print()
    print(f"  Totals across all matches:")
    print(f"    Drive energy         : {total_drive_E/1000:.2f} kJ")
    print(f"    Azimuth energy       : {total_azim_E/1000:.2f} kJ")
    print(f"    Combined energy      : {(total_drive_E+total_azim_E)/1000:.2f} kJ")
    print(f"    Combined log time    : {total_session:.1f} s  ({total_session/60:.2f} min)")
    if total_enabled > 0:
        print(f"    Combined enabled time: {total_enabled:.1f} s  ({total_enabled/60:.2f} min)")
    print(f"    ALIGN_TO_TARGET evts : {total_aligns}")
    print(f"    X_MODE evts          : {total_xmode}")

    print()
    print(f"  Per-match averages:")
    print(f"    Drive energy/match   : {(total_drive_E / n_matches)/1000:.2f} kJ")
    print(f"    Azim energy/match    : {(total_azim_E  / n_matches)/1000:.2f} kJ")
    print(f"    Aligns/match         : {total_aligns / n_matches:.1f}")
    print(f"    X_MODE/match         : {total_xmode  / n_matches:.1f}")

    # -- Hoot rollup (only when at least one match included a paired hoot)
    matches_with_hoot = [r for r in results if r.get("hoot_files_used")]
    if matches_with_hoot:
        # Per-CAN-ID peak temperature + supply current across season.
        per_id_peak_temp = {cid: -float("inf") for cid in (*CAN_DRIVE_BY_MODULE, *CAN_AZIMUTH_BY_MODULE)}
        per_id_peak_supc = {cid: 0.0           for cid in per_id_peak_temp}
        global_peak_temp = -float("inf")
        for r in matches_with_hoot:
            for m in r["modules"]:
                for axis_key, cid in (("drive",   m["drive_can_id"]),
                                      ("azimuth", m["azimuth_can_id"])):
                    h = m[axis_key].get("hoot")
                    if not h:
                        continue
                    t = h.get("peak_temp_c")
                    if t is not None:
                        per_id_peak_temp[cid] = max(per_id_peak_temp[cid], t)
                        global_peak_temp     = max(global_peak_temp, t)
                    c = h.get("peak_supply_curr")
                    if c is not None:
                        per_id_peak_supc[cid] = max(per_id_peak_supc[cid], c)

        print()
        print(f"  Hoot motor telemetry  (paired hoot data on {len(matches_with_hoot)} / "
              f"{n_matches} match{'es' if n_matches != 1 else ''}):")
        print(f"    Season peak temp    : {global_peak_temp:.1f} °C  (any motor)")
        print(f"    Per-motor peaks (°C / A_supply):")
        for cid in (*CAN_DRIVE_BY_MODULE, *CAN_AZIMUTH_BY_MODULE):
            label = ("DRV" if cid in CAN_DRIVE_BY_MODULE else "AZM")
            mod_idx = (CAN_DRIVE_BY_MODULE.index(cid) if cid in CAN_DRIVE_BY_MODULE
                       else CAN_AZIMUTH_BY_MODULE.index(cid))
            t = per_id_peak_temp[cid]
            c = per_id_peak_supc[cid]
            t_str = f"{t:>6.1f}°C" if t != -float("inf") else "  --   "
            c_str = f"{c:>6.1f} A" if c > 0 else "  --   "
            print(f"      TalonFX-{cid:<2} (M{mod_idx} {label}): {t_str}  {c_str}")

    # -- Aggregate per-module energy share (across all matches)
    mod_drive_E = np.zeros(NUM_MODULES)
    mod_azim_E  = np.zeros(NUM_MODULES)
    mod_drive_pk_I = np.zeros(NUM_MODULES)
    mod_azim_pk_I  = np.zeros(NUM_MODULES)
    for r in results:
        for i, m in enumerate(r["modules"]):
            mod_drive_E[i]    += m["drive"]["energy_J"]
            mod_azim_E[i]     += m["azimuth"]["energy_J"]
            mod_drive_pk_I[i] = max(mod_drive_pk_I[i], m["drive"]["peak_current"])
            mod_azim_pk_I[i]  = max(mod_azim_pk_I[i],  m["azimuth"]["peak_current"])

    print()
    print(f"  Per-module aggregate (across {n_matches} match{'es' if n_matches != 1 else ''}):")
    print(f"  {'#':>2}  {'Drv kJ':>7}  {'Drv %':>6}  {'Drv Ipk':>8}  "
          f"{'Azm kJ':>7}  {'Azm %':>6}  {'Azm Ipk':>8}")
    print(f"  {'-'*2}  {'-'*7}  {'-'*6}  {'-'*8}  "
          f"{'-'*7}  {'-'*6}  {'-'*8}")
    drv_total = mod_drive_E.sum()
    azm_total = mod_azim_E.sum()
    for i in range(NUM_MODULES):
        d_pct = (100.0 * mod_drive_E[i] / drv_total) if drv_total > 0 else 0.0
        a_pct = (100.0 * mod_azim_E[i]  / azm_total) if azm_total > 0 else 0.0
        print(f"  {i:>2}  {mod_drive_E[i]/1000:>7.2f}  {d_pct:>5.1f}%  {mod_drive_pk_I[i]:>7.1f}A  "
              f"{mod_azim_E[i]/1000:>7.2f}  {a_pct:>5.1f}%  {mod_azim_pk_I[i]:>7.1f}A")
    if drv_total > 0:
        share = 100.0 * mod_drive_E / drv_total
        spread = float(share.max() - share.min())
        verdict = "BALANCED" if spread <= 10 else "IMBALANCED"
        print(f"\n  Drive imbalance (max-min share spread): {spread:.1f}%  -- {verdict}")

    # -- Rotation state aggregates
    rot_totals = Counter()
    trans_totals = Counter()
    for r in results:
        for st, t in r["rotation_state_time"].items():    rot_totals[st]   += t
        for st, t in r["translation_state_time"].items(): trans_totals[st] += t

    print()
    print(f"  Driver Rotation State distribution (all matches):")
    print(f"    {'State':>20}  {'Total (s)':>10}  {'% of all logs':>14}")
    print(f"    {'-'*20}  {'-'*10}  {'-'*14}")
    for st in ROT_STATES:
        t = rot_totals.get(st, 0.0)
        pct = (100 * t / total_session) if total_session > 0 else 0.0
        print(f"    {st:>20}  {t:>10.1f}  {pct:>13.1f}%")

    print()
    print(f"  Driver Translation State distribution (all matches):")
    print(f"    {'State':>20}  {'Total (s)':>10}  {'% of all logs':>14}")
    print(f"    {'-'*20}  {'-'*10}  {'-'*14}")
    for st in TRANS_STATES:
        t = trans_totals.get(st, 0.0)
        pct = (100 * t / total_session) if total_session > 0 else 0.0
        print(f"    {st:>20}  {t:>10.1f}  {pct:>13.1f}%")

    # -- ALIGN_TO_TARGET aggregate
    all_aligns = [c for r in results for c in r["align_cycles"]]
    if all_aligns:
        durs    = np.array([c["dur"] for c in all_aligns])
        settled = np.array([c["settle_t"] for c in all_aligns if c["settle_t"] != float("inf")])
        print()
        print(f"  ALIGN_TO_TARGET stats ({len(all_aligns)} cycles total):")
        print(f"    Cycles that settled  : {len(settled)} / {len(all_aligns)}  "
              f"({100*len(settled)/len(all_aligns):.1f}%)")
        if len(settled):
            print(f"    Avg settle time      : {np.mean(settled):.2f} s  "
                  f"(min {np.min(settled):.2f}, max {np.max(settled):.2f})")
        print(f"    Avg cycle duration   : {np.mean(durs):.2f} s")

    print()
    print(SEP)


# -- CLI / parallel infrastructure -----------------------------------------------

def resolve_log_paths(args):
    if not args:
        return [DEFAULT_LOG]

    def walk_dir(d):
        found = []
        for root, dirs, files in os.walk(d):
            # Skip our own GUI cache dirs
            dirs[:] = [x for x in dirs if x != ".vlogger_cache"]
            for f in files:
                if f.lower().endswith((".wpilog", ".hoot")):
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
            elif os.path.isfile(h) and h.lower().endswith((".wpilog", ".hoot")):
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
            print(f"\nWARNING: required drivetrain signals missing in {p}.")
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
        write_markdown_report("Drivetrain Analysis - Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Drivetrain Analysis - Season Summary",
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

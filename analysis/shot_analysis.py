# -*- coding: utf-8 -*-
"""
Shot-system energy analysis for FRC Team Valor 6800.

Cross-subsystem aggregator: for every flywheel SHOOT cycle, integrates the
energy each of {flywheel, feeder, hopper} contributed to the shot. Lets you
answer "what does a shot cost the whole shooting stack in joules" and
"which cycles are the most/least efficient".

Cycle definition is canonical from flywheel_analysis.find_shoot_windows
(SHOOT → DISABLE windows on the Flywheel State machine). shot_analysis
asserts _cycles.CYCLE_SCHEMA on import so a flywheel-side change to the
cycle dict shape forces an explicit version bump here.

Subsystem decoding is done in one pass via a unioned regex covering all 7
motors + the flywheel state + aiming mode. We don't reuse the per-subsystem
analyses' load_series — each of those re-iterates the wpilog (3-7×
duplicate decode work for what's already a streaming I/O cost).

Usage:
    python shot_analysis.py                          # default log
    python shot_analysis.py logs/                    # directory (recursive)
    python shot_analysis.py logs/*.wpilog            # glob
    python shot_analysis.py -j 8 logs/               # 8 workers
    python shot_analysis.py --no-file logs/          # terminal only
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

# Sibling helpers + canonical cycle definition.
try:
    from . import _cycles, flywheel_analysis
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _cycles
    import flywheel_analysis

# The cycle dict shape we depend on (t_start, t_end, aim_mode, drive_state)
# is part of CYCLE_SCHEMA v1. Bump in lockstep with flywheel_analysis when
# any cycle field shot_analysis reads changes.
_REQUIRED_CYCLE_SCHEMA = 1
assert _cycles.CYCLE_SCHEMA == _REQUIRED_CYCLE_SCHEMA, (
    f"shot_analysis was written for CYCLE_SCHEMA={_REQUIRED_CYCLE_SCHEMA} "
    f"but found {_cycles.CYCLE_SCHEMA}; update shot_analysis to handle the "
    "new cycle dict shape, then bump _REQUIRED_CYCLE_SCHEMA."
)

# -- Configuration ---------------------------------------------------------------

DEFAULT_LOG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "GF1",
    "FRC_20260418_213237_TXCMP_E1.wpilog"
)).replace("\\", "/")

# Union of every signal we touch. Three groups:
#   1. Flywheel state + aiming mode (cycle source + categorisation).
#   2. Per-motor Speed / Stator Current / Out Volt for each subsystem motor.
SHOT_REGEX = (
    r"NT:/SmartDashboard/("
        r"Shooter/(Flywheel (Left|Right One|Right Two) Motor/(Speed|Stator Current|Out Volt)"
            r"|Flywheel State|Projectile Aiming Mode)"
        r"|Intake/(Left|Right) (Feeder|Hopper) Motor/(Speed|Stator Current|Out Volt)"
    r")"
)
REGEX = SHOT_REGEX

# Flywheel state + categorisation
F_STATE       = "NT:/SmartDashboard/Shooter/Flywheel State"
F_AIMING_MODE = "NT:/SmartDashboard/Shooter/Projectile Aiming Mode"

# Per-subsystem motor inventory: (subsystem_label, [(motor_label, NT_prefix), ...])
SUBSYSTEMS = (
    ("flywheel", [
        ("Left",      "NT:/SmartDashboard/Shooter/Flywheel Left Motor"),
        ("Right One", "NT:/SmartDashboard/Shooter/Flywheel Right One Motor"),
        ("Right Two", "NT:/SmartDashboard/Shooter/Flywheel Right Two Motor"),
    ]),
    ("feeder", [
        ("Left",  "NT:/SmartDashboard/Intake/Left Feeder Motor"),
        ("Right", "NT:/SmartDashboard/Intake/Right Feeder Motor"),
    ]),
    ("hopper", [
        ("Left",  "NT:/SmartDashboard/Intake/Left Hopper Motor"),
        ("Right", "NT:/SmartDashboard/Intake/Right Hopper Motor"),
    ]),
)

SEP = "-" * 72

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

# -- Data loading ----------------------------------------------------------------

def load_series(log_path):
    """Single-pass decode of all signals shot_analysis depends on.

    Returns a plain dict keyed by NT path. No hoot pairing — shot_analysis
    works entirely off the wpilog-side power signals. Per-motor temp /
    supply current from hoot is the per-subsystem analyses' job.
    """
    raw = defaultdict(list)
    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, SHOT_REGEX)
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

def _to_np(series, name):
    pts = series.get(name)
    if not pts or not isinstance(pts[0][1], (float, int)):
        return None, None
    return (np.array([p[0] for p in pts]),
            np.array([float(p[1]) for p in pts]))

def _interp(ts_target, ts_src, vals_src):
    if ts_src is None or len(ts_src) < 2:
        return np.zeros_like(ts_target, dtype=float)
    return np.interp(ts_target, ts_src, vals_src,
                     left=vals_src[0], right=vals_src[-1])

def _state_at_time(state_pts, t, default="?"):
    latest = default
    for ts, val in state_pts:
        if ts > t:
            break
        latest = val
    return latest

def _motor_power(series, prefix, ts_grid):
    """|V| * |I_stator| on the common grid for one motor.

    Returns a numpy array the same shape as ts_grid. Missing voltage or
    current series → zeros (motor effectively contributes nothing to the
    energy integral). Both signals are interpolated onto the shared grid
    so the resulting power series is integrable over arbitrary windows.
    """
    ts_v, v = _to_np(series, f"{prefix}/Out Volt")
    ts_i, i = _to_np(series, f"{prefix}/Stator Current")
    if ts_v is None or ts_i is None:
        return np.zeros_like(ts_grid, dtype=float)
    v_g = _interp(ts_grid, ts_v, v)
    i_g = _interp(ts_grid, ts_i, i)
    return np.abs(v_g) * np.abs(i_g)

# -- Per-log analysis ------------------------------------------------------------

def analyze_log(log_path):
    """Run cross-subsystem shot analysis. Returns a result dict, or None
    when the wpilog has no Flywheel State (no cycles to integrate over)."""
    series = load_series(log_path)

    state_pts  = series.get(F_STATE, [])
    aiming_pts = series.get(F_AIMING_MODE, [])
    if not state_pts:
        return None

    cycle_windows = flywheel_analysis.find_shoot_windows(state_pts)
    if not cycle_windows:
        return {
            "log_path":     log_path,
            "n_cycles":     0,
            "cycles":       [],
            "session_len":  0.0,
            "totals":       {label: 0.0 for label, _ in SUBSYSTEMS},
        }

    # Build the common time grid from every motor's voltage timestamps.
    # Voltage is the densest signal on TalonFX status frames so it makes
    # the tightest grid for energy integration.
    all_ts = []
    for _, motors in SUBSYSTEMS:
        for _, prefix in motors:
            ts_v, _ = _to_np(series, f"{prefix}/Out Volt")
            if ts_v is not None:
                all_ts.append(ts_v)
    if not all_ts:
        return None
    ts_grid = np.unique(np.concatenate(all_ts))
    session_len = float(ts_grid[-1] - ts_grid[0])

    # Per-subsystem total power on the common grid.
    subsys_power = {}
    for label, motors in SUBSYSTEMS:
        p = np.zeros_like(ts_grid, dtype=float)
        for _, prefix in motors:
            p += _motor_power(series, prefix, ts_grid)
        subsys_power[label] = p

    cycles = []
    for t_start, t_end in cycle_windows:
        mask = (ts_grid >= t_start) & (ts_grid <= t_end)
        if mask.sum() < 2:
            # Window too short for the trapezoidal integrator; record zeros.
            energies = {label: 0.0 for label in subsys_power}
            peaks    = {label: 0.0 for label in subsys_power}
            avgs     = {label: 0.0 for label in subsys_power}
        else:
            energies = {
                label: float(np.trapezoid(p[mask], ts_grid[mask]))
                for label, p in subsys_power.items()
            }
            peaks = {label: float(np.max(p[mask])) for label, p in subsys_power.items()}
            avgs  = {label: float(np.mean(p[mask])) for label, p in subsys_power.items()}
        total_E = sum(energies.values())
        total_pk = sum(peaks.values())  # not strictly meaningful (peaks may not align in time) but useful

        cycles.append({
            "t_start":     t_start,
            "t_end":       t_end,
            "dur":         t_end - t_start,
            "aim_mode":    _state_at_time(aiming_pts, t_start, default="UNKNOWN"),
            "energies":    energies,             # {subsystem: J}
            "peaks":       peaks,                # {subsystem: peak W within window}
            "avgs":        avgs,                 # {subsystem: mean W within window}
            "total_E_J":   total_E,
            "total_peak_W":total_pk,
        })

    # Season-style totals summed across cycles
    totals = {label: sum(c["energies"][label] for c in cycles) for label, _ in SUBSYSTEMS}

    return {
        "log_path":    log_path,
        "session_len": session_len,
        "n_cycles":    len(cycles),
        "cycles":      cycles,
        "totals":      totals,
    }

# -- Per-log report --------------------------------------------------------------

def print_per_log_report(r):
    log_name = os.path.basename(r["log_path"])
    cycles   = r["cycles"]

    print()
    print(SEP)
    print(f"  SHOT ANALYSIS  --  {log_name}")
    print(SEP)
    print(f"\n  Log duration         : {r['session_len']:.1f} s  ({r['session_len']/60:.2f} min)")
    print(f"  Shoot cycles         : {r['n_cycles']}")
    if r["n_cycles"] == 0:
        print("\n  No flywheel SHOOT cycles found — nothing to integrate.")
        print(SEP)
        return

    totals = r["totals"]
    grand = sum(totals.values())
    print(f"  Total shot-stack energy (sum of cycles): {grand/1000:.2f} kJ")
    print()
    print(f"  By subsystem (total across cycles):")
    print(f"  {'Subsystem':<12}  {'Energy (kJ)':>11}  {'% of total':>10}")
    print(f"  {'-'*12}  {'-'*11}  {'-'*10}")
    for label, _ in SUBSYSTEMS:
        e = totals[label]
        pct = (100 * e / grand) if grand > 0 else 0.0
        print(f"  {label:<12}  {e/1000:>11.2f}  {pct:>9.1f}%")

    print()
    print(f"  Per-cycle breakdown:")
    print()
    print(f"  {'#':>2}  {'Start':>7}  {'Dur':>5}  {'Mode':>9}  "
          f"{'Fly (J)':>8}  {'Fdr (J)':>8}  {'Hop (J)':>8}  {'Total (J)':>10}  "
          f"{'PkW':>5}")
    print(f"  {'-'*2}  {'-'*7}  {'-'*5}  {'-'*9}  "
          f"{'-'*8}  {'-'*8}  {'-'*8}  {'-'*10}  "
          f"{'-'*5}")
    for i, c in enumerate(cycles):
        print(f"  {i+1:>2}  {c['t_start']:>7.1f}  {c['dur']:>4.2f}s  "
              f"{c['aim_mode'][:9]:>9}  "
              f"{c['energies']['flywheel']:>8.1f}  "
              f"{c['energies']['feeder']:>8.1f}  "
              f"{c['energies']['hopper']:>8.1f}  "
              f"{c['total_E_J']:>10.1f}  "
              f"{c['total_peak_W']:>5.0f}")

    # Cycle-distribution summary
    durs = np.array([c["dur"] for c in cycles])
    tots = np.array([c["total_E_J"] for c in cycles])
    print()
    print(f"  Cycle stats:")
    print(f"    Avg duration         : {np.mean(durs):.2f} s  "
          f"(min {np.min(durs):.2f}, max {np.max(durs):.2f})")
    print(f"    Avg total energy/cyc : {np.mean(tots):.1f} J  "
          f"(min {np.min(tots):.1f}, max {np.max(tots):.1f})")
    print()
    print(SEP)

# -- Combined / season report ----------------------------------------------------

def print_combined_analysis(results):
    n_matches = len(results)
    if n_matches == 0:
        return

    print()
    print(SEP)
    print(f"  SHOT ANALYSIS  --  SEASON SUMMARY  ({n_matches} match{'es' if n_matches != 1 else ''})")
    print(SEP)

    print()
    print(f"  {'#':>2}  {'Match':<38}  {'Cyc':>4}  {'Fly kJ':>7}  {'Fdr kJ':>7}  {'Hop kJ':>7}  {'Tot kJ':>7}")
    print(f"  {'-'*2}  {'-'*38}  {'-'*4}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}")
    for i, r in enumerate(results):
        name = os.path.basename(r["log_path"])
        if len(name) > 38:
            name = name[:35] + "..."
        t = r["totals"]
        grand = sum(t.values())
        print(f"  {i+1:>2}  {name:<38}  {r['n_cycles']:>4d}  "
              f"{t['flywheel']/1000:>7.2f}  {t['feeder']/1000:>7.2f}  "
              f"{t['hopper']/1000:>7.2f}  {grand/1000:>7.2f}")

    all_cycles = [c for r in results for c in r["cycles"]]
    if not all_cycles:
        print("\n  No shoot cycles in any match.")
        print(SEP); return

    # Per-aim-mode breakdown.
    by_mode = defaultdict(list)
    for c in all_cycles:
        by_mode[c["aim_mode"]].append(c)

    print()
    print(SEP)
    print("  BREAKDOWN BY AIMING MODE")
    print(SEP)
    print()
    print(f"  {'Mode':<12}  {'Cyc':>4}  {'Avg Fly':>8}  {'Avg Fdr':>8}  "
          f"{'Avg Hop':>8}  {'Avg Tot':>8}  {'Total kJ':>9}")
    print(f"  {'-'*12}  {'-'*4}  {'-'*8}  {'-'*8}  "
          f"{'-'*8}  {'-'*8}  {'-'*9}")
    for mode in sorted(by_mode):
        cs = by_mode[mode]
        n = len(cs)
        avg_fly = np.mean([c["energies"]["flywheel"] for c in cs])
        avg_fdr = np.mean([c["energies"]["feeder"]   for c in cs])
        avg_hop = np.mean([c["energies"]["hopper"]   for c in cs])
        avg_tot = np.mean([c["total_E_J"]            for c in cs])
        sum_tot = sum(c["total_E_J"] for c in cs)
        print(f"  {mode[:12]:<12}  {n:>4d}  {avg_fly:>8.1f}  {avg_fdr:>8.1f}  "
              f"{avg_hop:>8.1f}  {avg_tot:>8.1f}  {sum_tot/1000:>9.2f}")

    # Subsystem rollups.
    print()
    print(f"  Across all {len(all_cycles)} cycles:")
    grand = 0.0
    for label, _ in SUBSYSTEMS:
        e = sum(c["energies"][label] for c in all_cycles)
        grand += e
        print(f"    {label:<10} total : {e/1000:>7.2f} kJ  "
              f"(avg {e/len(all_cycles):.1f} J/cyc)")
    print(f"    {'shot-stack':<10} total : {grand/1000:>7.2f} kJ  "
          f"(avg {grand/len(all_cycles):.1f} J/cyc)")

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
    summary_out = os.path.join(reports_dir, "shot_summary.md")
    matches_out = os.path.join(reports_dir, "shot_matches.md")
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
            print(f"\nWARNING: no flywheel state in {p}.")
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
        write_markdown_report("Shot Analysis - Per-Match Breakdown",
                              matches_buf.getvalue(), matches_out, paths,
                              extra_note="Season summary is in the companion summary file.")
        progress(f"Writing summary report to {summary_out} ...")
        write_markdown_report("Shot Analysis - Season Summary",
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

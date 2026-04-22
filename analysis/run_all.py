# -*- coding: utf-8 -*-
"""
Orchestrator: run every analysis script in this folder against a set of logs.

Each analysis is registered in the ANALYSES table below. Run:
    python -X utf8 analysis/run_all.py logs/
    python -X utf8 analysis/run_all.py --list
    python -X utf8 analysis/run_all.py --only flywheel,joystick logs/
    python -X utf8 analysis/run_all.py --skip intake logs/
    python -X utf8 analysis/run_all.py -j 4 logs/

The wrapper forwards positional log arguments and common flags (-j, --no-file,
--summary-out, --matches-out) to each child script. Each script is invoked as a
subprocess so it keeps its own isolated process pool and stderr/stdout streams.

---------------------------------------------------------------------------------
ADDING A NEW ANALYSIS SCRIPT

1. Copy an existing analysis script (e.g. `joystick_analysis.py`) as your
   starting template. The expected structure:
     - A `DEFAULT_LOG` constant for a single-log default run
     - A `<thing>_REGEX` constant naming the NT paths you need
     - A `load_series(log_path)` function
     - An `analyze_log(log_path) -> dict | None` function
     - A `print_per_log_report(result)` function
     - A `print_combined_analysis(results)` function
     - A `load_all(paths, workers)` process-pool loader
     - A `main()` that parses CLI args identically to the other scripts and
       writes two markdown files (`<name>_summary.md`, `<name>_matches.md`).

2. Keep the CLI flags consistent across all analysis scripts:
     positional: log paths / directories / globs
     -o / --output / --summary-out PATH
     --matches-out PATH
     --no-file
     -j N / --workers N
     --serial

3. Register the new script in the ANALYSES table below with a short `name`
   (used by --only / --skip), the `script` filename, and a one-line
   `description`.

4. Add a short section to README.md under "Analysis Scripts" describing what
   the script produces and the log signals it depends on.
---------------------------------------------------------------------------------
"""

import sys
import os
import time
import subprocess
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

# Registry of analysis scripts. Adding a new analysis = copy a template and
# append an entry here. Keep `name` short and lowercase (it's the CLI selector).
ANALYSES = [
    {
        "name":        "flywheel",
        "script":      "flywheel_analysis.py",
        "description": "Flywheel energy, spin-up, cruise power, drivetrain align + X-mode timing.",
    },
    {
        "name":        "intake",
        "script":      "intake_analysis.py",
        "description": "Intake motor current/energy, INTAKING/SHOOTING state windows, jam events.",
    },
    {
        "name":        "joystick",
        "script":      "joystick_analysis.py",
        "description": "Driver + operator gamepad input: axis activity, button presses, POV usage.",
    },
    {
        "name":        "limelight",
        "script":      "limelight_analysis.py",
        "description": "Vision: 3 cameras — latency, targets visible, distance, per-tag summary.",
    },
]

def banner(msg, ch="="):
    line = ch * 72
    sys.stderr.write(f"\n{line}\n  {msg}\n{line}\n")
    sys.stderr.flush()

def progress(msg):
    sys.stderr.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

def parse_cli(argv):
    selected_names = None   # None = all
    skipped_names  = set()
    passthrough    = []     # args forwarded to each child script
    list_only      = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--list":
            list_only = True
            i += 1
        elif a == "--only":
            if i + 1 >= len(argv):
                sys.stderr.write("ERROR: --only requires a comma-separated name list\n")
                sys.exit(2)
            selected_names = {x.strip() for x in argv[i + 1].split(",") if x.strip()}
            i += 2
        elif a == "--skip":
            if i + 1 >= len(argv):
                sys.stderr.write("ERROR: --skip requires a comma-separated name list\n")
                sys.exit(2)
            skipped_names.update(x.strip() for x in argv[i + 1].split(",") if x.strip())
            i += 2
        else:
            # Every other arg (positional logs + known per-script flags) passes through
            passthrough.append(a)
            i += 1
    return selected_names, skipped_names, passthrough, list_only

def print_list():
    sys.stderr.write("Available analyses:\n")
    w = max(len(a["name"]) for a in ANALYSES)
    for a in ANALYSES:
        sys.stderr.write(f"  {a['name']:<{w}}  {a['description']}\n")

def run_one(analysis, passthrough):
    script = os.path.join(HERE, analysis["script"])
    if not os.path.isfile(script):
        progress(f"SKIPPING {analysis['name']}: {script} not found")
        return 1, 0.0
    cmd = [sys.executable, "-X", "utf8", script, *passthrough]
    progress(f"-> {' '.join(os.path.basename(c) if c == script else c for c in cmd)}")
    t0  = time.time()
    # Use Popen so we can terminate cleanly on Ctrl-C. subprocess.call swallows
    # SIGINT and can leave the child running as an orphan on some platforms.
    proc = subprocess.Popen(cmd)
    try:
        rc = proc.wait()
    except KeyboardInterrupt:
        progress(f"Interrupted — terminating {analysis['name']} child process ...")
        proc.terminate()
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()
        raise
    dt  = time.time() - t0
    return rc, dt

def main():
    selected, skipped, passthrough, list_only = parse_cli(sys.argv[1:])
    if list_only:
        print_list()
        return

    # Build the run list in registry order
    to_run = []
    for a in ANALYSES:
        if selected is not None and a["name"] not in selected:
            continue
        if a["name"] in skipped:
            continue
        to_run.append(a)

    if not to_run:
        sys.stderr.write("No analyses selected (check --only / --skip).\n")
        print_list()
        sys.exit(2)

    banner(f"run_all: {len(to_run)} analysis script(s)")
    for a in to_run:
        sys.stderr.write(f"  - {a['name']:<10} {a['description']}\n")

    t_start = time.time()
    results = []
    for a in to_run:
        banner(f"ANALYSIS: {a['name']}")
        rc, dt = run_one(a, passthrough)
        results.append((a["name"], rc, dt))
        status = "OK" if rc == 0 else f"FAILED (rc={rc})"
        progress(f"{a['name']} {status} in {dt:.1f}s")

    banner("run_all summary", ch="=")
    sys.stderr.write(f"  {'Analysis':<12}  {'Status':>8}  {'Elapsed':>9}\n")
    sys.stderr.write(f"  {'-'*12}  {'-'*8}  {'-'*9}\n")
    for name, rc, dt in results:
        status = "OK" if rc == 0 else f"rc={rc}"
        sys.stderr.write(f"  {name:<12}  {status:>8}  {dt:>8.1f}s\n")
    sys.stderr.write(f"  {'-'*12}  {'-'*8}  {'-'*9}\n")
    total_dt = time.time() - t_start
    sys.stderr.write(f"  {'TOTAL':<12}  {'':>8}  {total_dt:>8.1f}s\n")

    # Exit non-zero if any child failed
    if any(rc != 0 for _, rc, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\nAborted by user.\n")
        sys.exit(130)

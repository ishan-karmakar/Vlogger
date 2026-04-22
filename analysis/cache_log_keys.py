# -*- coding: utf-8 -*-
"""
Regenerate the log-key reference file that documents every field published
by the robot in both WPILog (NT + DS) and the two .hoot logs (RIO +
Canivore buses).

Run this once per major robot-code change (new subsystems, renamed signals)
so future analysis scripts / LLM agents can grep a single markdown file
instead of probing every log themselves.

Usage:
    python cache_log_keys.py                          # auto-pick one wpilog
    python cache_log_keys.py path/to/match.wpilog     # explicit log
    python cache_log_keys.py logs/E1                  # folder; uses the
                                                      #   first wpilog + any
                                                      #   sibling .hoots
    python cache_log_keys.py --wpilog <path> --hoot <path> --hoot <path>

Output: analysis/LOG_REFERENCE.md (committed so it's searchable).
"""

import sys
import os
import glob
import shutil
import subprocess
import datetime
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
# wpiutil is vendored through robotpy-wpiutil; imported lazily when needed.

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DEFAULT_OUTPUT = os.path.join(HERE, "LOG_REFERENCE.md")

# Grouping heuristics — each regex/prefix groups field names under a heading
# in the generated reference. Order matters: the first match wins. Unmatched
# fields land in "Other / Uncategorized".
WPILOG_GROUPS = [
    ("DS / FMS / System",
        lambda n: n.startswith("DS:") or n.startswith("systemTime")
               or "FMSInfo" in n or "Messages" in n),
    ("Schema definitions",
        lambda n: n.startswith("NT:/.schema/")),
    ("Joysticks (DS)",
        lambda n: n.startswith("DS:joystick")),
    ("Limelight (NT)",
        lambda n: "/limelight-" in n.lower() or "limelight" in n.lower()),
    ("Camera publishers (NT)",
        lambda n: n.startswith("NT:/CameraPublisher/")),
    ("Shooter / Flywheel / Hood",
        lambda n: "/Shooter/" in n or "Flywheel" in n or "Hood" in n),
    ("Intake / Hopper / Feeder",
        lambda n: "/Intake/" in n),
    ("Swerve Drive modules",
        lambda n: "/SwerveDrive/Module " in n),
    ("Swerve Drive (other)",
        lambda n: "/SwerveDrive/" in n),
    ("Climber",
        lambda n: "/Climber/" in n or "climber" in n.lower()),
    ("Power Distribution",
        lambda n: "Power Distribution" in n or "PDP" in n or "PDH" in n),
    ("Auto / Trajectory",
        lambda n: "Auto" in n or "Traj" in n or "Choreo" in n),
    ("Smart Dashboard (misc)",
        lambda n: n.startswith("NT:/SmartDashboard/")),
    ("Other NT",
        lambda n: n.startswith("NT:/")),
]

# Noise filters — these patterns are auto-hidden from the primary listing and
# only summarized as a count (keeps the reference doc manageable).
NOISY_PATTERNS = [
    "/Operational Mode/",
    "/Tuning Mode/",
    "Tuning Setpoint",
    ".controllable", ".instance", ".name", ".type",
    "/active", "/default", "/options", "/selected",
    "/Tune",  # the boolean tuning-toggle flag
]

def _is_noisy(name):
    return any(p in name for p in NOISY_PATTERNS)

def _group_for(name):
    for label, pred in WPILOG_GROUPS:
        if pred(name):
            return label
    return "Other / Uncategorized"

# -- Log discovery --------------------------------------------------------------

def find_default_wpilog():
    """Return the first .wpilog found under logs/, sorted alphabetically."""
    logs_dir = os.path.join(REPO_ROOT, "logs")
    if not os.path.isdir(logs_dir):
        return None
    for root, _, files in os.walk(logs_dir):
        for f in sorted(files):
            if f.lower().endswith(".wpilog"):
                return os.path.join(root, f)
    return None

def find_sibling_hoots(wpilog_path):
    log_dir = os.path.dirname(os.path.abspath(wpilog_path))
    hoots = []
    for root, _, files in os.walk(log_dir):
        for f in files:
            if f.lower().endswith(".hoot"):
                hoots.append(os.path.join(root, f))
    return sorted(hoots)

def find_owlet():
    on_path = shutil.which("owlet")
    if on_path:
        return on_path
    repo_owlet = os.path.join(REPO_ROOT, "owlet.exe")
    return repo_owlet if os.path.isfile(repo_owlet) else None

# -- Scanners -------------------------------------------------------------------

def scan_wpilog(path):
    """
    Scan a wpilog via wpiutil.log.DataLogReader and return a list of
    (name, type) tuples.
    """
    from wpiutil.log import DataLogReader
    reader = DataLogReader(path)
    out = []
    seen = set()
    for rec in reader:
        if rec.isStart():
            d = rec.getStartData()
            key = d.name
            if key not in seen:
                seen.add(key)
                out.append((d.name, d.type))
    out.sort(key=lambda x: x[0])
    return out

def scan_hoot(path, owlet_exe):
    """Run `owlet --scan` and return list of (name, hex_id) tuples."""
    result = subprocess.run(
        [owlet_exe, path, "--scan"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        check=False, text=True,
    )
    out = []
    for line in (result.stdout or "").splitlines():
        if ":" not in line:
            continue
        name, _, rest = line.partition(":")
        name = name.strip()
        hex_id = rest.strip()
        if name and hex_id and all(c in "0123456789abcdefABCDEF" for c in hex_id):
            out.append((name, hex_id))
    out.sort(key=lambda x: x[0])
    return out

# -- Hoot grouping (by device kind + CAN ID) ------------------------------------

def hoot_device_key(name):
    """Extract device kind+id (e.g. 'TalonFX-12') from 'TalonFX-12/StatorCurrent'."""
    if "/" not in name:
        return "Other"
    head, _ = name.split("/", 1)
    return head or "Other"

# -- Markdown emission ----------------------------------------------------------

def emit_markdown(wpilog_path, wpilog_fields, hoot_scans):
    """
    Build the reference markdown. hoot_scans is a dict of
    hoot_path -> [(name, hex_id), ...].
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# Log field reference")
    lines.append("")
    lines.append(
        "Cached field catalog for the robot's WPILog + hoot logs. Scripts "
        "and agents can grep this file instead of probing a fresh log every "
        "time they need to know what signals are available.")
    lines.append("")
    lines.append(f"_Generated: {now} by `analysis/cache_log_keys.py`._")
    lines.append("")
    lines.append(f"Sources scanned:")
    lines.append(f"- WPILog: `{wpilog_path}`  ({len(wpilog_fields)} fields)")
    for hp, entries in hoot_scans.items():
        lines.append(f"- Hoot: `{hp}`  ({len(entries)} signals)")
    lines.append("")
    lines.append("Regenerate when the robot code adds/renames signals:")
    lines.append("```bash")
    lines.append("python -X utf8 analysis/cache_log_keys.py")
    lines.append("```")
    lines.append("")

    # --- WPILog grouped listing ---
    lines.append("---")
    lines.append("")
    lines.append("## WPILog fields")
    lines.append("")

    grouped = defaultdict(list)
    noisy_count = defaultdict(int)
    for name, dtype in wpilog_fields:
        if _is_noisy(name):
            noisy_count[_group_for(name)] += 1
            continue
        grouped[_group_for(name)].append((name, dtype))

    # Emit in the declared order
    group_order = [lbl for lbl, _ in WPILOG_GROUPS] + ["Other / Uncategorized"]
    for label in group_order:
        entries = grouped.get(label, [])
        hidden = noisy_count.get(label, 0)
        if not entries and not hidden:
            continue
        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"_{len(entries)} fields"
                     + (f"; {hidden} noise fields hidden (tune/mode/options/etc)"
                        if hidden else "")
                     + "._")
        lines.append("")
        lines.append("| Name | Type |")
        lines.append("|---|---|")
        for name, dtype in entries:
            # Escape pipes in names (rare)
            safe_name = name.replace("|", "\\|")
            lines.append(f"| `{safe_name}` | `{dtype}` |")
        lines.append("")

    # --- Hoot grouped listing ---
    if hoot_scans:
        lines.append("---")
        lines.append("")
        lines.append("## Hoot (Phoenix) signals")
        lines.append("")
        lines.append(
            "Hoot logs require `owlet` to decode. Signal IDs below are the "
            "hex values owlet uses with `-s` for filtered extraction (passing "
            "only the IDs you want keeps decode time to a second or two).")
        lines.append("")
        for hp, entries in hoot_scans.items():
            lines.append(f"### `{os.path.basename(hp)}`")
            lines.append("")
            lines.append(f"_{len(entries)} signals._")
            lines.append("")
            # Group by device
            by_device = defaultdict(list)
            for name, hex_id in entries:
                by_device[hoot_device_key(name)].append((name, hex_id))
            for dev in sorted(by_device):
                lines.append(f"#### `{dev}`")
                lines.append("")
                lines.append("| Signal | Hex ID |")
                lines.append("|---|---|")
                for name, hex_id in by_device[dev]:
                    # Show the short signal name (strip device prefix)
                    short = name.split("/", 1)[1] if "/" in name else name
                    lines.append(f"| `{short}` | `{hex_id}` |")
                lines.append("")

    return "\n".join(lines)

# -- CLI ------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("paths", nargs="*",
                    help="wpilog files and/or folders (default: auto-discover one "
                         "wpilog from logs/ and scan sibling hoots)")
    ap.add_argument("--wpilog", default=None,
                    help="explicit wpilog path (overrides positional)")
    ap.add_argument("--hoot", action="append", default=None,
                    help="explicit hoot path(s); repeat for multiple")
    ap.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                    help=f"output markdown (default: {DEFAULT_OUTPUT})")
    ap.add_argument("--no-hoot", action="store_true",
                    help="skip hoot scans even if owlet is available")
    return ap.parse_args()

def _resolve_inputs(args):
    """Figure out which wpilog + hoots to scan."""
    wpilog = args.wpilog
    hoots  = args.hoot

    # Positional args can be either files or folders
    if wpilog is None and args.paths:
        for p in args.paths:
            if os.path.isfile(p) and p.lower().endswith(".wpilog"):
                wpilog = p
                break
            if os.path.isdir(p):
                matches = sorted(glob.glob(os.path.join(p, "**", "*.wpilog"),
                                            recursive=True))
                if matches:
                    wpilog = matches[0]
                    break

    if wpilog is None:
        wpilog = find_default_wpilog()

    if wpilog is None:
        sys.stderr.write("ERROR: no wpilog found — pass one explicitly.\n")
        sys.exit(2)

    if hoots is None:
        hoots = find_sibling_hoots(wpilog) if not args.no_hoot else []

    return wpilog, hoots

def main():
    args = parse_args()
    wpilog_path, hoots = _resolve_inputs(args)

    sys.stderr.write(f"Scanning WPILog: {wpilog_path}\n")
    wpilog_fields = scan_wpilog(wpilog_path)
    sys.stderr.write(f"  {len(wpilog_fields)} fields found\n")

    hoot_scans = {}
    if hoots:
        owlet = find_owlet()
        if owlet is None:
            sys.stderr.write("WARNING: owlet not found; skipping hoot scans\n")
        else:
            for hp in hoots:
                sys.stderr.write(f"Scanning hoot: {hp}\n")
                entries = scan_hoot(hp, owlet)
                sys.stderr.write(f"  {len(entries)} signals found\n")
                hoot_scans[hp] = entries

    md = emit_markdown(wpilog_path, wpilog_fields, hoot_scans)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".",
                exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    sys.stderr.write(f"Wrote {args.output} ({os.path.getsize(args.output):,} bytes)\n")


if __name__ == "__main__":
    main()

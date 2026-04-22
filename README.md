# FRC Vlogger
## What is this?
Vlogger is a generic library that provides an abstraction over the various kinds of files and live sources that are used in FRC.  
This package is developed and used by FRC Valor 6800 for post match analysis.

## Supported Sources
- [x] [WPILog](https://github.com/wpilibsuite/allwpilib/blob/main/wpiutil/doc/datalog.adoc) (supports structs and protobufs)
- [x] [NetworkTables4](https://github.com/wpilibsuite/allwpilib/blob/main/ntcore/doc/networktables4.adoc) (supports structs and protobufs)
- [x] [CTRE Hoot](https://v6.docs.ctr-electronics.com/en/latest/docs/api-reference/api-usage/signal-logging.html) (file format does not support custom types)
- [ ] DSLog/DSEvents, unlikely to be added soon
- [x] Phoenix Diagnostic Server

## Motivation
Clients usually just care about the "meat" of the source (that is, the field name, the value, and the timestamp). It usually does not matter to the client where the data came from (i.e. the logic is the same whether it is from a live source or from a log file), and this means that every source should be exposed in a single API that should be a drop in replacement.  
Additionally, there is no ready to use package in Python to parse WPILog files or connect to NetworkTables4 servers.  
This package was heavily inspired by [AdvantageScope](https://github.com/Mechanical-Advantage/AdvantageScope)'s [dataSources](https://github.com/Mechanical-Advantage/AdvantageScope/tree/main/src/hub/dataSources) folder code.

## API Structure
Each source is initialized with:
- A reference to the "connection"
    - For historical logs (i.e. from a log file), this will usually be the path of the log file
    - For live sources (i.e. connecting to a server), this will usually be the hostname of the target machine
- A list of regexes to match the regexes against. This was a design choice made to improve performance by only parsing fields that are going to be used. While not recommended, a regex of `""` can be used to match all fields.
- Any additional arguments that are required for that specific source. This may be for additional configuration or outside executables (the hoot source uses this) to properly parse the file

## Examples
### Initializing a generic source
If the file/connection source is not known, it is recommended to use the `get_source` function to iterate through the sources and performing validation on each.
```python
import vlogger

# "" regex matches with anything, i.e. any field
with vlogger.get_source("my_log.wpilog", [""]) as source:
    for field in source:
        print(field)
```

### Initializing a specific source
If the file/connection source is known, it may be faster and more readable to explicitly initialize the specific source. This example uses the Hoot source, which requires a reference to the [owlet](https://docs.ctr-electronics.com/cli-tools.html) executable (if not found in `PATH`).
```python
from vlogger.sources.wpilog import Hoot

with Hoot("my_log.hoot", ["^MyTargetFields$"], owlet="../my-owlet") as hoot:
    for field in hoot:
        print(field)
```

### Merging sources
Vlogger has the ability to merge multiple sources into one iterable that will be parsed in chronological order. While it has been tested, keep in mind that some sources such as WPILog and even NT4 have been found to itself be store/give data in a non-chronological order. While it has a very low error rate, it is still something to keep in mind when using this feature.
```python
import vlogger

with vlogger.get_source("my_log.wpilog", [""]) as wpilog, \
     vlogger.get_source("my_log.hoot", [""]) as hoot:
    for field in vlogger.merge_sources(wpilog, hoot):
        print(field)
```

## Analysis Scripts

The `analysis/` folder contains ready-to-run scripts that use vlogger to produce match-by-match and season-wide reports from WPILog files. Use the orchestrator to run them all at once, or invoke any one directly — they all share the same CLI conventions:

- Accept any combination of files, globs, or directories (directories are walked **recursively** for `*.wpilog`).
- Run log parsing in parallel via a process pool (default workers = `min(cpu_count, n_logs)`).
- Print a per-match breakdown and a combined/season summary to the terminal.
- Write two markdown files into `analysis/reports/` (gitignored): a per-match breakdown and a season summary.

Common flags (identical across the three scripts):

| Flag | Purpose |
|---|---|
| `-o PATH` / `--output PATH` / `--summary-out PATH` | Path for the season-summary markdown file |
| `--matches-out PATH` | Path for the per-match markdown file |
| `--no-file` | Skip writing markdown files (terminal only) |
| `-j N` / `--workers N` | Parallel worker count (use `1` or `--serial` to debug) |
| `--serial` | Run single-process |

Put your WPILog files anywhere — a common layout is `logs/<match>/FRC_*.wpilog`. The scripts also read `DS:enabled` so time-based metrics are expressed against enabled match time, not wall-clock log time.

### `analysis/run_all.py` (orchestrator)

Runs every registered analysis script against the same set of logs and prints a per-script elapsed-time summary at the end. Each analysis is launched as a subprocess so it keeps its own isolated process pool and progress output.

```bash
# Run every analysis against a season of logs
python -X utf8 analysis/run_all.py logs/

# See which analyses are registered
python -X utf8 analysis/run_all.py --list

# Subset selection
python -X utf8 analysis/run_all.py --only flywheel,joystick logs/
python -X utf8 analysis/run_all.py --skip intake logs/

# Flags pass through to every child script
python -X utf8 analysis/run_all.py -j 8 --no-file logs/
```

Any flag the orchestrator doesn't recognize is forwarded verbatim to each child script, so anything that works on a single script (log paths, `-j`, `--no-file`, `--summary-out`, etc.) works through `run_all`.

### `analysis/flywheel_analysis.py`

Flywheel energy + performance analysis. Produces:
- Per-match: duration, enabled time, peak RPS, total flywheel energy, shoot cycle table (per-cycle: commanded speed, spin-up time, currents, energy, drivetrain align time, X-mode timing, aiming mode).
- Season summary: averaged spin-up stats, cruise power, three-way `SCORING | SHUTTLING | COMBINED` breakdown (cycle counts, energies, align/X-mode latency), `P(ω)` cruise-power fit, break-even analyses (keep-spinning vs spin-up-per-shot, low-speed idle strategies, coast-aware respin, higher-target extrapolation).

Required log signals (NetworkTables paths under `SmartDashboard/`):
- `Shooter/Flywheel Left Motor/*` and both `Right One`/`Right Two` motors (`Speed`, `Stator Current`, `Out Volt`, `reqSpeed`)
- `Shooter/Flywheel State` (`SHOOT` / `DISABLE`)
- `Shooter/Projectile Aiming Mode` (`SCORING` / `SHUTTLING`)
- `Intake/Left|Right Feeder Motor/Speed`
- `SwerveDrive/Gyro Yaw`, `SwerveDrive/Rotation Target`, `SwerveDrive/Driver Rotation State`
- `DS:enabled`

```bash
# Default log
python -X utf8 analysis/flywheel_analysis.py

# Recursive directory scan across a season
python -X utf8 analysis/flywheel_analysis.py logs/

# Custom output path, 8 workers
python -X utf8 analysis/flywheel_analysis.py -j 8 -o out/season.md logs/

# Single file, no markdown
python -X utf8 analysis/flywheel_analysis.py --no-file path/to/match.wpilog
```

Outputs (default paths): `analysis/reports/flywheel_summary.md`, `analysis/reports/flywheel_matches.md`.

### `analysis/intake_analysis.py`

Intake motor analysis covering two motors (Left/Right) plus jam events. Produces:
- Per-match: duration, peak speeds, total intake energy, time distribution across `OFF` / `INTAKING` / `SHOOTING` states, per-cycle table for every INTAKING window (duration, commanded vs actual speed, stator + supply current, energy, jam count), stall detection, jam event list with cycle/state context, SHOOTING state summary.

Required log signals (under `SmartDashboard/Intake/`):
- `Left Intake Motor/*` and `Right Intake Motor/*` (`Speed`, `Stator Current`, `Supply Current`, `Out Volt`, `reqSpeed`)
- `Intake State` (`OFF` / `INTAKING` / `SHOOTING`)
- `Intake Jam`

```bash
python -X utf8 analysis/intake_analysis.py
python -X utf8 analysis/intake_analysis.py logs/GF1/FRC_xxx.wpilog
```

Currently prints to terminal only (no markdown file output yet).

### `analysis/joystick_analysis.py`

Driver + Operator gamepad input analysis. Produces:
- Per-match: for each joystick, axis activity (min / max / mean |value| / time above deadband), rising-edge button press counts, POV/D-pad presses per direction.
- Season summary: total button presses across matches + per-match averages, POV totals, axis activity with season-wide min/max/mean/active-time, and a "busy-ness" comparison between Driver and Operator.

Assumes `joystick0` = Driver, `joystick1` = Operator. Axis / button labels use a standard Xbox controller mapping (see `AXIS_LABELS` / `BUTTON_LABELS` near the top of the script).

Required log signals: `DS:joystick0/{axes,buttons,povs}`, `DS:joystick1/{axes,buttons,povs}`, `DS:enabled`.

```bash
python -X utf8 analysis/joystick_analysis.py logs/
python -X utf8 analysis/joystick_analysis.py --serial logs/GF1/FRC_xxx.wpilog
```

Outputs (default paths): `analysis/reports/joystick_summary.md`, `analysis/reports/joystick_matches.md`.

### `analysis/limelight_analysis.py`

All three Limelights (`limelight-center` / `-left` / `-right`) analyzed against the robot's actual vision filter. Produces:
- **Per-camera, per-match:**
  - Active-as-pose-source %, raw `tv` %, team `hasTarget` %, `Vision Filter Pass` %
  - Capture / target / end-to-end latency (mean / p50 / p95 / max)
  - Frames with any tag + average tags per frame
  - Distance to primary target (mean / p95 / max)
  - Doubts Rotational / Translational with inf-rejection rate
  - **Rejection breakdown** — every vision frame is re-classified against the C++ filter gates from `AprilTagsSensor::applyVisionMeasurement()` + `Drivetrain.cpp`: `NOT_ACTIVE` / `NO_TARGET` / `MALFORMED` / `NO_TAGS` / `STALE` / `OUT_OF_FIELD` / `HIGH_AMBIGUITY` / `TOO_FAR`. Both raw counts and % of rejects shown.
- **Per-tag summary** (per match + season): tag ID, frame count, mean / min / max distance, mean / max ambiguity, which cameras saw it, avg-per-match count.
- **Season combined:** time-weighted metrics pooled across matches, full rejection breakdown.

Threshold constants come directly from the robot code (see top of the script):
- `AMBIGUITY_THRESHOLD = 0.2` (matches `Drivetrain.cpp:118` override)
- `MAX_LATENCY_MS = 2000` (AprilTagsSensor default `maxMeasurementAge`)
- `FIELD_BORDER_M = 0.5` (AprilTagsSensor default `fieldBorderMargin`)
- `MAX_VISION_DIST_M = 5.0` (Drivetrain.cpp `MAX_VISION_MEASUREMENT`)
- `FIELD_LENGTH_M / FIELD_WIDTH_M = 17.548 / 8.052` (WPILib `k2026RebuiltAndyMark`)

Required log signals per camera:
- `NT:/<cam>/{cl, tl, tv, tid, ta, rawfiducials, botpose_wpiblue}`
- `NT:/SmartDashboard/SwerveDrive/<cam>/{Active Camera, hasTarget, totalLatency, Vision Filter Pass, Doubts/Rotational, Doubts/Translational, Field Calibration/Distance to Tag}`
- `DS:enabled`, `DS:autonomous`

```bash
python -X utf8 analysis/limelight_analysis.py logs/
python -X utf8 analysis/limelight_analysis.py -j 8 logs/
```

Outputs (default paths): `analysis/reports/limelight_summary.md`, `analysis/reports/limelight_matches.md`.

### `analysis/gyro_analysis.py`

Pigeon2 gyro + robot accelerometer analysis, plus a separate per-Limelight IMU section. Produces:
- **Pigeon:** yaw range + net rotation (degrees, unwrapped), pitch / roll time-weighted stats with tilt-event fractions, angular-velocity magnitude stats, per-axis acceleration (x/y/z in m/s²), acceleration magnitude (mean_tw / p50 / p95 / peak in m/s² **and** g), debounced **G-shock event** list with per-event peak + timestamp.
- **Per Limelight IMU (separate from Pigeon):** roll / pitch / yaw from each camera's onboard IMU, acceleration magnitude in g, per-camera shock-event list. Limelights 4 publish acceleration in **g** directly, so the same `HIGH_G_THRESHOLD_G` is applied without unit conversion.
- **Season summary:** merges stats across matches with time-weighted means, top-N shock events across the season tagged with match name + alliance (so you can jump to the biggest hits), and the same per-camera split for the LL IMUs.
- Alliance is pulled from FMS using the same gated detection as `limelight_analysis.py` (only sampled when FMS is attached AND the robot is enabled).

Tunable constants at the top of the script:
- `HIGH_G_THRESHOLD_G = 3.0` — shock threshold in g
- `TILT_THRESHOLD_DEG = 10.0` — |pitch| or |roll| above this counts as a tilt event
- `SHOCK_DEBOUNCE_S = 0.25` — fuse near-simultaneous shock peaks into one event

Required log signals:
- `NT:/SmartDashboard/SwerveDrive/{Gyro Yaw, Gyro Pitch, Gyro Roll, Angular Velocity, Acceleration}`
- `NT:/limelight-{center,left,right}/imu` (10-element array: `[robotYaw, roll, pitch, yaw, gyroX, gyroY, gyroZ, accelX, accelY, accelZ]` per LL4 docs)
- `NT:/FMSInfo/{IsRedAlliance, FMSControlData}`
- `DS:enabled`, `DS:autonomous`

```bash
python -X utf8 analysis/gyro_analysis.py logs/
python -X utf8 analysis/gyro_analysis.py -j 8 logs/
```

Outputs (default paths): `analysis/reports/gyro_summary.md`, `analysis/reports/gyro_matches.md`.

Notes on the data this season:
- The Pigeon roll signal appears bimodal near ±180° — suggests the robot-side Pigeon mount offsets need review (expected roll at rest is near zero).
- LL IMUs saturate around **13.85 g** — any shock event hitting that value is a lower bound, real peak was higher.

### `analysis/drivetrain_analysis.py`

Swerve drivetrain current / speed / energy across all 8 motors (4 drive + 4 azimuth), separated into **AUTO** vs **TELEOP** phases so you can compare how hard the drivetrain works in each mode. Produces:
- **Per module, per role, per phase:** time-weighted mean / p50 / p95 / max of stator current, supply current, and |speed|, plus motor electrical energy (|V|·|I| integrated). Phases: AUTO (enabled + autonomous), TELEOP (enabled + not autonomous), COMBINED (all enabled time).
- **Role totals per phase:** rolled-up Drive-vs-Azimuth stats across all 4 modules.
- **Drivetrain grand totals:** total energy + avg power for AUTO / TELEOP / COMBINED.
- **AUTO vs TELEOP intensity ratio:** side-by-side comparison of mean/p95/peak stator current, mean speed, and avg power with an Auto-to-Teleop ratio column.

Uses the shared `analysis/can_config.py` CAN-ID mapping. NT publishes Stator Current + Speed + Out Volt for each motor but not Supply Current; the hoot overlay (same pattern as `intake_analysis.py`) fills that in from the Canivore `.hoot` file when present.

Module → CAN ID mapping (stable across robot variants):
- Module 0: Drive=CAN 2, Azimuth=CAN 1
- Module 1: Drive=CAN 4, Azimuth=CAN 3
- Module 2: Drive=CAN 6, Azimuth=CAN 5
- Module 3: Drive=CAN 8, Azimuth=CAN 7

Module → **corner** mapping (FL/FR/BL/BR) **varies by robot variant** (see `Constants::getModuleCoordsX/Y()` in the robot repo — DryBones/ShyGuy/Gold/Koopa/Drizzle/Downpour each have different orderings). The analyzer labels modules 0–3 and leaves corner correlation to you.

Required log signals:
- `NT:/SmartDashboard/SwerveDrive/Module {0..3}/Drive Motor/{Stator Current, Speed, Out Volt, reqSpeed}`
- `NT:/SmartDashboard/SwerveDrive/Module {0..3}/Azimuth Motor/{Stator Current, Speed, Out Volt, reqPosition}`
- `DS:enabled`, `DS:autonomous`

Optional (for Supply Current + higher-fidelity data):
- Canivore `.hoot` file next to the wpilog (`owlet.exe` on PATH or at repo root)

```bash
python -X utf8 analysis/drivetrain_analysis.py logs/E1
python -X utf8 analysis/drivetrain_analysis.py logs/
```

Outputs (default paths): `analysis/reports/drivetrain_summary.md`, `analysis/reports/drivetrain_matches.md`.

### `analysis/cache_log_keys.py` (log-field reference)

Utility that scans a WPILog + any sibling `.hoot` files and writes a single markdown catalog of every logged signal to [`analysis/LOG_REFERENCE.md`](analysis/LOG_REFERENCE.md). Future scripts and LLM agents can grep that file instead of re-probing a log every time they need to know what signals are available.

Run once per major robot-code change:
```bash
python -X utf8 analysis/cache_log_keys.py              # auto-pick a wpilog from logs/
python -X utf8 analysis/cache_log_keys.py logs/E1      # scan a folder's wpilog + sibling hoots
python -X utf8 analysis/cache_log_keys.py --wpilog path/to/match.wpilog --no-hoot
```

The generated `LOG_REFERENCE.md` groups fields by subsystem (DS/FMS, Joysticks, Limelight, Shooter, Intake, SwerveDrive modules, etc.), hides noise fields (`.controllable`, `Tuning Mode`, etc.), and includes both WPILog field types AND hoot signal hex IDs (useful for `owlet -s` filtered decodes).

### Notes on running the analysis scripts

- On Windows, use `python -X utf8 ...` to avoid CP1252 encoding errors on some terminals.
- The scripts drive vlogger directly and therefore only read `*.wpilog`. To analyze `.hoot` files you would need `owlet` on PATH; see the Hoot source section above.
- The `logs/` folder is gitignored to avoid committing large binary logs.

### Analysis script architecture

Each analysis is a **standalone Python file in `analysis/`** that follows a small, consistent shape. The orchestrator (`run_all.py`) invokes them as subprocesses via a registry, so adding a new analysis is mostly: copy an existing script, change the signal list + math, add one line to the registry.

**Contract that every analysis script should satisfy:**

1. **Self-contained** — no imports between analysis scripts. Shared code (e.g. `to_np`, `energy_in_window`, `state_at_time`) is intentionally duplicated rather than hoisted into a library, to keep each script readable on its own and its dependencies explicit.
2. **Single log via `analyze_log(path) -> dict | None`** — returns everything the report functions need, or `None` if required signals are missing. This function is the unit of parallelism.
3. **Two report functions:** `print_per_log_report(result)` and `print_combined_analysis(results)` — both emit text via `print`, which the orchestrator captures into markdown files.
4. **Parallel loader** — a `load_all(paths, workers)` helper backed by `concurrent.futures.ProcessPoolExecutor`. Uses `--serial` / `-j 1` to fall back to a single process for debugging.
5. **Consistent CLI** — positional log args (files / directories / globs), plus the shared flags table above. Writes two markdown files by default (`<name>_summary.md`, `<name>_matches.md`).
6. **Live progress on stderr** — via a `progress()` helper. Report output goes to stdout; progress goes to stderr so it survives `contextlib.redirect_stdout` capture.

**To add a new analysis:**

1. Copy an existing script as a template. `joystick_analysis.py` is the smallest and easiest to adapt; `flywheel_analysis.py` is the most complete reference.
2. Update the signal constants at the top (`*_REGEX`, field path constants).
3. Rewrite the math inside `analyze_log()` and the report functions. Keep the return-dict shape documented near the function so the combined analysis is easy to follow.
4. Change the default output file names (`<name>_summary.md` / `<name>_matches.md`).
5. Add an entry to `ANALYSES` in [`analysis/run_all.py`](analysis/run_all.py):
   ```python
   {
       "name":        "shortname",
       "script":      "your_analysis.py",
       "description": "One-line summary for --list.",
   },
   ```
6. Reports go into `analysis/reports/` by default, which is gitignored — no changes to `.gitignore` needed.
7. Add a short section to this README under "Analysis Scripts" describing what the script produces and the log signals it depends on.

Why subprocesses for the orchestrator instead of importing each script's `main()`? Each script owns its own `ProcessPoolExecutor` and stderr/stdout formatting. Subprocesses keep them fully decoupled so one script's failure can't corrupt another's state, and adding a new script requires zero changes to the wrapper beyond the registry entry.

## Notes
Vlogger uses the `logging` library internally to log information about the sources, but by design does not configure the logger at all. This means that program that uses Vlogger has the responsibility of setting up the logger.

## Contributing
Contributions are always welcome, especially tasks like adding new sources or fixing bugs. If you are making a big change, please create an issue beforehand to come up with a plan before finishing the code.
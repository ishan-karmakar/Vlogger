# FRC Vlogger
## What is this?
Vlogger is a generic library that provides an abstraction over the various kinds of files and live sources that are used in FRC.  
This package is developed and used by FRC Valor 6800 for post match analysis.

## Getting Started

Vlogger ships three things in one repo:
1. The **`vlogger` library** for parsing FRC log sources (see [API Structure](#api-structure)).
2. **CLI analysis scripts** in `analysis/` that produce per-match and season reports (see [Analysis Scripts](#analysis-scripts)).
3. A local **Streamlit GUI** in `gui/` that wraps the analysis scripts in a browser UI (see [Streamlit GUI](#streamlit-gui)).

### Prerequisites

- **Python ≥ 3.10** (download from <https://www.python.org/downloads/> — on Windows, check **"Add python.exe to PATH"** during install).
- A way to manage dependencies. Pick one:
  - **pip + venv** — built into Python; the path most FRC students already know.
  - **Poetry** — used for development on this project; install via `pipx install poetry` or the [official installer](https://python-poetry.org/docs/#installation).

### Easiest path — Windows (pits laptop)

Double-click **`run-gui.bat`** at the repo root. The script creates a virtual environment in `.venv/`, installs the dependencies from `requirements.txt`, and launches the Streamlit GUI in your browser. Subsequent runs skip straight to launch.

### Setup with pip + venv (cross-platform)

```bash
git clone git@git.valor6800.com:valor6800/vlogger.git
cd vlogger

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
.venv\Scripts\activate             # Windows (cmd)
.venv\Scripts\Activate.ps1         # Windows (PowerShell)

pip install -r requirements.txt
```

### Setup with Poetry (recommended for development)

```bash
git clone git@git.valor6800.com:valor6800/vlogger.git
cd vlogger
poetry install
```

### Quick start — GUI

After setup, launch the Streamlit app:

```bash
streamlit run gui/app.py            # pip + venv (with venv activated)
poetry run streamlit run gui/app.py # Poetry
```

Streamlit prints a local URL (defaults to <http://localhost:8501>). Open it, point the sidebar at a directory of `.wpilog` files (e.g. `logs/<event>/`), pick the matches you want, and each tab renders per-match and season-wide analysis. See [Streamlit GUI](#streamlit-gui) for details.

### Quick start — CLI

```bash
# Run every analysis in analysis/ against a directory of logs
python -X utf8 analysis/run_all.py logs/             # pip + venv
poetry run python -X utf8 analysis/run_all.py logs/  # Poetry

# Or invoke any one script directly
python -X utf8 analysis/flywheel_analysis.py logs/
```

Reports land in `analysis/reports/` (gitignored). See [Analysis Scripts](#analysis-scripts) for the full flag set.

### Quick start — library

```python
import vlogger

with vlogger.get_source("my_log.wpilog", [""]) as source:
    for field in source:
        print(field)
```

See [Examples](#examples) for more.

### Updating dependencies

When `requirements.txt` or `pyproject.toml` changes (`git pull` brings in new deps):

- **`run-gui.bat`** — re-running it picks up new packages automatically (`pip install` is idempotent).
- **pip + venv** — `pip install -r requirements.txt` again.
- **Poetry** — `poetry install`.

`requirements.txt` is generated from `pyproject.toml` via `poetry export --without-hashes -f requirements.txt -o requirements.txt`. Regenerate after every `poetry add` / `poetry remove` so the pip path stays in sync.

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
- Season summary: per-match summary table, totals + per-match averages, INTAKING cycle stats across all matches (reached/stalled/jammed rates, duration, energy, current), SHOOTING window aggregates, time distribution.

Required log signals (under `SmartDashboard/Intake/`):
- `Left Intake Motor/*` and `Right Intake Motor/*` (`Speed`, `Stator Current`, `Supply Current`, `Out Volt`, `reqSpeed`)
- `Intake State` (`OFF` / `INTAKING` / `SHOOTING`)
- `Intake Jam`

```bash
python -X utf8 analysis/intake_analysis.py
python -X utf8 analysis/intake_analysis.py logs/
python -X utf8 analysis/intake_analysis.py -j 8 logs/
python -X utf8 analysis/intake_analysis.py --no-file logs/GF1/FRC_xxx.wpilog
```

Outputs (default paths): `analysis/reports/intake_summary.md`, `analysis/reports/intake_matches.md`.

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
8. Add a tab module under `gui/tabs/` so the new analysis is reachable from the Streamlit GUI (see "Streamlit GUI" below).

Why subprocesses for the orchestrator instead of importing each script's `main()`? Each script owns its own `ProcessPoolExecutor` and stderr/stdout formatting. Subprocesses keep them fully decoupled so one script's failure can't corrupt another's state, and adding a new script requires zero changes to the wrapper beyond the registry entry.

## Streamlit GUI

A local-first Streamlit app at `gui/app.py` provides a browser UI over the same per-match and season analyses produced by the CLI scripts. It is intended to run on a single machine in the pits: point it at a directory of `.wpilog` files (downloaded after each match) and drill into the results without leaving the browser.

### Launching

The fastest path on Windows is to **double-click `run-gui.bat`** at the repo root — it sets up `.venv/`, installs deps, and launches the GUI in one step. See [Getting Started](#getting-started) for the manual cross-platform setup.

Once installed, launch the app with whichever stack you used to install:

```bash
streamlit run gui/app.py            # pip + venv (with venv activated)
poetry run streamlit run gui/app.py # Poetry
```

Then open the URL Streamlit prints (defaults to <http://localhost:8501>).

Sidebar workflow:
1. Enter a log directory — recursively scanned for `*.wpilog`.
2. Pick which matches to include (defaults to all).
3. Toggle which analyses to run (Flywheel / Intake / Joystick).
4. Each analysis renders as its own tab with two sub-tabs: **Per match** (drill into one match) and **Season** (aggregate across all selected matches).

Results are cached per `(log_path, mtime, kind)`. Re-runs are instant for unchanged files; only newly added or overwritten logs get re-parsed. Use **Rescan / clear cache** in the sidebar to force a full reload.

### GUI architecture

```
gui/
├── app.py             # Streamlit entry point — sidebar + top-level tabs
├── data.py            # find_logs, cached_analyze (@st.cache_data), load_results, capture_text
├── components.py      # per_match_picker, raw_report, empty_state
└── tabs/
    ├── flywheel.py    # render(), render_per_log(), render_combined()
    ├── intake.py
    └── joystick.py
```

Contract every tab module satisfies:

1. **`render(results: list[dict]) -> None`** — entry point called from `app.py` once per kind. Renders an empty state if `results` is empty; otherwise renders the per-match + season sub-tabs.
2. **`render_per_log(r: dict)`** — consumes one `analyze_log()` result dict. Top section is `st.metric` cards for headline numbers, then `st.dataframe` tables, then optional `st.plotly_chart` figures.
3. **`render_combined(results)`** — season aggregate: per-match summary table, totals, and at least one chart.
4. **Raw text fallback** — every tab calls `raw_report(capture_text(<script>.print_per_log_report, r))` so the existing CLI text output is always available behind an expander, with no risk of feature drift if a structured renderer misses a field.

The GUI does **not** duplicate analysis logic — it only imports `analyze_log` from each script and wraps it in `@st.cache_data`. All compute lives in `analysis/`; tabs are presentation only.

### Adding a tab for a new analysis

When you add a new analysis script (see steps above), wire it into the GUI:

1. Register the script's module in `gui/data.py`'s `ANALYSES` dict.
2. Copy `gui/tabs/intake.py` as a template — it's the smallest tab. Rewrite `render_per_log` / `render_combined` to consume the new result dict.
3. Import the module in `gui/app.py` and add its short name to `ALL_KINDS` and to the `tab_modules` mapping.

That is the entire GUI contribution — no app-shell changes required. The cache, sidebar, tab management, and raw-text fallback all work unchanged.

## Notes
Vlogger uses the `logging` library internally to log information about the sources, but by design does not configure the logger at all. This means that program that uses Vlogger has the responsibility of setting up the logger.

## Contributing
Contributions are always welcome, especially tasks like adding new sources or fixing bugs. If you are making a big change, please create an issue beforehand to come up with a plan before finishing the code.
# -*- coding: utf-8 -*-
"""
Worker-process entry points for the GUI's parallel log decoder.

Importing this module is intentionally cheap — it does NOT import streamlit,
which would add hundreds of milliseconds per worker spawn. The pool uses
``max_tasks_per_child=1`` (vlogger / wpiutil hold C-extension state Python's
GC can't reclaim), so a fresh worker is spawned for every (path, kind) task.

Public surface:
    ANALYSES                   — kind -> module mapping (single source of truth).
    analyze_one(task)          — top-level worker for ProcessPoolExecutor.
"""

import sys
from pathlib import Path

# Make analysis/ + src/ importable when the worker re-imports this module.
_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from analysis import (  # noqa: E402
    _hoot,
    drivetrain_analysis,
    feeder_analysis,
    flywheel_analysis,
    hopper_analysis,
    intake_analysis,
    joystick_analysis,
    shot_analysis,
)

ANALYSES = {
    "flywheel":   flywheel_analysis,
    "intake":     intake_analysis,
    "joystick":   joystick_analysis,
    "drivetrain": drivetrain_analysis,
    "feeder":     feeder_analysis,
    "hopper":     hopper_analysis,
    "shot":       shot_analysis,
}


def analyze_one(task):
    """Worker entry: ``(log_path, kind, skip_hoot) -> (log_path, kind, result_or_None)``.

    Sets the per-process hoot skip flag, calls the kind's analyze_log, returns
    the result dict (or ``None`` if required signals are missing — the
    documented "skip this log" return value). Exceptions are NOT caught — they
    surface to the parent via ``fut.result()`` so the parent can show a real
    warning instead of a silent None.

    The parent process is responsible for caching the result on disk and warming
    Streamlit's in-memory cache; the worker only computes.
    """
    log_path, kind, skip_hoot = task
    _hoot.set_skip(skip_hoot)
    try:
        return log_path, kind, ANALYSES[kind].analyze_log(log_path)
    finally:
        _hoot.set_skip(False)

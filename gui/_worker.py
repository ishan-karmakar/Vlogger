# -*- coding: utf-8 -*-
"""
Worker-process entry points for the GUI's parallel log decoder.

Importing this module is intentionally cheap — it does NOT import streamlit,
which would add hundreds of milliseconds per worker spawn (and the pool uses
``max_tasks_per_child=1`` so a worker is spawned per log).

The pair of public callables here:
    load_combined_series(log_path, kinds) -> {kind: series_dict}
    analyze_kinds(task)                  -> (log_path, {kind: result_or_None})
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Make analysis/ + src/ importable when the worker re-imports this module.
_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

import vlogger  # noqa: E402
from analysis import flywheel_analysis, intake_analysis, joystick_analysis  # noqa: E402

ANALYSES = {
    "flywheel": flywheel_analysis,
    "intake":   intake_analysis,
    "joystick": joystick_analysis,
}


def load_combined_series(log_path, kinds):
    """Decode a wpilog ONCE and partition records into per-kind series dicts.

    Each kind's regex still gates which records end up in that kind's dict, so
    the result for each kind is identical to running its module's load_series()
    independently — but we only iterate the DataLogReader once.
    """
    if not kinds:
        return {}
    modules = {k: ANALYSES[k] for k in kinds}
    union = "|".join(f"(?:{m.REGEX})" for m in modules.values())
    kind_regexes = {k: re.compile(m.REGEX) for k, m in modules.items()}
    out = {k: defaultdict(list) for k in kinds}

    url = f"wpilog:///{log_path}" if not log_path.startswith("wpilog:") else log_path
    src = vlogger.get_source(url, union)
    with src:
        for entry in src:
            name = entry["name"]
            ts   = entry["timestamp"] / 1e6
            data = entry["data"]
            for k, kr in kind_regexes.items():
                if kr.search(name):
                    v = modules[k].coerce_value(data)
                    if v is not None:
                        out[k][name].append((ts, v))

    return {
        k: {n: sorted(v, key=lambda x: x[0]) for n, v in d.items()}
        for k, d in out.items()
    }


def analyze_kinds(task):
    """Worker entry: ``(log_path, kinds_tuple) -> (log_path, {kind: result|None})``.

    Decodes the log once, dispatches each kind's series dict to the matching
    module's analyze_from_series. Each kind's series dict is dropped immediately
    after analysis to keep peak RSS bounded — long matches can produce tens of
    MB of intermediate per-kind data.
    """
    import gc
    log_path, kinds = task
    series_by_kind = load_combined_series(log_path, list(kinds))
    out = {}
    for k in kinds:
        try:
            out[k] = ANALYSES[k].analyze_from_series(
                series_by_kind.get(k, {}), log_path
            )
        except Exception:
            # Failure surfaces as None so the parent treats it the same as
            # missing-signals; the parent already shows a per-log warning.
            out[k] = None
        series_by_kind.pop(k, None)
    gc.collect()
    return log_path, out

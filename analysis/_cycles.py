# -*- coding: utf-8 -*-
"""
Shared cycle / state-window helpers for analysis modules.

Cycle definitions used across more than one analysis live here so that
``shot_analysis`` can import the canonical flywheel SHOOT cycle list
without pulling in flywheel_analysis's full module surface, and so that
the same state-window detection logic isn't reimplemented for every
subsystem (flywheel, intake, feeder, hopper).

``CYCLE_SCHEMA`` is a version constant attached to the cycle dicts that
participate in cross-system rollups (today: flywheel → shot). Downstream
consumers (e.g. ``shot_analysis``) assert against it so a flywheel-side
change to the cycle dict's shape forces an explicit version bump
instead of silently shifting downstream outputs.
"""

# Bump when any analysis changes its per-cycle dict shape in a way
# that affects shot_analysis (or any future cross-system aggregator).
# v1: flywheel cycles carry t_start, t_end, aim_mode, drive_state,
#     req_rps, spinup_s, total_E_J, at_speed, plus alignment + xmode
#     metrics. shot_analysis only depends on t_start / t_end / aim_mode.
CYCLE_SCHEMA = 1


def find_state_windows(state_pts, target_state, *, min_cycle_secs,
                       end_state=None):
    """Return ``[(t_start, t_end), ...]`` for each contiguous window where
    ``state == target_state``, lasting at least ``min_cycle_secs``.

    ``state_pts`` is a list of ``(timestamp_seconds, state_string)`` tuples,
    typically ``series[STATE_PATH]`` from an analysis script's load_series.

    ``end_state`` knob (the only behavioural difference between subsystems):
        * ``None``   — close on any state != target_state. Used by intake /
                       feeder / hopper, where SHOOTING / INTAKING / OUTTAKING
                       windows close as soon as the state changes at all.
        * ``"STR"``  — close only on this specific state. Used by flywheel,
                       where SHOOT closes only on DISABLE; transient
                       intermediate states stay *inside* the window.

    A window still "open" at the last sample is closed at that sample's
    timestamp. Windows shorter than ``min_cycle_secs`` are dropped — that
    filters out the brief transition blips state machines emit.
    """
    windows = []
    in_win  = False
    t_start = None
    for ts, val in state_pts:
        if not in_win and val == target_state:
            in_win  = True
            t_start = ts
        elif in_win and (
            (val != target_state) if end_state is None else (val == end_state)
        ):
            in_win = False
            if ts - t_start >= min_cycle_secs:
                windows.append((t_start, ts))
            t_start = None
    if in_win and t_start is not None:
        windows.append((t_start, state_pts[-1][0]))
    return windows

# -*- coding: utf-8 -*-
"""Joystick analysis tab — per-match drill-down + season aggregate."""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import joystick_analysis
from analysis.joystick_analysis import (
    AXIS_LABELS, BUTTON_LABELS, POV_DIRECTIONS,
    BUTTON_ACTIONS, AXIS_ACTIONS, POV_ACTIONS,
)
from gui.components import per_match_picker, raw_report, empty_state
from gui.data import capture_text, match_label


def _axes_df(role_id: int, axes_stats: dict) -> pd.DataFrame:
    rows = []
    for ax_idx in sorted(axes_stats):
        s = axes_stats[ax_idx]
        rows.append({
            "Ax":          ax_idx,
            "Label":       AXIS_LABELS.get(ax_idx, f"Axis{ax_idx}"),
            "Action":      AXIS_ACTIONS.get(role_id, {}).get(ax_idx, "--"),
            "Min":         round(s["min"], 2),
            "Max":         round(s["max"], 2),
            "Mean |v|":    round(s["mean_abs"], 3),
            "Active %":    round(100 * s["active_frac"], 1),
            "Active (s)":  round(s["active_s"], 1),
        })
    return pd.DataFrame(rows)


def _buttons_df(role_id: int, buttons: dict) -> pd.DataFrame:
    if not buttons:
        return pd.DataFrame()
    rows = []
    for idx in sorted(buttons):
        rows.append({
            "Idx":       idx,
            "Label":     BUTTON_LABELS.get(idx, f"Btn{idx}"),
            "Action":    BUTTON_ACTIONS.get(role_id, {}).get(idx, "--"),
            "Presses":   buttons[idx],
        })
    return pd.DataFrame(rows)


def _povs_df(role_id: int, povs: dict) -> pd.DataFrame:
    if not povs:
        return pd.DataFrame()
    rows = []
    for direction in sorted(povs):
        rows.append({
            "Deg":      direction,
            "Dir":      POV_DIRECTIONS.get(direction, str(direction)),
            "Action":   POV_ACTIONS.get(role_id, {}).get(direction, "--"),
            "Presses":  povs[direction],
        })
    return pd.DataFrame(rows)


def _render_joystick_block(role_id: int, jdata: dict) -> None:
    role = jdata.get("role", f"joystick{role_id}")
    st.markdown(f"### {role} (joystick{role_id})")
    if not jdata.get("has_data"):
        st.caption("No data for this joystick in this log.")
        return

    axes_df = _axes_df(role_id, jdata.get("axes", {}))
    if not axes_df.empty:
        st.markdown("**Axis activity** (teleop only)")
        st.dataframe(axes_df, hide_index=True, width="stretch")

    btns_df = _buttons_df(role_id, jdata.get("buttons", {}))
    if not btns_df.empty:
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown("**Button presses** (rising edges, teleop)")
            st.dataframe(btns_df, hide_index=True, width="stretch")
        with c2:
            fig = px.bar(btns_df, x="Label", y="Presses",
                         title=f"Button presses — {role}")
            st.plotly_chart(fig, width="stretch")

    povs_df = _povs_df(role_id, jdata.get("povs", {}))
    if not povs_df.empty:
        st.markdown("**POV / D-pad presses**")
        st.dataframe(povs_df, hide_index=True, width="content")


def render_per_log(r: dict) -> None:
    st.subheader(match_label(r["log_path"]))

    c1, c2, c3 = st.columns(3)
    c1.metric("Log duration", f"{r['session_len']:.1f} s")
    c2.metric("Enabled time", f"{r['enabled_s']:.1f} s")
    c3.metric("Teleop time",  f"{r['teleop_s']:.1f} s")

    for role_id in sorted(r["joysticks"]):
        _render_joystick_block(role_id, r["joysticks"][role_id])
        st.divider()

    raw_report(capture_text(joystick_analysis.print_per_log_report, r))


def render_combined(results: list[dict]) -> None:
    st.subheader(f"Season summary — {len(results)} match{'es' if len(results) != 1 else ''}")

    # Per-match summary
    rows = []
    for r in results:
        row = {
            "Match":     match_label(r["log_path"]),
            "Teleop s":  round(r["teleop_s"], 1),
        }
        for role_id, jdata in r["joysticks"].items():
            tag = jdata.get("role", f"j{role_id}")
            row[f"{tag} btn presses"] = sum(jdata.get("buttons", {}).values())
            row[f"{tag} pov presses"] = sum(jdata.get("povs", {}).values())
        rows.append(row)
    summary = pd.DataFrame(rows)
    st.dataframe(summary, hide_index=True, width="stretch")

    # Aggregate button presses across matches per joystick
    role_button_totals: dict[tuple[int, str, int], int] = {}
    role_names: dict[int, str] = {}
    for r in results:
        for role_id, jdata in r["joysticks"].items():
            role_names[role_id] = jdata.get("role", f"joystick{role_id}")
            for idx, count in jdata.get("buttons", {}).items():
                key = (role_id, BUTTON_LABELS.get(idx, f"Btn{idx}"), idx)
                role_button_totals[key] = role_button_totals.get(key, 0) + count

    if role_button_totals:
        bt_rows = [
            {"Role": role_names[rid], "Button": label, "Idx": idx, "Presses": count}
            for (rid, label, idx), count in role_button_totals.items()
        ]
        bt_df = pd.DataFrame(bt_rows).sort_values(["Role", "Idx"])
        st.markdown("**Total button presses across season**")
        fig = px.bar(bt_df, x="Button", y="Presses", color="Role", barmode="group",
                     title="Season-wide button presses")
        st.plotly_chart(fig, width="stretch")

    raw_report(capture_text(joystick_analysis.print_combined_analysis, results),
               label="Raw text season summary")


def render(results: list[dict]) -> None:
    if not results:
        empty_state("joystick")
        return
    tab_match, tab_season = st.tabs(["Per match", "Season"])
    with tab_match:
        chosen = per_match_picker(results, key="joystick_match_pick")
        if chosen is not None:
            render_per_log(chosen)
    with tab_season:
        render_combined(results)

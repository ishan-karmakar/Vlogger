# -*- coding: utf-8 -*-
"""Drivetrain analysis tab — per-match drill-down + season aggregate."""

import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import drivetrain_analysis
from analysis.drivetrain_analysis import (
    NUM_MODULES, ROT_STATES, TRANS_STATES, ALIGN_TOL_RAD,
    CAN_DRIVE_BY_MODULE, CAN_AZIMUTH_BY_MODULE,
)
from gui.components import per_match_picker, raw_report, empty_state
from gui.data import capture_text, match_label


def _has_hoot(r: dict) -> bool:
    return any(m["drive"].get("hoot") or m["azimuth"].get("hoot") for m in r["modules"])


def _hoot_motor_df(r: dict) -> pd.DataFrame:
    rows = []
    for m in r["modules"]:
        dh = m["drive"].get("hoot")   or {}
        ah = m["azimuth"].get("hoot") or {}
        rows.append({
            "Module":          f"M{m['idx']}",
            "Drv CAN":         m["drive_can_id"],
            "Drv °C pk":       dh.get("peak_temp_c"),
            "Drv °C avg":      dh.get("mean_temp_c"),
            "Drv I_sup pk":    dh.get("peak_supply_curr"),
            "Drv I_torq pk":   dh.get("peak_torque_curr"),
            "Azm CAN":         m["azimuth_can_id"],
            "Azm °C pk":       ah.get("peak_temp_c"),
            "Azm °C avg":      ah.get("mean_temp_c"),
            "Azm I_sup pk":    ah.get("peak_supply_curr"),
            "Azm I_torq pk":   ah.get("peak_torque_curr"),
        })
    df = pd.DataFrame(rows)
    for col in df.columns:
        if df[col].dtype == "float64":
            df[col] = df[col].round(2)
    return df


def _module_summary_df(modules: list[dict]) -> pd.DataFrame:
    rows = []
    for m in modules:
        d = m["drive"]; a = m["azimuth"]
        rows.append({
            "Module":         f"M{m['idx']}",
            "Pk Drv RPS":     round(d["peak_speed"], 1),
            "Drv I avg (A)":  round(d["mean_abs_current"], 1),
            "Drv I pk (A)":   round(d["peak_current"], 1),
            "Drv kJ":         round(d["energy_J"] / 1000, 2),
            "Drv ErrAvg":     round(d["tracking_err_avg"], 2),
            "Drv ErrPk":      round(d["tracking_err_pk"], 2),
            "Azm I avg (A)":  round(a["mean_abs_current"], 1),
            "Azm I pk (A)":   round(a["peak_current"], 1),
            "Azm kJ":         round(a["energy_J"] / 1000, 2),
            "Azm Err° avg":   round(a["tracking_err_deg_avg"], 1),
            "Azm Err° pk":    round(a["tracking_err_deg_pk"], 1),
        })
    return pd.DataFrame(rows)


def _state_dist_df(state_time: dict, all_states: tuple, total_s: float) -> pd.DataFrame:
    rows = []
    for st in all_states:
        t = state_time.get(st, 0.0)
        pct = (100 * t / total_s) if total_s > 0 else 0.0
        rows.append({"State": st, "Time (s)": round(t, 1), "% of log": round(pct, 1)})
    return pd.DataFrame(rows)


def render_per_log(r: dict) -> None:
    st.subheader(match_label(r["log_path"]))

    # -- Headline metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Log duration", f"{r['session_len']:.1f} s")
    c2.metric("Enabled",      f"{r['enabled_s']:.1f} s",
              f"auto {r['auto_s']:.1f}s + teleop {r['teleop_s']:.1f}s")
    c3.metric("Drive energy", f"{r['chassis']['drive_energy_J']/1000:.2f} kJ")
    c4.metric("Azim energy",  f"{r['chassis']['azim_energy_J']/1000:.2f} kJ")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total energy",  f"{r['chassis']['total_energy_J']/1000:.2f} kJ")
    c6.metric("Peak yaw rate", f"{r['chassis']['peak_yaw_rate_deg_s']:.0f} °/s")
    c7.metric("Net heading",   f"{r['chassis']['net_yaw_deg']:+.0f}°",
              f"{r['chassis']['total_yaw_revs']:.2f} revolutions")
    if r["chassis"].get("max_motor_temp_c") is not None:
        c8.metric("Peak motor temp",
                  f"{r['chassis']['max_motor_temp_c']:.1f} °C",
                  "any of 8 motors (hoot)")
    else:
        c8.metric("Align cycles",  f"{len(r['align_cycles'])}")

    if r.get("hoot_files_used"):
        st.caption(
            "Paired hoot: "
            + ", ".join(os.path.basename(p) for p in r["hoot_files_used"])
        )

    # -- Per-module table
    st.markdown("**Per-module summary** (WPI-derived)")
    st.dataframe(_module_summary_df(r["modules"]), hide_index=True, width="stretch")

    # -- Per-motor telemetry from hoot (only when paired)
    if _has_hoot(r):
        st.markdown(
            "**Per-motor telemetry** (from paired hoot — DeviceTemp, "
            "SupplyCurrent, TorqueCurrent at higher sample rate)"
        )
        st.dataframe(_hoot_motor_df(r), hide_index=True, width="stretch")

    # -- Drive energy share + imbalance
    drive_E = np.array([m["drive"]["energy_J"] for m in r["modules"]])
    if drive_E.sum() > 0:
        share = 100.0 * drive_E / drive_E.sum()
        share_df = pd.DataFrame({
            "Module": [f"M{i}" for i in range(NUM_MODULES)],
            "% of drive energy": share.round(1),
        })
        col_share, col_pie = st.columns([1, 1])
        with col_share:
            st.markdown("**Drive energy share**")
            st.dataframe(share_df, hide_index=True, width="content")
            spread = float(share.max() - share.min())
            verdict = "BALANCED" if spread <= 10 else "IMBALANCED"
            st.metric("Module imbalance",
                      f"{spread:.1f}%",
                      f"{verdict} (10% threshold)",
                      delta_color="off" if spread <= 10 else "inverse")
        with col_pie:
            fig_pie = px.pie(share_df, names="Module", values="% of drive energy",
                             title="Drive energy distribution")
            st.plotly_chart(fig_pie, width="stretch")

    # -- Stacked drive vs azim energy bar per module
    bar_rows = []
    for m in r["modules"]:
        bar_rows.append({"Module": f"M{m['idx']}", "Axis": "Drive",
                         "Energy (kJ)": m["drive"]["energy_J"] / 1000})
        bar_rows.append({"Module": f"M{m['idx']}", "Axis": "Azimuth",
                         "Energy (kJ)": m["azimuth"]["energy_J"] / 1000})
    fig_bar = px.bar(pd.DataFrame(bar_rows), x="Module", y="Energy (kJ)", color="Axis",
                     barmode="stack", title="Per-module energy: Drive vs Azimuth")
    st.plotly_chart(fig_bar, width="stretch")

    # -- State distributions
    col_rot, col_trans = st.columns(2)
    with col_rot:
        st.markdown("**Driver Rotation State**")
        st.dataframe(
            _state_dist_df(r["rotation_state_time"], ROT_STATES, r["session_len"]),
            hide_index=True, width="content",
        )
    with col_trans:
        st.markdown("**Driver Translation State**")
        st.dataframe(
            _state_dist_df(r["translation_state_time"], TRANS_STATES, r["session_len"]),
            hide_index=True, width="content",
        )

    # -- ALIGN_TO_TARGET cycles
    if r["align_cycles"]:
        st.markdown(f"**ALIGN_TO_TARGET cycles** ({len(r['align_cycles'])} total · "
                    f"settle tolerance ±{np.rad2deg(ALIGN_TOL_RAD):.1f}°)")
        cdf = pd.DataFrame(r["align_cycles"])
        cdf["Settled?"] = cdf["settle_t"].apply(lambda x: "yes" if x != float("inf") else "no")
        cdf["Settle (s)"] = cdf["settle_t"].apply(lambda x: round(x, 2) if x != float("inf") else None)
        view = cdf[["t_start", "dur", "Settle (s)", "Settled?", "E_J"]].rename(columns={
            "t_start": "Start (s)", "dur": "Dur (s)", "E_J": "Energy (J)",
        })
        view["Start (s)"] = view["Start (s)"].round(1)
        view["Dur (s)"]   = view["Dur (s)"].round(2)
        view["Energy (J)"] = view["Energy (J)"].round(0).astype(int)
        st.dataframe(view, hide_index=True, width="stretch")

        # Settle time histogram (only cycles that settled)
        settled = cdf[cdf["Settled?"] == "yes"]
        if len(settled):
            fig = px.histogram(settled, x="Settle (s)", nbins=20,
                               title="Distribution of ALIGN settle times")
            st.plotly_chart(fig, width="stretch")
    else:
        st.caption("No ALIGN_TO_TARGET windows in this log.")

    # -- X_MODE windows
    if r["x_mode_windows"]:
        st.markdown(f"**X_MODE windows** ({len(r['x_mode_windows'])} total)")
        xdf = pd.DataFrame(r["x_mode_windows"])
        view = xdf[["t_start", "dur", "E_J"]].rename(columns={
            "t_start": "Start (s)", "dur": "Dur (s)", "E_J": "Energy (J)",
        })
        view["Start (s)"] = view["Start (s)"].round(1)
        view["Dur (s)"]   = view["Dur (s)"].round(2)
        view["Energy (J)"] = view["Energy (J)"].round(0).astype(int)
        st.dataframe(view, hide_index=True, width="content")

    raw_report(capture_text(drivetrain_analysis.print_per_log_report, r))


def render_combined(results: list[dict]) -> None:
    st.subheader(f"Season summary — {len(results)} match{'es' if len(results) != 1 else ''}")

    # -- Per-match summary table
    rows = []
    for r in results:
        rows.append({
            "Match":      match_label(r["log_path"]),
            "Dur (s)":    round(r["session_len"], 1),
            "Enabled":    round(r["enabled_s"], 1),
            "Drv kJ":     round(r["chassis"]["drive_energy_J"] / 1000, 2),
            "Azm kJ":     round(r["chassis"]["azim_energy_J"]  / 1000, 2),
            "Pk yaw °/s": round(r["chassis"]["peak_yaw_rate_deg_s"], 0),
            "Aligns":     len(r["align_cycles"]),
            "X-mode":     len(r["x_mode_windows"]),
        })
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, hide_index=True, width="stretch")

    # -- Aggregates
    n = len(results)
    total_drive_E = sum(r["chassis"]["drive_energy_J"] for r in results) / 1000
    total_azim_E  = sum(r["chassis"]["azim_energy_J"]  for r in results) / 1000
    total_aligns  = sum(len(r["align_cycles"])    for r in results)
    total_xmode   = sum(len(r["x_mode_windows"])  for r in results)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Drive energy", f"{total_drive_E:.2f} kJ", f"{total_drive_E/n:.2f} kJ / match")
    c2.metric("Azim energy",  f"{total_azim_E:.2f} kJ",  f"{total_azim_E/n:.2f} kJ / match")
    c3.metric("Aligns",       f"{total_aligns}",         f"{total_aligns/n:.1f} / match")
    c4.metric("X-mode evts",  f"{total_xmode}",          f"{total_xmode/n:.1f} / match")

    # -- Hoot rollup (season-wide peak temp per motor)
    matches_with_hoot = [r for r in results if r.get("hoot_files_used")]
    if matches_with_hoot:
        per_id_temp = {cid: -float("inf") for cid in (*CAN_DRIVE_BY_MODULE, *CAN_AZIMUTH_BY_MODULE)}
        per_id_supc = {cid: 0.0 for cid in per_id_temp}
        for r in matches_with_hoot:
            for m in r["modules"]:
                for axis_key, cid in (("drive",   m["drive_can_id"]),
                                      ("azimuth", m["azimuth_can_id"])):
                    h = m[axis_key].get("hoot")
                    if not h:
                        continue
                    t = h.get("peak_temp_c")
                    if t is not None:
                        per_id_temp[cid] = max(per_id_temp[cid], t)
                    c = h.get("peak_supply_curr")
                    if c is not None:
                        per_id_supc[cid] = max(per_id_supc[cid], c)

        st.markdown(
            f"**Hoot motor telemetry** (paired hoot data on "
            f"{len(matches_with_hoot)} / {n} match{'es' if n != 1 else ''})"
        )
        rows = []
        for cid in (*CAN_DRIVE_BY_MODULE, *CAN_AZIMUTH_BY_MODULE):
            mod_idx = (CAN_DRIVE_BY_MODULE.index(cid) if cid in CAN_DRIVE_BY_MODULE
                       else CAN_AZIMUTH_BY_MODULE.index(cid))
            axis = "DRIVE" if cid in CAN_DRIVE_BY_MODULE else "AZIM"
            rows.append({
                "TalonFX":       cid,
                "Module":        f"M{mod_idx} {axis}",
                "Season °C pk":  None if per_id_temp[cid] == -float("inf") else round(per_id_temp[cid], 1),
                "Season I_sup pk": round(per_id_supc[cid], 1) if per_id_supc[cid] > 0 else None,
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="content")

    # -- Per-module energy aggregate (across all matches)
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

    drv_total = mod_drive_E.sum()
    if drv_total > 0:
        agg_rows = []
        for i in range(NUM_MODULES):
            d_pct = (100.0 * mod_drive_E[i] / drv_total) if drv_total > 0 else 0.0
            a_pct = (100.0 * mod_azim_E[i]  / mod_azim_E.sum())  if mod_azim_E.sum()  > 0 else 0.0
            agg_rows.append({
                "Module":      f"M{i}",
                "Drive kJ":    round(mod_drive_E[i] / 1000, 2),
                "Drive %":     round(d_pct, 1),
                "Drive Ipk":   round(mod_drive_pk_I[i], 1),
                "Azim kJ":     round(mod_azim_E[i]  / 1000, 2),
                "Azim %":      round(a_pct, 1),
                "Azim Ipk":    round(mod_azim_pk_I[i],  1),
            })
        st.markdown(f"**Per-module aggregate (across {n} match{'es' if n != 1 else ''})**")
        st.dataframe(pd.DataFrame(agg_rows), hide_index=True, width="stretch")

        share = 100.0 * mod_drive_E / drv_total
        spread = float(share.max() - share.min())
        verdict = "BALANCED" if spread <= 10 else "IMBALANCED"
        st.metric("Drive imbalance (season)",
                  f"{spread:.1f}%",
                  f"{verdict} (10% threshold)",
                  delta_color="off" if spread <= 10 else "inverse")

    # -- Per-match energy bar chart
    long_E = summary_df.melt(
        id_vars="Match",
        value_vars=["Drv kJ", "Azm kJ"],
        var_name="Axis",
        value_name="Energy (kJ)",
    )
    fig = px.bar(long_E, x="Match", y="Energy (kJ)", color="Axis",
                 barmode="stack", title="Per-match energy: Drive vs Azimuth")
    st.plotly_chart(fig, width="stretch")

    # -- ALIGN_TO_TARGET aggregate distribution
    all_settled = [c["settle_t"] for r in results for c in r["align_cycles"]
                   if c["settle_t"] != float("inf")]
    all_aligns_total = sum(len(r["align_cycles"]) for r in results)
    if all_aligns_total:
        c1, c2 = st.columns(2)
        c1.metric("Cycles that settled",
                  f"{len(all_settled)}/{all_aligns_total}",
                  f"{100*len(all_settled)/all_aligns_total:.1f}%")
        if all_settled:
            c2.metric("Avg settle time", f"{np.mean(all_settled):.2f} s",
                      f"min {np.min(all_settled):.2f} · max {np.max(all_settled):.2f}")
            fig = px.histogram(
                pd.DataFrame({"Settle (s)": all_settled}),
                x="Settle (s)", nbins=30,
                title="Distribution of ALIGN settle times (all matches)",
            )
            st.plotly_chart(fig, width="stretch")

    raw_report(capture_text(drivetrain_analysis.print_combined_analysis, results),
               label="Raw text season summary")


def render(results: list[dict]) -> None:
    if not results:
        empty_state("drivetrain")
        return
    tab_match, tab_season = st.tabs(["Per match", "Season"])
    with tab_match:
        chosen = per_match_picker(results, key="drivetrain_match_pick")
        if chosen is not None:
            render_per_log(chosen)
    with tab_season:
        render_combined(results)

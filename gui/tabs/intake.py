# -*- coding: utf-8 -*-
"""Intake analysis tab — per-match drill-down + season aggregate."""

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import intake_analysis
from gui.components import per_match_picker, raw_report, empty_state
from gui.data import capture_text, match_label


def _hoot_motor_df(r: dict) -> pd.DataFrame:
    rows = []
    for m in r.get("hoot_motors", []):
        s = m.get("stats") or {}
        rows.append({
            "Motor":         m["label"],
            "CAN":           m["can_id"],
            "°C pk":         s.get("peak_temp_c"),
            "°C avg":        s.get("mean_temp_c"),
            "I_sup pk (A)":  s.get("peak_supply_curr"),
            "I_torq pk (A)": s.get("peak_torque_curr"),
        })
    df = pd.DataFrame(rows)
    for col in df.columns:
        if df[col].dtype == "float64":
            df[col] = df[col].round(2)
    return df


def render_per_log(r: dict) -> None:
    st.subheader(match_label(r["log_path"]))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Log duration", f"{r['session_len']:.1f} s")
    c2.metric("Total energy", f"{r['total_energy_J']/1000:.2f} kJ")
    c3.metric("INTAKING cycles", f"{r['n_intaking']}")
    c4.metric("Jam events", f"{r['total_jams']}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Peak speed L", f"{r['max_speed_L']:.1f} RPS")
    c6.metric("Peak speed R", f"{r['max_speed_R']:.1f} RPS")
    c7.metric("SHOOTING cycles", f"{r['n_shooting']}")
    if r.get("max_motor_temp_c") is not None:
        c8.metric("Peak motor temp", f"{r['max_motor_temp_c']:.1f} °C",
                  "either motor (hoot)")
    else:
        c8.empty()

    if r.get("hoot_files_used"):
        st.caption(
            "Paired hoot: "
            + ", ".join(os.path.basename(p) for p in r["hoot_files_used"])
        )

    if any(m.get("stats") for m in r.get("hoot_motors", [])):
        st.markdown(
            "**Per-motor telemetry** (from paired rio-bus hoot — DeviceTemp, "
            "SupplyCurrent, TorqueCurrent)"
        )
        st.dataframe(_hoot_motor_df(r), hide_index=True, width="content")

    # State time distribution
    st.markdown("**Time in each Intake State**")
    rows = []
    for st_name in ("OFF", "INTAKING", "SHOOTING"):
        t = r["state_time"].get(st_name, 0.0)
        pct = (100 * t / r["session_len"]) if r["session_len"] > 0 else 0.0
        rows.append({"State": st_name, "Time (s)": round(t, 1), "% of log": round(pct, 1)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="content")

    # Current draw summary
    st.markdown("**Current draw**")
    cs = pd.DataFrame(r["current_stats"]).rename(
        columns={"label": "Channel", "mean": "Mean (A)", "peak": "Peak (A)"}
    )
    cs["Mean (A)"] = cs["Mean (A)"].round(1)
    cs["Peak (A)"] = cs["Peak (A)"].round(1)
    st.dataframe(cs, hide_index=True, width="content")

    # INTAKING cycles
    if r["cycles"]:
        st.markdown(f"**INTAKING cycles** ({len(r['cycles'])} total)")
        cdf = pd.DataFrame(r["cycles"])
        cdf["status"] = cdf.apply(
            lambda x: "STAL" if x["stalled"] else ("OK" if x["reached"] else ("n/a" if x["req_rps"] == 0 else "low")),
            axis=1,
        )
        view = cdf[[
            "t_start", "t_end", "dur", "req_rps", "act_L", "act_R",
            "status", "I_stat_avg", "I_stat_pk", "I_sup_avg", "I_sup_pk", "E_J", "jams",
        ]].rename(columns={
            "t_start": "Start (s)", "t_end": "End (s)", "dur": "Dur (s)",
            "req_rps": "Req RPS", "act_L": "Act L", "act_R": "Act R",
            "I_stat_avg": "I_stat avg", "I_stat_pk": "I_stat pk",
            "I_sup_avg": "I_sup avg",   "I_sup_pk": "I_sup pk",
            "E_J": "Energy (J)", "jams": "Jams",
        })
        st.dataframe(view, hide_index=True, width="stretch")

        # Per-cycle energy bar chart
        chart_df = cdf.reset_index().rename(columns={"index": "Cycle #"})
        chart_df["Cycle #"] = chart_df["Cycle #"] + 1
        fig = px.bar(
            chart_df, x="Cycle #", y="E_J",
            color="status",
            labels={"E_J": "Energy (J)"},
            title="Energy per INTAKING cycle",
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("No INTAKING cycles in this log.")

    # Jam events
    if r["jam_events"]:
        st.markdown("**Jam events**")
        jdf = pd.DataFrame(r["jam_events"])
        jdf["cycle"] = jdf["cycle_idx"].apply(lambda x: f"#{x}" if x else "-")
        view = jdf[["time", "cycle", "state"]].rename(columns={
            "time": "Time (s)", "cycle": "During cycle", "state": "State at t",
        })
        view["Time (s)"] = view["Time (s)"].round(2)
        st.dataframe(view, hide_index=True, width="content")

    # SHOOTING windows
    if r["shooting_cycles"]:
        st.markdown(f"**SHOOTING windows** ({len(r['shooting_cycles'])} total)")
        sdf = pd.DataFrame(r["shooting_cycles"])
        view = sdf[["t_start", "t_end", "dur", "E_J", "I_stat_avg"]].rename(columns={
            "t_start": "Start (s)", "t_end": "End (s)", "dur": "Dur (s)",
            "E_J": "Energy (J)", "I_stat_avg": "I_stat avg (A)",
        })
        st.dataframe(view, hide_index=True, width="content")

    raw_report(capture_text(intake_analysis.print_per_log_report, r))


def render_combined(results: list[dict]) -> None:
    st.subheader(f"Season summary — {len(results)} match{'es' if len(results) != 1 else ''}")

    rows = []
    for r in results:
        rows.append({
            "Match":          match_label(r["log_path"]),
            "Duration (s)":   round(r["session_len"], 1),
            "INTAKING":       r["n_intaking"],
            "SHOOTING":       r["n_shooting"],
            "Jams":           r["total_jams"],
            "Energy (kJ)":    round(r["total_energy_J"] / 1000, 2),
        })
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, hide_index=True, width="stretch")

    # Aggregates
    n = len(results)
    total_intaking = sum(r["n_intaking"] for r in results)
    total_shooting = sum(r["n_shooting"] for r in results)
    total_jams     = sum(r["total_jams"] for r in results)
    total_E_kJ     = sum(r["total_energy_J"] for r in results) / 1000

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("INTAKING cycles",  f"{total_intaking}", f"{total_intaking/n:.1f} / match")
    c2.metric("SHOOTING cycles",  f"{total_shooting}", f"{total_shooting/n:.1f} / match")
    c3.metric("Jam events",       f"{total_jams}",     f"{total_jams/n:.2f} / match")
    c4.metric("Total energy",     f"{total_E_kJ:.2f} kJ", f"{total_E_kJ/n:.2f} kJ / match")

    # Per-match cycle counts (stacked: INTAKING / SHOOTING)
    long = summary_df.melt(
        id_vars="Match",
        value_vars=["INTAKING", "SHOOTING"],
        var_name="State",
        value_name="Cycles",
    )
    fig = px.bar(long, x="Match", y="Cycles", color="State",
                 title="Per-match cycle counts", barmode="stack")
    st.plotly_chart(fig, width="stretch")

    # Aggregate INTAKING cycle stats
    all_cycles = [c for r in results for c in r["cycles"]]
    if all_cycles:
        cdf = pd.DataFrame(all_cycles)
        n_cycles = len(cdf)
        n_reached = int(cdf["reached"].sum())
        n_stalled = int(cdf["stalled"].sum())
        n_jammed  = int((cdf["jams"] > 0).sum())
        st.markdown("**INTAKING cycle stats across all matches**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Reached target", f"{n_reached}/{n_cycles}",
                  f"{100*n_reached/n_cycles:.1f}%")
        c2.metric("Stalled",        f"{n_stalled}/{n_cycles}",
                  f"{100*n_stalled/n_cycles:.1f}%")
        c3.metric("With jam event", f"{n_jammed}/{n_cycles}",
                  f"{100*n_jammed/n_cycles:.1f}%")

        fig2 = px.histogram(
            cdf, x="dur", nbins=30,
            title="Distribution of INTAKING cycle durations (all matches)",
            labels={"dur": "Duration (s)"},
        )
        st.plotly_chart(fig2, width="stretch")

    raw_report(capture_text(intake_analysis.print_combined_analysis, results),
               label="Raw text season summary")


def render(results: list[dict]) -> None:
    if not results:
        empty_state("intake")
        return
    tab_match, tab_season = st.tabs(["Per match", "Season"])
    with tab_match:
        chosen = per_match_picker(results, key="intake_match_pick")
        if chosen is not None:
            render_per_log(chosen)
    with tab_season:
        render_combined(results)

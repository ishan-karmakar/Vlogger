# -*- coding: utf-8 -*-
"""Flywheel analysis tab — per-match drill-down + season aggregate."""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import flywheel_analysis
from gui.components import per_match_picker, raw_report, empty_state
from gui.data import capture_text, match_label


def render_per_log(r: dict) -> None:
    st.subheader(match_label(r["log_path"]))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Log duration", f"{r['session_len']:.1f} s")
    c2.metric("Enabled time", f"{r['enabled_s']:.1f} s")
    c3.metric("Total energy", f"{r['total_energy_J']/1000:.2f} kJ")
    c4.metric("Peak speed",   f"{r['max_speed']:.1f} RPS")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Shoot cycles", f"{len(r['cycles'])}")
    c6.metric("Mean stator I (sum)", f"{r['mean_I_tot']:.1f} A")
    c7.metric("Peak stator I (sum)", f"{r['peak_I_tot']:.1f} A")
    c8.metric("Cruise samples", f"{r.get('cruise_n', 0)}")

    cycles = r["cycles"]
    if cycles:
        st.markdown(f"**Shoot cycles** ({len(cycles)} total)")
        cdf = pd.DataFrame(cycles)
        cdf["dur_s"] = cdf["t_end"] - cdf["t_start"]
        cdf["align_t_s"] = cdf["align_t_s"].astype("float")
        view = cdf[[
            "t_start", "dur_s", "req_rps", "spinup_s", "spinup_E_J", "spinup_pk_I",
            "total_E_J", "at_speed", "aim_mode", "drive_state", "align_t_s", "t_xmode_s",
        ]].rename(columns={
            "t_start": "Start (s)", "dur_s": "Dur (s)",
            "req_rps": "Req RPS", "spinup_s": "Spin-up (s)",
            "spinup_E_J": "Spin-up E (J)", "spinup_pk_I": "Spin-up I pk (A)",
            "total_E_J": "Total E (J)", "at_speed": "At speed",
            "aim_mode": "Aim mode", "drive_state": "Drive state",
            "align_t_s": "Align (s)", "t_xmode_s": "X-mode (s)",
        })
        st.dataframe(view, hide_index=True, width="stretch")

        # Spin-up time per cycle
        chart_df = cdf.reset_index().rename(columns={"index": "Cycle #"})
        chart_df["Cycle #"] = chart_df["Cycle #"] + 1
        fig = px.bar(
            chart_df, x="Cycle #", y="spinup_s",
            color="aim_mode",
            title="Spin-up time per cycle",
            labels={"spinup_s": "Spin-up time (s)"},
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("No shoot cycles detected in this log.")

    raw_report(capture_text(flywheel_analysis.print_per_log_report, r))


def render_combined(results: list[dict]) -> None:
    st.subheader(f"Season summary — {len(results)} match{'es' if len(results) != 1 else ''}")

    rows = []
    for r in results:
        rows.append({
            "Match":         match_label(r["log_path"]),
            "Duration (s)":  round(r["session_len"], 1),
            "Enabled (s)":   round(r["enabled_s"], 1),
            "Cycles":        len(r["cycles"]),
            "Energy (kJ)":   round(r["total_energy_J"] / 1000, 2),
            "Peak speed":    round(r["max_speed"], 1),
            "Peak I (A)":    round(r["peak_I_tot"], 1),
        })
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, hide_index=True, width="stretch")

    # Aggregates
    n = len(results)
    all_cycles = [c for r in results for c in r["cycles"]]
    total_energy_kJ = sum(r["total_energy_J"] for r in results) / 1000

    c1, c2, c3 = st.columns(3)
    c1.metric("Total shoot cycles", f"{len(all_cycles)}",
              f"{len(all_cycles)/n:.1f} / match")
    c2.metric("Total energy",       f"{total_energy_kJ:.2f} kJ",
              f"{total_energy_kJ/n:.2f} / match")
    if all_cycles:
        reached = sum(1 for c in all_cycles if c["at_speed"])
        c3.metric("Reached target speed", f"{reached}/{len(all_cycles)}",
                  f"{100*reached/len(all_cycles):.1f}%")

    # Per-match cycle count
    fig1 = px.bar(summary_df, x="Match", y="Cycles", title="Per-match shoot cycle count")
    st.plotly_chart(fig1, width="stretch")

    # Spin-up time distribution across all cycles
    if all_cycles:
        cdf = pd.DataFrame(all_cycles)
        fig2 = px.histogram(
            cdf, x="spinup_s", nbins=30, color="aim_mode",
            title="Distribution of spin-up times (all matches)",
            labels={"spinup_s": "Spin-up (s)"},
        )
        st.plotly_chart(fig2, width="stretch")

    raw_report(capture_text(flywheel_analysis.print_combined_analysis, results),
               label="Raw text season summary")


def render(results: list[dict]) -> None:
    if not results:
        empty_state("flywheel")
        return
    tab_match, tab_season = st.tabs(["Per match", "Season"])
    with tab_match:
        chosen = per_match_picker(results, key="flywheel_match_pick")
        if chosen is not None:
            render_per_log(chosen)
    with tab_season:
        render_combined(results)

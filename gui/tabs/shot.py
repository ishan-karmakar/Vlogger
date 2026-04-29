# -*- coding: utf-8 -*-
"""Shot analysis tab — total per-shot energy across flywheel + feeder + hopper."""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import shot_analysis
from gui.components import per_match_picker, raw_report, empty_state
from gui.data import capture_text, match_label

_SUBSYSTEM_LABELS = [label for label, _ in shot_analysis.SUBSYSTEMS]


def _cycle_dataframe(cycles: list[dict]) -> pd.DataFrame:
    """Flatten per-cycle dicts (with nested `energies`/`peaks`/`avgs`) into
    a tidy table for display + plotting."""
    rows = []
    for i, c in enumerate(cycles):
        row = {
            "Cycle":         i + 1,
            "Start (s)":     round(c["t_start"], 1),
            "End (s)":       round(c["t_end"],   1),
            "Dur (s)":       round(c["dur"],     2),
            "Mode":          c["aim_mode"],
        }
        for label in _SUBSYSTEM_LABELS:
            row[f"{label} (J)"] = round(c["energies"].get(label, 0.0), 1)
        row["Total (J)"]    = round(c["total_E_J"],    1)
        row["Peak W (sum)"] = round(c["total_peak_W"], 0)
        rows.append(row)
    return pd.DataFrame(rows)


def render_per_log(r: dict) -> None:
    st.subheader(match_label(r["log_path"]))

    if r["n_cycles"] == 0:
        st.info("No flywheel SHOOT cycles in this log — nothing to integrate.")
        return

    totals = r["totals"]
    grand = sum(totals.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shoot cycles",      f"{r['n_cycles']}")
    c2.metric("Total shot energy", f"{grand/1000:.2f} kJ",
              f"{grand/r['n_cycles']:.0f} J / cycle")
    c3.metric("Flywheel share",
              f"{totals['flywheel']/1000:.2f} kJ",
              f"{100*totals['flywheel']/grand:.1f}%" if grand > 0 else None)
    c4.metric("Feeder + hopper",
              f"{(totals['feeder']+totals['hopper'])/1000:.2f} kJ",
              f"{100*(totals['feeder']+totals['hopper'])/grand:.1f}%" if grand > 0 else None)

    cdf = _cycle_dataframe(r["cycles"])

    # Stacked-bar of per-cycle energy contributions.
    long = cdf.melt(
        id_vars=["Cycle", "Mode"],
        value_vars=[f"{label} (J)" for label in _SUBSYSTEM_LABELS],
        var_name="Subsystem", value_name="Energy (J)",
    )
    long["Subsystem"] = long["Subsystem"].str.replace(r" \(J\)$", "", regex=True)
    fig = px.bar(
        long, x="Cycle", y="Energy (J)", color="Subsystem",
        title="Energy per shoot cycle (stacked by subsystem)",
        hover_data=["Mode"],
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Per-cycle breakdown**")
    st.dataframe(cdf, hide_index=True, width="stretch")

    raw_report(capture_text(shot_analysis.print_per_log_report, r))


def render_combined(results: list[dict]) -> None:
    st.subheader(f"Season summary — {len(results)} match{'es' if len(results) != 1 else ''}")

    rows = []
    for r in results:
        t = r["totals"]
        grand = sum(t.values())
        rows.append({
            "Match":         match_label(r["log_path"]),
            "Cycles":        r["n_cycles"],
            "Flywheel kJ":   round(t["flywheel"] / 1000, 2),
            "Feeder kJ":     round(t["feeder"]   / 1000, 2),
            "Hopper kJ":     round(t["hopper"]   / 1000, 2),
            "Total kJ":      round(grand          / 1000, 2),
            "Avg J/cyc":     round(grand / r["n_cycles"], 0) if r["n_cycles"] else 0,
        })
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, hide_index=True, width="stretch")

    all_cycles = [c for r in results for c in r["cycles"]]
    if not all_cycles:
        st.info("No shoot cycles across any match.")
        return

    n = len(all_cycles)
    grand = sum(c["total_E_J"] for c in all_cycles)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shoot cycles (all)",   f"{n}")
    c2.metric("Total shot energy",    f"{grand/1000:.2f} kJ",
              f"{grand/n:.0f} J / cycle")
    c3.metric("Most expensive shot",  f"{max(c['total_E_J'] for c in all_cycles):.0f} J")
    c4.metric("Cheapest shot",        f"{min(c['total_E_J'] for c in all_cycles):.0f} J")

    # Per-aim-mode breakdown
    mode_rows = []
    by_mode = {}
    for c in all_cycles:
        by_mode.setdefault(c["aim_mode"], []).append(c)
    for mode, cs in sorted(by_mode.items()):
        total = sum(x["total_E_J"] for x in cs)
        mode_rows.append({
            "Mode":         mode,
            "Cycles":       len(cs),
            "Avg total J":  round(total / len(cs), 1),
            "Sum kJ":       round(total / 1000,    2),
            "Avg flywheel": round(sum(x["energies"]["flywheel"] for x in cs) / len(cs), 1),
            "Avg feeder":   round(sum(x["energies"]["feeder"]   for x in cs) / len(cs), 1),
            "Avg hopper":   round(sum(x["energies"]["hopper"]   for x in cs) / len(cs), 1),
        })
    st.markdown("**Per-aim-mode breakdown**")
    st.dataframe(pd.DataFrame(mode_rows), hide_index=True, width="content")

    # Distribution of per-cycle total energy across the season.
    fig = px.histogram(
        pd.DataFrame({"Total (J)": [c["total_E_J"] for c in all_cycles],
                      "Mode":      [c["aim_mode"]   for c in all_cycles]}),
        x="Total (J)", color="Mode", nbins=30,
        title="Distribution of per-cycle total shot energy (all matches)",
    )
    st.plotly_chart(fig, width="stretch")

    raw_report(capture_text(shot_analysis.print_combined_analysis, results),
               label="Raw text season summary")


def render(results: list[dict]) -> None:
    if not results:
        empty_state("shot")
        return
    tab_match, tab_season = st.tabs(["Per match", "Season"])
    with tab_match:
        chosen = per_match_picker(results, key="shot_match_pick")
        if chosen is not None:
            render_per_log(chosen)
    with tab_season:
        render_combined(results)

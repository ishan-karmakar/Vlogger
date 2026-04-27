# -*- coding: utf-8 -*-
"""Small shared widgets used across tabs."""

import streamlit as st

from gui.data import match_label


def per_match_picker(results: list[dict], key: str):
    """Render a selectbox to pick one match from the loaded results.

    Returns the chosen result dict (or None if no results).
    """
    if not results:
        st.info("No matches loaded yet — pick a directory and matches in the sidebar.")
        return None
    labels = [match_label(r["log_path"]) for r in results]
    idx = st.selectbox(
        "Inspect match",
        options=range(len(results)),
        format_func=lambda i: labels[i],
        key=key,
    )
    return results[idx]


def raw_report(text: str, *, label: str = "Raw text report"):
    """Show a captured stdout report inside a collapsible code block."""
    if not text.strip():
        return
    with st.expander(label, expanded=False):
        st.code(text, language="text")


def empty_state(kind: str):
    st.info(
        f"Pick a log directory in the sidebar and select matches to run the "
        f"**{kind}** analysis."
    )

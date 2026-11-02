"""System Overview: specs, architecture diagrams and controller summaries."""

from __future__ import annotations

import path_setup  # noqa: F401
import streamlit as st
import streamlit.components.v1 as components

from mpc_core.sim import theme as T
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.copy_text import (
    FAIRNESS_NOTE,
    LQR_NOTE,
    OVERVIEW_LEDE,
    OVERVIEW_PAGES,
    OVERVIEW_TITLE,
    SAFETY_NOTE,
)
from mpc_core.sim.diagrams import drive_architecture, four_controller_architecture
from mpc_core.sim.ui import InsightItem, insight_strip, page_header, panel, status_bar
from mpc_core.sim.ui_state import chrome

chrome()
cfg = default_demo_config()
m = cfg.motor
page_header(title=OVERVIEW_TITLE, look_for=OVERVIEW_LEDE, eyebrow="DriveBench")
status_bar(plant="PMDC motor", model="3-state, RK4 1 ms", ts_ms=cfg.dt_s * 1e3, scenario="overview")

insight_strip(
    [
        InsightItem("Supply limit", f"{m.V_max:g} V"),
        InsightItem("Current limit", f"{m.I_max:g} A"),
        InsightItem("Top speed", f"{m.omega_max_rpm:g} RPM"),
        InsightItem("Nominal load", f"{m.T_L:g} N·m"),
        InsightItem("Electrical τ", f"{m.tau_e * 1e3:.0f} ms"),
        InsightItem("Controller period", f"{cfg.dt_s * 1e3:g} ms"),
    ]
)

st.markdown("#### Motor drive")
st.markdown(drive_architecture(), unsafe_allow_html=True)
st.markdown("#### Control loop")
st.markdown(four_controller_architecture(), unsafe_allow_html=True)

st.markdown("#### The four controllers")
cols = st.columns(2)
for i, cid in enumerate(("pid", "optimized_pid", "lqr", "mpc")):
    with cols[i % 2]:
        st.markdown(
            f'<div class="db-panel" style="border-left:3px solid {T.CONTROLLER_COLORS[cid]}">'
            f'<h4 style="color:{T.CONTROLLER_COLORS[cid]}">{T.CONTROLLER_LABELS[cid]}</h4>'
            f"<p>{T.CONTROLLER_NOTES[cid]}</p></div>",
            unsafe_allow_html=True,
        )
panel("About LQR", LQR_NOTE)
panel("Fairness", FAIRNESS_NOTE)
panel("Safety layers", SAFETY_NOTE)

st.markdown("#### Workspace")
for name, line in OVERVIEW_PAGES:
    st.markdown(f"**{name}**: {line}")
try:
    st.page_link("ui_pages/bench.py", label="Open the Experiment Bench →")
except Exception:  # page run outside st.navigation (tests): no link available
    st.markdown("Open **Experiment Bench** from the sidebar.")

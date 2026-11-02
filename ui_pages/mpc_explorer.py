"""MPC Prediction Explorer: step through the receding horizon."""

from __future__ import annotations

import path_setup  # noqa: F401
import streamlit as st

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.copy_text import MPC_LEDE, MPC_TITLE, SAFETY_NOTE
from mpc_core.sim.plotly_charts import mpc_explorer_figure
from mpc_core.sim.scenarios import SCENARIOS
from mpc_core.sim.simulate import run_mpc_step_log
from mpc_core.sim.ui import constraint_chips, page_header, panel, status_bar
from mpc_core.sim.ui_cache import DEFAULT_STEP_HORIZON, load_step_log
from mpc_core.sim.ui_state import chrome

chrome()
page_header(title=MPC_TITLE, look_for=MPC_LEDE, eyebrow="Page 4")
cfg = default_demo_config()

top_l, top_r = st.columns([2, 1])
with top_l:
    scenario_key = st.selectbox("Scenario", list(SCENARIOS), format_func=lambda k: SCENARIOS[k].title)
with top_r:
    horizon = st.slider("Horizon [10 ms samples]", 20, 100, DEFAULT_STEP_HORIZON)
status_bar(
    plant="PMDC motor", model="2-state [i, ω] ZOH", ts_ms=cfg.dt_s * 1e3,
    scenario=SCENARIOS[scenario_key].title,
)


@st.cache_data(show_spinner="Loading MPC steps…")
def compute_log(key: str, h: int):
    return run_mpc_step_log(SCENARIOS[key], cfg=cfg, horizon_steps=h, max_steps=150)


log = load_step_log(scenario_key, horizon) or compute_log(scenario_key, horizon)
state_key = f"{scenario_key}:{horizon}"
if st.session_state.get("mpc_step_key") != state_key:
    st.session_state.mpc_step_key = state_key
    st.session_state.mpc_step_idx = 0
idx = max(0, min(st.session_state.get("mpc_step_idx", 0), len(log.snapshots) - 1))
snap = log.snapshots[idx]

n1, n2, n3 = st.columns([1, 1, 3])
if n1.button("Previous", disabled=idx <= 0, use_container_width=True):
    st.session_state.mpc_step_idx = idx - 1
    st.rerun()
if n2.button("Next", type="primary", disabled=idx >= len(log.snapshots) - 1, use_container_width=True):
    st.session_state.mpc_step_idx = idx + 1
    st.rerun()
with n3:
    scrub = st.slider("Sample", 1, len(log.snapshots), idx + 1, help=f"t = {snap.time_s:.2f} s")
    if scrub - 1 != idx:
        st.session_state.mpc_step_idx = scrub - 1
        st.rerun()

c = st.columns(6)
c[0].metric("Time", f"{snap.time_s:.2f} s")
c[1].metric("Measured speed", f"{snap.y_meas:.0f} RPM")
c[2].metric("Armature current", f"{snap.i_a:.2f} A")
c[3].metric("Planned voltage now", f"{snap.u_applied:.2f} V")
c[4].metric("Load estimate", f"{snap.d_hat:.3f} N·m")
c[5].metric("Solve time", f"{snap.solve_ms:.2f} ms")

st.markdown("**Active constraints at this step**")
constraint_chips(snap.active_constraints)
st.info(snap.caption)
st.plotly_chart(
    mpc_explorer_figure(snap, ts_s=cfg.dt_s, i_max=cfg.drive.I_max, v_max=cfg.drive.V_max),
    use_container_width=True,
)
panel(
    "Receding horizon",
    "Only the first planned voltage is applied. At the next sample the model is re-anchored "
    "to the new measurement and the whole plan is recomputed.",
)
panel("Constraints", SAFETY_NOTE)

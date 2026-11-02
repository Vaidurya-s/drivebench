"""Step-through MPC horizon."""

from __future__ import annotations

import path_setup  # noqa: F401
import streamlit as st

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.copy_text import STEP_LEDE, STEP_TITLE
from mpc_core.sim.plotly_charts import mpc_horizon_figure
from mpc_core.sim.scenarios import SCENARIOS
from mpc_core.sim.simulate import run_mpc_step_log
from mpc_core.sim.ui import inject_styles, page_header
from mpc_core.sim.ui_cache import DEFAULT_STEP_HORIZON, load_step_log

inject_styles()

page_header(title=STEP_TITLE, look_for=STEP_LEDE)

top_l, top_r = st.columns([2, 1])
with top_l:
    scenario_key = st.selectbox(
        "Scenario",
        options=list(SCENARIOS.keys()),
        format_func=lambda k: SCENARIOS[k].title,
    )
with top_r:
    horizon = st.slider("Horizon [10 ms samples]", 20, 100, DEFAULT_STEP_HORIZON)

cfg = default_demo_config()


@st.cache_data(show_spinner="Loading MPC steps…")
def compute_log(key: str, h: int):
    sc = SCENARIOS[key]
    return run_mpc_step_log(sc, cfg=cfg, horizon_steps=h, max_steps=150)


disk_log = load_step_log(scenario_key, horizon)
log = disk_log if disk_log is not None else compute_log(scenario_key, horizon)

if "mpc_step_idx" not in st.session_state:
    st.session_state.mpc_step_idx = 0

state_key = f"{scenario_key}:{horizon}"
if st.session_state.get("mpc_step_key") != state_key:
    st.session_state.mpc_step_key = state_key
    st.session_state.mpc_step_idx = 0

idx = st.session_state.mpc_step_idx
idx = max(0, min(idx, len(log.snapshots) - 1))
snap = log.snapshots[idx]

nav1, nav2, nav3 = st.columns([1, 1, 3])
with nav1:
    if st.button("Previous", disabled=idx <= 0, use_container_width=True):
        st.session_state.mpc_step_idx = idx - 1
        st.rerun()
with nav2:
    if st.button(
        "Next",
        type="primary",
        disabled=idx >= len(log.snapshots) - 1,
        use_container_width=True,
    ):
        st.session_state.mpc_step_idx = idx + 1
        st.rerun()
with nav3:
    scrub = st.slider(
        "Step",
        min_value=1,
        max_value=len(log.snapshots),
        value=idx + 1,
        help=f"t = {snap.time_s:.2f} s",
    )
    if scrub - 1 != idx:
        st.session_state.mpc_step_idx = scrub - 1
        st.rerun()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Planned voltage", f"{snap.u_applied:.2f} V")
m2.metric("Load-torque estimate", f"{snap.d_hat:.3f} N·m")
m3.metric("Measured speed", f"{snap.y_meas:.0f} RPM")
m4.metric("Reference", f"{snap.y_ref:.0f} RPM")
m5.metric("Solve time", f"{snap.solve_ms:.2f} ms")

st.info(snap.caption)
st.plotly_chart(mpc_horizon_figure(snap, ts_s=cfg.dt_s), use_container_width=True)

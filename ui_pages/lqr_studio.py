"""LQR Design Studio: weights, gain, poles, Riccati checks and a response preview."""

from __future__ import annotations

from dataclasses import replace

import path_setup  # noqa: F401
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mpc_core.sim import theme as T
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.copy_text import LQR_LEDE, LQR_NOTE, LQR_TITLE
from mpc_core.sim.diagrams import lqr_design_process
from mpc_core.sim.lqr import LqrWeights, try_design_lqr
from mpc_core.sim.playground import PlaygroundParams
from mpc_core.sim.plotly_charts import chart_layout, pole_figure, style_axes
from mpc_core.sim.scenarios import SCENARIOS
from mpc_core.sim.simulate import run_closed_loop
from mpc_core.sim.ui import badge, page_header, status_bar
from mpc_core.sim.ui_state import chrome

chrome()
page_header(title=LQR_TITLE, look_for=LQR_LEDE, eyebrow="Page 3")
cfg = default_demo_config(st.session_state.motor_params)
motor = cfg.motor
status_bar(plant="PMDC motor", model="2-state + integrator", ts_ms=cfg.dt_s * 1e3, scenario="LQR design")
st.caption(LQR_NOTE)

st.markdown(lqr_design_process(), unsafe_allow_html=True)

p: PlaygroundParams = st.session_state.playground_params
REC = LqrWeights.recommended()
FIELDS = (
    ("lqr_q_current", "Current weight q_current (scale 1/I_max²)"),
    ("lqr_q_speed", "Speed weight q_speed (scale 1/ω_max²)"),
    ("lqr_q_integral", "Integral weight q_integral (scale 1/(ω_max·0.5 s)²)"),
    ("lqr_r_voltage", "Voltage weight r_voltage (scale 1/V_max²)"),
)

if st.button("Restore recommended weights"):
    for pf, _ in FIELDS:
        st.session_state.pop(f"slider_{pf}", None)
    st.session_state.playground_params = replace(
        p,
        lqr_q_current=REC.q_current,
        lqr_q_speed=REC.q_speed,
        lqr_q_integral=REC.q_integral,
        lqr_r_voltage=REC.r_voltage,
    )
    st.rerun()

st.markdown("#### Weights (logarithmic scale)")
new = {}
cols = st.columns(2)
for i, (pf, label) in enumerate(FIELDS):
    with cols[i % 2]:
        exponent = st.slider(
            label, -4.0, 4.0, float(np.log10(getattr(p, pf))), 0.1,
            key=f"slider_{pf}", format="10^%.1f",
        )
        new[pf] = float(10**exponent)
        st.caption(f"value = {new[pf]:.4g}")
if any(abs(new[pf] - getattr(p, pf)) > 1e-9 * max(1.0, abs(new[pf])) for pf, _ in FIELDS):
    # New weights change K, so only LQR results are recomputed; other controllers stay cached.
    st.session_state.playground_params = replace(p, **new)
    p = st.session_state.playground_params

w = p.lqr_weights
design, err = try_design_lqr(motor, cfg.dt_s, w)

st.markdown("#### Model")
eq1, eq2 = st.columns(2)
with eq1:
    st.latex(
        r"x=\begin{bmatrix} i_a\\ \omega\end{bmatrix},\;"
        r"A=\begin{bmatrix}-R_a/L_a & -K_e/L_a\\ K_t/J & -B/J\end{bmatrix},\;"
        r"B=\begin{bmatrix}1/L_a\\0\end{bmatrix},\; C=[0\;1]"
    )
with eq2:
    st.latex(
        r"\dot\xi=\omega-r,\quad A_{aug}=\begin{bmatrix}A&0\\C&0\end{bmatrix},\;"
        r"B_{aug}=\begin{bmatrix}B\\0\end{bmatrix},\; B_{ref}=\begin{bmatrix}0\\0\\-1\end{bmatrix}"
    )
st.latex(
    r"J=\sum_k x_{aug}^T Q\, x_{aug}+u^T R\, u,\qquad "
    r"K=(R+B_d^TPB_d)^{-1}B_d^TPA_d,\qquad u=-K x_{aug}"
)

if design is None:
    st.markdown(badge(False, "design rejected"), unsafe_allow_html=True)
    st.error(f"No LQR gain is used: {err}")
    st.stop()

st.markdown(
    "#### Design result  " + badge(True, "stable · controllable · Riccati verified"),
    unsafe_allow_html=True,
)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Controllability rank", f"{design.controllability_rank} / 3")
m2.metric("Max |closed-loop pole|", f"{np.abs(design.eigenvalues).max():.4f}")
m3.metric("Riccati residual", f"{design.riccati_residual:.1e}")
m4.metric("Gain calculation", f"{design.design_time_ms:.2f} ms")

a, b = st.columns(2)
with a:
    st.markdown("**Gain K** (V/A, V/(rad/s), V/rad)")
    st.dataframe(
        pd.DataFrame(design.K, columns=["K_i [V/A]", "K_ω [V/(rad/s)]", "K_ξ [V/rad]"]).style.format("{:.4g}"),
        hide_index=True,
        width="stretch",
    )
    st.markdown("**Q (normalised units) and R**")
    st.code(np.array2string(design.Q, precision=3) + "\nR = " + np.array2string(design.R, precision=3), language="text")
    st.markdown("**Riccati solution P**")
    st.code(np.array2string(design.P, precision=3), language="text")
with b:
    st.plotly_chart(pole_figure(design.eigenvalues), width="stretch")
    poles_s = ", ".join(f"{(np.log(z) / cfg.dt_s).real:.1f}" for z in design.eigenvalues)
    st.caption(f"Equivalent continuous poles s = ln(z)/Ts: {poles_s} 1/s")

st.markdown("#### Speed-response preview")
sc = replace(SCENARIOS["motor_startup"], key="lqr_preview", duration_s=4.0)
run = run_closed_loop(sc, "lqr", cfg=cfg, lqr_weights=w)
fig = go.Figure()
fig.add_trace(go.Scatter(x=run.time_s, y=run.ref_rpm, name="Reference",
                         line=dict(color=T.SETPOINT, dash="dash", width=1.5)))
fig.add_trace(go.Scatter(x=run.time_s, y=run.speed_rpm, name="LQR speed",
                         line=dict(color=T.CONTROLLER_COLORS["lqr"], width=2.2, dash="dashdot")))
fig.update_yaxes(title_text="Speed [RPM]")
fig.update_xaxes(title_text="Time [s]")
fig.update_layout(**chart_layout("Startup step response", height=320))
style_axes(fig)
st.plotly_chart(fig, width="stretch")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=run.time_s, y=run.v_cmd, name="Requested",
                          line=dict(color=T.CONTROLLER_COLORS["lqr"], width=1.5, dash="dot")))
fig2.add_trace(go.Scatter(x=run.time_s, y=run.v_applied, name="Applied",
                          line=dict(color=T.TEXT_PRIMARY, width=1.8)))
fig2.update_yaxes(title_text="Voltage [V]")
fig2.update_xaxes(title_text="Time [s]")
fig2.update_layout(**chart_layout("Armature voltage", height=280))
style_axes(fig2)
st.plotly_chart(fig2, width="stretch")
mm = run.metrics
settle = "did not settle" if mm.settling_time_s is None else f"settles in {mm.settling_time_s:.2f} s"
st.caption(
    f"LQR {settle}, overshoot {mm.overshoot_pct:.1f} %, peak current {mm.max_current_a:.2f} A. "
    "These weights are also used for the LQR curve on the Experiment Bench."
)

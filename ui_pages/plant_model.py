"""Plant Model: equations, matrices, parameters, limits, assumptions."""

from __future__ import annotations

import path_setup  # noqa: F401
import numpy as np
import pandas as pd
import streamlit as st

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.copy_text import PLANT_LEDE, PLANT_LIMITATIONS, PLANT_TITLE, SAFETY_NOTE
from mpc_core.sim.ui import page_header, panel, status_bar
from mpc_core.sim.ui_state import chrome
from mpc_core.twin.pmdc import PMDCParams

chrome()
page_header(title=PLANT_TITLE, look_for=PLANT_LEDE, eyebrow="Page 6")
cfg = default_demo_config()
m: PMDCParams = st.session_state.motor_params
status_bar(plant="PMDC motor", model="3-state, RK4 1 ms", ts_ms=cfg.dt_s * 1e3, scenario="reference model")

st.markdown("#### Equations")
st.latex(r"L_a \dfrac{di_a}{dt} = V_a - R_a i_a - K_e \omega")
st.latex(r"J \dfrac{d\omega}{dt} = K_t i_a - B\omega - T_L \qquad \dfrac{d\theta}{dt} = \omega")
st.latex(
    r"\dfrac{\Omega(s)}{V_a(s)} = \dfrac{K_t}{L_a J s^2 + (L_a B + R_a J)s + (R_a B + K_e K_t)}"
)

A, B, E = m.state_matrices()
num, den = m.transfer_function()
poles = np.roots(den)
c1, c2 = st.columns(2)
with c1:
    st.markdown("#### State space  x = [i_a, ω, θ]")
    st.code(
        "A =\n" + np.array2string(A, precision=4, suppress_small=True)
        + "\n\nB =\n" + np.array2string(B, precision=4)
        + "\n\nE (load torque) =\n" + np.array2string(E, precision=4),
        language="text",
    )
with c2:
    st.markdown("#### Transfer function")
    st.code(
        f"num = {num}\nden = {np.array2string(den, precision=6)}\n"
        f"poles = {np.array2string(poles, precision=3)} 1/s\n"
        f"electrical τ = {m.tau_e * 1e3:.1f} ms\nDC gain = {m.dc_gain():.2f} (rad/s)/V",
        language="text",
    )

st.markdown("#### Parameters and limits")
rows = [
    ("Armature resistance R_a", f"{m.R_a:g}", "Ω"),
    ("Armature inductance L_a", f"{m.L_a:g}", "H"),
    ("Torque constant K_t", f"{m.K_t:g}", "N·m/A"),
    ("Back-EMF constant K_e", f"{m.K_e:g}", "V·s/rad"),
    ("Inertia J", f"{m.J:g}", "kg·m²"),
    ("Viscous friction B", f"{m.B:g}", "N·m·s/rad"),
    ("Nominal load torque T_L", f"{m.T_L:g}", "N·m"),
    ("Maximum drive voltage V_max", f"{m.V_max:g}", "V"),
    ("Maximum armature current I_max", f"{m.I_max:g}", "A"),
    ("Maximum speed", f"{m.omega_max_rpm:g}", "RPM"),
    ("Voltage slew limit", f"{cfg.drive.slew_v_per_s:g}", "V/s"),
    ("Controller period Ts / plant step", f"{cfg.dt_s * 1e3:g} / {cfg.plant_dt_s * 1e3:g}", "ms"),
]
st.dataframe(pd.DataFrame(rows, columns=["Parameter", "Value", "Unit"]), hide_index=True, use_container_width=True)

st.markdown("#### Plant, prediction model, drive and measurement")
a, b = st.columns(2)
with a:
    panel("Actual plant", "Three-state motor integrated with RK4 at 1 ms. Under model mismatch its R, L, J and B differ from the nominal values.")
    panel("Controller models", "MPC predicts with a 2-state [i, ω] zero-order-hold model of the nominal motor. LQR designs on the same nominal pair.")
with b:
    panel("Drive", "Enable and e-stop, slew limit, ±V_max × bus, then a current window. " + SAFETY_NOTE)
    panel("Measurement", "Speed from an encoder with Gaussian noise; armature current measured ideally. Sampled every 10 ms.")

st.markdown("#### Modelling assumptions and limitations")
for item in PLANT_LIMITATIONS:
    st.markdown(f"- {item}")

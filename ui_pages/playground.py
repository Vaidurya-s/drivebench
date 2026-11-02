"""Playground: three controllers on one motor, presets, motor configuration and animation."""

from __future__ import annotations

from dataclasses import fields, replace

import path_setup  # noqa: F401
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.copy_text import (
    MOTOR_CONFIG_NOTE,
    PLAYGROUND_CAPTION,
    PLAYGROUND_LEDE,
    PLAYGROUND_TITLE,
)
from mpc_core.sim.motor_view import motor_animation_html
from mpc_core.sim.pid import PIDGains
from mpc_core.sim.playground import (
    PRESETS,
    PlaygroundParams,
    baseline_optimized_pid,
    build_playground_scenario,
    run_options_from_playground,
    run_triple,
)
from mpc_core.sim.plotly_charts import triple_control_figure
from mpc_core.sim.ui import (
    InsightItem,
    controller_legend,
    inject_styles,
    insight_strip,
    page_header,
)
from mpc_core.sim.ui_cache import load_playground_triple
from mpc_core.twin.pmdc import PARAM_RANGES, InvalidMotorParameter, PMDCParams

inject_styles()

DEFAULT_MOTOR = PMDCParams()

if "playground_params" not in st.session_state:
    # Open on a load step: the disturbance case where MPC's estimator shows.
    st.session_state.playground_params = PRESETS["load_step"](PlaygroundParams())
if "motor_params" not in st.session_state:
    st.session_state.motor_params = DEFAULT_MOTOR
if "retune_pid" not in st.session_state:
    st.session_state.retune_pid = False


def _key(obj) -> tuple:
    return tuple((f.name, getattr(obj, f.name)) for f in fields(obj))


@st.cache_data(show_spinner="Running closed-loop simulations…")
def cached_triple(params_key: tuple, motor_key: tuple, retune: bool):
    p = PlaygroundParams(**dict(params_key))
    motor = PMDCParams(**dict(motor_key))
    cfg = default_demo_config(motor)
    frozen = None if retune else baseline_optimized_pid(cfg=default_demo_config())
    return run_triple(
        build_playground_scenario(p),
        cfg=cfg,
        options=run_options_from_playground(p),
        horizon_steps=p.mpc_horizon,
        mpc_tracking_weight=p.mpc_tracking_weight,
        plain_pid_gains=PIDGains(kp=p.pid_kp, ki=p.pid_ki, kd=p.pid_kd),
        tune_maxiter=20,
        optimized_gains=frozen,
    )


def resolve_triple(p: PlaygroundParams, motor: PMDCParams, retune: bool):
    if motor == DEFAULT_MOTOR and not retune:
        disk = load_playground_triple(p)
        if disk is not None:
            return disk
    return cached_triple(_key(p), _key(motor), retune)


page_header(title=PLAYGROUND_TITLE, look_for=PLAYGROUND_LEDE)
controller_legend()

st.markdown("##### Presets")
preset_actions = [
    ("Speed step", "setpoint_step"),
    ("Load step", "load_step"),
    ("Load removal", "load_removal"),
    ("Periodic load", "periodic_load"),
    ("Noisy encoder", "noisy_encoder"),
    ("Tight limits", "tight_limits"),
    ("Mismatch", "model_mismatch"),
    ("Reverse", "reverse"),
]
pcols = st.columns(len(preset_actions) + 1)
for col, (label, key) in zip(pcols, preset_actions):
    if col.button(label, use_container_width=True):
        # Always start from defaults so presets do not stack on the previous case.
        base = PlaygroundParams(
            v_max=st.session_state.motor_params.V_max,
            i_max=st.session_state.motor_params.I_max,
            load_nm=st.session_state.motor_params.T_L,
        )
        st.session_state.playground_params = PRESETS[key](base)
        st.session_state._loaded_preset = key
        st.rerun()
if pcols[-1].button("Reset", type="secondary", use_container_width=True):
    st.session_state.playground_params = PlaygroundParams()
    st.session_state.motor_params = DEFAULT_MOTOR
    st.session_state.retune_pid = False
    st.session_state._loaded_preset = "default"
    st.rerun()

params: PlaygroundParams = st.session_state.playground_params
motor: PMDCParams = st.session_state.motor_params
triple = resolve_triple(params, motor, st.session_state.retune_pid)

active = (
    f"Active: {params.ref_low_rpm:.0f}→{params.ref_high_rpm:.0f} RPM at "
    f"{params.ref_step_at_s:.0f} s · load {params.load_nm:.3f} N m"
)
if params.load_step_to_nm is not None:
    active += f" → {params.load_step_to_nm:.3f} at {params.load_step_at_s:.0f} s"
if params.load_sine_amp_nm > 0:
    active += f" ± {params.load_sine_amp_nm:.3f} sin({params.load_sine_hz:g} Hz)"
active += f" · encoder σ={params.noise_std_rpm:.0f} RPM · {params.v_max:.0f} V / {params.i_max:.1f} A"
if (params.r_scale, params.j_scale, params.b_scale) != (1.0, 1.0, 1.0):
    active += " · plant mismatch on"
if motor != DEFAULT_MOTOR:
    active += " · custom motor"
st.caption(active)

chart_col, ctrl_col = st.columns([2.2, 1], gap="large")

with chart_col:
    fig = triple_control_figure(
        mpc=triple.mpc,
        pid=triple.pid,
        opt_pid=triple.optimized_pid,
        step_at_s=params.ref_step_at_s if params.ref_high_rpm != params.ref_low_rpm else None,
        load_change_at_s=params.load_step_at_s if params.load_step_to_nm is not None else None,
    )
    st.plotly_chart(fig, use_container_width=True)

    items: list[InsightItem] = []
    for name, run in (
        ("MPC", triple.mpc),
        ("PID", triple.pid),
        ("Opt. PID", triple.optimized_pid),
    ):
        m = run.metrics
        settle = "did not settle" if m.settling_time_s is None else f"settled in {m.settling_time_s:.2f} s"
        tone = "warning" if m.current_limit_s > 0 else "success"
        items.append(
            InsightItem(
                label=name,
                value=settle.capitalize(),
                hint=f"peak {m.max_current_a:.1f} A · current-limited {m.current_limit_s:.2f} s",
                tone=tone,
            )
        )
    insight_strip(items)

    st.markdown("##### Key metrics")
    rows = []
    for name, run in (
        ("MPC", triple.mpc),
        ("PID", triple.pid),
        ("Optimized PID", triple.optimized_pid),
    ):
        m = run.metrics
        rows.append(
            {
                "Controller": name,
                "Rise [s]": m.rise_time_s,
                "Settling [s]": m.settling_time_s,
                "Overshoot [%]": m.overshoot_pct,
                "IAE [RPM·s]": m.iae,
                "Max current [A]": m.max_current_a,
                "Voltage sat. [s]": m.voltage_saturation_s,
                "Energy [J]": m.electrical_energy_j,
                "Drive eff.": m.drive_efficiency,
            }
        )
    st.dataframe(
        pd.DataFrame(rows).style.format(
            {
                "Rise [s]": "{:.2f}",
                "Settling [s]": "{:.2f}",
                "Overshoot [%]": "{:.1f}",
                "IAE [RPM·s]": "{:.0f}",
                "Max current [A]": "{:.2f}",
                "Voltage sat. [s]": "{:.2f}",
                "Energy [J]": "{:.0f}",
                "Drive eff.": "{:.2f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("##### Motor view")
    pick = st.radio(
        "Controller",
        ["MPC", "PID", "Optimized PID"],
        horizontal=True,
        label_visibility="collapsed",
    )
    run = {"MPC": triple.mpc, "PID": triple.pid, "Optimized PID": triple.optimized_pid}[pick]
    components.html(motor_animation_html(run, title=f"{pick} · shaft replay"), height=470)

    if triple.mpc.mpc_solve_ms is not None:
        avg_ms = float(triple.mpc.mpc_solve_ms.mean())
        p95 = float(np.percentile(triple.mpc.mpc_solve_ms, 95))
        st.caption(f"MPC solve time — mean {avg_ms:.2f} ms / p95 {p95:.2f} ms per 10 ms sample.")
    st.caption(PLAYGROUND_CAPTION)

with ctrl_col:
    with st.form("sliders", border=False):
        p: PlaygroundParams = st.session_state.playground_params
        # Remount widgets when the preset changes so slider defaults match the case.
        pk = str(st.session_state.get("_loaded_preset", "default"))
        w_max = float(motor.omega_max_rpm)

        with st.expander("Scenario", expanded=True):
            ref_low = st.slider(
                "Speed reference, start [RPM]", -w_max, w_max, float(p.ref_low_rpm), 50.0,
                key=f"ref_low_{pk}",
            )
            ref_high = st.slider(
                "Speed reference, after step [RPM]", -w_max, w_max, float(p.ref_high_rpm), 50.0,
                key=f"ref_high_{pk}",
            )
            step_at = st.slider(
                "Reference step at [s]", 0.5, float(p.duration_s) - 1.0, float(p.ref_step_at_s),
                0.5, key=f"step_{pk}",
            )
            from_rest = st.checkbox(
                "Start from rest (0 RPM)", value=p.start_from_rest, key=f"rest_{pk}"
            )
            load = st.slider(
                "Load torque [N m]", 0.0, 0.25, float(p.load_nm), 0.005, key=f"load_{pk}"
            )
            has_step = st.checkbox(
                "Load step", value=p.load_step_to_nm is not None, key=f"hasstep_{pk}"
            )
            load_to = st.slider(
                "Load after step [N m]", 0.0, 0.25,
                float(p.load_step_to_nm if p.load_step_to_nm is not None else p.load_nm),
                0.005, key=f"loadto_{pk}",
            )
            load_at = st.slider(
                "Load step at [s]", 0.5, float(p.duration_s) - 1.0, float(p.load_step_at_s),
                0.5, key=f"loadat_{pk}",
            )
            sine_a = st.slider(
                "Periodic load amplitude [N m]", 0.0, 0.1, float(p.load_sine_amp_nm), 0.005,
                key=f"sinea_{pk}",
            )
            sine_f = st.slider(
                "Periodic load frequency [Hz]", 0.1, 5.0, float(p.load_sine_hz), 0.1,
                key=f"sinef_{pk}",
            )
            noise = st.slider(
                "Encoder noise σ [RPM]", 0.0, 50.0, float(p.noise_std_rpm), 1.0,
                key=f"noise_{pk}",
            )

        with st.expander("Plant mismatch (controllers keep nominal model)", expanded=False):
            r_scale = st.slider("Armature resistance ×", 0.7, 1.3, float(p.r_scale), 0.05, key=f"rs_{pk}")
            j_scale = st.slider("Inertia ×", 0.5, 1.5, float(p.j_scale), 0.05, key=f"js_{pk}")
            b_scale = st.slider("Viscous friction ×", 0.5, 1.5, float(p.b_scale), 0.05, key=f"bs_{pk}")

        with st.expander("Drive limits", expanded=False):
            v_lim = st.slider(
                "Voltage limit [V]", 2.0, float(motor.V_max), float(min(p.v_max, motor.V_max)),
                0.5, key=f"vmax_{pk}",
            )
            i_lim = st.slider(
                "Current limit [A]", 0.5, float(motor.I_max), float(min(p.i_max, motor.I_max)),
                0.5, key=f"imax_{pk}",
            )
            slew = st.slider(
                "Voltage slew limit [V/s]", 100.0, 5000.0, float(p.slew_v_per_s), 50.0,
                key=f"slew_{pk}",
            )
            bus_after = st.slider(
                "DC-bus level after sag", 0.6, 1.0, float(p.bus_scale_after), 0.05,
                key=f"bus_{pk}",
            )
            bus_at = st.slider(
                "Bus sag at [s]", 0.5, float(p.duration_s) - 1.0, float(p.bus_sag_at_s), 0.5,
                key=f"busat_{pk}",
            )

        with st.expander("Controllers", expanded=False):
            kp = st.slider("PID Kp [V/RPM]", 0.001, 0.1, float(p.pid_kp), 0.001, format="%.3f", key=f"kp_{pk}")
            ki = st.slider("PID Ki [V/(RPM·s)]", 0.0, 1.0, float(p.pid_ki), 0.005, format="%.3f", key=f"ki_{pk}")
            kd = st.slider("PID Kd [V·s/RPM]", 0.0, 0.01, float(p.pid_kd), 0.0005, format="%.4f", key=f"kd_{pk}")
            horizon = st.slider("MPC horizon [samples of 10 ms]", 20, 100, int(p.mpc_horizon), key=f"hor_{pk}")
            q_weight = st.slider(
                "MPC tracking weight", 0.2, 5.0, float(p.mpc_tracking_weight), 0.1, key=f"qw_{pk}"
            )

        submitted = st.form_submit_button(
            "Update simulation", type="primary", use_container_width=True
        )

    if submitted:
        st.session_state.playground_params = replace(
            p,
            ref_low_rpm=ref_low,
            ref_high_rpm=ref_high,
            ref_step_at_s=step_at,
            start_from_rest=from_rest,
            load_nm=load,
            load_step_to_nm=load_to if has_step else None,
            load_step_at_s=load_at,
            load_sine_amp_nm=sine_a,
            load_sine_hz=sine_f,
            noise_std_rpm=noise,
            r_scale=r_scale,
            j_scale=j_scale,
            b_scale=b_scale,
            v_max=v_lim,
            i_max=i_lim,
            slew_v_per_s=slew,
            bus_scale_after=bus_after,
            bus_sag_at_s=bus_at,
            mpc_horizon=horizon,
            mpc_tracking_weight=q_weight,
            pid_kp=kp,
            pid_ki=ki,
            pid_kd=kd,
        )
        st.rerun()

    with st.expander("Motor configuration", expanded=False):
        st.caption(MOTOR_CONFIG_NOTE)
        with st.form("motor_form", border=False):
            m0: PMDCParams = st.session_state.motor_params

            def num(label: str, name: str, fmt: str, step: float) -> float:
                lo, hi = PARAM_RANGES[name]
                return st.number_input(
                    label, min_value=lo, max_value=hi, value=float(getattr(m0, name)),
                    step=step, format=fmt, key=f"m_{name}",
                )

            new_vals = {
                "V_max": num("Supply / max drive voltage [V]", "V_max", "%.1f", 1.0),
                "R_a": num("Armature resistance [Ω]", "R_a", "%.3f", 0.05),
                "L_a": num("Armature inductance [H]", "L_a", "%.4f", 0.001),
                "K_t": num("Torque constant [N·m/A]", "K_t", "%.4f", 0.005),
                "K_e": num("Back-EMF constant [V·s/rad]", "K_e", "%.4f", 0.005),
                "J": num("Rotor + load inertia [kg·m²]", "J", "%.5f", 0.0005),
                "B": num("Viscous friction [N·m·s/rad]", "B", "%.5f", 0.0005),
                "T_L": num("Nominal load torque [N·m]", "T_L", "%.3f", 0.005),
                "I_max": num("Maximum armature current [A]", "I_max", "%.1f", 0.5),
                "omega_max_rpm": num("Maximum speed [RPM]", "omega_max_rpm", "%.0f", 100.0),
            }
            retune = st.checkbox(
                "Retune optimised PID for this motor (slower)",
                value=st.session_state.retune_pid,
                key="m_retune",
            )
            apply_motor = st.form_submit_button("Apply motor", use_container_width=True)
        if st.button("Restore defaults", use_container_width=True):
            st.session_state.motor_params = DEFAULT_MOTOR
            st.session_state.retune_pid = False
            for k in [k for k in st.session_state if str(k).startswith("m_")]:
                del st.session_state[k]
            st.session_state.playground_params = replace(
                st.session_state.playground_params,
                v_max=DEFAULT_MOTOR.V_max,
                i_max=DEFAULT_MOTOR.I_max,
                load_nm=DEFAULT_MOTOR.T_L,
            )
            st.rerun()
        if apply_motor:
            try:
                new_motor = PMDCParams(
                    **{**{f.name: getattr(m0, f.name) for f in fields(m0)}, **new_vals,
                       "V_rated": new_vals["V_max"]}
                )
            except InvalidMotorParameter as exc:
                st.error(str(exc))
            else:
                if abs(new_motor.K_t - new_motor.K_e) > 0.01 * max(new_motor.K_t, new_motor.K_e):
                    st.warning("K_t and K_e differ: SI units normally make them equal.")
                st.session_state.motor_params = new_motor
                st.session_state.retune_pid = retune
                st.session_state.playground_params = replace(
                    st.session_state.playground_params,
                    v_max=new_motor.V_max,
                    i_max=new_motor.I_max,
                    load_nm=new_motor.T_L,
                )
                st.rerun()

    tg = triple.tune.gains
    st.markdown("##### Optimised PID gains")
    st.caption(
        f"Kp = **{tg.kp:.3g}** V/RPM, Ki = **{tg.ki:.3g}**, Kd = **{tg.kd:.3g}**. "
        + (
            "Retuned for this motor."
            if st.session_state.retune_pid
            else "Found once on the speed-tracking scenario, then left unchanged here."
        )
    )

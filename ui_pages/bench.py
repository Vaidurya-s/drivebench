"""Experiment Bench: configure a run and compare up to four controllers."""

from __future__ import annotations

from dataclasses import fields, replace

import path_setup  # noqa: F401
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from mpc_core.sim import theme as T
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.copy_text import BENCH_CAPTION, BENCH_LEDE, BENCH_TITLE, MOTOR_CONFIG_NOTE
from mpc_core.sim.motor_view import motor_animation_html
from mpc_core.sim.playground import PRESETS, PlaygroundParams
from mpc_core.sim.plotly_charts import QUANTITIES, quantity_figure, requested_vs_applied_figure
from mpc_core.sim.ui import controller_legend, page_header, readout_tiles, status_bar
from mpc_core.sim.ui_state import (
    DEFAULT_MOTOR,
    chrome,
    is_default_motor,
    events_for,
    readouts,
    resolve_runs,
    scenario_name,
    selected_runs,
)
from mpc_core.twin.pmdc import PARAM_RANGES, InvalidMotorParameter, PMDCParams

chrome()
page_header(title=BENCH_TITLE, look_for=BENCH_LEDE, eyebrow="Page 2")

PRESET_LABELS = {
    "setpoint_step": "Speed step",
    "load_step": "Load step",
    "load_removal": "Load removal",
    "periodic_load": "Periodic load",
    "noisy_encoder": "Noisy encoder",
    "tight_limits": "Tight limits",
    "model_mismatch": "Mismatch",
    "reverse": "Reverse",
}

pcols = st.columns(len(PRESET_LABELS) + 1)
for col, (key, label) in zip(pcols, PRESET_LABELS.items()):
    if col.button(label, use_container_width=True, key=f"preset_{key}"):
        mo: PMDCParams = st.session_state.motor_params
        old: PlaygroundParams = st.session_state.playground_params
        base = PlaygroundParams(
            v_max=mo.V_max, i_max=mo.I_max, load_nm=mo.T_L,
            lqr_q_current=old.lqr_q_current, lqr_q_speed=old.lqr_q_speed,
            lqr_q_integral=old.lqr_q_integral, lqr_r_voltage=old.lqr_r_voltage,
        )
        st.session_state.playground_params = PRESETS[key](base)
        st.session_state.preset_name = key
        st.rerun()
if pcols[-1].button("Reset", use_container_width=True):
    st.session_state.playground_params = PlaygroundParams()
    st.session_state.motor_params = DEFAULT_MOTOR
    st.session_state.retune_pid = False
    st.session_state.preset_name = "default"
    st.rerun()

params: PlaygroundParams = st.session_state.playground_params
motor: PMDCParams = st.session_state.motor_params
cfg = default_demo_config(motor)
status_bar(
    plant="PMDC motor" + ("" if is_default_motor(motor) else " (custom)"),
    model="3-state, RK4 1 ms",
    ts_ms=cfg.dt_s * 1e3,
    scenario=scenario_name(params),
)

rail, work = st.columns([1, 2.6], gap="large")

with rail:
    st.markdown("##### Controllers shown")
    ids = st.multiselect(
        "Controllers",
        list(T.CONTROLLER_LABELS),
        default=st.session_state.selected_controllers,
        format_func=T.CONTROLLER_LABELS.get,
        label_visibility="collapsed",
    )
    if not ids:
        ids = list(T.CONTROLLER_LABELS)
        st.warning("Select at least one controller; showing all four.")
    st.session_state.selected_controllers = ids

    with st.form("bench_form", border=False):
        p = params
        pk = str(st.session_state.preset_name)
        w_max = float(motor.omega_max_rpm)
        with st.expander("1 · Speed reference", expanded=True):
            ref_low = st.slider("Start speed [RPM]", -w_max, w_max, float(p.ref_low_rpm), 50.0, key=f"ref_low_{pk}")
            ref_high = st.slider("Speed after step [RPM]", -w_max, w_max, float(p.ref_high_rpm), 50.0, key=f"ref_high_{pk}")
            step_at = st.slider("Step at [s]", 0.5, float(p.duration_s) - 1.0, float(p.ref_step_at_s), 0.5, key=f"step_{pk}")
            from_rest = st.checkbox("Start from rest", value=p.start_from_rest, key=f"rest_{pk}")
        with st.expander("2 · Mechanical load", expanded=True):
            load = st.slider("Load torque [N·m]", 0.0, 0.25, float(p.load_nm), 0.005, key=f"load_{pk}")
            has_step = st.checkbox("Load step", value=p.load_step_to_nm is not None, key=f"hasstep_{pk}")
            load_to = st.slider("Load after step [N·m]", 0.0, 0.25,
                                float(p.load_step_to_nm if p.load_step_to_nm is not None else p.load_nm), 0.005, key=f"loadto_{pk}")
            load_at = st.slider("Load step at [s]", 0.5, float(p.duration_s) - 1.0, float(p.load_step_at_s), 0.5, key=f"loadat_{pk}")
            sine_a = st.slider("Periodic load amplitude [N·m]", 0.0, 0.1, float(p.load_sine_amp_nm), 0.005, key=f"sinea_{pk}")
            sine_f = st.slider("Periodic load frequency [Hz]", 0.1, 5.0, float(p.load_sine_hz), 0.1, key=f"sinef_{pk}")
        with st.expander("3 · Drive constraints", expanded=False):
            v_lim = st.slider("Voltage limit [V]", 2.0, float(motor.V_max), float(min(p.v_max, motor.V_max)), 0.5, key=f"vmax_{pk}")
            i_lim = st.slider("Current limit [A]", 0.5, float(motor.I_max), float(min(p.i_max, motor.I_max)), 0.5, key=f"imax_{pk}")
            slew = st.slider("Slew limit [V/s]", 100.0, 5000.0, float(p.slew_v_per_s), 50.0, key=f"slew_{pk}")
            bus_after = st.slider("DC bus level after sag [fraction]", 0.6, 1.0, float(p.bus_scale_after), 0.05, key=f"bus_{pk}")
            bus_at = st.slider("Bus sag at [s]", 0.5, float(p.duration_s) - 1.0, float(p.bus_sag_at_s), 0.5, key=f"busat_{pk}")
        with st.expander("4 · Sensor", expanded=False):
            noise = st.slider("Encoder noise σ [RPM]", 0.0, 50.0, float(p.noise_std_rpm), 1.0, key=f"noise_{pk}")
            seed = st.number_input("Noise seed", 0, 9999, int(p.noise_seed), key=f"seed_{pk}")
        with st.expander("5 · Plant mismatch (controllers keep the nominal model)", expanded=False):
            r_scale = st.slider("Armature resistance ×", 0.7, 1.3, float(p.r_scale), 0.05, key=f"rs_{pk}")
            j_scale = st.slider("Inertia ×", 0.5, 1.5, float(p.j_scale), 0.05, key=f"js_{pk}")
            b_scale = st.slider("Viscous friction ×", 0.5, 1.5, float(p.b_scale), 0.05, key=f"bs_{pk}")
        with st.expander("6 · Controller settings", expanded=False):
            kp = st.number_input("PID Kp [V/RPM]", 0.0, 0.1, float(p.pid_kp), 0.001, format="%.4f", key=f"kp_{pk}")
            ki = st.number_input("PID Ki [V/(RPM·s)]", 0.0, 1.0, float(p.pid_ki), 0.005, format="%.4f", key=f"ki_{pk}")
            kd = st.number_input("PID Kd [V·s/RPM]", 0.0, 0.01, float(p.pid_kd), 0.0005, format="%.4f", key=f"kd_{pk}")
            horizon = st.slider("MPC horizon [10 ms samples]", 20, 100, int(p.mpc_horizon), key=f"hor_{pk}")
            q_weight = st.slider("MPC tracking weight", 0.2, 5.0, float(p.mpc_tracking_weight), 0.1, key=f"qw_{pk}")
            st.caption("LQR weights are set in the LQR Design Studio.")
        with st.expander("7 · Simulation options", expanded=False):
            duration = st.slider("Duration [s]", 6.0, 20.0, float(p.duration_s), 1.0, key=f"dur_{pk}")
        submitted = st.form_submit_button("Run experiment", type="primary", use_container_width=True)

    if submitted:
        st.session_state.playground_params = replace(
            p, ref_low_rpm=ref_low, ref_high_rpm=ref_high, ref_step_at_s=step_at,
            start_from_rest=from_rest, load_nm=load,
            load_step_to_nm=load_to if has_step else None, load_step_at_s=load_at,
            load_sine_amp_nm=sine_a, load_sine_hz=sine_f, noise_std_rpm=noise, noise_seed=int(seed),
            r_scale=r_scale, j_scale=j_scale, b_scale=b_scale, v_max=v_lim, i_max=i_lim,
            slew_v_per_s=slew, bus_scale_after=bus_after, bus_sag_at_s=bus_at,
            mpc_horizon=horizon, mpc_tracking_weight=q_weight, pid_kp=kp, pid_ki=ki, pid_kd=kd,
            duration_s=duration,
        )
        st.session_state.preset_name = "custom"
        st.rerun()

    with st.expander("Motor operating conditions", expanded=False):
        st.caption(MOTOR_CONFIG_NOTE)
        with st.form("motor_form", border=False):
            m0: PMDCParams = st.session_state.motor_params

            def num(label: str, name: str, fmt: str, step: float) -> float:
                lo, hi = PARAM_RANGES[name]
                return st.number_input(label, min_value=lo, max_value=hi, value=float(getattr(m0, name)),
                                       step=step, format=fmt, key=f"m_{name}")

            new_vals = {
                "V_max": num("Max drive voltage [V]", "V_max", "%.1f", 1.0),
                "R_a": num("Armature resistance [Ω]", "R_a", "%.3f", 0.05),
                "L_a": num("Armature inductance [H]", "L_a", "%.4f", 0.001),
                "K_t": num("Torque constant [N·m/A]", "K_t", "%.4f", 0.005),
                "K_e": num("Back-EMF constant [V·s/rad]", "K_e", "%.4f", 0.005),
                "J": num("Inertia [kg·m²]", "J", "%.5f", 0.0005),
                "B": num("Viscous friction [N·m·s/rad]", "B", "%.5f", 0.0005),
                "T_L": num("Nominal load torque [N·m]", "T_L", "%.3f", 0.005),
                "I_max": num("Max armature current [A]", "I_max", "%.1f", 0.5),
                "omega_max_rpm": num("Max speed [RPM]", "omega_max_rpm", "%.0f", 100.0),
            }
            retune = st.checkbox("Retune optimised PID for this motor (slower)", value=st.session_state.retune_pid, key="m_retune")
            apply_motor = st.form_submit_button("Apply motor", use_container_width=True)
        if st.button("Restore defaults", use_container_width=True):
            st.session_state.motor_params = DEFAULT_MOTOR
            st.session_state.retune_pid = False
            for k in [k for k in st.session_state if str(k).startswith("m_")]:
                del st.session_state[k]
            st.session_state.playground_params = replace(
                st.session_state.playground_params, v_max=DEFAULT_MOTOR.V_max,
                i_max=DEFAULT_MOTOR.I_max, load_nm=DEFAULT_MOTOR.T_L)
            st.rerun()
        if apply_motor:
            try:
                new_motor = PMDCParams(**{**{f.name: getattr(m0, f.name) for f in fields(m0)}, **new_vals,
                                          "V_rated": new_vals["V_max"]})
            except InvalidMotorParameter as exc:
                st.error(str(exc))
            else:
                if abs(new_motor.K_t - new_motor.K_e) > 0.01 * max(new_motor.K_t, new_motor.K_e):
                    st.warning("K_t and K_e differ: in SI units they are normally equal.")
                st.session_state.motor_params = new_motor
                st.session_state.retune_pid = retune
                st.session_state.playground_params = replace(
                    st.session_state.playground_params, v_max=new_motor.V_max,
                    i_max=new_motor.I_max, load_nm=new_motor.T_L)
                st.rerun()

runs_all = resolve_runs(params, motor, st.session_state.retune_pid)
runs = selected_runs(runs_all, ids)

with work:
    controller_legend(tuple(runs))
    st.plotly_chart(quantity_figure(runs, "speed", events=events_for(params), ts_s=cfg.dt_s),
                    use_container_width=True)
    readout_tiles(readouts(runs_all, list(runs)))

    tabs = st.tabs(["Armature current", "Drive voltage", "Torque", "Power & energy", "Requested vs applied"])
    for tab, q in zip(tabs[:4], ("current", "voltage", "torque", "power")):
        with tab:
            st.plotly_chart(quantity_figure(runs, q, events=events_for(params), ts_s=cfg.dt_s),
                            use_container_width=True)
    with tabs[4]:
        pick_v = st.selectbox("Controller", list(runs), format_func=T.CONTROLLER_LABELS.get, key="rva_pick")
        st.plotly_chart(requested_vs_applied_figure(runs[pick_v], T.CONTROLLER_LABELS[pick_v]), use_container_width=True)

    st.markdown("##### Key metrics")
    rows = []
    for cid, run in runs.items():
        m = run.metrics
        rows.append({
            "Controller": T.CONTROLLER_LABELS[cid], "Rise [s]": m.rise_time_s,
            "Settling [s]": m.settling_time_s, "Overshoot [%]": m.overshoot_pct,
            "IAE [RPM·s]": m.iae, "Max current [A]": m.max_current_a,
            "Voltage sat. [s]": m.voltage_saturation_s, "Energy [J]": m.electrical_energy_j,
            "Drive eff.": m.drive_efficiency,
            "Mean exec [ms]": None if run.exec_ms is None else float(np.mean(run.exec_ms)),
        })
    st.dataframe(
        pd.DataFrame(rows).style.format(
            {"Rise [s]": "{:.2f}", "Settling [s]": "{:.2f}", "Overshoot [%]": "{:.1f}",
             "IAE [RPM·s]": "{:.0f}", "Max current [A]": "{:.2f}", "Voltage sat. [s]": "{:.2f}",
             "Energy [J]": "{:.0f}", "Drive eff.": "{:.2f}", "Mean exec [ms]": "{:.3f}"}, na_rep="—"),
        use_container_width=True, hide_index=True)

    st.markdown("##### Motor view")
    pick = st.radio("Motor view controller", list(runs), horizontal=True,
                    format_func=T.CONTROLLER_LABELS.get, label_visibility="collapsed")
    components.html(motor_animation_html(runs[pick], title=f"{T.CONTROLLER_LABELS[pick]} · shaft replay"), height=470)
    st.caption(BENCH_CAPTION)
    tg = runs_all.tune.gains
    st.caption(f"Optimised PID gains: Kp = {tg.kp:.3g} V/RPM, Ki = {tg.ki:.3g}, Kd = {tg.kd:.3g}. "
               + ("Retuned for this motor." if st.session_state.retune_pid else "Tuned once on speed tracking, then frozen."))

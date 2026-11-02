"""Shared Streamlit state and cached runners for the DriveBench pages."""

from __future__ import annotations

from dataclasses import fields

import streamlit as st

from mpc_core.sim import theme as T
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.pid import PIDGains
from mpc_core.sim.playground import (
    PRESETS,
    ControllerRuns,
    PlaygroundParams,
    baseline_optimized_pid,
    build_playground_scenario,
    run_bench,
    run_options_from_playground,
)
from mpc_core.sim.simulate import CONTROLLER_IDS
from mpc_core.sim.ui import sidebar_brand
from mpc_core.sim.ui_cache import load_playground_runs
from mpc_core.twin.pmdc import PMDCParams

DEFAULT_MOTOR = PMDCParams()


def is_default_motor(m) -> bool:
    """Value comparison (robust to Streamlit reloading the PMDCParams class)."""
    return _key(m) == _key(DEFAULT_MOTOR)


def init_state() -> None:
    """Session defaults shared by every page (idempotent)."""
    if "playground_params" not in st.session_state:
        st.session_state.playground_params = PRESETS["load_step"](PlaygroundParams())
    if "motor_params" not in st.session_state:
        st.session_state.motor_params = DEFAULT_MOTOR
    if "retune_pid" not in st.session_state:
        st.session_state.retune_pid = False
    if "preset_name" not in st.session_state:
        st.session_state.preset_name = "load_step"
    if "selected_controllers" not in st.session_state:
        st.session_state.selected_controllers = list(CONTROLLER_IDS)


def chrome() -> None:
    """Brand + state init; call at the top of every page."""
    from mpc_core.sim.ui import inject_styles

    inject_styles()
    sidebar_brand()
    init_state()


def _key(obj) -> tuple:
    return tuple((f.name, getattr(obj, f.name)) for f in fields(obj))


@st.cache_data(show_spinner="Running closed-loop simulations…")
def _cached_runs(params_key: tuple, motor_key: tuple, retune: bool) -> ControllerRuns:
    p = PlaygroundParams(**dict(params_key))
    motor = PMDCParams(**dict(motor_key))
    cfg = default_demo_config(motor)
    frozen = None if retune else baseline_optimized_pid(cfg=default_demo_config())
    return run_bench(
        build_playground_scenario(p),
        cfg=cfg,
        options=run_options_from_playground(p),
        horizon_steps=p.mpc_horizon,
        mpc_tracking_weight=p.mpc_tracking_weight,
        plain_pid_gains=PIDGains(kp=p.pid_kp, ki=p.pid_ki, kd=p.pid_kd),
        lqr_weights=p.lqr_weights,
        tune_maxiter=20,
        optimized_gains=frozen,
    )


def resolve_runs(p: PlaygroundParams, motor: PMDCParams, retune: bool) -> ControllerRuns:
    """Disk cache for the default motor (LQR recomputed if its weights changed), else live."""
    if is_default_motor(motor) and not retune:
        disk = load_playground_runs(p)
        if disk is not None:
            return disk
    return _cached_runs(_key(p), _key(motor), retune)


def events_for(p: PlaygroundParams) -> list[tuple[float, str]]:
    ev: list[tuple[float, str]] = []
    if p.ref_high_rpm != p.ref_low_rpm:
        ev.append((p.ref_step_at_s, "speed step"))
    if p.load_step_to_nm is not None:
        ev.append((p.load_step_at_s, "load step"))
    if p.bus_scale_after != 1.0:
        ev.append((p.bus_sag_at_s, "bus sag"))
    return ev


def scenario_name(p: PlaygroundParams) -> str:
    name = st.session_state.get("preset_name", "custom")
    return str(name).replace("_", " ")


def readouts(runs: ControllerRuns, ids: list[str]) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for cid in ids:
        m = runs[cid].metrics
        settle = "n/a" if m.settling_time_s is None else f"{m.settling_time_s:.2f} s"
        out[cid] = [
            ("Settling", settle),
            ("Overshoot", f"{m.overshoot_pct:.1f} %"),
            ("IAE", f"{m.iae:.0f} RPM·s"),
            ("Peak current", f"{m.max_current_a:.2f} A"),
            ("Current-limited", f"{m.current_limit_s:.2f} s"),
        ]
    return out


def selected_runs(runs: ControllerRuns, ids: list[str]) -> dict:
    return {c: runs[c] for c in CONTROLLER_IDS if c in ids and c in runs.runs}


__all__ = [
    "DEFAULT_MOTOR", "T", "is_default_motor", "chrome", "events_for", "init_state", "readouts", "resolve_runs",
    "scenario_name", "selected_runs",
]

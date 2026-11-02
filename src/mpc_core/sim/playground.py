"""Build ad-hoc scenarios and run three-controller comparisons for the Streamlit UI."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import numpy as np

from mpc_core.sim.config import DemoConfig, default_demo_config
from mpc_core.sim.pid import PIDGains
from mpc_core.sim.pid_tune import TuneResult, tune_pid_gains
from mpc_core.sim.scenarios import ScenarioConfig, add, constant, piecewise, sinusoid
from mpc_core.sim.simulate import RunOptions, SimulationResult, run_closed_loop
from mpc_core.twin.pmdc import PMDCParams


@dataclass(frozen=True)
class PlaygroundParams:
    duration_s: float = 12.0
    # Reference [RPM]: start low, step to high at ref_step_at_s.
    ref_low_rpm: float = 1000.0
    ref_high_rpm: float = 2000.0
    ref_step_at_s: float = 3.0
    start_from_rest: bool = False
    # Load torque [N m]: nominal, optional step and optional sinusoid.
    load_nm: float = 0.05
    load_step_to_nm: float | None = None
    load_step_at_s: float = 6.0
    load_sine_amp_nm: float = 0.0
    load_sine_hz: float = 0.5
    # Measurement and plant.
    noise_std_rpm: float = 0.0
    noise_seed: int = 42
    r_scale: float = 1.0
    j_scale: float = 1.0
    b_scale: float = 1.0
    # Drive limits.
    v_max: float = 24.0
    i_max: float = 8.0
    slew_v_per_s: float = 1200.0
    bus_scale_after: float = 1.0
    bus_sag_at_s: float = 6.0
    # Controllers.
    mpc_horizon: int = 60
    mpc_tracking_weight: float = 1.0
    pid_kp: float = 0.01
    pid_ki: float = 0.03
    pid_kd: float = 0.0


def build_playground_scenario(p: PlaygroundParams) -> ScenarioConfig:
    ref_fn = piecewise([(0.0, p.ref_low_rpm), (p.ref_step_at_s, p.ref_high_rpm)])
    steps = [(0.0, p.load_nm)]
    if p.load_step_to_nm is not None:
        steps.append((p.load_step_at_s, p.load_step_to_nm))
    load_fn = piecewise(steps)
    if p.load_sine_amp_nm > 0.0:
        load_fn = add(load_fn, sinusoid(0.0, p.load_sine_amp_nm, p.load_sine_hz))
    bus_fn = None
    if p.bus_scale_after != 1.0:
        bus_fn = piecewise([(0.0, 1.0), (p.bus_sag_at_s, p.bus_scale_after)])
    return ScenarioConfig(
        key="playground",
        title="Playground",
        description="Interactive scenario from the Playground sliders.",
        duration_s=p.duration_s,
        y_ref_fn=ref_fn,
        load_fn=load_fn,
        omega0_rpm=0.0 if p.start_from_rest else p.ref_low_rpm,
        bus_fn=bus_fn,
        noise_std_rpm=p.noise_std_rpm,
        noise_seed=p.noise_seed,
        plant_scale=(p.r_scale, 1.0, p.j_scale, p.b_scale),
        v_max=p.v_max,
        i_max=p.i_max,
        slew_v_per_s=p.slew_v_per_s,
        load_change_at_s=p.load_step_at_s if p.load_step_to_nm is not None else None,
        pid_gains=(p.pid_kp, p.pid_ki, p.pid_kd),
        mpc_horizon=p.mpc_horizon,
    )


def run_options_from_playground(p: PlaygroundParams) -> RunOptions:
    return RunOptions(noise_std_rpm=p.noise_std_rpm, noise_seed=p.noise_seed)


@dataclass(frozen=True)
class TripleRun:
    mpc: SimulationResult
    pid: SimulationResult
    optimized_pid: SimulationResult
    tune: TuneResult


# Gains tuned once on the mild speed-tracking scenario, then reused everywhere. That
# matches field practice (you do not retune a drive for every load change) and
# lets MPC's constraint planning show against a strong but fixed PID baseline.
FROZEN_PID_PATH = Path(__file__).resolve().parents[3] / "data" / "ui" / "optimized_pid.json"
_BASELINE_OPT_PID: dict[PMDCParams, TuneResult] = {}


def _load_frozen(motor: PMDCParams) -> TuneResult | None:
    if motor != PMDCParams() or not FROZEN_PID_PATH.is_file():
        return None
    d = json.loads(FROZEN_PID_PATH.read_text())
    return TuneResult(
        gains=PIDGains(kp=d["kp"], ki=d["ki"], kd=d["kd"]),
        final_objective=d["objective"],
        metrics_iae=d["iae"],
        violation_steps=d["violation_steps"],
    )


def baseline_optimized_pid(
    *,
    cfg: DemoConfig | None = None,
    tune_maxiter: int = 35,
    force_retune: bool = False,
) -> TuneResult:
    """Optimised PID gains locked to the speed-tracking scenario, then frozen.

    The nominal motor reads the frozen gains from ``data/ui/optimized_pid.json``
    (written by ``scripts/precompute_ui_data.py``); other motors are tuned once
    per process and cached.
    """
    cfg = cfg or default_demo_config()
    if not force_retune:
        if cfg.motor in _BASELINE_OPT_PID:
            return _BASELINE_OPT_PID[cfg.motor]
        frozen = _load_frozen(cfg.motor)
        if frozen is not None:
            _BASELINE_OPT_PID[cfg.motor] = frozen
            return frozen
    from mpc_core.sim.scenarios import SCENARIOS

    result = tune_pid_gains(SCENARIOS["speed_tracking"], cfg=cfg, maxiter=tune_maxiter)
    _BASELINE_OPT_PID[cfg.motor] = result
    return result


def save_frozen_pid(result: TuneResult) -> None:
    FROZEN_PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    FROZEN_PID_PATH.write_text(
        json.dumps(
            {
                "kp": result.gains.kp,
                "ki": result.gains.ki,
                "kd": result.gains.kd,
                "objective": result.final_objective,
                "iae": result.metrics_iae,
                "violation_steps": result.violation_steps,
                "tuned_on": "speed_tracking",
            },
            indent=2,
        )
    )


def run_triple(
    scenario: ScenarioConfig,
    *,
    cfg: DemoConfig | None = None,
    options: RunOptions | None = None,
    horizon_steps: int | None = None,
    mpc_tracking_weight: float | None = None,
    plain_pid_gains: PIDGains | None = None,
    tune_maxiter: int = 35,
    freeze_optimized_pid: bool = True,
    optimized_gains: TuneResult | None = None,
) -> TripleRun:
    cfg = cfg or default_demo_config()
    opt = options or RunOptions()
    plain = plain_pid_gains or PIDGains(*scenario.pid_gains)
    if optimized_gains is not None:
        tune = optimized_gains
    elif freeze_optimized_pid:
        tune = baseline_optimized_pid(cfg=cfg, tune_maxiter=tune_maxiter)
    else:
        tune = tune_pid_gains(
            scenario,
            cfg=cfg,
            options=opt,
            x0=(plain.kp, plain.ki, plain.kd),
            maxiter=tune_maxiter,
        )
    mpc = run_closed_loop(
        scenario,
        "mpc",
        cfg=cfg,
        horizon_steps=horizon_steps,
        options=opt,
        mpc_tracking_weight=mpc_tracking_weight,
    )
    pid = run_closed_loop(
        scenario, "pid", cfg=cfg, options=opt, pid_gains=plain, result_label="pid"
    )
    opt_pid = run_closed_loop(
        scenario,
        "pid",
        cfg=cfg,
        options=opt,
        pid_gains=tune.gains,
        result_label="optimized_pid",
    )
    return TripleRun(mpc=mpc, pid=pid, optimized_pid=opt_pid, tune=tune)


PRESETS: dict[str, Callable[[PlaygroundParams], PlaygroundParams]] = {
    "setpoint_step": lambda p: replace(
        p, ref_low_rpm=1000.0, ref_high_rpm=2000.0, ref_step_at_s=3.0
    ),
    "load_step": lambda p: replace(
        p,
        ref_low_rpm=2000.0,
        ref_high_rpm=2000.0,
        load_step_to_nm=0.10,
        load_step_at_s=5.0,
    ),
    "load_removal": lambda p: replace(
        p,
        ref_low_rpm=2000.0,
        ref_high_rpm=2000.0,
        load_nm=0.10,
        load_step_to_nm=0.05,
        load_step_at_s=5.0,
    ),
    "periodic_load": lambda p: replace(
        p,
        ref_low_rpm=1500.0,
        ref_high_rpm=1500.0,
        load_nm=0.07,
        load_sine_amp_nm=0.03,
        load_sine_hz=0.5,
    ),
    "noisy_encoder": lambda p: replace(
        p,
        ref_low_rpm=1000.0,
        ref_high_rpm=1500.0,
        ref_step_at_s=4.0,
        noise_std_rpm=15.0,
        noise_seed=7,
    ),
    "tight_limits": lambda p: replace(
        p,
        start_from_rest=True,
        ref_low_rpm=1500.0,
        ref_high_rpm=2500.0,
        ref_step_at_s=5.0,
        v_max=14.0,
        i_max=4.0,
    ),
    "model_mismatch": lambda p: replace(
        p,
        r_scale=1.2,
        j_scale=1.3,
        b_scale=1.25,
        ref_low_rpm=1000.0,
        ref_high_rpm=2000.0,
        ref_step_at_s=3.0,
        load_step_to_nm=0.09,
        load_step_at_s=8.0,
        duration_s=14.0,
    ),
    "reverse": lambda p: replace(
        p, ref_low_rpm=1000.0, ref_high_rpm=-1000.0, ref_step_at_s=3.0, duration_s=10.0
    ),
}

"""Optimise PID gains on the same plant, drive, noise and limits as closed-loop runs.

The objective is a weighted sum of dimensionless terms, all taken from the
recorded run so tuning sees exactly what the scorecard sees:

    J = w_iae * IAE/(T * 1000 RPM)        tracking error
      + w_os  * overshoot/100             overshoot
      + w_ts  * settling/T                settling time (T if never settled)
      + w_u   * rms(dV) / (0.1 V_max)     control effort (voltage activity)
      + w_vsat * t_vsat/T                 voltage-saturation duration
      + w_ilim * t_ilim/T                 current-limit duration

Gains are optimised in scaled variables (kp, ki, kd divided by typical sizes) so
L-BFGS-B sees a well-conditioned problem.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from mpc_core.sim.config import DemoConfig, default_demo_config
from mpc_core.sim.pid import PIDGains
from mpc_core.sim.scenarios import ScenarioConfig
from mpc_core.sim.simulate import RunOptions, SimulationResult, run_closed_loop


@dataclass(frozen=True)
class TuneWeights:
    iae: float = 3.0
    overshoot: float = 1.0
    settling: float = 1.0
    effort: float = 0.05
    v_saturation: float = 1.0
    i_limit: float = 0.25


@dataclass(frozen=True)
class TuneResult:
    gains: PIDGains
    final_objective: float
    metrics_iae: float
    violation_steps: int


# Typical size of each gain: optimisation variable = gain / scale.
_SCALE = np.array([0.02, 0.05, 0.001])
_BOUNDS = [(0.0005, 0.5), (0.0, 2.0), (0.0, 0.02)]  # kp, ki, kd


def tuning_objective(run: SimulationResult, duration_s: float, w: TuneWeights) -> float:
    """Composite objective of one closed-loop run (see module docstring)."""
    m = run.metrics
    ts = m.settling_time_s if m.settling_time_s is not None else duration_s
    dv = np.diff(run.v_applied, prepend=run.v_applied[0])
    effort = float(np.sqrt(np.mean(dv**2))) / (0.1 * run.v_max)
    return float(
        w.iae * m.iae / (duration_s * 1000.0)
        + w.overshoot * m.overshoot_pct / 100.0
        + w.settling * ts / duration_s
        + w.effort * effort
        + w.v_saturation * m.voltage_saturation_s / duration_s
        + w.i_limit * m.current_limit_s / duration_s
    )


def tune_pid_gains(
    scenario: ScenarioConfig,
    *,
    cfg: DemoConfig | None = None,
    options: RunOptions | None = None,
    x0: tuple[float, float, float] | None = None,
    weights: TuneWeights | None = None,
    maxiter: int = 30,
    starts: tuple[float, ...] = (1.0, 2.0, 4.0),
) -> TuneResult:
    """Minimise the composite objective over (kp, ki, kd) with L-BFGS-B."""
    cfg = cfg or default_demo_config()
    base = options or RunOptions()
    w = weights or TuneWeights()
    start = np.array(x0 or scenario.pid_gains, dtype=float)

    def run_with(x: np.ndarray) -> SimulationResult:
        gains = PIDGains(kp=float(x[0]), ki=float(x[1]), kd=float(x[2]))
        return run_closed_loop(scenario, "pid", cfg=cfg, options=base, pid_gains=gains)

    def objective(z: np.ndarray) -> float:
        return tuning_objective(run_with(z * _SCALE), scenario.duration_s, w)

    # The objective has flat spots and kinks (settling time, saturation time), so
    # forward differences use a coarse step and L-BFGS-B restarts from a few scaled
    # copies of the starting gains; the best end point wins.
    best_z, best_j = None, np.inf
    for mult in starts:
        z0 = np.array([start[0] * mult, start[1] * mult, start[2]]) / _SCALE
        z0 = np.clip(z0, [b[0] / s for b, s in zip(_BOUNDS, _SCALE)], [b[1] / s for b, s in zip(_BOUNDS, _SCALE)])
        res = minimize(
            objective,
            z0,
            method="L-BFGS-B",
            bounds=[(lo / s, hi / s) for (lo, hi), s in zip(_BOUNDS, _SCALE)],
            options={"maxiter": maxiter, "eps": 0.05},
        )
        if res.fun < best_j:
            best_z, best_j = res.x, float(res.fun)
    best_x = best_z * _SCALE
    best = PIDGains(kp=float(best_x[0]), ki=float(best_x[1]), kd=float(best_x[2]))
    verify = run_with(best_x)
    return TuneResult(
        gains=best,
        final_objective=tuning_objective(verify, scenario.duration_s, w),
        metrics_iae=verify.metrics.iae,
        violation_steps=verify.metrics.constraint_violation_steps,
    )

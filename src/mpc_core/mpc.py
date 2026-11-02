"""Offset-free MPC on an identified linear model.

Integrating disturbance per Pannocchia and Rawlings (2003). The disturbance is
refreshed each run from the one-step innovation, scaled by an optional observer
gain. The quadratic programme tracks a CV reference (with optional preview)
under window and rate limits, with a free control horizon, move penalty, and
terminal cost. Nothing here writes to a plant.

Two prediction models share this entry point (``solve``):

* ``IdentifiedLinearModel``: SISO first-order ARX (generic, kept for tests).
* ``MotorStateSpaceModel``: the PMDC motor, state [i_a, omega], input armature
  voltage, disturbance load torque. Adds a predicted-current constraint
  |i_a| <= I_max, voltage box and voltage-rate limits. Speeds are RPM at the
  interface, so tracking and terminal weights act on RPM^2 and the move weight
  on V^2.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from mpc_core.identified import IdentifiedLinearModel, MotorStateSpaceModel
from mpc_core.thresholds import SetpointLimits


class MpcTimedOut(Exception):
    pass


@dataclass
class MpcState:
    """Carried across shadow runs for the integrating disturbance."""

    d_hat: float = 0.0
    last_y: float | None = None
    last_u: float | None = None
    last_i: float | None = None
    d_v: float = 0.0  # motor model only: armature-voltage disturbance estimate [V]


@dataclass(frozen=True)
class MpcResult:
    best: dict[str, float]
    y_ref: float
    d_hat: float
    predicted_y: list[float]
    active_constraints: list[str]
    state: MpcState
    planned_u: list[float] | None = None
    predicted_i: list[float] | None = None
    d_v_hat: float = 0.0


def refresh_disturbance(
    model: IdentifiedLinearModel | MotorStateSpaceModel,
    state: MpcState,
    y_meas: float,
    u_current: float,
    *,
    observer_gain: float = 1.0,
    i_meas: float | None = None,
) -> MpcState:
    """Update integrating disturbance from the one-step innovation.

    For the motor model the disturbance is the load torque [N m] and
    ``i_meas`` (armature current, measured) is required.
    """
    if observer_gain <= 0.0:
        raise ValueError("observer_gain must be positive")
    if isinstance(model, MotorStateSpaceModel):
        from mpc_core.mpc_motor import refresh_torque

        return refresh_torque(model, state, y_meas, u_current, i_meas, observer_gain)
    if state.last_y is None or state.last_u is None:
        d0 = (1.0 - model.a) * y_meas - model.b * u_current
        return MpcState(d_hat=d0, last_y=y_meas, last_u=u_current)
    y_pred = model.a * state.last_y + model.b * state.last_u + state.d_hat
    innovation = y_meas - y_pred
    return MpcState(
        d_hat=state.d_hat + observer_gain * innovation,
        last_y=y_meas,
        last_u=u_current,
    )


def _simulate(
    model: IdentifiedLinearModel,
    y0: float,
    d_hat: float,
    u_seq: NDArray[np.float64],
) -> NDArray[np.float64]:
    y = y0
    out = np.empty(len(u_seq), dtype=np.float64)
    for i, u in enumerate(u_seq):
        y = model.a * y + model.b * float(u) + d_hat
        out[i] = y
    return out


def _expand_control_sequence(
    x: NDArray[np.float64],
    horizon_steps: int,
) -> NDArray[np.float64]:
    """Hold the last free move for the remainder of the prediction horizon."""
    nu = len(x)
    if nu >= horizon_steps:
        return np.asarray(x[:horizon_steps], dtype=np.float64)
    u_seq = np.empty(horizon_steps, dtype=np.float64)
    u_seq[:nu] = x
    u_seq[nu:] = x[-1]
    return u_seq


def solve(
    model: IdentifiedLinearModel | MotorStateSpaceModel,
    limits: Sequence[SetpointLimits],
    current: Mapping[str, float],
    y_meas: float,
    y_ref: float,
    horizon_steps: int,
    time_limit_s: float,
    state: MpcState,
    tracking_weight: float = 1.0,
    *,
    control_horizon: int | None = None,
    move_weight: float = 0.0,
    terminal_weight: float = 0.0,
    y_ref_traj: Sequence[float] | None = None,
    observer_gain: float = 1.0,
    i_meas: float | None = None,
    i_max: float | None = None,
) -> MpcResult:
    """SISO offset-free QP; returns the first-move proposal (receding horizon).

    With a ``MotorStateSpaceModel``, ``y_meas``/``y_ref`` are speeds in RPM, the
    manipulated variable is armature voltage (``limits[0]`` is the voltage box
    and per-sample slew), ``i_meas`` is the measured armature current and
    ``i_max`` the predicted-current bound (see ``mpc_motor``).
    """
    if isinstance(model, MotorStateSpaceModel):
        from mpc_core.mpc_motor import solve_motor

        return solve_motor(
            model,
            limits,
            current,
            y_meas,
            y_ref,
            horizon_steps,
            time_limit_s,
            state,
            tracking_weight,
            control_horizon=control_horizon,
            move_weight=move_weight,
            terminal_weight=terminal_weight,
            y_ref_traj=y_ref_traj,
            observer_gain=observer_gain,
            i_meas=i_meas,
            i_max=i_max,
        )
    if horizon_steps < 1:
        raise ValueError("horizon_steps must be at least 1")
    if len(limits) != 1:
        raise ValueError("identified_linear offset-free MPC is SISO in W5.1")
    if tracking_weight < 0.0 or move_weight < 0.0 or terminal_weight < 0.0:
        raise ValueError("weights must be non-negative")
    lim = limits[0]
    sp = lim.setpoint_id
    u0 = float(current[sp])
    st = refresh_disturbance(
        model, state, y_meas, u0, observer_gain=observer_gain
    )
    nu = control_horizon if control_horizon is not None else 1
    if nu < 1:
        raise ValueError("control_horizon must be at least 1")
    nu = min(nu, horizon_steps)

    if y_ref_traj is None:
        ref = np.full(horizon_steps, float(y_ref), dtype=np.float64)
    else:
        if len(y_ref_traj) < horizon_steps:
            raise ValueError("y_ref_traj must cover horizon_steps")
        ref = np.asarray(y_ref_traj[:horizon_steps], dtype=np.float64)

    # Box on absolute power; rate limits enforced as SLSQP inequalities.
    bounds = [(lim.low, lim.high)] * nu
    lo0 = max(lim.low, u0 - lim.max_step)
    hi0 = min(lim.high, u0 + lim.max_step)
    if lo0 > hi0:
        raise ValueError("no feasible setting within one step of the current setting")
    bounds[0] = (lo0, hi0)

    deadline = time.monotonic() + time_limit_s
    max_step = float(lim.max_step)

    def f(x: NDArray[np.float64]) -> float:
        if time.monotonic() > deadline:
            raise MpcTimedOut()
        u_seq = _expand_control_sequence(x, horizon_steps)
        ys = _simulate(model, y_meas, st.d_hat, u_seq)
        track = tracking_weight * float(np.sum((ys - ref) ** 2))
        term = terminal_weight * float((ys[-1] - ref[-1]) ** 2)
        if move_weight == 0.0:
            move = 0.0
        else:
            du = np.diff(u_seq, prepend=u0)
            move = move_weight * float(np.sum(du**2))
        return track + term + move

    cons = []
    # |u[i] - u[i-1]| <= max_step  for i = 1..nu-1
    for i in range(1, nu):
        cons.append(
            {
                "type": "ineq",
                "fun": (lambda x, i=i: max_step - (x[i] - x[i - 1])),
            }
        )
        cons.append(
            {
                "type": "ineq",
                "fun": (lambda x, i=i: max_step - (x[i - 1] - x[i])),
            }
        )

    x0 = np.full(nu, float(np.clip(u0, lo0, hi0)), dtype=np.float64)
    method = "SLSQP" if nu > 1 else "L-BFGS-B"
    res = minimize(
        f,
        x0,
        method=method,
        bounds=bounds,
        constraints=cons if nu > 1 else (),
        options={"maxiter": 60, "ftol": 1e-9},
    )
    x_star = np.asarray(res.x, dtype=np.float64)
    # Project first move into the one-step feasible set (numerical safety).
    u_star = float(np.clip(x_star[0], lo0, hi0))
    x_star = x_star.copy()
    x_star[0] = u_star
    u_seq = _expand_control_sequence(x_star, horizon_steps)
    u_seq[0] = u_star
    ys = _simulate(model, y_meas, st.d_hat, u_seq)
    active: list[str] = []
    if np.isclose(u_star, lim.low) or np.isclose(u_star, lim.high):
        active.append(f"{sp}.window")
    elif np.isclose(abs(u_star - u0), lim.max_step):
        active.append(f"{sp}.max_step")
    st_out = MpcState(d_hat=st.d_hat, last_y=y_meas, last_u=u_star)
    return MpcResult(
        best={sp: u_star},
        y_ref=float(y_ref),
        d_hat=st.d_hat,
        predicted_y=[float(v) for v in ys],
        active_constraints=active,
        state=st_out,
        planned_u=[float(v) for v in u_seq],
    )

"""Offset-free MPC for the PMDC motor (called through ``mpc.solve``).

Prediction model: ``MotorStateSpaceModel`` (x = [i_a, omega], input armature
voltage, disturbance load torque). Speeds are RPM at the interface, so the
tracking and terminal weights act on RPM^2 and the move weight on V^2.

The QP is solved with SciPy SLSQP using an analytic gradient and linear
constraints (voltage box, voltage rate between moves, predicted armature
current |i_k| <= I_max). The model is linear, so the condensed prediction
matrices are built once per (model, horizon) and cached.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from mpc_core.identified import MotorStateSpaceModel
from mpc_core.mpc import MpcResult, MpcState, MpcTimedOut
from mpc_core.thresholds import SetpointLimits
from mpc_core.twin.pmdc import RAD_S_PER_RPM


_OBJ_SCALE = 1e-6


def refresh_torque(
    model: MotorStateSpaceModel,
    state: MpcState,
    y_meas_rpm: float,
    v_applied: float,
    i_meas: float | None,
    observer_gain: float,
) -> MpcState:
    """Joint load-torque and armature-voltage disturbance estimate.

    The one-step innovations of speed and current are mapped back to the two
    disturbances through the model's input matrix [B_d, E_d]. The torque estimate
    absorbs load and friction error; the voltage estimate absorbs electrical error
    (a wrong resistance or back-EMF constant), which a torque-only estimate cannot
    remove. With both estimated, the model's two steady-state equations hold at the
    measured steady state, so the planned speed target is reached without offset.

    ``v_applied`` is the voltage the drive applied over the previous interval
    (not the MPC's own earlier proposal, which the drive may have modified).
    """
    if i_meas is None:
        raise ValueError("i_meas is required for the motor model")
    p = model.params
    if state.last_y is None or state.last_u is None or state.last_i is None:
        # Zero-acceleration torque balance K_t i = B w + T_L at the first sample.
        d0 = p.K_t * i_meas - p.B * y_meas_rpm * RAD_S_PER_RPM
        return MpcState(
            d_hat=d0, last_y=y_meas_rpm, last_u=v_applied, last_i=i_meas, d_v=0.0
        )
    Ad, Bd, Ed = model.Ad, model.Bd, model.Ed
    x_prev = np.array([state.last_i, state.last_y * RAD_S_PER_RPM])
    x_pred = Ad @ x_prev + Bd * (v_applied + state.d_v) + Ed * state.d_hat
    innovation = np.array([i_meas, y_meas_rpm * RAD_S_PER_RPM]) - x_pred
    # innovation = [Bd Ed] @ [delta_dv, delta_dT]
    delta = np.linalg.solve(np.column_stack([Bd, Ed]), innovation)
    return MpcState(
        d_hat=state.d_hat + observer_gain * float(delta[1]),
        last_y=y_meas_rpm,
        last_u=v_applied,
        last_i=i_meas,
        d_v=state.d_v + observer_gain * float(delta[0]),
    )


def blocking_matrix(horizon_steps: int, n_moves: int) -> NDArray[np.float64]:
    """(N, nu) hold matrix with block lengths 1, 2, 4, ... and a long last block.

    Early samples get fine resolution while the last move covers the slow
    mechanical tail of the horizon.
    """
    n_moves = max(1, min(n_moves, horizon_steps))
    sizes: list[int] = []
    remaining = horizon_steps
    for j in range(n_moves - 1):
        size = min(2**j, remaining - (n_moves - 1 - j))
        sizes.append(max(1, size))
        remaining -= sizes[-1]
    sizes.append(remaining)
    mat = np.zeros((horizon_steps, n_moves))
    row = 0
    for j, size in enumerate(sizes):
        mat[row : row + size, j] = 1.0
        row += size
    return mat


def solve_motor(
    model: MotorStateSpaceModel,
    limits: Sequence[SetpointLimits],
    current: Mapping[str, float],
    y_meas: float,
    y_ref: float,
    horizon_steps: int,
    time_limit_s: float,
    state: MpcState,
    tracking_weight: float,
    *,
    control_horizon: int | None,
    move_weight: float,
    terminal_weight: float,
    y_ref_traj: Sequence[float] | None,
    observer_gain: float,
    i_meas: float | None,
    i_max: float | None,
) -> MpcResult:
    """Speed-tracking QP over armature-voltage moves with a current constraint."""
    if horizon_steps < 1:
        raise ValueError("horizon_steps must be at least 1")
    if len(limits) != 1:
        raise ValueError("motor MPC is SISO: exactly one voltage limit")
    if tracking_weight < 0.0 or move_weight < 0.0 or terminal_weight < 0.0:
        raise ValueError("weights must be non-negative")
    if i_meas is None:
        raise ValueError("i_meas is required for the motor model")
    lim = limits[0]
    sp = lim.setpoint_id
    u0 = float(current[sp])
    st = refresh_torque(model, state, y_meas, u0, i_meas, observer_gain)
    n = horizon_steps
    nu = control_horizon if control_horizon is not None else 1
    if nu < 1:
        raise ValueError("control_horizon must be at least 1")
    pm = model.prediction_matrices(n)
    hold = blocking_matrix(n, nu)
    nu = hold.shape[1]

    if y_ref_traj is None:
        ref = np.full(n, float(y_ref))
    else:
        if len(y_ref_traj) < n:
            raise ValueError("y_ref_traj must cover horizon_steps")
        ref = np.asarray(y_ref_traj[:n], dtype=np.float64)

    x0 = np.array([i_meas, y_meas * RAD_S_PER_RPM])
    ones = np.ones(n)
    # Free response (zero move) including both disturbance estimates; the voltage
    # estimate acts like a constant offset on the input.
    free_w = pm.phi_w @ x0 + pm.psi_w * st.d_hat + (pm.gamma_w @ ones) * st.d_v
    free_i = pm.phi_i @ x0 + pm.psi_i * st.d_hat + (pm.gamma_i @ ones) * st.d_v
    Gw = pm.gamma_w @ hold  # (N, nu)
    Gi = pm.gamma_i @ hold

    lo0 = max(lim.low, u0 - lim.max_step)
    hi0 = min(lim.high, u0 + lim.max_step)
    if lo0 > hi0:
        raise ValueError("no feasible setting within one step of the current setting")
    bounds = [(lim.low, lim.high)] * nu
    bounds[0] = (lo0, hi0)

    # Move vector D v - d_off, with D the first difference of the block values.
    D = np.eye(nu) - np.eye(nu, k=-1)
    d_off = np.zeros(nu)
    d_off[0] = u0
    e_err = free_w - ref  # tracking error at v = 0
    g_n = Gw[-1]

    # J(v) = q|e|^2 + qT e_N^2 + r|Dv - d_off|^2 = 0.5 v'Hv + g'v + c.
    # All three terms are multiplied by _OBJ_SCALE: RPM^2 errors make J ~ 1e8 next to
    # O(1-10) constraints, which stalls SLSQP's line search. The minimiser is unchanged.
    H = 2.0 * _OBJ_SCALE * (
        tracking_weight * Gw.T @ Gw
        + terminal_weight * np.outer(g_n, g_n)
        + move_weight * D.T @ D
    )
    g0 = 2.0 * _OBJ_SCALE * (
        tracking_weight * Gw.T @ e_err
        + terminal_weight * g_n * e_err[-1]
        - move_weight * D.T @ d_off
    )
    c0 = _OBJ_SCALE * (
        tracking_weight * float(e_err @ e_err)
        + terminal_weight * float(e_err[-1] ** 2)
        + move_weight * float(d_off @ d_off)
    )

    deadline = time.monotonic() + time_limit_s
    max_step = float(lim.max_step)

    def f(v: NDArray[np.float64]) -> float:
        if time.monotonic() > deadline:
            raise MpcTimedOut()
        return float(0.5 * v @ H @ v + g0 @ v + c0)

    def grad(v: NDArray[np.float64]) -> NDArray[np.float64]:
        return H @ v + g0

    # Linear inequalities A v <= b: voltage rate between moves, then (when given)
    # the predicted armature current |i_k| <= i_max.
    rows: list[NDArray[np.float64]] = []
    rhs: list[float] = []
    for j in range(1, nu):
        r = np.zeros(nu)
        r[j], r[j - 1] = 1.0, -1.0
        rows += [r, -r]
        rhs += [max_step, max_step]
    n_rate = len(rows)
    if i_max is not None:
        for k in range(n):
            rows += [Gi[k], -Gi[k]]
            rhs += [i_max - free_i[k], i_max + free_i[k]]
    A = np.array(rows) if rows else np.zeros((0, nu))
    b = np.array(rhs)

    def solve_with(n_rows: int, x_init: NDArray[np.float64]):
        cons = []
        if n_rows:
            Ac, bc = A[:n_rows], b[:n_rows]
            cons.append(
                {"type": "ineq", "fun": lambda v: bc - Ac @ v, "jac": lambda v: -Ac}
            )
        return minimize(
            f,
            x_init,
            jac=grad,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"maxiter": 80, "ftol": 1e-9},
        )

    x_init = np.full(nu, float(np.clip(u0, lo0, hi0)))
    res = solve_with(len(b), x_init)
    violation = float(np.max(A @ res.x - b)) if len(b) else 0.0
    scale = abs(i_max) if i_max else 1.0
    if (not res.success) or violation > 1e-3 * scale:
        # Current bound infeasible from this state: fall back to the rate-only
        # QP and let the drive's current protection act. Keeps the loop live.
        res = solve_with(n_rate, x_init)
    v_star = np.array(res.x, dtype=np.float64)
    u_star = float(np.clip(v_star[0], lo0, hi0))
    v_star[0] = u_star
    u_seq = hold @ v_star
    ys = free_w + Gw @ v_star
    iis = free_i + Gi @ v_star

    active: list[str] = []
    if np.isclose(u_star, lim.low) or np.isclose(u_star, lim.high):
        active.append(f"{sp}.window")
    elif np.isclose(abs(u_star - u0), lim.max_step):
        active.append(f"{sp}.max_step")
    if i_max is not None and float(np.max(np.abs(iis))) >= i_max * 0.995:
        active.append("current.limit")

    return MpcResult(
        best={sp: u_star},
        y_ref=float(y_ref),
        d_hat=st.d_hat,
        predicted_y=[float(v) for v in ys],
        active_constraints=active,
        state=MpcState(
            d_hat=st.d_hat, last_y=y_meas, last_u=u_star, last_i=i_meas, d_v=st.d_v
        ),
        planned_u=[float(v) for v in u_seq],
        predicted_i=[float(v) for v in iis],
        d_v_hat=st.d_v,
    )

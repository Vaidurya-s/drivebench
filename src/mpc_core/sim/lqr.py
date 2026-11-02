"""Integral-augmented LQR (LQI) speed controller for the PMDC motor.

Design model (nominal motor, SI units, speed in rad/s)::

    x = [i_a, omega],  xi' = omega - r
    x_aug = [i_a, omega, xi]

The plant part is discretised exactly (zero-order hold) at the controller
period ``Ts``; the integrator is the same forward-Euler update the controller
executes, ``xi[k+1] = xi[k] + Ts (omega[k] - r[k])``. The Riccati design
therefore certifies the loop that actually runs at the controller sample time.

Control law (tracking form)::

    u = u_ff(r) - Kx (x - x_eq(r)) - K_xi xi

``x_eq(r)`` and ``u_ff(r)`` are the zero-load equilibrium at reference ``r``
(``ff_enabled=False`` gives exactly ``u = -K x_aug``). A constant load torque
is rejected by the integrator; there is no disturbance estimator.

The physical drive (saturation, slew, current protection) stays outside this
module. Nothing here imports Streamlit.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import expm, solve_discrete_are

from mpc_core.twin.pmdc import PMDCParams

WEIGHT_RANGE = (1e-4, 1e4)
T_REF_S = 0.5  # time scale used to normalise the integral state


class LqrDesignError(ValueError):
    """The LQR design is invalid, uncontrollable, unsolvable or unstable."""


@dataclass(frozen=True)
class LqrWeights:
    """Dimensionless weights on normalised states and voltage.

    Each state is divided by an engineering scale (I_max, omega_max,
    omega_max * T_REF_S) and the voltage by V_max, so 1.0 means "a full-scale
    excursion costs one unit".
    """

    q_current: float = 0.1
    q_speed: float = 300.0
    q_integral: float = 10000.0
    r_voltage: float = 1.0
    ff_enabled: bool = True
    t_track_s: float = 0.1  # anti-windup back-calculation time constant

    @staticmethod
    def recommended() -> "LqrWeights":
        return LqrWeights()

    def validate(self) -> None:
        lo, hi = WEIGHT_RANGE
        for name in ("q_current", "q_speed", "q_integral", "r_voltage"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                raise LqrDesignError(f"{name} must be a finite number, got {v!r}")
            if v < lo or v > hi:
                raise LqrDesignError(f"{name}={v} is outside the allowed range [{lo}, {hi}]")
        if not math.isfinite(self.t_track_s) or self.t_track_s <= 0:
            raise LqrDesignError("t_track_s must be positive")


@dataclass(frozen=True)
class LqrDesign:
    """Result of one gain calculation, with the diagnostics the UI shows."""

    ok: bool
    error: str | None
    weights: LqrWeights
    ts_s: float
    A: NDArray[np.float64]  # continuous 2x2
    B: NDArray[np.float64]  # continuous 2x1
    A_aug: NDArray[np.float64]  # continuous 3x3
    B_aug: NDArray[np.float64]
    Ad: NDArray[np.float64]  # discrete augmented 3x3
    Bd: NDArray[np.float64]
    Q: NDArray[np.float64]
    R: NDArray[np.float64]
    K: NDArray[np.float64]  # 1x3, physical units [V/A, V/(rad/s), V/rad]
    P: NDArray[np.float64]
    eigenvalues: NDArray[np.complex128]
    controllability_rank: int
    riccati_residual: float
    design_time_ms: float
    scales: dict[str, float] = field(default_factory=dict)
    xi_max: float = 0.0

    @property
    def stable(self) -> bool:
        return bool(np.all(np.abs(self.eigenvalues) < 1.0))


def continuous_models(motor: PMDCParams):
    """(A, B, C, A_aug, B_aug, B_ref) of the speed-regulation design model."""
    A = np.array(
        [[-motor.R_a / motor.L_a, -motor.K_e / motor.L_a], [motor.K_t / motor.J, -motor.B / motor.J]]
    )
    B = np.array([[1.0 / motor.L_a], [0.0]])
    C = np.array([[0.0, 1.0]])
    A_aug = np.zeros((3, 3))
    A_aug[:2, :2] = A
    A_aug[2, :2] = C
    B_aug = np.vstack([B, [[0.0]]])
    B_ref = np.array([[0.0], [0.0], [-1.0]])
    return A, B, C, A_aug, B_aug, B_ref


def _discretise(motor: PMDCParams, ts_s: float):
    A, B, C, _, _, _ = continuous_models(motor)
    M = np.zeros((3, 3))
    M[:2, :2] = A
    M[:2, 2:] = B
    Md = expm(M * ts_s)
    Ad2, Bd2 = Md[:2, :2], Md[:2, 2:]
    Ad = np.zeros((3, 3))
    Ad[:2, :2] = Ad2
    Ad[2, :2] = ts_s * C[0]
    Ad[2, 2] = 1.0
    Bd = np.vstack([Bd2, [[0.0]]])
    return Ad, Bd


def _scales(motor: PMDCParams) -> dict[str, float]:
    return {
        "i": motor.I_max,
        "omega": motor.omega_max,
        "xi": motor.omega_max * T_REF_S,
        "v": motor.V_max,
    }


def design_lqr(motor: PMDCParams, ts_s: float, weights: LqrWeights | None = None) -> LqrDesign:
    """Compute the LQI gain; raise ``LqrDesignError`` if it is not valid."""
    return _design_cached(motor, float(ts_s), weights or LqrWeights.recommended())


@lru_cache(maxsize=128)
def _design_cached(motor: PMDCParams, ts_s: float, weights: LqrWeights) -> LqrDesign:
    t0 = time.perf_counter()
    weights.validate()
    if not math.isfinite(ts_s) or ts_s <= 0:
        raise LqrDesignError("controller period must be positive")

    A, B, _, A_aug, B_aug, _ = continuous_models(motor)
    Ad, Bd = _discretise(motor, ts_s)
    s = _scales(motor)
    Q = np.diag(
        [weights.q_current / s["i"] ** 2, weights.q_speed / s["omega"] ** 2, weights.q_integral / s["xi"] ** 2]
    )
    R = np.array([[weights.r_voltage / s["v"] ** 2]])

    ctrb = np.hstack([Bd, Ad @ Bd, Ad @ Ad @ Bd])
    rank = int(np.linalg.matrix_rank(ctrb))
    if rank < 3:
        raise LqrDesignError(f"augmented system is not controllable (rank {rank} of 3)")

    try:
        P = solve_discrete_are(Ad, Bd, Q, R)
        K = np.linalg.solve(R + Bd.T @ P @ Bd, Bd.T @ P @ Ad)
    except (np.linalg.LinAlgError, ValueError) as exc:
        raise LqrDesignError(f"Riccati equation could not be solved: {exc}") from exc
    if not (np.all(np.isfinite(P)) and np.all(np.isfinite(K))):
        raise LqrDesignError("Riccati solution is not finite")

    eig = np.linalg.eigvals(Ad - Bd @ K)
    if np.any(np.abs(eig) >= 1.0):
        raise LqrDesignError(f"closed loop is not stable (max |lambda| = {np.abs(eig).max():.4f})")

    residual = float(
        np.linalg.norm(Ad.T @ P @ Ad - P - Ad.T @ P @ Bd @ K + Q) / max(1.0, np.linalg.norm(P))
    )
    k_xi = float(K[0, 2])
    xi_max = motor.V_max / abs(k_xi) if abs(k_xi) > 0 else float("inf")
    return LqrDesign(
        ok=True,
        error=None,
        weights=weights,
        ts_s=ts_s,
        A=A,
        B=B,
        A_aug=A_aug,
        B_aug=B_aug,
        Ad=Ad,
        Bd=Bd,
        Q=Q,
        R=R,
        K=K,
        P=P,
        eigenvalues=eig,
        controllability_rank=rank,
        riccati_residual=residual,
        design_time_ms=(time.perf_counter() - t0) * 1e3,
        scales=s,
        xi_max=xi_max,
    )


def try_design_lqr(motor: PMDCParams, ts_s: float, weights: LqrWeights | None = None):
    """Return ``(design, None)`` or ``(None, message)``; never raises on bad design."""
    try:
        return design_lqr(motor, ts_s, weights), None
    except (LqrDesignError, TypeError) as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Online controller
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LqrState:
    xi: float = 0.0  # integral of (omega - r) [rad]
    last_raw: float = 0.0  # unclipped command issued last sample [V]
    started: bool = False

    def reset(self) -> "LqrState":
        return LqrState()


def lqr_step(
    *,
    design: LqrDesign,
    motor: PMDCParams,
    i_meas: float,
    omega_meas: float,
    omega_ref: float,
    u_prev: float,
    state: LqrState,
    u_min: float,
    u_max: float,
) -> tuple[float, LqrState, float]:
    """One LQI update (rad/s, A, V). ``u_prev`` is the voltage the drive applied.

    Returns ``(v_cmd, new_state, u_raw)``; ``v_cmd`` is ``u_raw`` clipped to
    ``[u_min, u_max]``.
    """
    Kx = design.K[0, :2]
    k_xi = float(design.K[0, 2])
    ts = design.ts_s
    w = design.weights

    if w.ff_enabled:
        i_eq = motor.B * omega_ref / motor.K_t
        u_ff = motor.R_a * i_eq + motor.K_e * omega_ref
    else:
        i_eq, u_ff = 0.0, 0.0
    x_dev_term = float(Kx[0] * (i_meas - i_eq) + Kx[1] * (omega_meas - (omega_ref if w.ff_enabled else 0.0)))

    xi = state.xi
    if not state.started:
        # Bumpless start: choose xi so the first raw command equals the applied voltage.
        xi = (u_ff - x_dev_term - u_prev) / k_xi if k_xi != 0 else 0.0
        last_raw = u_prev
    else:
        last_raw = state.last_raw
        # Back-calculation: move xi so -K_xi*xi shifts the command toward what was applied.
        # u = ... - k_xi*xi, so a wanted command change du needs dxi = -du / k_xi.
        xi += -(ts / w.t_track_s) * (u_prev - last_raw) / k_xi
    xi += ts * (omega_meas - omega_ref)
    xi = max(-design.xi_max, min(design.xi_max, xi))

    u_raw = u_ff - x_dev_term - k_xi * xi
    v_cmd = max(u_min, min(u_max, u_raw))
    return v_cmd, LqrState(xi=xi, last_raw=u_raw, started=True), u_raw

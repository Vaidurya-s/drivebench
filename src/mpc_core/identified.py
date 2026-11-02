"""MPC prediction models.

``IdentifiedLinearModel`` is the original SISO first-order record (kept for the
generic MPC tests). ``MotorStateSpaceModel`` is the PMDC motor model the lab
uses: a 2-state [i_a, omega] ZOH discretisation of the nominal motor.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import expm

from mpc_core.twin.pmdc import RAD_S_PER_RPM, PMDCParams


@dataclass(frozen=True)
class IdentifiedLinearModel:
    """SISO discrete model y[k+1] = a*y[k] + b*u[k]."""

    fit_id: str
    a: float
    b: float
    dt_s: float
    n_samples: int
    residual_rms: float
    experiment: str

    def __post_init__(self) -> None:
        if not self.fit_id:
            raise ValueError("fit_id is required")
        if self.dt_s <= 0:
            raise ValueError("dt_s must be positive")
        if self.n_samples < 3:
            raise ValueError("n_samples must be at least 3")
        if self.b == 0.0:
            raise ValueError("b must be non-zero (no input effect)")


@dataclass(frozen=True)
class MotorStateSpaceModel:
    """Controller prediction model of the PMDC motor: x = [i_a, omega].

    Zero-order-hold discretisation at ``ts_s`` of

        x+ = Ad x + Bd V_a + Ed T_L

    built from the *nominal* motor parameters. Load torque is the disturbance
    the offset-free observer estimates. This is the MPC's model, not the
    plant: model-mismatch runs simulate a different ``PMDCParams``.
    """

    params: PMDCParams
    ts_s: float

    def __post_init__(self) -> None:
        if self.ts_s <= 0:
            raise ValueError("ts_s must be positive")

    @cached_property
    def _discrete(self) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        p = self.params
        A = np.array([[-p.R_a / p.L_a, -p.K_e / p.L_a], [p.K_t / p.J, -p.B / p.J]])
        Bc = np.array([1.0 / p.L_a, 0.0])
        Ec = np.array([0.0, -1.0 / p.J])
        M = np.zeros((4, 4))
        M[:2, :2] = A
        M[:2, 2] = Bc
        M[:2, 3] = Ec
        ex = expm(M * self.ts_s)
        return ex[:2, :2], ex[:2, 2], ex[:2, 3]

    @property
    def Ad(self) -> NDArray[np.float64]:
        return self._discrete[0]

    @property
    def Bd(self) -> NDArray[np.float64]:
        return self._discrete[1]

    @property
    def Ed(self) -> NDArray[np.float64]:
        return self._discrete[2]

    def prediction_matrices(self, horizon_steps: int) -> "PredictionMatrices":
        """Condensed prediction over ``horizon_steps`` samples (cached per model)."""
        key = (self.params, self.ts_s, horizon_steps)
        cached = _PREDICTION_CACHE.get(key)
        if cached is None:
            cached = _build_prediction(self, horizon_steps)
            _PREDICTION_CACHE[key] = cached
        return cached


@dataclass(frozen=True)
class PredictionMatrices:
    """x_k = phi x0 + gamma u + psi d for k = 1..N; speed in RPM, current in A."""

    phi_w: NDArray[np.float64]  # (N, 2)
    gamma_w: NDArray[np.float64]  # (N, N)
    psi_w: NDArray[np.float64]  # (N,)
    phi_i: NDArray[np.float64]
    gamma_i: NDArray[np.float64]
    psi_i: NDArray[np.float64]


_PREDICTION_CACHE: dict[tuple[PMDCParams, float, int], PredictionMatrices] = {}


def _build_prediction(model: MotorStateSpaceModel, n: int) -> PredictionMatrices:
    Ad, Bd, Ed = model.Ad, model.Bd, model.Ed
    to_rpm = 1.0 / RAD_S_PER_RPM
    phi = np.zeros((n, 2, 2))
    psi = np.zeros((n, 2))
    gamma = np.zeros((n, n, 2))
    powers = [np.eye(2)]
    for _ in range(n):
        powers.append(Ad @ powers[-1])
    acc = np.zeros(2)
    for k in range(n):
        phi[k] = powers[k + 1]
        acc = acc + powers[k] @ Ed
        psi[k] = acc
        for j in range(k + 1):
            gamma[k, j] = powers[k - j] @ Bd
    return PredictionMatrices(
        phi_w=phi[:, 1, :] * to_rpm,
        gamma_w=gamma[:, :, 1] * to_rpm,
        psi_w=psi[:, 1] * to_rpm,
        phi_i=phi[:, 0, :],
        gamma_i=gamma[:, :, 0],
        psi_i=psi[:, 0],
    )

"""Permanent-magnet brushed DC motor twin (industrial speed-drive plant).

Coupled electrical and mechanical dynamics, SI units throughout:

    L_a * di/dt     = V_a - R_a * i - K_e * omega
    J   * domega/dt = K_t * i - B * omega - T_L
    dtheta/dt       = omega

State x = [i_a, omega, theta], input u = V_a, disturbance d = T_L.
This module is the single home of the motor parameters. Controllers, the
drive and the UI read them from ``PMDCParams``; nothing else hardcodes a
motor number. The CasADi step (``pmdc_step_function``) and the scalar RK4
(``step_pmdc``) implement the same fixed-step RK4 scheme and are tested for
parity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

RAD_S_PER_RPM = 2.0 * math.pi / 60.0

PMDC_PARAM_NAMES: tuple[str, ...] = ("R_a", "L_a", "K_t", "K_e", "J", "B")


def rpm_to_rad_s(rpm: float) -> float:
    """Convert shaft speed from RPM to rad/s."""
    return rpm * RAD_S_PER_RPM


def rad_s_to_rpm(omega: float) -> float:
    """Convert shaft speed from rad/s to RPM."""
    return omega / RAD_S_PER_RPM


class InvalidMotorParameter(ValueError):
    """Raised when a motor parameter is outside its physical range."""


# (low, high) inclusive physical ranges used for validation and UI sliders.
PARAM_RANGES: dict[str, tuple[float, float]] = {
    "V_rated": (1.0, 600.0),
    "R_a": (0.05, 50.0),
    "L_a": (1e-4, 1.0),
    "K_t": (1e-3, 5.0),
    "K_e": (1e-3, 5.0),
    "J": (1e-5, 10.0),
    "B": (0.0, 1.0),
    "T_L": (-50.0, 50.0),
    "V_max": (1.0, 600.0),
    "I_max": (0.1, 500.0),
    "omega_max_rpm": (100.0, 20000.0),
}


@dataclass(frozen=True)
class PMDCParams:
    """Physical and rating parameters of one PMDC motor drive (SI units).

    Defaults are the proposed simulation baseline, not a commercial motor.
    """

    V_rated: float = 24.0  # V
    R_a: float = 1.0  # Ohm
    L_a: float = 0.010  # H
    K_t: float = 0.050  # N m / A
    K_e: float = 0.050  # V / (rad/s)
    J: float = 0.002  # kg m^2
    B: float = 0.001  # N m / (rad/s)
    T_L: float = 0.050  # N m, nominal load torque
    V_max: float = 24.0  # V, maximum drive voltage
    I_max: float = 8.0  # A, maximum armature current
    omega_max_rpm: float = 3000.0  # RPM

    def __post_init__(self) -> None:
        for name, (lo, hi) in PARAM_RANGES.items():
            v = getattr(self, name)
            if not math.isfinite(v) or v < lo or v > hi:
                raise InvalidMotorParameter(
                    f"{name}={v} is outside the physical range [{lo}, {hi}]"
                )

    # -- derived quantities -------------------------------------------------
    @property
    def omega_max(self) -> float:
        """Maximum operating speed [rad/s]."""
        return rpm_to_rad_s(self.omega_max_rpm)

    @property
    def tau_e(self) -> float:
        """Electrical time constant L_a / R_a [s]."""
        return self.L_a / self.R_a

    def scaled(
        self,
        *,
        R: float = 1.0,
        L: float = 1.0,
        J: float = 1.0,
        B: float = 1.0,
    ) -> "PMDCParams":
        """Return a copy with R_a, L_a, J and B multiplied (mismatch studies)."""
        return replace(
            self,
            R_a=self.R_a * R,
            L_a=self.L_a * L,
            J=self.J * J,
            B=self.B * B,
        )

    def as_vector(self) -> list[float]:
        """Parameter vector in ``PMDC_PARAM_NAMES`` order (CasADi interface)."""
        return [self.R_a, self.L_a, self.K_t, self.K_e, self.J, self.B]

    # -- linear model -------------------------------------------------------
    def state_matrices(
        self,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        """Continuous (A, B, E) for xdot = A x + B V_a + E T_L, x=[i, w, theta]."""
        A = np.array(
            [
                [-self.R_a / self.L_a, -self.K_e / self.L_a, 0.0],
                [self.K_t / self.J, -self.B / self.J, 0.0],
                [0.0, 1.0, 0.0],
            ]
        )
        Bm = np.array([[1.0 / self.L_a], [0.0], [0.0]])
        E = np.array([[0.0], [-1.0 / self.J], [0.0]])
        return A, Bm, E

    def transfer_function(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """omega/V_a as (numerator, denominator) polynomial coefficients in s.

        K_t / (L J s^2 + (L B + R J) s + (R B + K_e K_t))
        """
        num = np.array([self.K_t])
        den = np.array(
            [
                self.L_a * self.J,
                self.L_a * self.B + self.R_a * self.J,
                self.R_a * self.B + self.K_e * self.K_t,
            ]
        )
        return num, den

    def dc_gain(self) -> float:
        """Steady-state d(omega)/d(V_a) [rad/s per V]."""
        num, den = self.transfer_function()
        return float(num[0] / den[-1])

    def equilibrium(self, *, omega: float, T_L: float | None = None) -> tuple[float, float]:
        """Steady (i_a, V_a) holding ``omega`` [rad/s] against load ``T_L``.

        K_t * i = B * omega + T_L and V_a = R_a * i + K_e * omega.
        """
        load = self.T_L if T_L is None else T_L
        i = (self.B * omega + load) / self.K_t
        return i, self.R_a * i + self.K_e * omega

    def equilibrium_from_voltage(self, V_a: float, T_L: float | None = None) -> tuple[float, float]:
        """Steady (i_a, omega) for a constant applied voltage and load."""
        load = self.T_L if T_L is None else T_L
        den = self.R_a * self.B + self.K_e * self.K_t
        omega = (self.K_t * V_a - self.R_a * load) / den
        i = (self.B * omega + load) / self.K_t
        return i, omega

    # -- monitored outputs --------------------------------------------------
    def torque(self, i: float) -> float:
        """Electromagnetic torque K_t * i [N m]."""
        return self.K_t * i

    def back_emf(self, omega: float) -> float:
        """Back EMF K_e * omega [V]."""
        return self.K_e * omega


# ---------------------------------------------------------------------------
# Scalar RK4 (fast path used by the closed-loop simulator)
# ---------------------------------------------------------------------------
def _rhs(
    i: float, w: float, V: float, T_L: float, p: PMDCParams
) -> tuple[float, float, float]:
    return (
        (V - p.R_a * i - p.K_e * w) / p.L_a,
        (p.K_t * i - p.B * w - T_L) / p.J,
        w,
    )


def step_pmdc(
    x: tuple[float, float, float],
    V_a: float,
    T_L: float,
    dt_s: float,
    params: PMDCParams,
    *,
    substeps: int = 1,
) -> tuple[float, float, float]:
    """Advance (i, omega, theta) by ``dt_s`` with ``substeps`` RK4 sub-steps.

    V_a and T_L are held constant over the interval (zero-order hold).
    """
    if dt_s <= 0:
        raise ValueError("dt_s must be positive")
    if substeps < 1:
        raise ValueError("substeps must be at least 1")
    h = dt_s / substeps
    i, w, th = x
    for _ in range(substeps):
        k1 = _rhs(i, w, V_a, T_L, params)
        k2 = _rhs(i + 0.5 * h * k1[0], w + 0.5 * h * k1[1], V_a, T_L, params)
        k3 = _rhs(i + 0.5 * h * k2[0], w + 0.5 * h * k2[1], V_a, T_L, params)
        k4 = _rhs(i + h * k3[0], w + h * k3[1], V_a, T_L, params)
        i += h / 6.0 * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        w += h / 6.0 * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
        th += h / 6.0 * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2])
    return i, w, th


def pmdc_step_function():
    """CasADi Function: (x[3], V_a, T_L, dt_s, p[6]) -> x_next[3] (one RK4 step)."""
    import casadi as ca  # type: ignore[import-untyped]

    x = ca.SX.sym("x", 3)
    V = ca.SX.sym("V_a")
    TL = ca.SX.sym("T_L")
    dt = ca.SX.sym("dt_s")
    p = ca.SX.sym("p", len(PMDC_PARAM_NAMES))
    R, L, Kt, Ke, J, B = (p[k] for k in range(6))

    def f(s):
        return ca.vertcat(
            (V - R * s[0] - Ke * s[1]) / L,
            (Kt * s[0] - B * s[1] - TL) / J,
            s[1],
        )

    k1 = f(x)
    k2 = f(x + 0.5 * dt * k1)
    k3 = f(x + 0.5 * dt * k2)
    k4 = f(x + dt * k3)
    x_next = x + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
    return ca.Function(
        "pmdc_step",
        [x, V, TL, dt, p],
        [x_next],
        ["x", "V_a", "T_L", "dt_s", "p"],
        ["x_next"],
    )

"""PMDC motor truth model (the simulated plant, independent of any controller).

The plant integrates the coupled electrical and mechanical equations with
fixed-step RK4. Its parameters may differ from the controller's nominal
prediction model (model-mismatch experiments); the drive and controllers never
reach into it except through ``measure``.
"""

from __future__ import annotations

from dataclasses import dataclass

from mpc_core.twin.pmdc import PMDCParams, rad_s_to_rpm, step_pmdc


@dataclass(frozen=True)
class MotorState:
    """Plant state x = [i_a, omega, theta] plus the parameters that drive it."""

    i_a: float
    omega: float
    theta: float
    params: PMDCParams

    @property
    def speed_rpm(self) -> float:
        return rad_s_to_rpm(self.omega)

    @property
    def torque_nm(self) -> float:
        """Electromagnetic torque K_t * i_a [N m]."""
        return self.params.K_t * self.i_a

    @property
    def back_emf_v(self) -> float:
        return self.params.K_e * self.omega


def initial_state(
    params: PMDCParams,
    *,
    omega: float = 0.0,
    i_a: float | None = None,
    theta: float = 0.0,
    T_L: float | None = None,
) -> MotorState:
    """State at rest, or at the steady current that holds ``omega`` against ``T_L``."""
    if i_a is None:
        i_a = params.equilibrium(omega=omega, T_L=T_L)[0] if omega != 0.0 else 0.0
    return MotorState(i_a=i_a, omega=omega, theta=theta, params=params)


def step_plant(
    state: MotorState,
    V_a: float,
    T_L: float,
    dt_s: float,
    *,
    substeps: int = 1,
) -> MotorState:
    """Advance one controller interval with V_a and T_L held (zero-order hold)."""
    i, w, th = step_pmdc(
        (state.i_a, state.omega, state.theta),
        V_a,
        T_L,
        dt_s,
        state.params,
        substeps=substeps,
    )
    return MotorState(i_a=i, omega=w, theta=th, params=state.params)

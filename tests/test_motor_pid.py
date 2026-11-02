"""PID: derivative filter, anti-windup, sign handling."""

from __future__ import annotations

import pytest

from mpc_core.sim.drive import DriveConfig, MotorDrive
from mpc_core.sim.pid import PIDGains, PIDState, pid_step
from mpc_core.sim.plant import initial_state, step_plant
from mpc_core.twin.pmdc import PMDCParams

P = PMDCParams()
TS = 0.01


def _loop(gains: PIDGains, anti_windup: bool, ref_rpm: float, steps: int, cfg: DriveConfig):
    s = initial_state(P)
    drive = MotorDrive(cfg, P, TS)
    st = PIDState()
    out = []
    for _ in range(steps):
        v_cmd, st = pid_step(
            y=s.speed_rpm,
            y_ref=ref_rpm,
            u_prev=drive.v_applied,
            dt_s=TS,
            gains=gains,
            state=st,
            u_min=-cfg.V_max,
            u_max=cfg.V_max,
            anti_windup=anti_windup,
        )
        v, _ = drive.step(v_cmd, i_a=s.i_a, omega=s.omega)
        s = step_plant(s, v, P.T_L, TS, substeps=10)
        out.append(s.speed_rpm)
    return out


def test_proportional_sign_and_clipping() -> None:
    g = PIDGains(0.01, 0.0, 0.0)
    u, _ = pid_step(
        y=0.0, y_ref=1000.0, u_prev=0.0, dt_s=TS, gains=g, state=PIDState(),
        u_min=-24.0, u_max=24.0,
    )
    assert u == pytest.approx(10.0)
    u, _ = pid_step(
        y=0.0, y_ref=-5000.0, u_prev=0.0, dt_s=TS, gains=g, state=PIDState(),
        u_min=-24.0, u_max=24.0,
    )
    assert u == pytest.approx(-24.0)


def test_derivative_acts_on_measurement_and_is_filtered() -> None:
    g = PIDGains(0.0, 0.0, 0.01, tf_s=0.05)
    # Measurement jumps 100 RPM in one sample: the filtered derivative is attenuated.
    u, _ = pid_step(
        y=100.0, y_ref=100.0, u_prev=0.0, dt_s=TS, gains=g, state=PIDState(last_y=0.0),
        u_min=-24, u_max=24,
    )
    raw = 0.01 * 100.0 / TS
    assert -raw < u < 0.0  # opposes the rise, attenuated
    # A reference step alone causes no derivative kick.
    u0, _ = pid_step(
        y=0.0, y_ref=1000.0, u_prev=0.0, dt_s=TS, gains=g, state=PIDState(last_y=0.0),
        u_min=-24, u_max=24,
    )
    assert u0 == pytest.approx(0.0)


def test_anti_windup_reduces_overshoot() -> None:
    # A big step keeps the controller saturated, so the integrator can wind up.
    cfg = DriveConfig()
    g = PIDGains(0.02, 0.5, 0.0)
    with_aw = _loop(g, True, 2500.0, 600, cfg)
    without = _loop(g, False, 2500.0, 600, cfg)
    assert max(with_aw) - 2500.0 < max(without) - 2500.0


def test_integrator_state_stays_bounded_when_saturated() -> None:
    cfg = DriveConfig()
    drive = MotorDrive(cfg, P, TS)
    s = initial_state(P)
    st = PIDState()
    g = PIDGains(0.02, 0.5, 0.0)
    for _ in range(300):
        v_cmd, st = pid_step(
            y=s.speed_rpm, y_ref=3000.0, u_prev=drive.v_applied, dt_s=TS, gains=g,
            state=st, u_min=-24.0, u_max=24.0,
        )
        v, _ = drive.step(v_cmd, i_a=s.i_a, omega=s.omega)
        s = step_plant(s, v, P.T_L, TS, substeps=10)
    assert abs(st.integral) < 3 * cfg.V_max


def test_bumpless_start_holds_applied_voltage() -> None:
    # Loop starts at steady speed with 8.3 V applied: first output must not drop to 0 V.
    u, _ = pid_step(
        y=1000.0, y_ref=1000.0, u_prev=8.3, dt_s=TS, gains=PIDGains(0.02, 0.05, 0.0),
        state=PIDState(), u_min=-24.0, u_max=24.0,
    )
    assert u == pytest.approx(8.3, abs=1e-6)


def test_start_from_rest_keeps_proportional_kick() -> None:
    u, _ = pid_step(
        y=0.0, y_ref=1000.0, u_prev=0.0, dt_s=TS, gains=PIDGains(0.01, 0.0, 0.0),
        state=PIDState(), u_min=-24.0, u_max=24.0,
    )
    assert u == pytest.approx(10.0)

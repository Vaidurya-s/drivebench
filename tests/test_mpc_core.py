"""Offset-free MPC core tests. Thresholds and model coeffs are test-only."""

from __future__ import annotations

import pytest

from mpc_core import (
    IdentifiedLinearModel,
    MpcState,
    SetpointLimits,
    refresh_disturbance,
    solve,
)

# Test ARX: a=0.9, b=0.05 → steady-state gain b/(1-a) = 0.5. Not plant numbers.
FIT = IdentifiedLinearModel(
    fit_id="fit-test-1",
    a=0.9,
    b=0.05,
    dt_s=1.0,
    n_samples=200,
    residual_rms=1e-9,
    experiment="step",
)


def test_refresh_disturbance_steady_state_init() -> None:
    st = refresh_disturbance(FIT, MpcState(), y_meas=100.0, u_current=200.0)
    assert st.d_hat == pytest.approx(0.0)
    assert st.last_y == 100.0
    assert st.last_u == 200.0


def test_refresh_disturbance_innovation_update() -> None:
    st0 = MpcState(d_hat=0.0, last_y=100.0, last_u=200.0)
    # Model predicts y = 0.9*100 + 0.05*200 + 0 = 100. Measured 105 → d += 5.
    st = refresh_disturbance(FIT, st0, y_meas=105.0, u_current=200.0)
    assert st.d_hat == pytest.approx(5.0)
    assert st.last_y == 105.0
    assert st.last_u == 200.0


def test_solve_moves_toward_reference() -> None:
    lim = SetpointLimits("power_setpoint", "kW", 900.0, 1100.0, 50.0)
    r = solve(
        FIT,
        [lim],
        {"power_setpoint": 1000.0},
        y_meas=500.0,
        y_ref=510.0,
        horizon_steps=20,
        time_limit_s=2.0,
        state=MpcState(),
    )
    assert r.best["power_setpoint"] > 1000.0
    assert r.best["power_setpoint"] <= 1050.0
    assert len(r.predicted_y) == 20


def test_solve_respects_max_step() -> None:
    lim = SetpointLimits("power_setpoint", "kW", 0.0, 2000.0, 10.0)
    r = solve(
        FIT,
        [lim],
        {"power_setpoint": 1000.0},
        y_meas=500.0,
        y_ref=600.0,
        horizon_steps=20,
        time_limit_s=2.0,
        state=MpcState(),
    )
    assert abs(r.best["power_setpoint"] - 1000.0) <= 10.0 + 1e-9


def test_solve_rejects_bad_horizon() -> None:
    lim = SetpointLimits("power_setpoint", "kW", 900.0, 1100.0, 50.0)
    with pytest.raises(ValueError, match="horizon_steps"):
        solve(
            FIT,
            [lim],
            {"power_setpoint": 1000.0},
            y_meas=500.0,
            y_ref=510.0,
            horizon_steps=0,
            time_limit_s=2.0,
            state=MpcState(),
        )


def test_identified_rejects_zero_b() -> None:
    with pytest.raises(ValueError, match="non-zero"):
        IdentifiedLinearModel(
            fit_id="x",
            a=0.9,
            b=0.0,
            dt_s=1.0,
            n_samples=10,
            residual_rms=0.0,
            experiment="step",
        )


def test_refresh_disturbance_observer_gain() -> None:
    st0 = MpcState(d_hat=0.0, last_y=100.0, last_u=200.0)
    st = refresh_disturbance(
        FIT, st0, y_meas=105.0, u_current=200.0, observer_gain=0.5
    )
    assert st.d_hat == pytest.approx(2.5)


def test_solve_accepts_reference_preview() -> None:
    lim = SetpointLimits("power_setpoint", "kW", 900.0, 1100.0, 50.0)
    traj = [500.0] * 5 + [520.0] * 15
    r = solve(
        FIT,
        [lim],
        {"power_setpoint": 1000.0},
        y_meas=500.0,
        y_ref=500.0,
        horizon_steps=20,
        time_limit_s=2.0,
        state=MpcState(),
        y_ref_traj=traj,
        terminal_weight=10.0,
    )
    assert r.best["power_setpoint"] >= 1000.0
    assert r.planned_u is not None
    assert len(r.planned_u) == 20


def test_solve_control_horizon_respects_rate() -> None:
    lim = SetpointLimits("power_setpoint", "kW", 0.0, 2000.0, 10.0)
    r = solve(
        FIT,
        [lim],
        {"power_setpoint": 1000.0},
        y_meas=500.0,
        y_ref=600.0,
        horizon_steps=20,
        time_limit_s=2.0,
        state=MpcState(),
        control_horizon=3,
        move_weight=0.01,
    )
    assert abs(r.best["power_setpoint"] - 1000.0) <= 10.0 + 1e-9
    assert r.planned_u is not None
    assert len(r.planned_u) == 20


def test_default_demo_config_motor_defaults() -> None:
    from mpc_core.sim.config import default_demo_config

    cfg = default_demo_config()
    assert cfg.dt_s == pytest.approx(0.010)
    assert cfg.plant_dt_s == pytest.approx(0.001)
    assert cfg.substeps == 10
    assert cfg.horizon_steps * cfg.dt_s >= 0.5  # covers the mechanical time constant
    assert cfg.terminal_weight == 50.0
    assert cfg.limits.high == pytest.approx(cfg.motor.V_max)
    assert cfg.limits.max_step == pytest.approx(cfg.drive.slew_v_per_s * cfg.dt_s)

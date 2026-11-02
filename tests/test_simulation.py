"""Tests for closed-loop simulation helpers."""

from __future__ import annotations

import numpy as np
import pytest

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.scenarios import SCENARIOS
from mpc_core.sim.simulate import RunOptions, run_closed_loop


def test_run_closed_loop_mpc_and_pid_finite() -> None:
    scenario = SCENARIOS["motor_startup"]
    for kind in ("mpc", "pid"):
        r = run_closed_loop(scenario, kind)
        n = len(r.time_s)
        for arr in (r.speed_rpm, r.i_a, r.v_applied, r.torque_nm, r.load_nm):
            assert len(arr) == n
            assert np.all(np.isfinite(arr))


def test_startup_reaches_reference_and_steady_state_balance() -> None:
    cfg = default_demo_config()
    r = run_closed_loop(SCENARIOS["motor_startup"], "mpc", cfg=cfg)
    assert r.speed_rpm[-1] == pytest.approx(1000.0, abs=1.0)
    m = cfg.motor
    w = r.omega_rad_s[-1]
    # Equilibrium: V = R i + Ke w and Kt i = B w + T_L
    assert r.v_applied[-1] == pytest.approx(m.R_a * r.i_a[-1] + m.K_e * w, abs=0.05)
    assert m.K_t * r.i_a[-1] == pytest.approx(m.B * w + r.load_nm[-1], abs=2e-3)


@pytest.mark.parametrize("key", list(SCENARIOS))
def test_current_and_voltage_limits_hold_for_every_scenario(key: str) -> None:
    sc = SCENARIOS[key]
    cfg = default_demo_config()
    for kind in ("mpc", "pid"):
        r = run_closed_loop(sc, kind, cfg=cfg)
        assert np.all(np.isfinite(r.speed_rpm))
        assert np.max(np.abs(r.i_a)) <= r.i_max * 1.02
        assert np.max(np.abs(r.v_applied)) <= r.v_max + 1e-9


def test_voltage_saturation_scenario_saturates() -> None:
    r = run_closed_loop(SCENARIOS["voltage_saturation"], "pid")
    assert r.metrics.voltage_saturation_s > 0.0


def test_current_protection_scenario_activates_limit() -> None:
    for kind in ("mpc", "pid"):
        r = run_closed_loop(SCENARIOS["current_protection"], kind)
        assert r.metrics.current_limit_s > 0.0
        assert r.metrics.max_current_a <= r.i_max * 1.02


def test_load_step_mpc_rejects_better_than_hand_pid() -> None:
    mpc = run_closed_loop(SCENARIOS["load_step"], "mpc")
    pid = run_closed_loop(SCENARIOS["load_step"], "pid")
    assert mpc.metrics.iae < pid.metrics.iae
    assert abs(mpc.metrics.steady_state_error_rpm) < 1.0
    assert mpc.d_hat is not None
    assert mpc.d_hat[-1] == pytest.approx(0.10, abs=0.01)  # estimated load torque


def test_reverse_operation_reverses_direction() -> None:
    r = run_closed_loop(SCENARIOS["reverse_operation"], "mpc")
    assert r.speed_rpm.min() < -900.0


def test_plant_scale_changes_plant_not_controller() -> None:
    sc = SCENARIOS["load_step"]
    base = run_closed_loop(sc, "pid")
    mism = run_closed_loop(sc, "pid", options=RunOptions(plant_scale=(1.2, 1.0, 1.3, 1.25)))
    assert not np.allclose(base.speed_rpm, mism.speed_rpm)


def test_mpc_preview_path_runs() -> None:
    cfg = default_demo_config()
    r = run_closed_loop(
        SCENARIOS["speed_tracking"],
        "mpc",
        cfg=cfg,
        mpc_preview=True,
        mpc_terminal_weight=cfg.terminal_weight,
    )
    assert r.metrics.iae > 0.0
    assert r.metrics.constraint_violation_steps == 0

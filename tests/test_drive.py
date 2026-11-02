"""Motor drive: saturation, slew, current protection, enable/e-stop."""

from __future__ import annotations

import pytest

from mpc_core.sim.drive import DriveConfig, MotorDrive
from mpc_core.sim.plant import initial_state, step_plant
from mpc_core.twin.pmdc import PMDCParams

P = PMDCParams()
TS = 0.01


def make(**kw) -> MotorDrive:
    return MotorDrive(DriveConfig(**kw), P, TS)


def test_voltage_saturation_both_polarities() -> None:
    d = make(slew_v_per_s=1e6, current_protection=False)
    v, f = d.step(100.0, i_a=0.0, omega=0.0)
    assert v == pytest.approx(24.0) and f.v_saturated
    v, f = d.step(-100.0, i_a=0.0, omega=0.0)
    assert v == pytest.approx(-24.0) and f.v_saturated


def test_bus_sag_scales_limit() -> None:
    d = make(slew_v_per_s=1e6, current_protection=False)
    v, _ = d.step(24.0, i_a=0.0, omega=0.0, bus_scale=0.8)
    assert v == pytest.approx(19.2)


def test_slew_limit_bounds_each_step() -> None:
    d = make(slew_v_per_s=500.0, current_protection=False)  # 5 V / sample
    prev = 0.0
    for _ in range(6):
        v, f = d.step(24.0, i_a=0.0, omega=0.0)
        assert abs(v - prev) <= 5.0 + 1e-12
        assert f.slew_limited or v == pytest.approx(24.0)
        prev = v
    assert prev == pytest.approx(24.0)


def test_estop_forces_zero_and_latches() -> None:
    d = make(slew_v_per_s=1e6)
    d.step(10.0, i_a=0.0, omega=0.0)
    d.emergency_stop()
    assert d.v_applied == 0.0
    v, f = d.step(20.0, i_a=0.0, omega=0.0)
    assert v == 0.0 and f.disabled
    with pytest.raises(RuntimeError):
        d.enable()
    d.reset()
    v, _ = d.step(5.0, i_a=0.0, omega=0.0)
    assert v == pytest.approx(5.0)


def test_disable_ramps_down_under_slew() -> None:
    d = make(slew_v_per_s=500.0, current_protection=False)
    d.reset(v_applied=12.0)
    d.disable()
    vs = [d.step(12.0, i_a=0.0, omega=0.0)[0] for _ in range(4)]
    assert vs == pytest.approx([7.0, 2.0, 0.0, 0.0])


def test_current_window_contains_steady_equilibrium() -> None:
    d = make()
    i, V = P.equilibrium(omega=200.0)
    lo, hi = d.current_window(i, 200.0)
    assert lo < V < hi


def test_locked_start_never_exceeds_current_limit() -> None:
    """Full-voltage command at standstill: protection holds |i| <= I_max."""
    d = make(slew_v_per_s=1e6)
    s = initial_state(P)
    peak = 0.0
    limited = 0
    for _ in range(300):
        v, f = d.step(24.0, i_a=s.i_a, omega=s.omega)
        limited += f.i_limited
        for _ in range(1):
            s = step_plant(s, v, P.T_L, TS, substeps=10)
        peak = max(peak, abs(s.i_a))
    assert peak <= P.I_max * 1.02
    assert limited > 0  # protection engaged at startup


def test_unprotected_startup_would_exceed_limit() -> None:
    d = make(slew_v_per_s=1e6, current_protection=False)
    s = initial_state(P)
    peak = 0.0
    for _ in range(50):
        v, _ = d.step(24.0, i_a=s.i_a, omega=s.omega)
        s = step_plant(s, v, P.T_L, TS, substeps=10)
        peak = max(peak, abs(s.i_a))
    assert peak > 2 * P.I_max


def test_reverse_current_protected_during_braking() -> None:
    d = make(slew_v_per_s=1e6)
    s = initial_state(P, omega=250.0, T_L=P.T_L)
    peak = 0.0
    for _ in range(300):
        v, _ = d.step(-24.0, i_a=s.i_a, omega=s.omega)
        s = step_plant(s, v, P.T_L, TS, substeps=10)
        peak = max(peak, abs(s.i_a))
    assert peak <= P.I_max * 1.02
    assert s.omega < 0.0  # actually reversed


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        DriveConfig(V_max=0.0)
    with pytest.raises(ValueError):
        MotorDrive(DriveConfig(), P, 0.0)

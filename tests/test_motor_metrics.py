"""Metric calculations on closed-form signals."""

from __future__ import annotations

import numpy as np
import pytest

from mpc_core.sim.metrics import compute_metrics

DT = 0.01


def _metrics(speed, ref, i=None, v=None, tq=None, load=None, vs=None, il=None, **kw):
    n = len(speed)
    t = np.arange(n) * DT
    z = np.zeros(n)
    omega = np.asarray(speed, float) * 2 * np.pi / 60
    return compute_metrics(
        time_s=t,
        speed_rpm=np.asarray(speed, float),
        ref_rpm=np.asarray(ref, float),
        i_a=z if i is None else i,
        v_applied=z if v is None else v,
        torque_nm=z if tq is None else tq,
        load_nm=z if load is None else load,
        omega_rad_s=omega,
        v_saturated=np.zeros(n, bool) if vs is None else vs,
        i_limited=np.zeros(n, bool) if il is None else il,
        i_max=8.0,
        v_max=24.0,
        b_friction=0.001,
        **kw,
    )


def test_error_integrals_for_constant_offset() -> None:
    n = 1000
    m = _metrics(np.full(n, 90.0), np.full(n, 100.0))
    T = n * DT
    assert m.iae == pytest.approx(10.0 * T, rel=1e-6)
    assert m.ise == pytest.approx(100.0 * T, rel=1e-6)
    assert m.itae == pytest.approx(10.0 * np.sum(np.arange(n) * DT) * DT, rel=1e-6)
    assert m.max_abs_error_rpm == pytest.approx(10.0)
    assert m.mean_abs_error_rpm == pytest.approx(10.0)
    assert m.steady_state_error_rpm == pytest.approx(10.0)


def test_rise_settling_overshoot_for_known_response() -> None:
    n = 1000
    t = np.arange(n) * DT
    ref = np.full(n, 1000.0)
    y = 1000.0 * (1.0 - np.exp(-t / 0.5))
    y[(t > 1.0) & (t < 1.2)] += 200.0  # a bump that crosses the reference
    m = _metrics(y, ref)
    peak = float(np.max(y))
    assert m.overshoot_pct == pytest.approx((peak - 1000.0) / 10.0, abs=0.01)
    assert m.rise_time_s is not None and 0.0 < m.rise_time_s < 1.3
    # After the bump the exponential re-enters the 2 % band at 0.5 ln(50) s.
    assert m.settling_time_s == pytest.approx(0.5 * np.log(50.0), abs=0.03)


def test_never_settles_returns_none() -> None:
    n = 500
    y = np.linspace(0.0, 500.0, n)
    m = _metrics(y, np.full(n, 1000.0))
    assert m.settling_time_s is None


def test_electrical_and_saturation_accounting() -> None:
    n = 200
    i = np.full(n, 4.0)
    v = np.full(n, 10.0)
    vs = np.zeros(n, bool)
    vs[:50] = True
    il = np.zeros(n, bool)
    il[:20] = True
    m = _metrics(np.zeros(n), np.zeros(n), i=i, v=v, vs=vs, il=il)
    assert m.max_current_a == 4.0 and m.rms_current_a == pytest.approx(4.0)
    assert m.mean_voltage_v == pytest.approx(10.0) and m.max_voltage_v == 10.0
    assert m.electrical_energy_j == pytest.approx(40.0 * n * DT)
    assert m.voltage_saturation_s == pytest.approx(0.5)
    assert m.current_limit_s == pytest.approx(0.2)


def test_efficiency_and_zero_input_safety() -> None:
    n = 100
    w_rpm = np.full(n, 1000.0)
    w = w_rpm * 2 * np.pi / 60
    i = np.full(n, 3.0944)  # steady: K_t i = B w + T_L
    v = np.full(n, 8.3)
    tq = 0.05 * i
    load = np.full(n, 0.05)
    m = _metrics(w_rpm, w_rpm, i=i, v=v, tq=tq, load=load, power_stage_efficiency=0.9)
    p_in = 8.3 * 3.0944
    shaft = tq[0] * w[0] - 0.001 * w[0] ** 2
    assert m.motor_efficiency == pytest.approx(shaft / p_in, rel=1e-6)
    assert m.drive_efficiency == pytest.approx(0.05 * w[0] / (p_in / 0.9), rel=1e-6)
    assert m.drive_efficiency < m.motor_efficiency  # the converter adds loss
    # Zero speed and zero input: no division by zero.
    z = _metrics(np.zeros(n), np.zeros(n))
    assert z.drive_efficiency is None and z.motor_efficiency is None


def test_speed_recovery_after_load_step() -> None:
    n = 1000
    t = np.arange(n) * DT
    ref = np.full(n, 1000.0)
    y = np.full(n, 1000.0)
    y[(t >= 5.0) & (t < 6.0)] = 900.0
    m = _metrics(y, ref, load_change_at_s=5.0)
    assert m.speed_recovery_time_s == pytest.approx(1.0, abs=0.02)

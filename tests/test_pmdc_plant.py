"""PMDC motor twin: state space, RK4, steady state, transfer function."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

from mpc_core.sim.plant import initial_state, step_plant
from mpc_core.twin import (
    InvalidMotorParameter,
    PMDCParams,
    generate_pmdc_step_c,
    pmdc_step_function,
    rad_s_to_rpm,
    rpm_to_rad_s,
    step_pmdc,
    write_pmdc_step_c,
)

P = PMDCParams()


def test_baseline_state_space_matches_spec() -> None:
    A, B, E = P.state_matrices()
    assert A == pytest.approx(np.array([[-100, -5, 0], [25, -0.5, 0], [0, 1, 0]]))
    assert B.ravel() == pytest.approx([100, 0, 0])
    assert E.ravel() == pytest.approx([0, -500, 0])
    assert P.tau_e == pytest.approx(0.01)


def test_rhs_matches_state_space() -> None:
    A, B, E = P.state_matrices()
    x = np.array([2.0, 50.0, 1.0])
    V, TL = 12.0, 0.07
    xdot = A @ x + B.ravel() * V + E.ravel() * TL
    # Direct differential equations.
    di = (V - P.R_a * x[0] - P.K_e * x[1]) / P.L_a
    dw = (P.K_t * x[0] - P.B * x[1] - TL) / P.J
    assert xdot == pytest.approx([di, dw, x[1]])


def test_rk4_matches_matrix_exponential_for_linear_system() -> None:
    A, B, E = P.state_matrices()
    x0 = np.array([1.0, 20.0, 0.0])
    V, TL, dt = 10.0, 0.05, 0.01
    # Exact ZOH step through an augmented matrix exponential.
    from scipy.linalg import expm

    M = np.zeros((5, 5))
    M[:3, :3] = A
    M[:3, 3] = B.ravel()
    M[:3, 4] = E.ravel()
    ex = expm(M * dt)
    exact = ex[:3, :3] @ x0 + ex[:3, 3] * V + ex[:3, 4] * TL
    got = step_pmdc(tuple(x0), V, TL, dt, P, substeps=10)
    assert np.array(got) == pytest.approx(exact, rel=1e-5, abs=1e-6)


def test_rk4_converges_fourth_order() -> None:
    x0 = (0.0, 0.0, 0.0)
    ref = np.array(step_pmdc(x0, 24.0, 0.05, 0.05, P, substeps=2000))
    errs = []
    for n in (5, 10, 20):
        got = np.array(step_pmdc(x0, 24.0, 0.05, 0.05, P, substeps=n))
        errs.append(np.linalg.norm(got - ref))
    assert errs[0] / errs[1] > 8.0 and errs[1] / errs[2] > 8.0


def test_one_ms_substeps_converged_vs_fine_reference() -> None:
    coarse = np.array(step_pmdc((0, 0, 0), 24.0, 0.05, 0.01, P, substeps=10))
    fine = np.array(step_pmdc((0, 0, 0), 24.0, 0.05, 0.01, P, substeps=200))
    assert coarse == pytest.approx(fine, rel=1e-5, abs=1e-7)


def test_casadi_matches_python_rk4() -> None:
    fn = pmdc_step_function()
    x = [1.5, 40.0, 0.3]
    got = np.array(fn(x, 9.0, 0.06, 0.001, P.as_vector())).ravel()
    ref = np.array(step_pmdc(tuple(x), 9.0, 0.06, 0.001, P))
    assert got == pytest.approx(ref, rel=1e-12, abs=1e-12)


def test_steady_state_equilibrium_equations() -> None:
    omega = rpm_to_rad_s(1000.0)
    i, V = P.equilibrium(omega=omega)
    assert V == pytest.approx(P.R_a * i + P.K_e * omega)
    assert P.K_t * i == pytest.approx(P.B * omega + P.T_L)
    # Holding that voltage keeps the plant there.
    s = initial_state(P, omega=omega, T_L=P.T_L)
    for _ in range(100):
        s = step_plant(s, V, P.T_L, 0.01, substeps=10)
    assert s.omega == pytest.approx(omega, rel=1e-9)
    assert s.i_a == pytest.approx(i, rel=1e-9)


def test_simulated_settles_to_equilibrium_from_rest() -> None:
    s = initial_state(P)
    for _ in range(1000):  # 10 s, many mechanical time constants
        s = step_plant(s, 12.0, P.T_L, 0.01, substeps=10)
    i_ss, w_ss = P.equilibrium_from_voltage(12.0)
    assert s.omega == pytest.approx(w_ss, rel=1e-4)
    assert s.i_a == pytest.approx(i_ss, rel=1e-4)
    # Torque balance: K_t i = B w + T_L
    assert s.torque_nm == pytest.approx(P.B * s.omega + P.T_L, rel=1e-3)


def test_startup_speed_rises_monotonically() -> None:
    s = initial_state(P)
    prev = 0.0
    for _ in range(300):
        s = step_plant(s, 6.0, 0.0, 0.01, substeps=10)
        assert s.omega >= prev - 1e-12
        prev = s.omega


def test_step_response_matches_transfer_function() -> None:
    V, dt = 5.0, 0.01
    num, den = P.transfer_function()
    t = np.arange(1, 201) * dt
    _, w_tf = signal.step(signal.TransferFunction(num * V, den), T=np.r_[0.0, t])
    s = initial_state(P)
    sim = []
    for _ in t:
        s = step_plant(s, V, 0.0, dt, substeps=10)  # no load: linear, T_L=0
        sim.append(s.omega)
    assert np.array(sim) == pytest.approx(w_tf[1:], rel=1e-4, abs=1e-4)


def test_dc_gain_and_poles() -> None:
    _, den = P.transfer_function()
    poles = np.roots(den)
    assert np.all(poles.real < 0)
    # mechanical pole ~ -1.75 /s, electrical ~ -98.7 /s
    assert sorted(poles.real) == pytest.approx([-98.7, -1.75], abs=0.1)
    assert P.dc_gain() == pytest.approx(0.05 / 0.0035)


def test_rpm_conversion_round_trip() -> None:
    assert rad_s_to_rpm(rpm_to_rad_s(1234.5)) == pytest.approx(1234.5)
    assert rpm_to_rad_s(60.0) == pytest.approx(2.0 * math.pi)


def test_scaled_changes_only_requested_parameters() -> None:
    q = P.scaled(R=1.2, J=0.7)
    assert q.R_a == pytest.approx(1.2) and q.J == pytest.approx(0.0014)
    assert q.L_a == P.L_a and q.B == P.B and q.K_t == P.K_t


def test_parameter_validation() -> None:
    with pytest.raises(InvalidMotorParameter):
        PMDCParams(R_a=-1.0)
    with pytest.raises(InvalidMotorParameter):
        PMDCParams(J=0.0)
    with pytest.raises(InvalidMotorParameter):
        PMDCParams(I_max=float("nan"))


def test_step_rejects_bad_dt() -> None:
    with pytest.raises(ValueError, match="dt_s"):
        step_pmdc((0, 0, 0), 1.0, 0.0, 0.0, P)


def test_write_pmdc_step_c_round_trip(tmp_path: Path) -> None:
    write_pmdc_step_c(tmp_path / "generated")
    assert (tmp_path / "generated" / "pmdc_step.c").read_text() == generate_pmdc_step_c()
    header = (tmp_path / "include" / "pmdc" / "pmdc_step.h").read_text()
    assert "PMDC_STEP_H" in header
    body = generate_pmdc_step_c()
    assert "pmdc_step(" in body
    # No invented plant constants in the C body (only formula + p[] reads).
    assert "0.05" not in body and "0.002" not in body

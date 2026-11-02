"""LQI design and controller tests (no Streamlit)."""

from __future__ import annotations

import numpy as np
import pytest

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.drive import MotorDrive
from mpc_core.sim.lqr import (
    LqrDesignError,
    LqrState,
    LqrWeights,
    continuous_models,
    design_lqr,
    lqr_step,
    try_design_lqr,
)
from mpc_core.sim.plant import initial_state, step_plant
from mpc_core.twin.pmdc import PMDCParams, rpm_to_rad_s

TS = 0.01


def _loop(ref_rpm, load, n=400, weights=None, plant_motor=None, start_rpm=0.0):
    cfg = default_demo_config()
    m = cfg.motor
    d = design_lqr(m, TS, weights)
    drive = MotorDrive(cfg.drive, m, TS)
    pl = initial_state(plant_motor or m)
    st, out = LqrState(), []
    for k in range(n):
        v, st, _ = lqr_step(
            design=d, motor=m, i_meas=pl.i_a, omega_meas=pl.omega,
            omega_ref=rpm_to_rad_s(ref_rpm), u_prev=drive.v_applied, state=st,
            u_min=-m.V_max, u_max=m.V_max,
        )
        va, fl = drive.step(v, i_a=pl.i_a, omega=pl.omega)
        pl = step_plant(pl, va, load(k * TS), TS, substeps=10)
        out.append((pl.speed_rpm, pl.i_a, va, fl))
    return d, out


def test_augmented_matrices_and_sign():
    m = PMDCParams()
    A, B, C, A_aug, B_aug, B_ref = continuous_models(m)
    assert np.allclose(A, [[-100, -5], [25, -0.5]])
    assert np.allclose(B.ravel(), [100, 0])
    assert np.allclose(A_aug[2], [0, 1, 0])
    assert np.allclose(B_ref.ravel(), [0, 0, -1])
    d = design_lqr(m, TS)
    assert d.K[0, 2] > 0  # xi = integral(omega - r): positive error lowers voltage


def test_zoh_poles_match_exact():
    m = PMDCParams()
    d = design_lqr(m, TS)
    lam = np.sort(np.linalg.eigvals(d.A))
    disc = np.sort(np.linalg.eigvals(d.Ad[:2, :2]))
    assert np.allclose(disc, np.sort(np.exp(lam * TS)), atol=1e-9)


def test_design_diagnostics():
    d = design_lqr(PMDCParams(), TS)
    assert d.controllability_rank == 3
    assert d.stable and d.riccati_residual < 1e-9
    assert d.design_time_ms >= 0


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf"), 1e9, 1e-9])
def test_invalid_weights_rejected(bad):
    with pytest.raises(LqrDesignError):
        design_lqr(PMDCParams(), TS, LqrWeights(q_speed=bad))
    design, err = try_design_lqr(PMDCParams(), TS, LqrWeights(r_voltage=bad))
    assert design is None and err


def test_gain_recalculation_changes_k():
    m = PMDCParams()
    k1 = design_lqr(m, TS, LqrWeights()).K
    k2 = design_lqr(m, TS, LqrWeights(r_voltage=100.0)).K
    assert not np.allclose(k1, k2)
    assert np.allclose(design_lqr(m, TS, LqrWeights()).K, k1)


def test_integral_tracking_zero_steady_state_error():
    _, out = _loop(1000.0, lambda t: 0.05, n=600)
    assert abs(out[-1][0] - 1000.0) < 1.0


def test_load_step_rejected():
    _, out = _loop(1000.0, lambda t: 0.05 if t < 3.0 else 0.10, n=700)
    assert abs(out[-1][0] - 1000.0) < 1.0


def test_current_protection_through_common_drive():
    _, out = _loop(2500.0, lambda t: 0.05, n=300)
    assert max(abs(o[1]) for o in out) <= 8.3
    assert any(o[3].i_limited for o in out)


def test_antiwindup_recovers_after_saturation():
    # Unreachable reference for 2 s (3000 RPM against heavy load), then a feasible one.
    cfg = default_demo_config()
    m = cfg.motor
    d = design_lqr(m, TS)
    drive = MotorDrive(cfg.drive, m, TS)
    pl, st = initial_state(m), LqrState()
    for k in range(500):
        ref = 5000.0 if k < 200 else 500.0
        v, st, _ = lqr_step(design=d, motor=m, i_meas=pl.i_a, omega_meas=pl.omega,
                            omega_ref=rpm_to_rad_s(ref), u_prev=drive.v_applied, state=st,
                            u_min=-24, u_max=24)
        va, _ = drive.step(v, i_a=pl.i_a, omega=pl.omega)
        pl = step_plant(pl, va, 0.05, TS, substeps=10)
        assert abs(st.xi) <= d.xi_max + 1e-9
    assert abs(pl.speed_rpm - 500.0) < 20.0


def test_bumpless_start_at_steady_speed():
    cfg = default_demo_config()
    m = cfg.motor
    d = design_lqr(m, TS)
    u_hold = m.equilibrium(omega=rpm_to_rad_s(1000.0))[1]
    i_eq = m.equilibrium(omega=rpm_to_rad_s(1000.0))[0]
    v, _, raw = lqr_step(design=d, motor=m, i_meas=i_eq, omega_meas=rpm_to_rad_s(1000.0),
                         omega_ref=rpm_to_rad_s(1000.0), u_prev=u_hold, state=LqrState(),
                         u_min=-24, u_max=24)
    assert abs(raw - u_hold) < 1e-9

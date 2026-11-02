"""Motor MPC: constraints, disturbance estimate, offset-free behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from mpc_core import MpcState, SetpointLimits, refresh_disturbance, solve
from mpc_core.identified import MotorStateSpaceModel
from mpc_core.mpc_motor import blocking_matrix
from mpc_core.sim.plant import initial_state, step_plant
from mpc_core.twin.pmdc import PMDCParams, rad_s_to_rpm

P = PMDCParams()
TS = 0.01
MODEL = MotorStateSpaceModel(P, TS)
LIM = SetpointLimits("voltage", "V", -24.0, 24.0, 12.0)


def _solve(y, ref, i, u_prev=0.0, state=None, i_max=8.0, **kw):
    kw.setdefault("control_horizon", 5)
    return solve(
        MODEL, [LIM], {"voltage": u_prev}, y, ref, 60, 2.0, state or MpcState(),
        kw.pop("tracking_weight", 1.0), i_meas=i, i_max=i_max, **kw,
    )


def test_discrete_model_matches_continuous_zoh() -> None:
    from scipy.linalg import expm

    A, _, _ = P.state_matrices()
    assert MODEL.Ad == pytest.approx(expm(A * TS)[:2, :2])
    assert MODEL.Bd[0] == pytest.approx(0.63082766, rel=1e-6)


def test_prediction_matrices_match_stepping_the_model() -> None:
    pm = MODEL.prediction_matrices(10)
    x = np.array([1.0, 30.0])
    u = np.linspace(2.0, 8.0, 10)
    d = 0.04
    xs = []
    xk = x.copy()
    for k in range(10):
        xk = MODEL.Ad @ xk + MODEL.Bd * u[k] + MODEL.Ed * d
        xs.append(xk.copy())
    xs = np.array(xs)
    assert pm.phi_w @ x + pm.gamma_w @ u + pm.psi_w * d == pytest.approx(
        rad_s_to_rpm(xs[:, 1])
    )
    assert pm.phi_i @ x + pm.gamma_i @ u + pm.psi_i * d == pytest.approx(xs[:, 0])


def test_blocking_matrix_partitions_horizon() -> None:
    m = blocking_matrix(60, 6)
    assert m.shape == (60, 6)
    assert np.all(m.sum(axis=1) == 1.0)
    assert m[:, 0].sum() == 1.0


def test_voltage_box_and_rate_respected() -> None:
    r = _solve(0.0, 3000.0, 0.0, u_prev=0.0)
    assert -24.0 <= r.best["voltage"] <= 24.0
    assert abs(r.best["voltage"]) <= 12.0 + 1e-9
    assert r.planned_u is not None
    assert max(abs(np.diff(r.planned_u))) <= 12.0 + 1e-6
    assert max(abs(v) for v in r.planned_u) <= 24.0 + 1e-6


def test_predicted_current_obeys_limit() -> None:
    r = _solve(0.0, 3000.0, 0.0)
    assert r.predicted_i is not None
    assert max(abs(i) for i in r.predicted_i) <= 8.0 + 1e-2


def test_without_current_limit_plan_exceeds_it() -> None:
    r = _solve(0.0, 3000.0, 0.0, i_max=None)
    assert max(abs(i) for i in r.predicted_i) > 8.0


def test_torque_observer_converges_to_load() -> None:
    # Constant voltage on the true plant with 0.08 N m; the model does not know.
    s = initial_state(P, omega=100.0, T_L=0.05)
    st = MpcState()
    v = P.equilibrium(omega=100.0, T_L=0.05)[1]
    for _ in range(300):
        st = refresh_disturbance(MODEL, st, s.speed_rpm, v, observer_gain=0.3, i_meas=s.i_a)
        s = step_plant(s, v, 0.08, TS, substeps=10)
    assert st.d_hat == pytest.approx(0.08, abs=5e-3)


def test_observer_requires_current_measurement() -> None:
    with pytest.raises(ValueError, match="i_meas"):
        refresh_disturbance(MODEL, MpcState(), 100.0, 5.0)


def test_closed_loop_offset_free_under_unmodelled_load() -> None:
    s = initial_state(P, omega=200.0, T_L=0.05)
    st = MpcState()
    v_prev = P.equilibrium(omega=200.0, T_L=0.05)[1]
    for _ in range(400):
        r = _solve(
            s.speed_rpm, rad_s_to_rpm(200.0), s.i_a, u_prev=v_prev, state=st,
            observer_gain=0.2, move_weight=100.0,
        )
        st, v_prev = r.state, r.best["voltage"]
        s = step_plant(s, v_prev, 0.12, TS, substeps=10)  # load 0.12 vs nominal 0.05
    assert s.speed_rpm == pytest.approx(rad_s_to_rpm(200.0), abs=0.5)


def test_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError):
        solve(MODEL, [LIM], {"voltage": 0.0}, 0.0, 100.0, 0, 1.0, MpcState(), i_meas=0.0)
    with pytest.raises(ValueError, match="i_meas"):
        solve(MODEL, [LIM], {"voltage": 0.0}, 0.0, 100.0, 10, 1.0, MpcState())
    with pytest.raises(ValueError, match="weights"):
        _solve(0.0, 100.0, 0.0, tracking_weight=-1.0)

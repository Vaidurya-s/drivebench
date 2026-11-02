"""All three controllers must face the same plant, drive and exogenous inputs."""

from __future__ import annotations

import numpy as np
import pytest

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.pid import PIDGains
from mpc_core.sim.scenarios import SCENARIOS
from mpc_core.sim.simulate import RunOptions, build_inputs, run_closed_loop


@pytest.mark.parametrize("key", ["sensor_noise", "variable_load", "voltage_saturation"])
def test_same_inputs_for_every_controller(key: str) -> None:
    sc = SCENARIOS[key]
    cfg = default_demo_config()
    a = run_closed_loop(sc, "mpc", cfg=cfg)
    b = run_closed_loop(sc, "pid", cfg=cfg)
    c = run_closed_loop(sc, "pid", cfg=cfg, pid_gains=PIDGains(0.03, 0.2, 0.0))
    for other in (b, c):
        assert np.array_equal(a.ref_rpm, other.ref_rpm)
        assert np.array_equal(a.load_nm, other.load_nm)
        assert a.i_max == other.i_max and a.v_max == other.v_max
        # Same noise realisation: measurement minus truth is identical per sample.
        assert np.allclose(
            a.speed_meas_rpm - a.speed_rpm, other.speed_meas_rpm - other.speed_rpm
        )


def test_identical_initial_conditions() -> None:
    sc = SCENARIOS["load_step"]
    runs = [run_closed_loop(sc, k) for k in ("mpc", "pid")]
    assert runs[0].speed_rpm[0] == pytest.approx(runs[1].speed_rpm[0])
    assert runs[0].i_a[0] == pytest.approx(runs[1].i_a[0])


def test_noise_is_reproducible_and_seed_dependent() -> None:
    sc = SCENARIOS["sensor_noise"]
    cfg = default_demo_config()
    a = build_inputs(sc, cfg, RunOptions())
    b = build_inputs(sc, cfg, RunOptions())
    c = build_inputs(sc, cfg, RunOptions(noise_seed=1))
    assert np.array_equal(a.noise, b.noise)
    assert not np.array_equal(a.noise, c.noise)
    assert np.std(a.noise) == pytest.approx(sc.noise_std_rpm, rel=0.1)


def test_mpc_uses_nominal_model_under_mismatch() -> None:
    cfg = default_demo_config()
    assert cfg.model.params == cfg.motor  # prediction model is nominal, always

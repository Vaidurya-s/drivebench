"""Four-controller execution: shared inputs, complete results, cache invalidation."""

from __future__ import annotations

import numpy as np
import pytest

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.playground import (
    PlaygroundParams,
    build_playground_scenario,
    run_bench,
    run_options_from_playground,
)
from mpc_core.sim.scenarios import SCENARIOS
from mpc_core.sim.simulate import CONTROLLER_IDS
from mpc_core.sim.ui_cache import params_cache_key


def test_controller_ids_order() -> None:
    assert CONTROLLER_IDS == ("pid", "optimized_pid", "lqr", "mpc")


@pytest.mark.parametrize("key", list(SCENARIOS))
def test_all_scenarios_run_for_all_controllers(key: str) -> None:
    runs = run_bench(SCENARIOS[key], cfg=default_demo_config())
    assert list(runs) == list(CONTROLLER_IDS)
    ref = runs["pid"]
    for cid, r in runs.items():
        assert r.controller_id == cid
        for arr in (r.speed_rpm, r.i_a, r.v_cmd, r.v_applied, r.torque_nm, r.exec_ms):
            assert arr is not None and np.all(np.isfinite(arr)) and len(arr) == len(ref.time_s)
        assert np.array_equal(r.ref_rpm, ref.ref_rpm)
        assert np.array_equal(r.load_nm, ref.load_nm)
        assert r.config
        assert np.all(np.abs(r.v_applied) <= r.v_max + 1e-9)


def test_requested_and_applied_voltage_are_separate() -> None:
    r = run_bench(SCENARIOS["voltage_saturation"], cfg=default_demo_config(), controllers=("lqr",))["lqr"]
    assert not np.array_equal(r.v_cmd, r.v_applied)


def test_lqr_weights_invalidate_only_lqr_key() -> None:
    a = PlaygroundParams()
    b = PlaygroundParams(lqr_r_voltage=10.0)
    assert params_cache_key(a) == params_cache_key(b)
    assert params_cache_key(a, "lqr") != params_cache_key(b, "lqr")


def test_changing_lqr_weights_changes_response() -> None:
    p = PlaygroundParams(duration_s=3.0, ref_step_at_s=1.0)
    q = PlaygroundParams(duration_s=3.0, ref_step_at_s=1.0, lqr_r_voltage=100.0)
    cfg = default_demo_config()
    ra = run_bench(build_playground_scenario(p), cfg=cfg, options=run_options_from_playground(p),
                   lqr_weights=p.lqr_weights, controllers=("lqr",))["lqr"]
    rb = run_bench(build_playground_scenario(q), cfg=cfg, options=run_options_from_playground(q),
                   lqr_weights=q.lqr_weights, controllers=("lqr",))["lqr"]
    assert not np.allclose(ra.v_cmd, rb.v_cmd)


def test_reproducible() -> None:
    sc = SCENARIOS["sensor_noise"]
    a = run_bench(sc, cfg=default_demo_config(), controllers=("lqr",))["lqr"]
    b = run_bench(sc, cfg=default_demo_config(), controllers=("lqr",))["lqr"]
    assert np.array_equal(a.speed_rpm, b.speed_rpm)

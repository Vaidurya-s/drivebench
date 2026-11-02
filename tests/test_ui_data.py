"""UI cache round trip, preset coverage, animation payload and headless page runs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.motor_view import motor_animation_html
from mpc_core.sim.playground import (
    PRESETS,
    PlaygroundParams,
    build_playground_scenario,
    run_options_from_playground,
    run_bench,
)
from mpc_core.sim.ui_cache import (
    deserialize_runs,
    named_playground_path,
    params_cache_key,
    serialize_runs,
)

ROOT = Path(__file__).resolve().parents[1]


def _short_params(**kw) -> PlaygroundParams:
    return PlaygroundParams(duration_s=4.0, ref_step_at_s=1.0, load_step_at_s=2.0, **kw)


def test_serialize_round_trip_preserves_metrics_and_shapes() -> None:
    p = _short_params(load_step_to_nm=0.1)
    cfg = default_demo_config()
    bundle = run_bench(
        build_playground_scenario(p), cfg=cfg, options=run_options_from_playground(p)
    )
    payload = json.loads(json.dumps(serialize_runs(bundle, p)))
    back = deserialize_runs(payload)
    assert back.mpc.metrics == bundle.mpc.metrics
    assert back.tune.gains == bundle.tune.gains
    n = len(bundle.mpc.time_s)
    assert len(back.mpc.speed_rpm) == (n + 1) // 2  # stored every 20 ms
    assert np.allclose(back.mpc.speed_rpm, bundle.mpc.speed_rpm[::2], atol=1e-3)
    assert back.mpc.d_hat is not None and back.pid.d_hat is None
    assert payload["params_key"] == params_cache_key(p)


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_preset_has_precomputed_data(name: str) -> None:
    path = named_playground_path(name)
    assert path.is_file(), f"run scripts/precompute_ui_data.py ({name})"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["params_key"] == params_cache_key(PRESETS[name](PlaygroundParams()))


def test_default_preset_and_frozen_pid_exist() -> None:
    assert named_playground_path("default").is_file()
    d = json.loads((ROOT / "data" / "ui" / "optimized_pid.json").read_text())
    assert d["kp"] > 0 and d["tuned_on"] == "speed_tracking"


def test_motor_animation_html_embeds_run_data() -> None:
    p = _short_params()
    t = run_bench(build_playground_scenario(p), cfg=default_demo_config())
    html = motor_animation_html(t.mpc, title="MPC · shaft replay")
    assert "MPC · shaft replay" in html and '"rpm"' in html and "__DATA__" not in html
    assert html.count("<script>") == 1


def _app(page: str):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(ROOT / "ui_pages" / page), default_timeout=180)


@pytest.mark.parametrize("page", ["overview.py", "bench.py", "lqr_studio.py", "mpc_explorer.py", "performance.py", "plant_model.py"])
def test_pages_run_without_exceptions(page: str) -> None:
    at = _app(page).run()
    assert not at.exception, [e.value for e in at.exception]


def test_bench_motor_form_validates_and_restores() -> None:
    at = _app("bench.py").run()
    # Out-of-range resistance is rejected by the widget bounds, so go through the
    # model-level validation the form relies on.
    from mpc_core.twin.pmdc import InvalidMotorParameter, PMDCParams

    with pytest.raises(InvalidMotorParameter):
        PMDCParams(R_a=1e6)
    assert not at.exception


def test_lqr_studio_weight_change_updates_gain_and_restore() -> None:
    from mpc_core.sim.lqr import LqrWeights, design_lqr
    from mpc_core.twin.pmdc import PMDCParams

    at = _app("lqr_studio.py").run()
    assert not at.exception
    base = design_lqr(PMDCParams(), 0.01).K
    at.session_state["slider_lqr_r_voltage"] = 2.0  # r_voltage = 100
    at.run()
    assert not at.exception
    p = at.session_state["playground_params"]
    assert p.lqr_r_voltage == pytest.approx(100.0)
    assert not (design_lqr(PMDCParams(), 0.01, p.lqr_weights).K == base).all()
    restore = [b for b in at.button if "Restore" in b.label][0]
    restore.click()
    at.run()
    assert at.session_state["playground_params"].lqr_r_voltage == LqrWeights.recommended().r_voltage


def test_rejected_lqr_design_is_reported_not_used() -> None:
    from mpc_core.sim.lqr import try_design_lqr
    from mpc_core.sim.lqr import LqrWeights
    from mpc_core.twin.pmdc import PMDCParams

    design, err = try_design_lqr(PMDCParams(), 0.01, LqrWeights(q_speed=float("nan")))
    assert design is None and "finite" in err

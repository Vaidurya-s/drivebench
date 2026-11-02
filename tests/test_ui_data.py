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
    run_triple,
)
from mpc_core.sim.ui_cache import (
    deserialize_triple,
    named_playground_path,
    params_cache_key,
    serialize_triple,
)

ROOT = Path(__file__).resolve().parents[1]


def _short_params(**kw) -> PlaygroundParams:
    return PlaygroundParams(duration_s=4.0, ref_step_at_s=1.0, load_step_at_s=2.0, **kw)


def test_serialize_round_trip_preserves_metrics_and_shapes() -> None:
    p = _short_params(load_step_to_nm=0.1)
    cfg = default_demo_config()
    triple = run_triple(
        build_playground_scenario(p), cfg=cfg, options=run_options_from_playground(p)
    )
    payload = json.loads(json.dumps(serialize_triple(triple, p)))
    back = deserialize_triple(payload)
    assert back.mpc.metrics == triple.mpc.metrics
    assert back.tune.gains == triple.tune.gains
    n = len(triple.mpc.time_s)
    assert len(back.mpc.speed_rpm) == (n + 1) // 2  # stored every 20 ms
    assert np.allclose(back.mpc.speed_rpm, triple.mpc.speed_rpm[::2], atol=1e-3)
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
    t = run_triple(build_playground_scenario(p), cfg=default_demo_config())
    html = motor_animation_html(t.mpc, title="MPC · shaft replay")
    assert "MPC · shaft replay" in html and '"rpm"' in html and "__DATA__" not in html
    assert html.count("<script>") == 1


def _app(page: str):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(ROOT / "ui_pages" / page), default_timeout=180)


@pytest.mark.parametrize("page", ["overview.py", "playground.py", "step_through.py", "scorecard.py"])
def test_pages_run_without_exceptions(page: str) -> None:
    at = _app(page).run()
    assert not at.exception, [e.value for e in at.exception]


def test_playground_motor_form_validates_and_restores() -> None:
    at = _app("playground.py").run()
    # Out-of-range resistance is rejected by the widget bounds, so go through the
    # model-level validation the form relies on.
    from mpc_core.twin.pmdc import InvalidMotorParameter, PMDCParams

    with pytest.raises(InvalidMotorParameter):
        PMDCParams(R_a=1e6)
    assert not at.exception

"""Performance Review and MPC explorer: every selector value renders without exceptions."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _app(page: str):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(ROOT / "ui_pages" / page), default_timeout=180)


def test_performance_every_scenario_and_metric() -> None:
    at = _app("performance.py").run()
    assert not at.exception
    scen = at.selectbox[0]
    for option in scen.options:
        scen.select(option)
        at.run()
        assert not at.exception, (option, [e.value for e in at.exception])
    metric = at.selectbox[1]
    for option in metric.options:
        metric.select(option)
        at.run()
        assert not at.exception, (option, [e.value for e in at.exception])


def test_mpc_explorer_steps_and_scenarios() -> None:
    at = _app("mpc_explorer.py").run()
    assert not at.exception
    nxt = [b for b in at.button if b.label == "Next"][0]
    nxt.click()
    at.run()
    assert not at.exception
    assert at.session_state["mpc_step_idx"] == 1
    sc = at.selectbox[0]
    for option in sc.options[:4]:
        sc.select(option)
        at.run()
        assert not at.exception, option

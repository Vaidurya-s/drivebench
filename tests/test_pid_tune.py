"""Tests for scipy PID gain tuning."""

from __future__ import annotations

from mpc_core.sim.pid import PIDGains
from mpc_core.sim.pid_tune import TuneWeights, tune_pid_gains, tuning_objective
from mpc_core.sim.scenarios import SCENARIOS
from mpc_core.sim.simulate import run_closed_loop


def test_tune_pid_returns_finite_gains() -> None:
    result = tune_pid_gains(SCENARIOS["motor_startup"], maxiter=5)
    assert result.gains.kp > 0
    assert result.metrics_iae >= 0
    assert result.violation_steps == 0


def test_tuning_does_not_worsen_objective() -> None:
    sc = SCENARIOS["motor_startup"]
    start = run_closed_loop(sc, "pid")
    before = tuning_objective(start, sc.duration_s, TuneWeights())
    result = tune_pid_gains(sc, maxiter=6)
    assert result.final_objective <= before + 1e-9


def test_objective_penalises_saturation_and_current_limit() -> None:
    sc = SCENARIOS["motor_startup"]
    run = run_closed_loop(sc, "pid")
    plain = tuning_objective(run, sc.duration_s, TuneWeights(v_saturation=0, i_limit=0))
    full = tuning_objective(run, sc.duration_s, TuneWeights(v_saturation=1, i_limit=1))
    assert full > plain  # startup is current limited


def test_tuned_pid_runs_in_closed_loop() -> None:
    sc = SCENARIOS["load_step"]
    tune = tune_pid_gains(sc, maxiter=4)
    run = run_closed_loop(sc, "pid", pid_gains=tune.gains, result_label="optimized_pid")
    assert run.controller == "optimized_pid"
    assert isinstance(tune.gains, PIDGains)

"""Batch runs of every scenario for the results folder and the report.

Both ``examples/run_simulations.py`` and ``scripts/rebuild_report_metrics.py``
use this module so they cannot drift apart. The optimised PID gains are the
frozen baseline (tuned once on speed tracking), the same ones the app uses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from mpc_core.sim.config import DemoConfig, default_demo_config
from mpc_core.sim.pid_tune import TuneResult
from mpc_core.sim.playground import TripleRun, baseline_optimized_pid, run_triple
from mpc_core.sim.scenarios import MISMATCH_CASES, SCENARIOS, ScenarioConfig
from mpc_core.sim.simulate import RunOptions


@dataclass(frozen=True)
class BatchItem:
    key: str
    title: str
    scenario: ScenarioConfig
    options: RunOptions | None = None


def batch_items() -> list[BatchItem]:
    """Every named scenario, plus the opposite mismatch corner for scenario 7."""
    items = [BatchItem(k, s.title, s) for k, s in SCENARIOS.items()]
    items.append(
        BatchItem(
            "model_mismatch_low",
            "Model mismatch (low R, J, B)",
            SCENARIOS["model_mismatch"],
            RunOptions(plant_scale=MISMATCH_CASES["low"]),
        )
    )
    return items


def run_batch(
    cfg: DemoConfig | None = None,
    *,
    on_result: Callable[[BatchItem, TripleRun], None] | None = None,
) -> tuple[dict[str, TripleRun], TuneResult]:
    """Run MPC, PID and frozen optimised PID on every batch item."""
    cfg = cfg or default_demo_config()
    tune = baseline_optimized_pid(cfg=cfg)
    out: dict[str, TripleRun] = {}
    for item in batch_items():
        triple = run_triple(item.scenario, cfg=cfg, options=item.options, optimized_gains=tune)
        out[item.key] = triple
        if on_result is not None:
            on_result(item, triple)
    return out, tune


def summary_dict(
    results: dict[str, TripleRun], tune: TuneResult, cfg: DemoConfig
) -> dict:
    """JSON-ready summary: configuration plus per-scenario metrics."""
    titles = {i.key: i.title for i in batch_items()}
    return {
        "motor": asdict(cfg.motor),
        "drive": asdict(cfg.drive),
        "timing": {"controller_sample_s": cfg.dt_s, "plant_step_s": cfg.plant_dt_s},
        "mpc": {
            "horizon_steps": cfg.horizon_steps,
            "control_horizon_moves": cfg.control_horizon,
            "tracking_weight": cfg.tracking_weight,
            "move_weight": cfg.move_weight,
            "terminal_weight": cfg.terminal_weight,
            "observer_gain": cfg.observer_gain,
            "solver": "SciPy SLSQP",
        },
        "optimized_pid_gains": {"kp": tune.gains.kp, "ki": tune.gains.ki, "kd": tune.gains.kd},
        "scenarios": {
            key: {
                "title": titles[key],
                "mpc": t.mpc.metrics.as_dict(),
                "pid": t.pid.metrics.as_dict(),
                "optimized_pid": t.optimized_pid.metrics.as_dict(),
            }
            for key, t in results.items()
        },
    }

"""Batch runs of every scenario for the results folder and the report.

Both ``examples/run_simulations.py`` and ``scripts/rebuild_report_metrics.py``
use this module so they cannot drift apart. The optimised PID gains are the
frozen baseline (tuned once on speed tracking), the same ones the app uses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from mpc_core.sim.config import DemoConfig, default_demo_config
from mpc_core.sim.lqr import LqrWeights, design_lqr
from mpc_core.sim.pid_tune import TuneResult
from mpc_core.sim.playground import ControllerRuns, baseline_optimized_pid, run_bench
from mpc_core.sim.scenarios import MISMATCH_CASES, SCENARIOS, ScenarioConfig
from mpc_core.sim.metrics import scorecard_row
from mpc_core.sim.simulate import CONTROLLER_IDS, RunOptions, SimulationResult


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
    on_result: Callable[[BatchItem, ControllerRuns], None] | None = None,
) -> tuple[dict[str, ControllerRuns], TuneResult]:
    """Run PID, frozen optimised PID, LQR and MPC on every batch item."""
    cfg = cfg or default_demo_config()
    tune = baseline_optimized_pid(cfg=cfg)
    out: dict[str, ControllerRuns] = {}
    for item in batch_items():
        triple = run_bench(item.scenario, cfg=cfg, options=item.options, optimized_gains=tune)
        out[item.key] = triple
        if on_result is not None:
            on_result(item, triple)
    return out, tune


def summary_dict(
    results: dict[str, ControllerRuns], tune: TuneResult, cfg: DemoConfig
) -> dict:
    """JSON-ready summary: configuration plus per-scenario metrics."""
    titles = {i.key: i.title for i in batch_items()}
    cfg_lqr = LqrWeights.recommended()
    lqr_design = design_lqr(cfg.motor, cfg.dt_s, cfg_lqr)
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
        "lqr": {
            "q_current": cfg_lqr.q_current, "q_speed": cfg_lqr.q_speed,
            "q_integral": cfg_lqr.q_integral, "r_voltage": cfg_lqr.r_voltage,
            "gain_K": [float(x) for x in lqr_design.K[0]],
            "closed_loop_eigenvalues_abs": [float(abs(x)) for x in lqr_design.eigenvalues],
        },
        "optimized_pid_gains": {"kp": tune.gains.kp, "ki": tune.gains.ki, "kd": tune.gains.kd},
        "scenarios": {
            key: {
                "title": titles[key],
                **{cid: t[cid].metrics.as_dict() for cid in CONTROLLER_IDS},
            }
            for key, t in results.items()
        },
    }


CONTROLLER_LABELS = {
    "pid": "PID",
    "optimized_pid": "Optimized PID",
    "lqr": "LQR",
    "mpc": "MPC",
}


def result_row(run: SimulationResult) -> dict[str, float | None]:
    """Scorecard row for one run: metrics plus controller execution time."""
    row = scorecard_row(run.metrics)
    ms = run.exec_ms
    row["Mean exec [ms]"] = None if ms is None or len(ms) == 0 else float(ms.mean())
    row["Max exec [ms]"] = None if ms is None or len(ms) == 0 else float(ms.max())
    return row

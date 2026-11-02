#!/usr/bin/env python3
"""Rebuild report metrics and simulation plots from the repo sim code.

Run from the repository root after ``pip install -e ".[dev]"``::

    python3 scripts/rebuild_report_metrics.py

Writes ``report/metrics_summary.json`` and the report figures (``scripts/report_figures.py``), and
syncs ``results/metrics_summary.json`` plus ``results/<scenario>.png``.
Numbers in the report come only from this script; never edit them by hand.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_figures  # noqa: E402
from mpc_core.sim.batch import BatchItem, run_batch, summary_dict
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.pid_tune import tune_pid_gains
from mpc_core.sim.playground import ControllerRuns
from mpc_core.sim.plotting import save_runs_figure
from mpc_core.sim.scenarios import MISMATCH_CASES, SCENARIOS
from mpc_core.sim.simulate import RunOptions, run_closed_loop

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report"
FIG = OUT / "figures"
RESULTS = ROOT / "results"
FIG.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)


def main() -> None:
    cfg = default_demo_config()
    t_start = time.perf_counter()

    def figures(item: BatchItem, t: ControllerRuns) -> None:
        # Per-scenario overview PNGs go to results/ (the report builds its own figures).
        save_runs_figure(title=item.title, runs=t.runs, path=RESULTS / f"{item.key}.png")
        print(
            f"{item.key}: IAE pid/opt/lqr/mpc = " + "/".join(f"{t[c].metrics.iae:.0f}" for c in t),
            flush=True,
        )

    results, tune = run_batch(cfg, on_result=figures)
    summary = summary_dict(results, tune, cfg)
    report_figures.build_all({k: dict(v.runs) for k, v in results.items()})

    # Robustness: gains frozen on the nominal motor vs gains retuned on the mismatched plant.
    print("=== robustness ===", flush=True)
    scenario = SCENARIOS["model_mismatch"]
    retuned = tune_pid_gains(scenario, cfg=cfg, maxiter=20)
    mm = run_closed_loop(
        scenario, "pid", cfg=cfg, pid_gains=tune.gains, result_label="optimized_pid_frozen"
    )
    oracle = run_closed_loop(
        scenario, "pid", cfg=cfg, pid_gains=retuned.gains,
        result_label="optimized_pid_retuned_on_mismatch",
    )
    summary["robustness_model_mismatch"] = {
        "mpc": results["model_mismatch"].mpc.metrics.as_dict(),
        "optimized_pid_frozen_nominal_gains": mm.metrics.as_dict(),
        "optimized_pid_retuned_on_mismatch": oracle.metrics.as_dict(),
        "retuned_gains": {"kp": retuned.gains.kp, "ki": retuned.gains.ki, "kd": retuned.gains.kd},
        "mismatch_cases": {k: list(v) for k, v in MISMATCH_CASES.items()},
        "note": (
            "Frozen gains were tuned on the nominal motor; the retuned gains saw the "
            "mismatched plant during tuning."
        ),
    }
    summary["runtime_s"] = time.perf_counter() - t_start

    text = json.dumps(summary, indent=2) + "\n"
    (OUT / "metrics_summary.json").write_text(text)
    (RESULTS / "metrics_summary.json").write_text(text)
    print("Wrote", OUT / "metrics_summary.json")
    print("Wrote", RESULTS / "metrics_summary.json")
    _ = RunOptions  # RunOptions kept importable for ad-hoc experiments


if __name__ == "__main__":
    main()

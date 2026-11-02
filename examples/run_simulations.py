#!/usr/bin/env python3
"""Batch PID vs optimised PID vs LQR vs MPC on all motor scenarios.

Writes one figure and one metrics table per scenario plus
``metrics_summary.json`` under ``results/``. Optimised PID uses the frozen
baseline gains (tuned once on speed tracking), as in the app.
"""

from __future__ import annotations

import json
from pathlib import Path

from mpc_core.sim.batch import BatchItem, run_batch, summary_dict
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.playground import ControllerRuns
from mpc_core.sim.plotting import save_runs_figure

ROWS = (
    ("IAE [RPM s]", "iae"),
    ("Rise time [s]", "rise_time_s"),
    ("Settling time [s]", "settling_time_s"),
    ("Overshoot [%]", "overshoot_pct"),
    ("Max current [A]", "max_current_a"),
    ("Current-limit active [s]", "current_limit_s"),
    ("Voltage saturation [s]", "voltage_saturation_s"),
    ("Electrical energy [J]", "electrical_energy_j"),
    ("Drive efficiency", "drive_efficiency"),
)


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.3g}"


def _table(t: ControllerRuns) -> str:
    lines = ["| Metric | PID | Opt. PID | LQR | MPC |", "| --- | --- | --- | --- | --- |"]
    for label, attr in ROWS:
        cells = [_fmt(getattr(r.metrics, attr)) for r in t.runs.values()]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = default_demo_config()

    def write(item: BatchItem, t: ControllerRuns) -> None:
        save_runs_figure(
            title=item.title, runs=t.runs, path=out_dir / f"{item.key}.png",
        )
        g = t.tune.gains
        (out_dir / f"{item.key}_metrics.md").write_text(
            f"# {item.title}\n\n{item.scenario.description}\n\n"
            f"Optimised PID gains (frozen): Kp={g.kp:.3g}, Ki={g.ki:.3g}, Kd={g.kd:.3g}\n\n"
            f"{_table(t)}\n",
            encoding="utf-8",
        )
        print(f"Wrote {item.key}", flush=True)

    results, tune = run_batch(cfg, on_result=write)
    (out_dir / "metrics_summary.json").write_text(
        json.dumps(summary_dict(results, tune, cfg), indent=2) + "\n", encoding="utf-8"
    )
    print(f"Done. Figures and metrics in {out_dir}")


if __name__ == "__main__":
    main()

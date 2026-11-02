"""Closed-loop simulations: PMDC motor plant, drive, PID baselines, MPC comparison.

Keep this module light: eager imports here race Streamlit multipage loading
(pandas/plotly partial-init). Submodules are loaded on attribute access.
"""

from __future__ import annotations

__all__ = [
    "SCENARIOS",
    "ScenarioConfig",
    "SimulationMetrics",
    "SimulationResult",
    "compute_metrics",
    "run_closed_loop",
]


def __getattr__(name: str):
    if name in ("SCENARIOS", "ScenarioConfig"):
        from mpc_core.sim.scenarios import SCENARIOS, ScenarioConfig

        return {"SCENARIOS": SCENARIOS, "ScenarioConfig": ScenarioConfig}[name]
    if name in ("SimulationMetrics", "compute_metrics"):
        from mpc_core.sim.metrics import SimulationMetrics, compute_metrics

        return {"SimulationMetrics": SimulationMetrics, "compute_metrics": compute_metrics}[
            name
        ]
    if name in ("SimulationResult", "run_closed_loop"):
        from mpc_core.sim.simulate import SimulationResult, run_closed_loop

        return {"SimulationResult": SimulationResult, "run_closed_loop": run_closed_loop}[
            name
        ]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

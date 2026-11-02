#!/usr/bin/env python3
"""Precompute Streamlit UI traces. Regen: python scripts/precompute_ui_data.py"""

from __future__ import annotations

from mpc_core.sim.config import default_demo_config
from mpc_core.sim.batch import CONTROLLER_LABELS, result_row
from mpc_core.sim.simulate import CONTROLLER_IDS
from mpc_core.sim.pid import PIDGains
from mpc_core.sim.playground import (
    PRESETS,
    PlaygroundParams,
    baseline_optimized_pid,
    build_playground_scenario,
    run_options_from_playground,
    run_bench,
    save_frozen_pid,
)
from mpc_core.sim.scenarios import MISMATCH_CASES, SCENARIOS
from mpc_core.sim.simulate import RunOptions, run_mpc_step_log
from mpc_core.sim.ui_cache import (
    DEFAULT_STEP_HORIZON,
    SCORECARD_PATH,
    named_playground_path,
    serialize_step_log,
    serialize_runs,
    step_through_path,
    write_json,
)


def _playground_bundle(name: str, params: PlaygroundParams) -> None:
    cfg = default_demo_config()
    triple = run_bench(
        build_playground_scenario(params),
        cfg=cfg,
        options=run_options_from_playground(params),
        horizon_steps=params.mpc_horizon,
        mpc_tracking_weight=params.mpc_tracking_weight,
        plain_pid_gains=PIDGains(kp=params.pid_kp, ki=params.pid_ki, kd=params.pid_kd),
        lqr_weights=params.lqr_weights,
    )
    write_json(named_playground_path(name), serialize_runs(triple, params))
    print(f"Wrote playground/{name}.json", flush=True)


def _scorecard() -> None:
    cfg = default_demo_config()
    items = [(k, SCENARIOS[k].title, SCENARIOS[k], None) for k in SCENARIOS]
    # Scenario 7 also runs the opposite mismatch corner.
    items.append(
        (
            "model_mismatch_low",
            "Model mismatch (low R, J, B)",
            SCENARIOS["model_mismatch"],
            RunOptions(plant_scale=MISMATCH_CASES["low"]),
        )
    )
    rows = []
    for _, title, scenario, opt in items:
        triple = run_bench(scenario, cfg=cfg, options=opt)
        for cid in CONTROLLER_IDS:
            rows.append(
                {"Scenario": title, "Controller": CONTROLLER_LABELS[cid], **result_row(triple[cid])}
            )
        print(f"scorecard: {title}", flush=True)
    write_json(SCORECARD_PATH, {"rows": rows})
    print(f"Wrote {SCORECARD_PATH.name}", flush=True)


def _step_through() -> None:
    cfg = default_demo_config()
    h = DEFAULT_STEP_HORIZON
    for key, scenario in SCENARIOS.items():
        log = run_mpc_step_log(scenario, cfg=cfg, horizon_steps=h, max_steps=150)
        write_json(step_through_path(key, h), serialize_step_log(log, scenario_key=key, horizon=h))
        print(f"Wrote step_through/{key}_h{h}.json", flush=True)


def main() -> None:
    print("Tuning and freezing the optimised PID on speed_tracking...", flush=True)
    tune = baseline_optimized_pid(cfg=default_demo_config(), force_retune=True)
    save_frozen_pid(tune)
    print(f"  frozen gains: {tune.gains}", flush=True)
    print("Precomputing playground defaults and presets...", flush=True)
    _playground_bundle("default", PlaygroundParams())
    for name, fn in PRESETS.items():
        _playground_bundle(name, fn(PlaygroundParams()))
    print("Precomputing scorecard...", flush=True)
    _scorecard()
    print("Precomputing step-through logs...", flush=True)
    _step_through()
    print("Done.", flush=True)


if __name__ == "__main__":
    main()

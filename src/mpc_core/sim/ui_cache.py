"""Load precomputed UI simulation JSON (regen: python scripts/precompute_ui_data.py).

Traces are stored every ``TRACE_STRIDE`` controller samples (20 ms) to keep the
files small; metrics are computed from the full-rate run before serialising.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np

from mpc_core.sim.metrics import SimulationMetrics
from mpc_core.sim.pid import PIDGains
from mpc_core.sim.pid_tune import TuneResult
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.playground import (
    ControllerRuns,
    PlaygroundParams,
    build_playground_scenario,
    run_options_from_playground,
)
from mpc_core.sim.simulate import (
    CONTROLLER_IDS,
    MpcStepLog,
    MpcStepSnapshot,
    SimulationResult,
    run_closed_loop,
)

ROOT = Path(__file__).resolve().parents[3]
DATA_UI = ROOT / "data" / "ui"
PLAYGROUND_DIR = DATA_UI / "playground"
STEP_DIR = DATA_UI / "step_through"
SCORECARD_PATH = DATA_UI / "scorecard.json"

DEFAULT_STEP_HORIZON = 60
TRACE_STRIDE = 2
SCHEMA_VERSION = 2  # per-controller entries, LQR added

_FLOAT_FIELDS = (
    "time_s",
    "speed_rpm",
    "ref_rpm",
    "speed_meas_rpm",
    "i_a",
    "v_cmd",
    "v_applied",
    "torque_nm",
    "load_nm",
    "theta_rad",
)
_BOOL_FIELDS = ("v_saturated", "i_limited")


def _round_list(xs: np.ndarray | list[float], ndigits: int = 4) -> list[float]:
    arr = np.asarray(xs, dtype=float)
    return [round(float(v), ndigits) for v in arr.tolist()]


def params_cache_key(p: PlaygroundParams, controller: str | None = None) -> str:
    """Key of the scenario parameters a controller's result depends on.

    LQR weights only enter the LQR key, so editing them invalidates LQR results and
    nothing else. ``controller=None`` gives the key shared by PID, Opt. PID and MPC.
    """
    items = sorted(
        (k, v)
        for k, v in p.__dict__.items()
        if controller == "lqr" or not k.startswith("lqr_")
    )
    if controller == "lqr":
        skip = ("pid_kp", "pid_ki", "pid_kd", "mpc_horizon", "mpc_tracking_weight")
        items = [(k, v) for k, v in items if k not in skip]
    return json.dumps(items, separators=(",", ":"), default=str)


def named_playground_path(name: str) -> Path:
    return PLAYGROUND_DIR / f"{name}.json"


def step_through_path(scenario_key: str, horizon: int) -> Path:
    return STEP_DIR / f"{scenario_key}_h{horizon}.json"


def serialize_run(run: SimulationResult) -> dict:
    sl = slice(None, None, TRACE_STRIDE)
    payload: dict = {
        "controller": run.controller,
        "metrics": asdict(run.metrics),
        "active_constraints_last": list(run.active_constraints_last),
        "i_max": run.i_max,
        "v_max": run.v_max,
    }
    for name in _FLOAT_FIELDS:
        payload[name] = _round_list(getattr(run, name)[sl])
    for name in _BOOL_FIELDS:
        payload[name] = [int(v) for v in getattr(run, name)[sl]]
    if run.d_hat is not None:
        payload["d_hat"] = _round_list(run.d_hat[sl], 5)
    if run.mpc_solve_ms is not None:
        payload["mpc_solve_ms"] = _round_list(run.mpc_solve_ms, 3)
    if run.pid_gains is not None:
        payload["pid_gains"] = asdict(run.pid_gains)
    if run.exec_ms is not None:
        payload["exec_ms"] = _round_list(run.exec_ms, 3)
    payload["config"] = run.config
    return payload


def deserialize_run(data: dict) -> SimulationResult:
    metrics = SimulationMetrics(**data["metrics"])
    pid_gains = PIDGains(**data["pid_gains"]) if data.get("pid_gains") else None
    arrays = {k: np.asarray(data[k], dtype=float) for k in _FLOAT_FIELDS}
    flags = {k: np.asarray(data[k], dtype=bool) for k in _BOOL_FIELDS}
    return SimulationResult(
        controller=data["controller"],
        **arrays,
        **flags,
        d_hat=None if data.get("d_hat") is None else np.asarray(data["d_hat"], dtype=float),
        metrics=metrics,
        active_constraints_last=list(data.get("active_constraints_last", [])),
        i_max=float(data["i_max"]),
        v_max=float(data["v_max"]),
        mpc_solve_ms=(
            None
            if data.get("mpc_solve_ms") is None
            else np.asarray(data["mpc_solve_ms"], dtype=float)
        ),
        pid_gains=pid_gains,
        exec_ms=None if data.get("exec_ms") is None else np.asarray(data["exec_ms"], dtype=float),
        config=dict(data.get("config", {})),
    )


def serialize_runs(bundle: ControllerRuns, params: PlaygroundParams) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "params": {f.name: getattr(params, f.name) for f in fields(params)},
        "params_key": params_cache_key(params),
        "lqr_key": params_cache_key(params, "lqr"),
        "runs": {cid: serialize_run(bundle[cid]) for cid in bundle},
        "tune": {
            "gains": asdict(bundle.tune.gains),
            "final_objective": bundle.tune.final_objective,
            "metrics_iae": bundle.tune.metrics_iae,
            "violation_steps": bundle.tune.violation_steps,
        },
    }


def deserialize_runs(data: dict) -> ControllerRuns:
    tune = TuneResult(
        gains=PIDGains(**data["tune"]["gains"]),
        final_objective=float(data["tune"]["final_objective"]),
        metrics_iae=float(data["tune"]["metrics_iae"]),
        violation_steps=int(data["tune"]["violation_steps"]),
    )
    runs = {
        cid: deserialize_run(data["runs"][cid]) for cid in CONTROLLER_IDS if cid in data["runs"]
    }
    return ControllerRuns(runs=runs, tune=tune)


def load_playground_runs(params: PlaygroundParams) -> ControllerRuns | None:
    """Cached PID / Opt. PID / MPC runs; LQR is reused only if its own key matches.

    Returns None when the shared key misses (the caller then simulates live). A stale
    LQR entry is recomputed here (LQR is cheap) so other controllers stay cached.
    """
    key = params_cache_key(params)
    lqr_key = params_cache_key(params, "lqr")
    if not PLAYGROUND_DIR.exists():
        return None
    for path in sorted(PLAYGROUND_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("schema_version") != SCHEMA_VERSION or data.get("params_key") != key:
            continue
        bundle = deserialize_runs(data)
        if data.get("lqr_key") != lqr_key or "lqr" not in bundle.runs:
            lqr = run_closed_loop(
                build_playground_scenario(params),
                "lqr",
                cfg=default_demo_config(),
                options=run_options_from_playground(params),
                lqr_weights=params.lqr_weights,
            )
            runs = dict(bundle.runs)
            runs["lqr"] = lqr
            bundle = ControllerRuns(
                runs={c: runs[c] for c in CONTROLLER_IDS if c in runs}, tune=bundle.tune
            )
        return bundle
    return None


def load_scorecard_rows() -> list[dict] | None:
    if not SCORECARD_PATH.exists():
        return None
    data = json.loads(SCORECARD_PATH.read_text(encoding="utf-8"))
    return list(data["rows"])


def serialize_step_log(log: MpcStepLog, *, scenario_key: str, horizon: int) -> dict:
    snaps = []
    for s in log.snapshots:
        snaps.append(
            {
                "step_index": s.step_index,
                "time_s": round(float(s.time_s), 5),
                "y_meas": round(float(s.y_meas), 4),
                "y_ref": round(float(s.y_ref), 4),
                "u_applied": round(float(s.u_applied), 4),
                "d_hat": round(float(s.d_hat), 5),
                "predicted_y": _round_list(s.predicted_y, 3),
                "predicted_i": _round_list(s.predicted_i, 3),
                "planned_u": round(float(s.planned_u), 4),
                "planned_u_traj": _round_list(s.planned_u_traj, 3),
                "active_constraints": list(s.active_constraints),
                "d_v_hat": round(float(s.d_v_hat), 4),
                "solve_ms": round(float(s.solve_ms), 3),
                "caption": s.caption,
            }
        )
    return {"scenario_key": scenario_key, "horizon": horizon, "snapshots": snaps}


def load_step_log(scenario_key: str, horizon: int) -> MpcStepLog | None:
    path = step_through_path(scenario_key, horizon)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    snaps = [
        MpcStepSnapshot(
            step_index=int(s["step_index"]),
            time_s=float(s["time_s"]),
            y_meas=float(s["y_meas"]),
            y_ref=float(s["y_ref"]),
            u_applied=float(s["u_applied"]),
            d_hat=float(s["d_hat"]),
            predicted_y=list(s["predicted_y"]),
            predicted_i=list(s.get("predicted_i", [])),
            planned_u=float(s["planned_u"]),
            planned_u_traj=list(s.get("planned_u_traj", [])),
            active_constraints=list(s.get("active_constraints", [])),
            d_v_hat=float(s.get("d_v_hat", 0.0)),
            solve_ms=float(s["solve_ms"]),
            caption=str(s["caption"]),
        )
        for s in data["snapshots"]
    ]
    return MpcStepLog(snapshots=snaps)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

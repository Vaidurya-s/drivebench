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
from mpc_core.sim.playground import PlaygroundParams, TripleRun
from mpc_core.sim.simulate import MpcStepLog, MpcStepSnapshot, SimulationResult

ROOT = Path(__file__).resolve().parents[3]
DATA_UI = ROOT / "data" / "ui"
PLAYGROUND_DIR = DATA_UI / "playground"
STEP_DIR = DATA_UI / "step_through"
SCORECARD_PATH = DATA_UI / "scorecard.json"

DEFAULT_STEP_HORIZON = 60
TRACE_STRIDE = 2

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


def params_cache_key(p: PlaygroundParams) -> str:
    items = sorted(p.__dict__.items())
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
    )


def serialize_triple(triple: TripleRun, params: PlaygroundParams) -> dict:
    return {
        "params": {f.name: getattr(params, f.name) for f in fields(params)},
        "params_key": params_cache_key(params),
        "mpc": serialize_run(triple.mpc),
        "pid": serialize_run(triple.pid),
        "optimized_pid": serialize_run(triple.optimized_pid),
        "tune": {
            "gains": asdict(triple.tune.gains),
            "final_objective": triple.tune.final_objective,
            "metrics_iae": triple.tune.metrics_iae,
            "violation_steps": triple.tune.violation_steps,
        },
    }


def deserialize_triple(data: dict) -> TripleRun:
    tune = TuneResult(
        gains=PIDGains(**data["tune"]["gains"]),
        final_objective=float(data["tune"]["final_objective"]),
        metrics_iae=float(data["tune"]["metrics_iae"]),
        violation_steps=int(data["tune"]["violation_steps"]),
    )
    return TripleRun(
        mpc=deserialize_run(data["mpc"]),
        pid=deserialize_run(data["pid"]),
        optimized_pid=deserialize_run(data["optimized_pid"]),
        tune=tune,
    )


def load_playground_triple(params: PlaygroundParams) -> TripleRun | None:
    key = params_cache_key(params)
    if PLAYGROUND_DIR.exists():
        for path in sorted(PLAYGROUND_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("params_key") == key:
                return deserialize_triple(data)
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
            solve_ms=float(s["solve_ms"]),
            caption=str(s["caption"]),
        )
        for s in data["snapshots"]
    ]
    return MpcStepLog(snapshots=snaps)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

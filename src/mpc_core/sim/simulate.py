"""Run MPC or PID against the PMDC motor plant through the shared drive.

One closed-loop path serves every controller: identical plant, drive,
initial state, reference, load, bus and measurement-noise arrays. The
controller runs every ``cfg.dt_s`` (10 ms); the plant integrates with RK4
sub-steps (1 ms) while the applied voltage is held (zero-order hold).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Callable, Literal

import numpy as np

from mpc_core import MpcState, SetpointLimits, solve
from mpc_core.sim.config import DemoConfig, default_demo_config, voltage_limits
from mpc_core.sim.drive import DriveConfig, MotorDrive
from mpc_core.sim.metrics import SimulationMetrics, compute_metrics
from mpc_core.sim.pid import PIDGains, PIDState, pid_step
from mpc_core.sim.plant import initial_state, step_plant
from mpc_core.sim.scenarios import ScenarioConfig
from mpc_core.twin.pmdc import rad_s_to_rpm, rpm_to_rad_s

ControllerKind = Literal["mpc", "pid"]


@dataclass(frozen=True)
class RunOptions:
    """Overrides shared by MPC, PID and tuned PID (None keeps the scenario value)."""

    noise_std_rpm: float | None = None
    noise_seed: int | None = None
    plant_scale: tuple[float, float, float, float] | None = None  # R, L, J, B


@dataclass(frozen=True)
class SimulationResult:
    controller: ControllerKind | str
    time_s: np.ndarray
    speed_rpm: np.ndarray  # true shaft speed
    ref_rpm: np.ndarray
    speed_meas_rpm: np.ndarray  # what the controller saw (with noise)
    i_a: np.ndarray
    v_cmd: np.ndarray  # controller output
    v_applied: np.ndarray  # after the drive
    torque_nm: np.ndarray  # electromagnetic
    load_nm: np.ndarray
    theta_rad: np.ndarray
    v_saturated: np.ndarray
    i_limited: np.ndarray
    d_hat: np.ndarray | None  # MPC load-torque estimate [N m]
    metrics: SimulationMetrics
    active_constraints_last: list[str]
    i_max: float = 8.0
    v_max: float = 24.0
    mpc_solve_ms: np.ndarray | None = None
    pid_gains: PIDGains | None = None

    @property
    def omega_rad_s(self) -> np.ndarray:
        return rpm_to_rad_s(1.0) * self.speed_rpm

    @property
    def p_elec_w(self) -> np.ndarray:
        return self.v_applied * self.i_a

    @property
    def p_mech_w(self) -> np.ndarray:
        return self.torque_nm * self.omega_rad_s


@dataclass(frozen=True)
class MpcStepSnapshot:
    step_index: int
    time_s: float
    y_meas: float
    y_ref: float
    u_applied: float
    d_hat: float
    predicted_y: list[float]
    planned_u: float
    solve_ms: float
    caption: str
    i_a: float = 0.0
    predicted_i: list[float] = field(default_factory=list)


@dataclass
class MpcStepLog:
    snapshots: list[MpcStepSnapshot] = field(default_factory=list)


def scenario_drive(cfg: DemoConfig, scenario: ScenarioConfig) -> DriveConfig:
    """Drive configuration after the scenario's overrides."""
    d = cfg.drive
    return replace(
        d,
        V_max=scenario.v_max if scenario.v_max is not None else d.V_max,
        I_max=scenario.i_max if scenario.i_max is not None else d.I_max,
        slew_v_per_s=scenario.slew_v_per_s if scenario.slew_v_per_s is not None else d.slew_v_per_s,
    )


@dataclass(frozen=True)
class _Inputs:
    """The exogenous sequences every controller is given, built once."""

    time_s: np.ndarray
    ref: np.ndarray
    load: np.ndarray
    bus: np.ndarray
    noise: np.ndarray


def build_inputs(
    scenario: ScenarioConfig, cfg: DemoConfig, options: RunOptions
) -> _Inputs:
    n = int(round(scenario.duration_s / cfg.dt_s))
    t = np.arange(n, dtype=float) * cfg.dt_s
    std = options.noise_std_rpm if options.noise_std_rpm is not None else scenario.noise_std_rpm
    seed = options.noise_seed if options.noise_seed is not None else scenario.noise_seed
    noise = np.random.default_rng(seed).normal(0.0, std, n) if std > 0 else np.zeros(n)
    bus = scenario.bus_fn(t) if scenario.bus_fn is not None else np.ones(n)
    return _Inputs(
        time_s=t,
        ref=np.clip(
            np.asarray(scenario.y_ref_fn(t), dtype=float),
            -cfg.motor.omega_max_rpm,
            cfg.motor.omega_max_rpm,
        ),
        load=np.asarray(scenario.load_fn(t), dtype=float),
        bus=np.asarray(bus, dtype=float),
        noise=noise,
    )


def _run(
    scenario: ScenarioConfig,
    controller: ControllerKind,
    cfg: DemoConfig,
    *,
    horizon_steps: int | None,
    options: RunOptions,
    pid_gains: PIDGains | None,
    mpc_tracking_weight: float | None,
    mpc_control_horizon: int | None,
    mpc_move_weight: float | None,
    mpc_terminal_weight: float | None,
    mpc_observer_gain: float | None,
    mpc_preview: bool,
    max_steps: int | None,
    on_mpc_step: Callable[[int, float, float, float, float, object, float], None] | None,
) -> dict:
    inp = build_inputs(scenario, cfg, options)
    n = len(inp.time_s) if max_steps is None else min(len(inp.time_s), max_steps)
    drive_cfg = scenario_drive(cfg, scenario)
    limits: SetpointLimits = voltage_limits(drive_cfg, cfg.dt_s)
    scale = options.plant_scale or scenario.plant_scale
    plant_params = cfg.motor.scaled(R=scale[0], L=scale[1], J=scale[2], B=scale[3])

    # Plant starts in steady state at the scenario's initial speed and load.
    w0 = rpm_to_rad_s(scenario.omega0_rpm)
    plant = initial_state(plant_params, omega=w0, T_L=float(inp.load[0]))
    drive = MotorDrive(drive_cfg, cfg.motor, cfg.dt_s)  # the drive knows nominal R, K_e
    _, v0 = plant_params.equilibrium(omega=w0, T_L=float(inp.load[0]))
    drive.reset(v_applied=float(np.clip(v0, -drive_cfg.V_max, drive_cfg.V_max)))

    gains = pid_gains or PIDGains(*scenario.pid_gains)
    pid_state = PIDState()
    mpc_state = MpcState()
    h = horizon_steps if horizon_steps is not None else (
        scenario.mpc_horizon if scenario.mpc_horizon else cfg.horizon_steps
    )
    nu = mpc_control_horizon if mpc_control_horizon is not None else cfg.control_horizon
    q = mpc_tracking_weight if mpc_tracking_weight is not None else cfg.tracking_weight
    r = mpc_move_weight if mpc_move_weight is not None else cfg.move_weight
    qt = mpc_terminal_weight if mpc_terminal_weight is not None else cfg.terminal_weight
    lg = mpc_observer_gain if mpc_observer_gain is not None else cfg.observer_gain
    model = cfg.model  # controllers always use the nominal motor
    ref_ext = np.concatenate([inp.ref, np.full(h + 1, inp.ref[-1])])

    keys = (
        "speed", "meas", "i", "vcmd", "vapp", "tq", "theta", "vsat", "ilim", "dhat", "ms",
    )
    rec: dict[str, list] = {k: [] for k in keys}
    active_last: list[str] = []

    for k in range(n):
        y_true = plant.speed_rpm
        y_meas = y_true + float(inp.noise[k])
        y_r = float(inp.ref[k])

        if controller == "mpc":
            t0 = time.perf_counter()
            ref_traj = [float(v) for v in ref_ext[k + 1 : k + 1 + h]] if mpc_preview else None
            result = solve(
                model,
                [limits],
                {limits.setpoint_id: drive.v_applied},
                y_meas=y_meas,
                y_ref=y_r,
                horizon_steps=h,
                time_limit_s=cfg.solver_time_limit_s,
                state=mpc_state,
                tracking_weight=q,
                control_horizon=nu,
                move_weight=r,
                terminal_weight=qt,
                y_ref_traj=ref_traj,
                observer_gain=lg,
                i_meas=plant.i_a,
                i_max=drive_cfg.I_max,
            )
            solve_ms = (time.perf_counter() - t0) * 1000.0
            v_cmd = float(result.best[limits.setpoint_id])
            mpc_state = result.state
            active_last = list(result.active_constraints)
            rec["dhat"].append(result.d_hat)
            rec["ms"].append(solve_ms)
            if on_mpc_step is not None:
                on_mpc_step(k, float(inp.time_s[k]), y_meas, y_r, v_cmd, result, solve_ms)
        else:
            v_cmd, pid_state = pid_step(
                y=y_meas,
                y_ref=y_r,
                u_prev=drive.v_applied,
                dt_s=cfg.dt_s,
                gains=gains,
                state=pid_state,
                u_min=-drive_cfg.V_max,
                u_max=drive_cfg.V_max,
            )

        v_app, flags = drive.step(
            v_cmd, i_a=plant.i_a, omega=plant.omega, bus_scale=float(inp.bus[k])
        )
        rec["speed"].append(y_true)
        rec["meas"].append(y_meas)
        rec["i"].append(plant.i_a)
        rec["vcmd"].append(v_cmd)
        rec["vapp"].append(v_app)
        rec["tq"].append(plant.torque_nm)
        rec["theta"].append(plant.theta)
        rec["vsat"].append(flags.v_saturated)
        rec["ilim"].append(flags.i_limited)
        plant = step_plant(plant, v_app, float(inp.load[k]), cfg.dt_s, substeps=cfg.substeps)

    arr = {k: np.array(v, dtype=float) for k, v in rec.items() if v}
    return {
        "inp": inp,
        "n": n,
        "arr": arr,
        "drive_cfg": drive_cfg,
        "plant_params": plant_params,
        "active_last": active_last,
        "gains": gains,
    }


def run_closed_loop(
    scenario: ScenarioConfig,
    controller: ControllerKind,
    cfg: DemoConfig | None = None,
    *,
    horizon_steps: int | None = None,
    options: RunOptions | None = None,
    pid_gains: PIDGains | None = None,
    mpc_tracking_weight: float | None = None,
    mpc_control_horizon: int | None = None,
    mpc_move_weight: float | None = None,
    mpc_terminal_weight: float | None = None,
    mpc_observer_gain: float | None = None,
    mpc_preview: bool = True,
    result_label: str | None = None,
) -> SimulationResult:
    cfg = cfg or default_demo_config()
    opt = options or RunOptions()
    out = _run(
        scenario,
        controller,
        cfg,
        horizon_steps=horizon_steps,
        options=opt,
        pid_gains=pid_gains,
        mpc_tracking_weight=mpc_tracking_weight,
        mpc_control_horizon=mpc_control_horizon,
        mpc_move_weight=mpc_move_weight,
        mpc_terminal_weight=mpc_terminal_weight,
        mpc_observer_gain=mpc_observer_gain,
        mpc_preview=mpc_preview,
        max_steps=None,
        on_mpc_step=None,
    )
    inp: _Inputs = out["inp"]
    a = out["arr"]
    drive_cfg: DriveConfig = out["drive_cfg"]
    n = out["n"]
    omega = a["speed"] * rpm_to_rad_s(1.0)
    metrics = compute_metrics(
        time_s=inp.time_s[:n],
        speed_rpm=a["speed"],
        ref_rpm=inp.ref[:n],
        i_a=a["i"],
        v_applied=a["vapp"],
        torque_nm=a["tq"],
        load_nm=inp.load[:n],
        omega_rad_s=omega,
        v_saturated=a["vsat"].astype(bool),
        i_limited=a["ilim"].astype(bool),
        i_max=drive_cfg.I_max,
        v_max=drive_cfg.V_max,
        b_friction=out["plant_params"].B,
        power_stage_efficiency=drive_cfg.power_stage_efficiency,
        load_change_at_s=scenario.load_change_at_s,
    )
    label: ControllerKind | str = result_label or controller
    return SimulationResult(
        controller=label,
        time_s=inp.time_s[:n],
        speed_rpm=a["speed"],
        ref_rpm=inp.ref[:n],
        speed_meas_rpm=a["meas"],
        i_a=a["i"],
        v_cmd=a["vcmd"],
        v_applied=a["vapp"],
        torque_nm=a["tq"],
        load_nm=inp.load[:n],
        theta_rad=a["theta"],
        v_saturated=a["vsat"].astype(bool),
        i_limited=a["ilim"].astype(bool),
        d_hat=a.get("dhat"),
        metrics=metrics,
        active_constraints_last=out["active_last"],
        i_max=drive_cfg.I_max,
        v_max=drive_cfg.V_max,
        mpc_solve_ms=a.get("ms"),
        pid_gains=out["gains"] if controller == "pid" else None,
    )


def run_mpc_step_log(
    scenario: ScenarioConfig,
    cfg: DemoConfig | None = None,
    *,
    horizon_steps: int | None = None,
    options: RunOptions | None = None,
    max_steps: int | None = 80,
) -> MpcStepLog:
    """Record MPC predictions and the first move applied each sample (teaching UI)."""
    cfg = cfg or default_demo_config()
    h = horizon_steps if horizon_steps is not None else (
        scenario.mpc_horizon if scenario.mpc_horizon else cfg.horizon_steps
    )
    log = MpcStepLog()

    def capture(k, t, y_meas, y_ref, v_cmd, result, solve_ms) -> None:
        caption = (
            f"At t={t:.2f}s the measured speed is {y_meas:.0f} RPM against a reference "
            f"of {y_ref:.0f} RPM. MPC plans {v_cmd:.1f} V now over the next "
            f"{h} samples ({h * cfg.dt_s:.1f} s); only that first move is applied, "
            f"then the horizon shifts."
        )
        if result.active_constraints:
            caption += f" Active limits: {', '.join(result.active_constraints)}."
        log.snapshots.append(
            MpcStepSnapshot(
                step_index=k,
                time_s=t,
                y_meas=y_meas,
                y_ref=y_ref,
                u_applied=v_cmd,
                d_hat=result.d_hat,
                predicted_y=list(result.predicted_y),
                planned_u=v_cmd,
                solve_ms=solve_ms,
                caption=caption,
                predicted_i=list(result.predicted_i or []),
            )
        )

    _run(
        scenario,
        "mpc",
        cfg,
        horizon_steps=horizon_steps,
        options=options or RunOptions(),
        pid_gains=None,
        mpc_tracking_weight=None,
        mpc_control_horizon=None,
        mpc_move_weight=None,
        mpc_terminal_weight=None,
        mpc_observer_gain=None,
        mpc_preview=True,
        max_steps=max_steps,
        on_mpc_step=capture,
    )
    return log

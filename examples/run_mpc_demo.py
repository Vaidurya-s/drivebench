#!/usr/bin/env python3
"""Small closed-loop demo: offset-free MPC on the PMDC motor twin.

Starts a motor from rest, asks for 1000 RPM against an unmodelled extra load,
and prints what the MPC plans each step. The plant is the RK4 motor twin; the
MPC predicts with the nominal two-state model. Nothing here writes to hardware.
"""

from __future__ import annotations

from mpc_core import MpcState, solve
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.drive import MotorDrive
from mpc_core.sim.plant import initial_state, step_plant


def main() -> None:
    cfg = default_demo_config()
    drive = MotorDrive(cfg.drive, cfg.motor, cfg.dt_s)
    plant = initial_state(cfg.motor)
    state = MpcState()
    limits = cfg.limits
    load_nm = 0.09  # the model's nominal load is 0.05: the observer must find the rest
    ref_rpm = 1000.0

    print(f"offset-free MPC on the PMDC motor: reference {ref_rpm:.0f} RPM, load {load_nm} N m")
    for k in range(60):
        result = solve(
            cfg.model,
            [limits],
            {limits.setpoint_id: drive.v_applied},
            y_meas=plant.speed_rpm,
            y_ref=ref_rpm,
            horizon_steps=cfg.horizon_steps,
            time_limit_s=cfg.solver_time_limit_s,
            state=state,
            tracking_weight=cfg.tracking_weight,
            control_horizon=cfg.control_horizon,
            move_weight=cfg.move_weight,
            terminal_weight=cfg.terminal_weight,
            observer_gain=cfg.observer_gain,
            i_meas=plant.i_a,
            i_max=cfg.drive.I_max,
        )
        state = result.state
        v, flags = drive.step(
            result.best[limits.setpoint_id], i_a=plant.i_a, omega=plant.omega
        )
        plant = step_plant(plant, v, load_nm, cfg.dt_s, substeps=cfg.substeps)
        if k % 6 == 0:
            print(
                f"t={k * cfg.dt_s:5.2f}s V={v:6.2f} i={plant.i_a:5.2f} A "
                f"speed={plant.speed_rpm:7.1f} RPM d_hat={result.d_hat:6.3f} N m "
                f"current_limited={flags.i_limited}"
            )


if __name__ == "__main__":
    main()

"""Simulation configuration: motor, drive, timing and MPC defaults (SI units).

Motor numbers live only in ``PMDCParams``; this module wires them to the drive
limits, the MPC prediction model and the controller defaults. Illustrative
course parameters, not a commercial motor.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from mpc_core.identified import MotorStateSpaceModel
from mpc_core.sim.drive import DriveConfig
from mpc_core.thresholds import SetpointLimits
from mpc_core.twin.pmdc import PMDCParams

VOLTAGE_ID = "voltage_setpoint"


@dataclass(frozen=True)
class DemoConfig:
    """Shared knobs for batch runs and the Streamlit app."""

    motor: PMDCParams
    drive: DriveConfig
    dt_s: float  # controller sample period Ts
    plant_dt_s: float  # plant integration step
    horizon_steps: int
    solver_time_limit_s: float
    setpoint_id: str = VOLTAGE_ID
    control_horizon: int = 6
    move_weight: float = 0.0
    terminal_weight: float = 0.0
    observer_gain: float = 1.0
    tracking_weight: float = 1.0

    def __post_init__(self) -> None:
        if self.plant_dt_s <= 0 or self.dt_s < self.plant_dt_s:
            raise ValueError("need 0 < plant_dt_s <= dt_s")
        ratio = self.dt_s / self.plant_dt_s
        if abs(ratio - round(ratio)) > 1e-9:
            raise ValueError("dt_s must be an integer multiple of plant_dt_s")

    @property
    def substeps(self) -> int:
        """Plant RK4 sub-steps per controller sample."""
        return int(round(self.dt_s / self.plant_dt_s))

    @property
    def model(self) -> MotorStateSpaceModel:
        """MPC prediction model: always the nominal motor."""
        return MotorStateSpaceModel(self.motor, self.dt_s)

    @property
    def limits(self) -> SetpointLimits:
        """Voltage window and per-sample slew the MPC plans within."""
        return voltage_limits(self.drive, self.dt_s)

    def with_motor(self, motor: PMDCParams) -> "DemoConfig":
        """Same controller defaults on another motor; drive limits follow ratings."""
        drive = replace(self.drive, V_max=motor.V_max, I_max=motor.I_max)
        return replace(self, motor=motor, drive=drive)


def voltage_limits(drive: DriveConfig, ts_s: float) -> SetpointLimits:
    """MPC voltage constraint set implied by a drive configuration."""
    return SetpointLimits(VOLTAGE_ID, "V", -drive.V_max, drive.V_max, drive.max_step(ts_s))


def default_demo_config(motor: PMDCParams | None = None) -> DemoConfig:
    """Baseline motor drive: 1 ms plant step under a 10 ms controller.

    MPC defaults: 0.6 s prediction (the mechanical time constant is ~0.57 s),
    six blocked voltage moves, terminal weight on the last predicted error.
    """
    motor = motor or PMDCParams()
    return DemoConfig(
        motor=motor,
        drive=DriveConfig.from_motor(motor),
        dt_s=0.010,
        plant_dt_s=0.001,
        horizon_steps=60,
        solver_time_limit_s=2.0,
        control_horizon=6,
        move_weight=5000.0,
        terminal_weight=50.0,
        observer_gain=0.1,
        tracking_weight=1.0,
    )

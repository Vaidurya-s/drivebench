"""Named, reproducible motor scenarios for controller comparison.

Every scenario fixes the reference trajectory (RPM), load torque T_L(t),
optional DC-bus profile, initial speed, measurement noise level, plant
mismatch and drive-limit overrides. All three controllers see exactly the same
arrays and the same seeded noise sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from mpc_core.sim.config import DemoConfig

Profile = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class ScenarioConfig:
    key: str
    title: str
    description: str
    duration_s: float
    y_ref_fn: Profile  # speed reference [RPM]
    load_fn: Profile  # load torque T_L [N m]
    omega0_rpm: float = 0.0
    bus_fn: Profile | None = None  # DC-bus voltage as a fraction of nominal
    noise_std_rpm: float = 0.0
    noise_seed: int = 42
    plant_scale: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)  # R, L, J, B
    v_max: float | None = None  # drive overrides (None = configuration default)
    i_max: float | None = None
    slew_v_per_s: float | None = None
    load_change_at_s: float | None = None  # for speed-recovery time
    pid_gains: tuple[float, float, float] = (0.01, 0.03, 0.0)
    mpc_horizon: int | None = None


# -- profile builders ---------------------------------------------------------
def piecewise(levels: list[tuple[float, float]]) -> Profile:
    """Zero-order-hold profile from (start_time_s, value) pairs."""
    pts = sorted(levels)

    def fn(t: np.ndarray) -> np.ndarray:
        out = np.full_like(t, pts[0][1], dtype=float)
        for t0, v in pts:
            out[t >= t0] = v
        return out

    return fn


def constant(value: float) -> Profile:
    return piecewise([(0.0, value)])


def sinusoid(base: float, amplitude: float, freq_hz: float) -> Profile:
    """T_L(t) = T_0 + A sin(2 pi f t)."""

    def fn(t: np.ndarray) -> np.ndarray:
        return base + amplitude * np.sin(2.0 * np.pi * freq_hz * t)

    return fn


def bounded_random(
    base: float, amplitude: float, seed: int, hold_s: float = 0.5
) -> Profile:
    """Seeded, bounded, piecewise-linear random variation around ``base``."""

    def fn(t: np.ndarray) -> np.ndarray:
        rng = np.random.default_rng(seed)
        knots_t = np.arange(0.0, float(t[-1]) + 2 * hold_s, hold_s)
        knots_v = rng.uniform(-amplitude, amplitude, size=len(knots_t))
        return base + np.interp(t, knots_t, knots_v)

    return fn


def add(*profiles: Profile) -> Profile:
    def fn(t: np.ndarray) -> np.ndarray:
        return sum(p(t) for p in profiles)  # type: ignore[return-value]

    return fn


# Scenario 7 / scorecard mismatch cases: (R_a, L_a, J, B) multipliers.
MISMATCH_CASES: dict[str, tuple[float, float, float, float]] = {
    "high": (1.20, 1.0, 1.30, 1.25),
    "low": (0.80, 1.0, 0.70, 0.75),
}


def build_scenarios(cfg: DemoConfig | None = None) -> dict[str, ScenarioConfig]:
    _ = cfg
    return {
        "motor_startup": ScenarioConfig(
            key="motor_startup",
            title="Motor startup",
            description=(
                "Start from rest to 1000 RPM at nominal load. Startup current is "
                "limited by the drive, so the first second is a current-limited ramp."
            ),
            duration_s=6.0,
            y_ref_fn=constant(1000.0),
            load_fn=constant(0.05),
        ),
        "speed_tracking": ScenarioConfig(
            key="speed_tracking",
            title="Speed-reference tracking",
            description=(
                "Reference staircase 1000 / 2000 / 1500 / 2500 RPM every 5 s. "
                "Compares rise, overshoot and settling for each step."
            ),
            duration_s=20.0,
            y_ref_fn=piecewise([(0, 1000), (5, 2000), (10, 1500), (15, 2500)]),
            load_fn=constant(0.05),
        ),
        "load_step": ScenarioConfig(
            key="load_step",
            title="Sudden mechanical load",
            description=(
                "Running at 2000 RPM, the load torque doubles from 0.05 to 0.10 N m "
                "at 5 s. Measures dip and recovery."
            ),
            duration_s=12.0,
            y_ref_fn=constant(2000.0),
            load_fn=piecewise([(0, 0.05), (5, 0.10)]),
            omega0_rpm=2000.0,
            load_change_at_s=5.0,
        ),
        "load_removal": ScenarioConfig(
            key="load_removal",
            title="Load removal",
            description=(
                "Running at 2000 RPM with 0.10 N m, the load drops to 0.05 N m at 5 s. "
                "Measures speed overshoot and recovery."
            ),
            duration_s=12.0,
            y_ref_fn=constant(2000.0),
            load_fn=piecewise([(0, 0.10), (5, 0.05)]),
            omega0_rpm=2000.0,
            load_change_at_s=5.0,
        ),
        "voltage_saturation": ScenarioConfig(
            key="voltage_saturation",
            title="Voltage saturation",
            description=(
                "A near-maximum 2900 RPM reference, then the DC bus sags to 85 % at "
                "8 s so the available voltage can no longer hold the speed."
            ),
            duration_s=14.0,
            y_ref_fn=piecewise([(0, 1000), (2, 2900)]),
            load_fn=constant(0.05),
            bus_fn=piecewise([(0, 1.0), (8, 0.85)]),
            
        ),
        "current_protection": ScenarioConfig(
            key="current_protection",
            title="Current protection",
            description=(
                "Start to 2500 RPM under 0.10 N m, then raise the load to 0.14 N m at "
                "6 s. Holding speed would need more than the 8 A limit, so the drive's "
                "current protection engages."
            ),
            duration_s=12.0,
            y_ref_fn=constant(2500.0),
            load_fn=piecewise([(0, 0.10), (6, 0.14)]),
            load_change_at_s=6.0,
        ),
        "model_mismatch": ScenarioConfig(
            key="model_mismatch",
            title="Model mismatch",
            description=(
                "The plant has R_a +20 %, inertia +30 % and friction +25 % versus the "
                "controllers' nominal model; a load step arrives at 8 s."
            ),
            duration_s=14.0,
            y_ref_fn=piecewise([(0, 1000), (3, 2000)]),
            load_fn=piecewise([(0, 0.05), (8, 0.09)]),
            plant_scale=MISMATCH_CASES["high"],
            load_change_at_s=8.0,
        ),
        "sensor_noise": ScenarioConfig(
            key="sensor_noise",
            title="Sensor noise",
            description=(
                "Encoder speed noise (15 RPM standard deviation) while stepping "
                "from 1000 to 1500 RPM."
            ),
            duration_s=10.0,
            y_ref_fn=piecewise([(0, 1000), (4, 1500)]),
            load_fn=constant(0.05),
            omega0_rpm=1000.0,
            noise_std_rpm=15.0,
        ),
        "variable_load": ScenarioConfig(
            key="variable_load",
            title="Variable load",
            description=(
                "Constant 1500 RPM against a sinusoidal 0.5 Hz torque plus bounded "
                "random variation."
            ),
            duration_s=12.0,
            y_ref_fn=constant(1500.0),
            load_fn=add(sinusoid(0.07, 0.03, 0.5), bounded_random(0.0, 0.015, seed=11)),
            omega0_rpm=1500.0,
        ),
        "reverse_operation": ScenarioConfig(
            key="reverse_operation",
            title="Reverse operation",
            description=(
                "The bidirectional drive reverses from +1000 to -1000 RPM at 3 s and "
                "back at 9 s. Compares braking and reversal transients."
            ),
            duration_s=14.0,
            y_ref_fn=piecewise([(0, 1000), (3, -1000), (9, 1000)]),
            load_fn=constant(0.05),
            omega0_rpm=1000.0,
        ),
    }


SCENARIOS = build_scenarios()

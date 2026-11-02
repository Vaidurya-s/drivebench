"""Shared motor-drive layer between every controller and the plant.

The drive turns a voltage command into the voltage actually applied to the
armature. It is independent of any controller and sees only the command and
the sensed speed and current. Order of operations each controller sample:

1. enable / emergency-stop gate
2. slew-rate limit (relative to the previously applied voltage)
3. voltage saturation at +/- V_max * bus scale (DC-bus variation)
4. current protection (overrides the slew limit)

Current protection is a current-limited voltage drive, not a clip of the
simulated current state: the voltage is confined to the window for which the
exact one-interval electrical response keeps |i_a| <= I_max,

    i_next = alpha * i + (1 - alpha) * (V - K_e * w) / R,  alpha = exp(-Ts / tau_e)

using the drive's own nominal R_a, L_a, K_e (a real drive does not know the
true plant parameters) and the measured i_a and w.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from mpc_core.twin.pmdc import PMDCParams


@dataclass(frozen=True)
class DriveConfig:
    """Drive limits. Defaults follow the baseline motor ratings."""

    V_max: float = 24.0  # V
    I_max: float = 8.0  # A
    slew_v_per_s: float = 1200.0  # V/s, voltage slew-rate limit (12 V per 10 ms)
    current_protection: bool = True
    # Illustrative converter efficiency (supply power -> motor terminals). Only the
    # efficiency metrics use it; the applied voltage is not affected.
    power_stage_efficiency: float = 0.95

    def __post_init__(self) -> None:
        if self.V_max <= 0 or self.I_max <= 0 or self.slew_v_per_s <= 0:
            raise ValueError("V_max, I_max and slew_v_per_s must be positive")
        if not 0.5 <= self.power_stage_efficiency <= 1.0:
            raise ValueError("power_stage_efficiency must be in [0.5, 1]")

    @classmethod
    def from_motor(cls, params: PMDCParams, **kwargs: float) -> "DriveConfig":
        """Drive limits taken from the motor ratings."""
        return cls(V_max=params.V_max, I_max=params.I_max, **kwargs)

    def max_step(self, ts_s: float) -> float:
        """Largest voltage change per controller sample [V]."""
        return self.slew_v_per_s * ts_s


@dataclass(frozen=True)
class DriveFlags:
    """What the drive did to the command this sample (feeds the metrics)."""

    v_saturated: bool = False
    i_limited: bool = False
    slew_limited: bool = False
    disabled: bool = False


class MotorDrive:
    """Stateful bidirectional voltage drive with current protection."""

    def __init__(
        self,
        config: DriveConfig,
        nominal: PMDCParams,
        ts_s: float,
    ) -> None:
        if ts_s <= 0:
            raise ValueError("ts_s must be positive")
        self.config = config
        self.nominal = nominal
        self.ts_s = ts_s
        self.v_applied = 0.0
        self.enabled = True
        self.estopped = False
        self._alpha = math.exp(-ts_s / nominal.tau_e)

    # -- supervisory controls ------------------------------------------------
    def enable(self) -> None:
        """Start the drive (ramps the voltage up under the slew limit)."""
        if self.estopped:
            raise RuntimeError("emergency stop is latched; call reset() first")
        self.enabled = True

    def disable(self) -> None:
        """Controlled shutdown: command forced to 0 V and ramped by the slew limit."""
        self.enabled = False

    def emergency_stop(self) -> None:
        """Latched emergency shutdown: applied voltage drops to 0 V immediately."""
        self.estopped = True
        self.enabled = False
        self.v_applied = 0.0

    def reset(self, v_applied: float = 0.0) -> None:
        """Clear a latched e-stop and set the held voltage (used at run start)."""
        self.estopped = False
        self.enabled = True
        self.v_applied = v_applied

    # -- per-sample update ---------------------------------------------------
    def current_window(self, i_a: float, omega: float) -> tuple[float, float]:
        """Voltage window that keeps |i_a| <= I_max one interval ahead."""
        n, c = self.nominal, self.config
        gain = n.R_a / (1.0 - self._alpha)
        e = n.K_e * omega
        lo = e + gain * (-c.I_max - self._alpha * i_a)
        hi = e + gain * (c.I_max - self._alpha * i_a)
        # Feedback pull-down on measured excess current. The feedforward window uses
        # the drive's nominal R_a; if the real winding differs, the measured current
        # can still exceed I_max, so back the voltage off in proportion to the excess.
        if i_a > c.I_max:
            hi = min(hi, self.v_applied - gain * (i_a - c.I_max))
        elif i_a < -c.I_max:
            lo = max(lo, self.v_applied + gain * (-c.I_max - i_a))
        return lo, hi

    def step(
        self,
        v_cmd: float,
        *,
        i_a: float,
        omega: float,
        bus_scale: float = 1.0,
    ) -> tuple[float, DriveFlags]:
        """Return (applied voltage, flags) for one controller sample."""
        c = self.config
        if self.estopped:
            self.v_applied = 0.0
            return 0.0, DriveFlags(disabled=True)

        target = v_cmd if self.enabled else 0.0
        step_max = c.max_step(self.ts_s)
        lo_s = self.v_applied - step_max
        hi_s = self.v_applied + step_max
        slewed = min(max(target, lo_s), hi_s)
        slew_limited = slewed != target

        v_lim = c.V_max * max(bus_scale, 0.0)
        saturated = min(max(slewed, -v_lim), v_lim)
        v_saturated = saturated != slewed

        v = saturated
        i_limited = False
        if c.current_protection:
            lo_i, hi_i = self.current_window(i_a, omega)
            v = min(max(saturated, lo_i), hi_i)
            i_limited = v != saturated

        self.v_applied = v
        return v, DriveFlags(
            v_saturated=v_saturated,
            i_limited=i_limited,
            slew_limited=slew_limited,
            disabled=not self.enabled,
        )

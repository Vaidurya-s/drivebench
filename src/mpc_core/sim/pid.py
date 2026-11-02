"""Discrete speed PID: RPM in, armature voltage out.

Positional form with a filtered derivative-on-measurement and back-calculation
anti-windup. The anti-windup tracks the voltage the drive *actually applied*
last sample, so slew limiting, voltage saturation and current protection all
unwind the integrator, not only this controller's own clip.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PIDGains:
    """kp [V/RPM], ki [V/(RPM s)], kd [V s/RPM], tf_s derivative filter [s]."""

    kp: float
    ki: float
    kd: float
    tf_s: float = 0.02
    tt_s: float = 0.05  # anti-windup tracking time constant


@dataclass
class PIDState:
    integral: float = 0.0  # integrator contribution to the output [V]
    last_y: float | None = None
    d_filt: float = 0.0  # filtered measurement derivative [RPM/s]
    last_cmd: float = 0.0  # last unsaturated-then-clipped command we issued


def pid_step(
    *,
    y: float,
    y_ref: float,
    u_prev: float,
    dt_s: float,
    gains: PIDGains,
    state: PIDState,
    u_min: float,
    u_max: float,
    du_max: float | None = None,
    anti_windup: bool = True,
) -> tuple[float, PIDState]:
    """One PID update. ``u_prev`` is the voltage the drive applied last sample."""
    error = y_ref - y

    integral = state.integral
    if state.last_y is None:
        # Bumpless start: the integrator begins at the voltage already applied (the
        # steady-state holding voltage), so a loop that starts at steady speed does not
        # see a spurious 0 V command. From rest u_prev is 0 and nothing changes.
        integral = u_prev
        state = PIDState(integral=integral, last_y=None, d_filt=0.0, last_cmd=u_prev)
    if anti_windup:
        # Back-calculation: pull the integrator toward what was actually applied.
        integral += dt_s / gains.tt_s * (u_prev - state.last_cmd)

    if state.last_y is None or dt_s <= 0:
        d_filt = 0.0
    else:
        alpha = gains.tf_s / (gains.tf_s + dt_s)
        d_filt = alpha * state.d_filt + (1.0 - alpha) * (y - state.last_y) / dt_s

    integral += gains.ki * error * dt_s
    u_raw = gains.kp * error + integral - gains.kd * d_filt

    u = max(u_min, min(u_max, u_raw))
    if du_max is not None:
        u = u_prev + max(-du_max, min(du_max, u - u_prev))
    if anti_windup and u != u_raw and gains.ki != 0.0:
        # Conditional clamp: do not let the integrator push further into the limit.
        headroom = u - (gains.kp * error - gains.kd * d_filt)
        integral = headroom if abs(headroom) < abs(integral) else integral

    return u, PIDState(integral=integral, last_y=y, d_filt=d_filt, last_cmd=u)

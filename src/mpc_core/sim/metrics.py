"""Performance metrics for closed-loop motor runs (speed in RPM, SI otherwise)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class SimulationMetrics:
    # Speed regulation
    rise_time_s: float | None
    settling_time_s: float | None
    overshoot_pct: float
    steady_state_error_rpm: float
    max_abs_error_rpm: float
    mean_abs_error_rpm: float
    iae: float  # RPM s
    ise: float  # RPM^2 s
    itae: float  # RPM s^2
    speed_recovery_time_s: float | None
    # Electrical
    max_current_a: float
    rms_current_a: float
    mean_voltage_v: float
    max_voltage_v: float
    voltage_saturation_s: float
    current_limit_s: float
    electrical_energy_j: float
    # Mechanical (shaft output = K_t i w - B w^2)
    max_torque_nm: float
    mean_load_torque_nm: float
    mean_mech_power_w: float
    mechanical_energy_j: float
    # Efficiency (energy-weighted; None when no electrical energy is consumed)
    drive_efficiency: float | None
    motor_efficiency: float | None
    # Constraint accounting
    constraint_violation_steps: int

    def as_dict(self) -> dict:
        return asdict(self)


def _trapz(y: np.ndarray, dt: float) -> float:
    return float(np.sum(y) * dt)


def _last_reference_change(y_ref: np.ndarray) -> int:
    changed = np.nonzero(np.abs(np.diff(y_ref)) > 1e-9)[0]
    return int(changed[-1] + 1) if len(changed) else 0


def compute_metrics(
    *,
    time_s: np.ndarray,
    speed_rpm: np.ndarray,
    ref_rpm: np.ndarray,
    i_a: np.ndarray,
    v_applied: np.ndarray,
    torque_nm: np.ndarray,
    load_nm: np.ndarray,
    omega_rad_s: np.ndarray,
    v_saturated: np.ndarray,
    i_limited: np.ndarray,
    i_max: float,
    v_max: float,
    b_friction: float,
    power_stage_efficiency: float = 1.0,
    settling_band_pct: float = 2.0,
    load_change_at_s: float | None = None,
) -> SimulationMetrics:
    """Compute the scorecard from one recorded run.

    Settling, rise time and overshoot refer to the final reference segment
    (steps taken from the last reference change). ``load_change_at_s`` enables
    the speed-recovery time after a load step.
    """
    n = len(time_s)
    dt = float(time_s[1] - time_s[0]) if n > 1 else 1.0
    err = ref_rpm - speed_rpm
    abs_err = np.abs(err)
    iae = _trapz(abs_err, dt)
    ise = _trapz(err**2, dt)
    itae = _trapz(time_s * abs_err, dt)

    k0 = _last_reference_change(ref_rpm)
    final_ref = float(ref_rpm[-1])
    start_ref = float(ref_rpm[k0 - 1]) if k0 > 0 else float(speed_rpm[0])
    step = final_ref - start_ref
    seg_t = time_s[k0:] - time_s[k0]
    seg_y = speed_rpm[k0:]
    band = max(abs(final_ref) * settling_band_pct / 100.0, 0.005 * abs(step), 1.0)

    # Overshoot: excursion beyond the final reference in the direction of travel.
    if abs(step) > 1e-6:
        direction = np.sign(step)
        overshoot = max(0.0, float(np.max((seg_y - final_ref) * direction)))
        overshoot_pct = overshoot / abs(step) * 100.0
        frac = (seg_y - start_ref) / step
        t10 = np.nonzero(frac >= 0.1)[0]
        t90 = np.nonzero(frac >= 0.9)[0]
        rise = float(seg_t[t90[0]] - seg_t[t10[0]]) if len(t10) and len(t90) else None
    else:
        overshoot_pct = 0.0
        rise = None

    settling: float | None = None
    outside = np.nonzero(np.abs(seg_y - final_ref) > band)[0]
    if len(outside) == 0:
        settling = 0.0
    elif outside[-1] < len(seg_y) - 1:
        settling = float(seg_t[outside[-1] + 1])

    tail = slice(int(n * 0.9), n)
    ss_err = float(np.mean(err[tail]))

    recovery: float | None = None
    if load_change_at_s is not None:
        k_l = int(round(load_change_at_s / dt))
        if 0 < k_l < n:
            ref_l = ref_rpm[k_l:]
            dev = np.abs(speed_rpm[k_l:] - ref_l)
            band_l = max(1.0, 0.02 * float(np.max(np.abs(ref_l))))
            out = np.nonzero(dev > band_l)[0]
            if len(out) == 0:
                recovery = 0.0
            elif out[-1] < len(dev) - 1:
                recovery = float((out[-1] + 1) * dt)

    p_elec = v_applied * i_a
    p_shaft = torque_nm * omega_rad_s - b_friction * omega_rad_s**2  # motor shaft output
    p_load = load_nm * omega_rad_s  # useful power delivered into the load
    e_term = _trapz(np.maximum(p_elec, 0.0), dt)  # energy into the motor terminals
    e_shaft = _trapz(np.maximum(p_shaft, 0.0), dt)
    e_load = _trapz(np.maximum(p_load, 0.0), dt)
    # Motor efficiency: shaft output / terminal input (copper + viscous friction
    # losses). Drive (overall) efficiency: useful load energy / supply energy,
    # where the supply also covers the power-stage loss.
    e_supply = e_term / power_stage_efficiency
    motor_eff = e_shaft / e_term if e_term > 1e-9 else None
    drive_eff = e_load / e_supply if e_supply > 1e-9 else None

    violations = int(
        np.sum(np.abs(i_a) > i_max * 1.02) + np.sum(np.abs(v_applied) > v_max * (1 + 1e-9))
    )

    return SimulationMetrics(
        rise_time_s=rise,
        settling_time_s=settling,
        overshoot_pct=float(overshoot_pct),
        steady_state_error_rpm=ss_err,
        max_abs_error_rpm=float(np.max(abs_err)),
        mean_abs_error_rpm=float(np.mean(abs_err)),
        iae=iae,
        ise=ise,
        itae=itae,
        speed_recovery_time_s=recovery,
        max_current_a=float(np.max(np.abs(i_a))),
        rms_current_a=float(np.sqrt(np.mean(i_a**2))),
        mean_voltage_v=float(np.mean(v_applied)),
        max_voltage_v=float(np.max(np.abs(v_applied))),
        voltage_saturation_s=float(np.sum(v_saturated) * dt),
        current_limit_s=float(np.sum(i_limited) * dt),
        electrical_energy_j=float(np.sum(p_elec) * dt),
        max_torque_nm=float(np.max(np.abs(torque_nm))),
        mean_load_torque_nm=float(np.mean(load_nm)),
        mean_mech_power_w=float(np.mean(p_shaft)),
        mechanical_energy_j=float(np.sum(p_shaft) * dt),
        drive_efficiency=drive_eff,
        motor_efficiency=motor_eff,
        constraint_violation_steps=violations,
    )


# Scorecard column label -> SimulationMetrics attribute (single source for UI and report).
SCORECARD_COLUMNS: dict[str, str] = {
    "Rise [s]": "rise_time_s",
    "Settling [s]": "settling_time_s",
    "Overshoot [%]": "overshoot_pct",
    "Steady-state error [RPM]": "steady_state_error_rpm",
    "Max error [RPM]": "max_abs_error_rpm",
    "Mean abs error [RPM]": "mean_abs_error_rpm",
    "IAE [RPM·s]": "iae",
    "ISE [RPM²·s]": "ise",
    "ITAE [RPM·s²]": "itae",
    "Recovery [s]": "speed_recovery_time_s",
    "Max current [A]": "max_current_a",
    "RMS current [A]": "rms_current_a",
    "Mean voltage [V]": "mean_voltage_v",
    "Max voltage [V]": "max_voltage_v",
    "Voltage saturation [s]": "voltage_saturation_s",
    "Current limit [s]": "current_limit_s",
    "Energy [J]": "electrical_energy_j",
    "Max torque [N·m]": "max_torque_nm",
    "Mean load [N·m]": "mean_load_torque_nm",
    "Mean shaft power [W]": "mean_mech_power_w",
    "Mechanical energy [J]": "mechanical_energy_j",
    "Motor efficiency": "motor_efficiency",
    "Drive efficiency": "drive_efficiency",
}


def scorecard_row(m: SimulationMetrics) -> dict[str, float | None]:
    """One scorecard row (column label -> value) from a run's metrics."""
    return {label: getattr(m, attr) for label, attr in SCORECARD_COLUMNS.items()}

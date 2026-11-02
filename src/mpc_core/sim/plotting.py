"""Matplotlib figures for MPC vs PID motor runs (batch results and report)."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

from mpc_core.sim.metrics import SimulationMetrics
from mpc_core.sim.simulate import SimulationResult

COLORS = {"MPC": "#2563eb", "PID": "#71717a", "Opt. PID": "#0d9488", "LQR": "#d97706"}


def apply_plot_style() -> None:
    """Readable defaults."""
    mpl.rcParams.update(
        {
            "axes.grid": True,
            "font.size": 11,
            "lines.linewidth": 1.8,
            "figure.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def save_runs_figure(*, title: str, runs, path: Path) -> None:
    """Speed, armature current, voltage and torque for every controller in ``runs``."""
    apply_plot_style()
    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(10, 10), constrained_layout=True)
    names = {"pid": "PID", "optimized_pid": "Opt. PID", "lqr": "LQR", "mpc": "MPC"}
    first = next(iter(runs.items()))[1]
    axes[0].plot(first.time_s, first.ref_rpm, "k--", label="Reference", alpha=0.7)
    for cid, run in runs.items():
        name = names[cid]
        axes[0].plot(run.time_s, run.speed_rpm, label=name, color=COLORS[name])
        axes[1].plot(run.time_s, run.i_a, label=name, color=COLORS[name])
        axes[2].plot(run.time_s, run.v_applied, label=name, color=COLORS[name])
        axes[3].plot(run.time_s, run.torque_nm, label=name, color=COLORS[name])
    axes[3].plot(first.time_s, first.load_nm, "k:", label="Load torque", alpha=0.8)
    for sign in (-1, 1):
        axes[1].axhline(sign * first.i_max, color="#a1a1aa", ls="--", lw=1)
        axes[2].axhline(sign * first.v_max, color="#a1a1aa", ls="--", lw=1)
    axes[0].set_ylabel("Speed [RPM]")
    axes[1].set_ylabel("Armature current [A]")
    axes[2].set_ylabel("Applied voltage [V]")
    axes[3].set_ylabel("Torque [N m]")
    axes[3].set_xlabel("Time [s]")
    axes[0].set_title(title)
    axes[0].legend(loc="best", ncols=5)
    axes[3].legend(loc="best", ncols=5)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_comparison_figure(
    *,
    title: str,
    mpc: SimulationResult,
    pid: SimulationResult,
    path: Path,
) -> None:
    """MPC vs PID with the MPC load-torque estimate."""
    apply_plot_style()
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(10, 8), constrained_layout=True)
    axes[0].plot(mpc.time_s, mpc.ref_rpm, "k--", label="Reference", alpha=0.7)
    axes[0].plot(mpc.time_s, mpc.speed_rpm, label="MPC", color=COLORS["MPC"])
    axes[0].plot(pid.time_s, pid.speed_rpm, label="PID", color=COLORS["PID"], alpha=0.85)
    axes[0].set_ylabel("Speed [RPM]")
    axes[0].legend(loc="best")
    axes[0].set_title(title)

    axes[1].plot(mpc.time_s, mpc.v_applied, label="MPC voltage", color=COLORS["MPC"])
    axes[1].plot(pid.time_s, pid.v_applied, label="PID voltage", color=COLORS["PID"], alpha=0.85)
    axes[1].set_ylabel("Voltage [V]")
    axes[1].legend(loc="best")

    axes[2].plot(mpc.time_s, mpc.load_nm, "k:", label="True load torque")
    if mpc.d_hat is not None:
        axes[2].plot(mpc.time_s, mpc.d_hat, color=COLORS["MPC"], label="MPC estimate")
    axes[2].set_ylabel("Load torque [N m]")
    axes[2].set_xlabel("Time [s]")
    axes[2].legend(loc="best")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _fmt(v: float | None, spec: str = ".3g") -> str:
    return "—" if v is None else format(v, spec)


def format_metrics_table(mpc_m: SimulationMetrics, pid_m: SimulationMetrics) -> str:
    """Markdown comparison of the headline motor metrics."""
    rows = [
        ("Rise time [s]", "rise_time_s"),
        ("Settling time [s]", "settling_time_s"),
        ("Overshoot [%]", "overshoot_pct"),
        ("Steady-state error [RPM]", "steady_state_error_rpm"),
        ("IAE [RPM s]", "iae"),
        ("ISE [RPM² s]", "ise"),
        ("ITAE [RPM s²]", "itae"),
        ("Max current [A]", "max_current_a"),
        ("RMS current [A]", "rms_current_a"),
        ("Voltage saturation [s]", "voltage_saturation_s"),
        ("Current-limit active [s]", "current_limit_s"),
        ("Electrical energy [J]", "electrical_energy_j"),
        ("Drive efficiency", "drive_efficiency"),
    ]
    lines = ["| Metric | MPC | PID |", "| --- | --- | --- |"]
    for label, attr in rows:
        lines.append(f"| {label} | {_fmt(getattr(mpc_m, attr))} | {_fmt(getattr(pid_m, attr))} |")
    return "\n".join(lines)

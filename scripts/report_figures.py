#!/usr/bin/env python3
"""Figures for the DriveBench technical report (report/drivebench_report.tex).

Every figure is computed from simulation output; nothing is typed in. ``build_all``
takes ``{scenario_key: {controller_id: SimulationResult}}`` (what ``run_batch`` produces).
Run standalone to rebuild from ``report/figures/_results.pkl`` if it exists.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FIG = ROOT / "report" / "figures"

IDS = ("pid", "optimized_pid", "lqr", "mpc")
LABEL = {"pid": "PID", "optimized_pid": "Optimised PID", "lqr": "LQR", "mpc": "MPC"}
COLOR = {"pid": "#5B6770", "optimized_pid": "#1B998B", "lqr": "#E08E0B", "mpc": "#6D3FC0"}
STYLE = {"pid": "-", "optimized_pid": "--", "lqr": "-.", "mpc": "-"}
WIDTH = {"pid": 1.5, "optimized_pid": 1.6, "lqr": 1.8, "mpc": 2.3}
TITLE = {
    "motor_startup": "Motor startup",
    "speed_tracking": "Speed tracking",
    "load_step": "Sudden load",
    "load_removal": "Load removal",
    "voltage_saturation": "Voltage saturation",
    "current_protection": "Current protection",
    "model_mismatch": "Mismatch (+)",
    "model_mismatch_low": "Mismatch (−)",
    "sensor_noise": "Encoder noise",
    "variable_load": "Variable load",
    "reverse_operation": "Reversal",
}


def _style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#E3E6EA",
            "grid.linewidth": 0.7,
            "axes.edgecolor": "#8A949E",
            "figure.dpi": 150,
            "savefig.bbox": "tight",
        }
    )


def _line(ax, run, cid, y, **kw):
    ax.plot(run.time_s, y, color=COLOR[cid], ls=STYLE[cid], lw=WIDTH[cid], label=LABEL[cid], **kw)


def fig_step_panels(res) -> None:
    """Four zoomed speed responses (small multiples) with the reference as a thin step."""
    spec = [
        ("motor_startup", (0, 1.6), "Startup 0 → 1000 RPM"),
        ("load_step", (4.8, 7.2), "Load 0.05 → 0.10 N·m at 5 s"),
        ("reverse_operation", (2.8, 5.6), "Reversal +1000 → −1000 RPM"),
        ("sensor_noise", (3.5, 6.5), "Speed step with 15 RPM encoder noise"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.6))
    for ax, (key, (t0, t1), ttl) in zip(axes.ravel(), spec):
        runs = res[key]
        ref = runs["pid"]
        m = (ref.time_s >= t0) & (ref.time_s <= t1)
        ax.plot(ref.time_s[m], ref.ref_rpm[m], color="#222", lw=0.9, ls=":", label="Reference")
        for cid in IDS:
            r = runs[cid]
            mm = (r.time_s >= t0) & (r.time_s <= t1)
            ax.plot(r.time_s[mm], r.speed_rpm[mm], color=COLOR[cid], ls=STYLE[cid], lw=WIDTH[cid], label=LABEL[cid])
        ax.set_title(ttl, fontsize=9, loc="left", fontweight="bold")
        ax.set_xlabel("t [s]")
        ax.set_ylabel("speed [RPM]")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG / "fig_step_panels.png")
    plt.close(fig)


def fig_rank_heatmap(res) -> None:
    """IAE relative to the best controller in each scenario (1.00 = best)."""
    keys = [k for k in TITLE if k in res]
    mat = np.array([[res[k][c].metrics.iae for c in IDS] for k in keys])
    ratio = mat / mat.min(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    im = ax.imshow(np.log10(ratio), cmap="YlGnBu_r", vmin=0, vmax=np.log10(max(ratio.max(), 2.0)), aspect="auto")
    ax.set_xticks(range(4), [LABEL[c] for c in IDS], rotation=0)
    ax.set_yticks(range(len(keys)), [TITLE[k] for k in keys])
    ax.xaxis.tick_top()
    ax.grid(False)
    for i in range(len(keys)):
        for j in range(4):
            best = ratio[i, j] < 1.005
            ax.text(j, i, f"{ratio[i, j]:.2f}" + ("★" if best else ""), ha="center", va="center", fontsize=8,
                    color="white" if np.log10(ratio[i, j]) < 0.55 * np.log10(max(ratio.max(), 2.0)) else "#102a43",
                    fontweight="bold" if best else "normal")
    ax.set_title("IAE relative to the best controller (1.00★ = lowest)", fontsize=9, loc="left", pad=26)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_rank_heatmap.png")
    plt.close(fig)


def fig_phase_plane(res) -> None:
    """Armature current against speed: how each controller approaches the current limit."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2))
    for ax, key, ttl in zip(axes, ("motor_startup", "reverse_operation"), ("Startup 0 → 1000 RPM", "Reversal +1000 → −1000 RPM")):
        for cid in IDS:
            r = res[key][cid]
            ax.plot(r.speed_rpm, r.i_a, color=COLOR[cid], ls=STYLE[cid], lw=WIDTH[cid], label=LABEL[cid])
        imax = res[key]["pid"].i_max
        ax.axhline(imax, color="#C0392B", lw=1, ls="--")
        ax.text(ax.get_xlim()[0], imax + 0.2, "I_max", color="#C0392B", fontsize=8, va="bottom")
        ax.set_title(ttl, loc="left", fontsize=9, fontweight="bold")
        ax.set_xlabel("speed [RPM]")
        ax.set_ylabel("armature current [A]")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(FIG / "fig_phase_plane.png")
    plt.close(fig)


def fig_limit_timeline(res) -> None:
    """When the drive's current protection was active, per controller (current protection)."""
    key = "current_protection"
    fig, ax = plt.subplots(figsize=(7.2, 1.9))
    for k, cid in enumerate(IDS):
        r = res[key][cid]
        t = r.time_s
        dt = t[1] - t[0]
        on = r.i_limited.astype(bool)
        starts = np.flatnonzero(on & ~np.r_[False, on[:-1]])
        ends = np.flatnonzero(on & ~np.r_[on[1:], False])
        for s, e in zip(starts, ends):
            ax.barh(k, (e - s + 1) * dt, left=t[s], height=0.55, color=COLOR[cid])
        ax.text(t[-1] + 0.1, k, f"{r.metrics.current_limit_s:.2f} s", va="center", fontsize=8)
    ax.set_yticks(range(4), [LABEL[c] for c in IDS])
    ax.invert_yaxis()
    ax.set_xlabel("t [s]")
    ax.set_xlim(0, res[key]["pid"].time_s[-1] + 1.4)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_limit_timeline.png")
    plt.close(fig)


def fig_cost_vs_error(res) -> None:
    """Error against computation: geometric-mean IAE ratio versus mean execution time."""
    keys = [k for k in TITLE if k in res]
    mat = np.array([[res[k][c].metrics.iae for c in IDS] for k in keys])
    ratio = mat / mat.min(axis=1, keepdims=True)
    gmean = np.exp(np.log(ratio).mean(axis=0))
    ms = [np.mean([res[k][c].exec_ms.mean() for k in keys]) for c in IDS]
    fig, ax = plt.subplots(figsize=(4.6, 3.1))
    for g, t, c in zip(gmean, ms, IDS):
        ax.scatter(t, g, s=90, color=COLOR[c], zorder=3)
        ax.annotate(LABEL[c], (t, g), textcoords="offset points", xytext=(8, 6), fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("mean execution time per 10 ms sample [ms] (log)")
    ax.set_ylabel("geometric-mean IAE / best")
    ax.set_title("Error against computation", loc="left", fontsize=9, fontweight="bold")
    ax.set_ylim(0.95, max(gmean) * 1.12)
    fig.tight_layout()
    fig.savefig(FIG / "fig_cost_vs_error.png")
    plt.close(fig)


def fig_lqr_poles() -> None:
    """Open-loop discrete plant poles and the LQR closed-loop poles in the z-plane."""
    from mpc_core.sim.config import default_demo_config
    from mpc_core.sim.lqr import LqrWeights, design_lqr

    cfg = default_demo_config()
    d = design_lqr(cfg.motor, cfg.dt_s, LqrWeights.recommended())
    ol = np.linalg.eigvals(d.Ad)
    cl = d.eigenvalues
    th = np.linspace(0, 2 * np.pi, 300)
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    ax.plot(np.cos(th), np.sin(th), color="#8A949E", lw=0.9)
    ax.scatter(ol.real, ol.imag, marker="o", facecolor="none", edgecolor="#5B6770", s=60, label="open loop (with integrator)")
    ax.scatter(cl.real, cl.imag, marker="x", color=COLOR["lqr"], s=60, lw=2, label="LQR closed loop")
    ax.set_xlim(-0.1, 1.15)
    ax.set_ylim(-0.6, 0.6)
    ax.set_aspect("equal")
    ax.set_xlabel("Re z")
    ax.set_ylabel("Im z")
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax.set_title("z-plane poles, Ts = 10 ms", loc="left", fontsize=9, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "fig_lqr_poles.png")
    plt.close(fig)


def fig_robustness(res) -> None:
    """Dot plot of IAE ratio for the nominal, mismatched and noisy runs."""
    cases = [
        ("speed_tracking", "nominal tracking"),
        ("model_mismatch", "R +20 %, J +30 %, B +25 %"),
        ("model_mismatch_low", "R, J, B lowered"),
        ("sensor_noise", "15 RPM encoder noise"),
    ]
    cases = [c for c in cases if c[0] in res]
    fig, ax = plt.subplots(figsize=(6.2, 2.7))
    for row, (key, ttl) in enumerate(cases):
        vals = np.array([res[key][c].metrics.iae for c in IDS])
        ratio = vals / vals.min()
        ax.hlines(row, 1, ratio.max(), color="#D5DAE0", lw=2, zorder=1)
        for c, v in zip(IDS, ratio):
            ax.scatter(v, row, s=70, color=COLOR[c], zorder=3, label=LABEL[c] if row == 0 else None)
    ax.set_yticks(range(len(cases)), [c[1] for c in cases])
    ax.invert_yaxis()
    ax.set_xlabel("IAE relative to the best controller in that case")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, ncol=4, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout()
    fig.savefig(FIG / "fig_robustness.png")
    plt.close(fig)


def build_all(res) -> None:
    _style()
    FIG.mkdir(parents=True, exist_ok=True)
    fig_step_panels(res)
    fig_rank_heatmap(res)
    fig_phase_plane(res)
    fig_limit_timeline(res)
    fig_cost_vs_error(res)
    fig_lqr_poles()
    fig_robustness(res)
    print(f"wrote report figures under {FIG}")


if __name__ == "__main__":
    pkl = FIG / "_results.pkl"
    if not pkl.exists():
        raise SystemExit("missing report/figures/_results.pkl: run scripts/rebuild_report_metrics.py")
    build_all(pickle.loads(pkl.read_bytes()))

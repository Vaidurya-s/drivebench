#!/usr/bin/env python3
"""Build architecture and summary bar charts for the academic report.

Reads ``report/metrics_summary.json`` (run ``scripts/rebuild_report_metrics.py``
first) and writes PNGs under ``report/figures/``.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
FIG = REPORT / "figures"
METRICS = REPORT / "metrics_summary.json"

SHORT = {
    "motor_startup": "Startup",
    "speed_tracking": "Tracking",
    "load_step": "Load step",
    "load_removal": "Load removal",
    "voltage_saturation": "V saturation",
    "current_protection": "Current prot.",
    "model_mismatch": "Mismatch +",
    "model_mismatch_low": "Mismatch −",
    "sensor_noise": "Noise",
    "variable_load": "Var. load",
    "reverse_operation": "Reverse",
}


def _load():
    return json.loads(METRICS.read_text())


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.set_title("Closed-loop simulation architecture", fontsize=12, pad=8)

    def box(x, y, w, h, text, color):
        p = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15",
            facecolor=color, edgecolor="#111827", linewidth=1.2,
        )
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8)

    box(0.2, 2.3, 2.3, 1.2, "Speed + current\nsensors\n(encoder noise)", "#F3F4F6")
    box(3.0, 2.3, 2.9, 1.2, "Offset-free MPC\n[i, w] model + torque est.\nSLSQP, V / dV / I limits", "#EDE9FE")
    box(6.4, 2.3, 2.7, 1.2, "Motor drive\nV sat, slew limit,\ncurrent protection", "#D1FAE5")
    box(9.6, 2.3, 3.0, 1.2, "PMDC motor twin\nL di/dt, J dw/dt, RK4\n1 ms step", "#FFEDD5")
    box(0.2, 0.4, 2.6, 1.1, "Hand-tuned PID\n(filtered D, anti-windup)", "#DBEAFE")
    box(3.0, 0.4, 2.9, 1.1, "Optimised PID\ncomposite objective\nSciPy L-BFGS-B", "#CCFBF1")
    box(6.4, 0.4, 2.7, 1.1, "LQR with integral\naction (LQI), DARE gain\nTs = 10 ms", "#FEF3C7")

    for (x0, y0, x1, y1) in [
        (2.5, 2.9, 3.0, 2.9),
        (5.9, 2.9, 6.4, 2.9),
        (9.1, 2.9, 9.6, 2.9),
        (11.1, 2.3, 11.1, 1.6),
        (11.1, 1.6, 1.35, 1.6),
        (1.35, 1.6, 1.35, 2.3),
        (1.5, 1.5, 3.0, 2.5),
        (4.45, 1.5, 4.45, 2.3),
        (7.75, 1.5, 7.75, 2.3),
    ]:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="->", color="#374151", lw=1.2))

    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / "architecture.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def _grouped(ax, labels, series, colors, ylabel, title) -> None:
    x = np.arange(len(labels))
    w = 0.2
    for k, (name, vals) in enumerate(series):
        ax.bar(x + (k - 1.5) * w, vals, w, label=name, color=colors[k])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _series(data: dict, metric: str, keys: list[str]):
    out = []
    for ctl in ("pid", "optimized_pid", "lqr", "mpc"):
        out.append([data["scenarios"][k][ctl][metric] or 0.0 for k in keys])
    return list(zip(("PID", "Opt. PID", "LQR", "MPC"), out))


def iae_bars(data: dict) -> None:
    keys = [k for k in SHORT if k in data["scenarios"]]
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    _grouped(
        ax, [SHORT[k] for k in keys], _series(data, "iae", keys),
        ["#6B7280", "#0D9488", "#D97706", "#2563EB"], "IAE [RPM s]",
        "Integrated absolute speed error by scenario",
    )
    fig.tight_layout()
    fig.savefig(FIG / "iae_bars.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def current_limit_bars(data: dict) -> None:
    keys = ["motor_startup", "speed_tracking", "voltage_saturation", "current_protection", "reverse_operation"]
    keys = [k for k in keys if k in data["scenarios"]]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    _grouped(
        ax, [SHORT[k] for k in keys], _series(data, "current_limit_s", keys),
        ["#6B7280", "#0D9488", "#D97706", "#2563EB"], "Current protection active [s]",
        "Time the drive's current protection was limiting",
    )
    fig.tight_layout()
    fig.savefig(FIG / "current_limit_bars.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def robustness_bars(data: dict) -> None:
    rob = data["robustness_model_mismatch"]
    labels = ["MPC", "Opt. PID\n(frozen gains)", "Opt. PID\n(retuned on mismatch)"]
    vals = [
        rob["mpc"]["iae"],
        rob["optimized_pid_frozen_nominal_gains"]["iae"],
        rob["optimized_pid_retuned_on_mismatch"]["iae"],
    ]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    ax.bar(labels, vals, color=["#2563EB", "#0D9488", "#5EEAD4"])
    ax.set_ylabel("IAE [RPM s]")
    ax.set_title("Robustness under plant mismatch")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "robustness_bars.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def _fmt(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}"


# (label, metric key, decimals); lower is better for every column shown.
TABLE_COLS = [
    ("Settling [s]", "settling_time_s", 2),
    ("Overshoot [%]", "overshoot_pct", 1),
    ("IAE [RPM s]", "iae", 0),
    ("Peak I [A]", "max_current_a", 2),
    ("Current-limited [s]", "current_limit_s", 2),
]



def tables(data: dict) -> None:
    """Write generated results tables for report.md and main.tex (never hand-edit)."""
    ctl = (("pid", "PID"), ("optimized_pid", "Opt. PID"), ("lqr", "LQR"), ("mpc", "MPC"))
    md = [
        "| Scenario | Controller | " + " | ".join(c[0] for c in TABLE_COLS) + " |",
        "| --- | --- | " + " | ".join("---:" for _ in TABLE_COLS) + " |",
    ]
    blocks = []
    for sc in data["scenarios"].values():
        rows = []
        for ci, (ck, cl) in enumerate(ctl):
            md.append(
                f"| {sc['title'] if ci == 0 else ''} | {cl} | "
                + " | ".join(_fmt(sc[ck][mk], nd) for _, mk, nd in TABLE_COLS)
                + " |"
            )
            cells = []
            for _, mk, nd in TABLE_COLS:
                vals = [sc[k][mk] for k, _ in ctl if sc[k][mk] is not None]
                cell = _fmt(sc[ck][mk], nd)
                # Best (lowest) per column is bold; blue bold when MPC is the best.
                # Peak current and current-limited time are context, not "best" metrics.
                if (
                    mk in ("settling_time_s", "overshoot_pct", "iae")
                    and sc[ck][mk] is not None
                    and round(sc[ck][mk], nd) == round(min(vals), nd)
                ):
                    cell = rf"\mpcbest{{{cell}}}" if ck == "mpc" else rf"\textbf{{{cell}}}"
                cells.append(cell)
            first = rf"\multirow{{4}}{{*}}{{{sc['title']}}}" if ci == 0 else ""
            rows.append(f"{first} & {cl} & " + " & ".join(cells) + r" \\")
        blocks.append("\n".join(rows))
    (REPORT / "results_tables.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    head = (
        "\\begin{tabular}{@{}llrrrrr@{}}\n\\toprule\nScenario & Controller & "
        + " & ".join(c[0].replace("%", r"\%") for c in TABLE_COLS)
        + " \\\\\n\\midrule\n"
    )
    body = "\n\\midrule\n".join(blocks) + "\n\\bottomrule\n\\end{tabular}\n"
    (REPORT / "results_table.tex").write_text(head + body, encoding="utf-8")


def main() -> None:
    if not METRICS.exists():
        raise SystemExit(f"missing {METRICS}; run scripts/rebuild_report_metrics.py first")
    data = _load()
    FIG.mkdir(parents=True, exist_ok=True)
    architecture()
    iae_bars(data)
    current_limit_bars(data)
    robustness_bars(data)
    tables(data)
    print(f"wrote charts under {FIG}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the DriveBench static mirror data under web/.

Copies the precomputed simulation JSON from ``data/ui`` and writes the LQR design,
plant matrices and SVG diagrams as static files, all from the same Python code the
Streamlit app uses. Run by Vercel as the build command (needs numpy and scipy).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from mpc_core.sim.config import default_demo_config  # noqa: E402
from mpc_core.sim.diagrams import (  # noqa: E402
    drive_architecture,
    four_controller_architecture,
    lqr_design_process,
)
from mpc_core.sim.lqr import LqrWeights, design_lqr  # noqa: E402

WEB = ROOT / "web"
DATA_SRC = ROOT / "data" / "ui"
DATA_DST = WEB / "data"


def main() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    if DATA_DST.exists():
        shutil.rmtree(DATA_DST)
    shutil.copytree(DATA_SRC, DATA_DST)

    diagrams = WEB / "diagrams"
    diagrams.mkdir(exist_ok=True)
    (diagrams / "drive.html").write_text(drive_architecture(), encoding="utf-8")
    (diagrams / "controllers.html").write_text(four_controller_architecture(), encoding="utf-8")
    (diagrams / "lqr.html").write_text(lqr_design_process(), encoding="utf-8")

    cfg = default_demo_config()
    m = cfg.motor
    d = design_lqr(m, cfg.dt_s, LqrWeights.recommended())
    w = d.weights
    (DATA_DST / "lqr.json").write_text(
        json.dumps(
            {
                "weights": {"q_current": w.q_current, "q_speed": w.q_speed,
                            "q_integral": w.q_integral, "r_voltage": w.r_voltage},
                "K": d.K[0].tolist(),
                "Q_diag": np.diag(d.Q).tolist(),
                "R": float(d.R[0, 0]),
                "P": d.P.tolist(),
                "eig_re": d.eigenvalues.real.tolist(),
                "eig_im": d.eigenvalues.imag.tolist(),
                "rank": d.controllability_rank,
                "residual": d.riccati_residual,
                "design_time_ms": d.design_time_ms,
                "ts_s": d.ts_s,
            }
        ),
        encoding="utf-8",
    )
    A, B, E = m.state_matrices()
    num, den = m.transfer_function()
    (DATA_DST / "plant.json").write_text(
        json.dumps(
            {
                "params": {k: getattr(m, k) for k in
                           ("R_a", "L_a", "K_t", "K_e", "J", "B", "T_L", "V_max", "I_max", "omega_max_rpm")},
                "A": A.tolist(), "B": B.ravel().tolist(), "E": E.ravel().tolist(),
                "num": num.tolist(), "den": den.tolist(),
                "poles": np.roots(den).tolist(),
                "tau_e_ms": m.tau_e * 1e3,
                "slew_v_per_s": cfg.drive.slew_v_per_s,
            }
        ),
        encoding="utf-8",
    )
    print(f"Synced {DATA_SRC} -> {DATA_DST}; wrote diagrams, lqr.json, plant.json")


if __name__ == "__main__":
    main()

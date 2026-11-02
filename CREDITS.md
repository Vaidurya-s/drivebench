# Credits and third-party references

CasADi remains an external PyPI dependency (LGPL-3.0) and is not vendored.

## Matplotlib plot layout and typography

- **Project:** do-mpc (documentation and examples)
- **URL:** https://github.com/do-mpc/do-mpc
- **Licence:** GNU LGPL-3.0 (library); we did **not** import do-mpc or copy its
  source. Our `sim/plotting.py` only applies similar Matplotlib `rcParams`
  (grid, line width, shared-axis subplots) described in the public getting
  started guide.
- **Reference:** https://www.do-mpc.com/en/latest/getting_started.html

## Python Control (python-control)

- **Project:** python-control
- **URL:** https://github.com/python-control/python-control
- **Licence:** BSD-3-Clause
- **Use:** Documentation examples for step-response metrics and PID tuning
  workflow informed our choice of IAE/ISE reporting and discrete PID structure.
  No code was copied from python-control.

## SciPy optimisation

- **Project:** SciPy
- **URL:** https://github.com/scipy/scipy
- **Licence:** BSD-3-Clause
- **Use:** `scipy.optimize.minimize` (SLSQP in `mpc.py` and `mpc_motor.py`, L-BFGS-B in `sim/pid_tune.py`) and `scipy.linalg.expm` for the discretised motor model.

## IBM Plex

- **Project:** IBM Plex Sans and IBM Plex Mono
- **URL:** https://github.com/IBM/plex
- **Licence:** SIL Open Font License 1.1
- **Use:** Interface and numeric typography, loaded from Google Fonts at runtime with system
  fallbacks. Nothing is bundled.

## LQR design

- **Reference:** Linear-quadratic regulator with integral action; discrete algebraic Riccati
  equation via `scipy.linalg.solve_discrete_are` (SciPy, BSD-3-Clause). No python-control code is
  used.

## Upstream project

DriveBench started from the MPC Heater Lab at https://github.com/Vinayak-RZ/model-predictive-control.
The upstream repository has no LICENSE file at the time of writing, so reuse terms are unspecified;
confirm with the upstream author before any public redistribution.

## Streamlit

- **Project:** Streamlit
- **URL:** https://github.com/streamlit/streamlit
- **Licence:** Apache-2.0
- **Use:** Interactive UI in `app.py` (dependency only).

## CasADi

- **Project:** CasADi
- **URL:** https://web.casadi.org/
- **Licence:** GNU LGPL-3.0
- **Use:** PMDC motor twin RK4 step in `twin/pmdc.py` (pip dependency `casadi==3.8.2`).

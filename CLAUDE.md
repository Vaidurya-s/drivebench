# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The repo root is the `model-predictive-control/` folder (its own git repo, nested inside `ICD/`). See also `AGENTS.md` for report/commit conventions.

## Commands

Python >=3.12 (`.python-version`; Streamlit Cloud must also use 3.12). Scripts import `mpc_core` directly, so either `pip install -e ".[dev]"` or set `PYTHONPATH=src`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"

python3 -m pytest -q                        # all tests (pythonpath = src and repo root)
python3 -m pytest tests/test_motor_mpc.py -q
python3 -m pytest tests/test_drive.py::test_estop_forces_zero_and_latches -q

python3 examples/run_simulations.py         # all scenarios -> results/
python3 scripts/precompute_ui_data.py       # data/ui/*.json + frozen optimised-PID gains (~10 min)
python3 scripts/rebuild_report_metrics.py   # report/metrics_summary.json + figures
python3 scripts/rebuild_report_charts.py    # report tables and number macros (numbers.tex)
streamlit run app.py
```

`scripts/rebuild_academic_report.sh` rebuilds metrics, charts and the LaTeX PDF. `scripts/sync_web_data.py` rebuilds the static Vercel mirror data in `web/` (run it after `precompute_ui_data.py`); the `video/` exporters belong to the retired heater showcase (stale).

## Architecture

DriveBench compares hand-tuned PID, optimised PID, an integral-augmented LQR (LQI) and offset-free MPC regulating the speed of a PMDC motor through a shared drive. All code is the `mpc_core` package under `src/`.

- `twin/pmdc.py` — `PMDCParams` (single home of motor numbers, validated ranges, A/B/E matrices, transfer function, equilibrium), scalar RK4 `step_pmdc` and the CasADi step; `codegen.py` emits matching C.
- `sim/plant.py` — plant state and RK4 stepping (the plant may use mismatched parameters). `sim/drive.py` — `MotorDrive`: enable/e-stop, slew, ±V_max·bus, current protection as a voltage window (not state clipping).
- `identified.py` — `MotorStateSpaceModel`: 2-state `[i_a, omega]` ZOH model of the **nominal** motor, cached condensed prediction matrices (the original ARX `IdentifiedLinearModel` remains for generic tests).
- `mpc.py` — public `solve`/`refresh_disturbance`; the motor model dispatches to `mpc_motor.py` (SLSQP QP with analytic gradient, linear voltage-rate and predicted-current constraints, move blocking, joint load-torque + voltage disturbance observer, reference preview).
- `sim/pid.py` (positional PID, filtered D on measurement, anti-windup against the *applied* voltage, bumpless start) and `sim/pid_tune.py` (L-BFGS-B on a composite objective `TuneWeights`). The optimised PID is tuned once on `speed_tracking` and frozen in `data/ui/optimized_pid.json` (`playground.baseline_optimized_pid`).
- `sim/lqr.py` — LQI design (`design_lqr`, `LqrWeights`, `LqrDesign`) and `lqr_step`; no Streamlit import. See `docs/LQR.md`.
- `sim/simulate.py` — the single closed-loop path (`run_closed_loop`, `build_inputs`): controller every 10 ms, plant RK4 at 1 ms with zero-order hold. `sim/scenarios.py` — ten reproducible scenarios and profile builders. `sim/metrics.py` — scorecard metrics (`SCORECARD_COLUMNS`). `sim/batch.py` — batch runs shared by `examples/` and `scripts/`.
- UI: `app.py` is a thin `st.navigation` entry over `ui_pages/`. Pages read precomputed JSON from `data/ui/` through `sim/ui_cache.py`; a cache miss (custom motor, edited sliders) simulates live. `sim/motor_view.py` is the self-contained HTML/JS shaft animation. `path_setup.py` puts `src/` on `sys.path` for Streamlit Cloud.

## Conventions that matter

- Fairness: all controllers share plant, drive, initial state, reference, load, bus profile and noise realisation; MPC always predicts with the nominal motor, mismatch is plant-only.
- Changing controller defaults, scenarios or the drive invalidates `data/ui/`, `results/` and `report/` numbers: regenerate with the scripts above and update README/report in the same change. Never hand-edit numbers.
- MPC objective is scaled by `1e-6` internally (SLSQP fails without it); weights act on RPM² and V².
- Prose: say "permanent-magnet DC (PMDC) motor" once then "motor"; British spelling in the academic report; avoid course-forbidden product/part codenames.
- Conventional Commits, lowercase imperative; no force-push to shared branches.

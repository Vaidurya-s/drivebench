# Notes for future agents

## Repo purpose

Coursework lab: offset-free SISO MPC vs PID vs scenario-tuned PID on a permanent-magnet DC (PMDC) motor speed drive (`src/mpc_core/`, Streamlit `app.py`). The plant was converted from an induction heater; the architecture (MPC, PID, optimised PID, scorecard, precomputed UI data) is the same. Educational / illustrative parameters only.

## Branching and report work

- Academic PDF lives under `report/` (`main.tex`, `report.pdf`, `figures/`, `metrics_summary.json`). Rebuild with `bash scripts/rebuild_academic_report.sh` from the repo root (see `report/README.md`).
- MPC defaults (horizon 60, 6 blocked moves, `q_T=50`, `r=5000`, observer gain 0.1) live in `sim/config.py`; the solver is `mpc_motor.py`. Tests in `tests/` must stay green (`pytest`).
- When metrics or claims change, update `README.md` proof table, `results/` JSON/plots/markdown, and `report/report.md` / `HOW-IT-WORKS.md` **in the same change set** as the number change. Never invent figures for the PDF or the UI; run the rebuild scripts. The UI shows only real simulation output (the old "presentation" overlay that reshaped traces was removed on purpose).
- Controller or scenario changes invalidate `data/ui/`: rerun `python scripts/precompute_ui_data.py` (it also re-tunes and freezes the optimised PID).
- Prefer Conventional Commits, lowercase imperative, small focused commits. Commit identity for this repo: `Vinayak-RZ <179278780+Vinayak-RZ@users.noreply.github.com>`. No force-push to shared branches.

## Hard constraints

- Do not use the course-forbidden product or part codenames in prose, code, or docs. Run the pre-PR content grep from the course brief before opening a pull request.
- Say **permanent-magnet DC (PMDC) motor** once, then **motor**. British spelling in the academic report.
- Motor numbers live only in `PMDCParams` (`twin/pmdc.py`). Do not hardcode them elsewhere.
- Every controller must go through the same `MotorDrive` and see the same reference, load, bus and noise arrays (`tests/test_fairness.py`).
- Do not commit secrets, `.venv/`, or large unrelated binaries. `report/report.pdf` and `report/figures/` are intentional deliverables.
- `video/` and `web/` (the Vercel mirror) still describe the retired heater lab and are stale; `scripts/export_video_data.py` and `build_video_bundle.py` exit with an explanation.

## Useful entry points

| Task | Start here |
| --- | --- |
| Motor equations, parameters, validation | `src/mpc_core/twin/pmdc.py` |
| Drive (saturation, slew, current protection) | `src/mpc_core/sim/drive.py` |
| MPC solve / observer / constraints | `src/mpc_core/mpc.py` (dispatch), `src/mpc_core/mpc_motor.py` |
| Closed loop, noise, mismatch | `src/mpc_core/sim/simulate.py` |
| Scenarios and playground presets | `src/mpc_core/sim/scenarios.py`, `playground.py` |
| Metrics and scorecard columns | `src/mpc_core/sim/metrics.py` |
| Defaults | `src/mpc_core/sim/config.py` |
| Batch runs / report numbers | `src/mpc_core/sim/batch.py`, `scripts/rebuild_report_metrics.py` |
| Course PDF | `report/main.tex`, `report/README.md` |
| UI | `app.py`, `ui_pages/`, `sim/motor_view.py` |

# Industrial DC Motor Control Lab

<p align="center">
  <img src="assets/mpc-infographic.png" width="920" alt="Model Predictive Control infographic: optimiser, simulation model, and plant feedback loop">
</p>

<p align="center">
  <strong>Offset-free MPC vs hand-tuned PID vs optimised PID regulating the speed of a permanent-magnet DC motor drive.</strong>
</p>

<p align="center">
  <a href="#quick-start"><b>Quick start</b></a> ·
  <a href="#interactive-app"><b>Interactive app</b></a> ·
  <a href="#proof-batch-metrics"><b>Proof</b></a> ·
  <a href="docs/EXPLAINER.md"><b>Explainer</b></a> ·
  <a href="docs/THEORY.md"><b>Theory</b></a> ·
  <a href="HOW-IT-WORKS.md"><b>How it works</b></a> ·
  <a href="report/report.md"><b>Report</b></a>
</p>

A motor speed drive of the kind that turns conveyors, pumps and machine axes: the controller sets the armature voltage, a shared drive enforces voltage, slew and current limits, and a simulated permanent-magnet DC (PMDC) motor responds. Ten reproducible scenarios, a multipage Streamlit lab with precomputed data for fast opens, a 2D shaft replay, and batch results under `results/`.

This repository began as an MPC heater lab. The plant, drive, scenarios, metrics and UI are now the motor; the controllers, comparison framework, scorecard, tests and deployment setup are the same architecture.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
python3 -m pytest -q
python3 examples/run_simulations.py
python3 scripts/precompute_ui_data.py   # also re-tunes and freezes the optimised PID
streamlit run app.py
```

### Deploy

- **Streamlit Community Cloud** — full interactive lab. Align with
  [file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)
  and [app dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies):
  - **Main file:** `app.py` (repo root; multipage via `st.navigation` + `ui_pages/`).
  - **Dependencies:** root `requirements.txt` only (no `packages.txt`; no `-e .`).
    `app.py` adds `src/` to `sys.path` so `mpc_core` imports resolve. No new dependency was added for the motor lab.
  - **Python:** Advanced settings → **3.12** (matches `.python-version`). On 3.13/3.14,
    Cloud may build numpy/scipy/pandas from source and hang.
  - After a push, use **Reboot app** so the new entrypoint is picked up.
- **Vercel static mirror (`web/`) and the showcase video (`video/`)** still show the retired heater lab and are **stale**; they were not ported. Regenerating them needs a redesign for the motor scenarios.

## Interactive app

Theme: `.streamlit/config.toml` (cobalt accent `#2F6FEB`).

- **Overview** — landing page and MPC loop diagram.
- **Playground** — presets (speed step, load step, load removal, periodic load, noisy encoder, tight limits, plant mismatch, reverse) and sliders for reference, load, noise, mismatch, drive limits and controller knobs. Four synchronised panels (speed, armature current, voltage, torque) for all three controllers, a key-metrics table, and an animated **motor view** that replays the shaft with speed, direction, current, voltage, load and a limit indicator. A **Motor configuration** panel edits every motor parameter (with range validation and a restore-defaults button); custom motors simulate live.
- **Step-through** — walk one MPC horizon at a time: predicted speed and armature current, planned voltage, load-torque estimate.
- **Scorecard** — the same ten scenarios as the batch run, with a metric explorer.

Screenshots: `python scripts/capture_streamlit_screenshots.py` with the app running (needs Playwright).

## Proof (batch metrics)

Real output of `scripts/rebuild_report_metrics.py` (`report/metrics_summary.json`); the same numbers as the Scorecard page. Optimised PID uses the gains found once on `speed_tracking` (Kp 0.0326 V/RPM, Ki 0.131, Kd 0) and is **not** retuned per scenario. Every controller sees the same reference, load, bus and noise arrays and goes through the same drive.

| Scenario | Metric | MPC | PID | Optimised PID |
| --- | --- | --- | --- | --- |
| Motor startup (0→1000 RPM) | Settling [s] | **0.76** | 1.84 | 0.92 |
| Speed tracking (4 steps) | IAE [RPM·s] | **1071** | 1854 | 1660 |
| Load step (0.05→0.10 N·m) | IAE [RPM·s] | **3** | 35 | 8 |
| Variable load | IAE [RPM·s] | **45** | 275 | 96 |
| Sensor noise (15 RPM σ) | IAE [RPM·s] | **103** | 181 | 160 |
| Reverse (±1000 RPM) | Settling [s] | **0.69** | 2.37 | 1.44 |
| Voltage saturation (bus sag) | IAE [RPM·s] | **3307** | 4122 | 4092 |
| Current protection | Time current-limited [s] | **4.34** | 9.18 | 9.71 |
| Model mismatch (R +20 %, J +30 %, B +25 %) | IAE [RPM·s] | **1290** | 1794 | 1700 |

Read these with the caveats in mind:

- The MPC knows the nominal motor model and uses the measured armature current; the PID loops use speed only. That is the point of the comparison, not a like-for-like feedback structure.
- The load-step and load-removal differences are mostly the MPC's disturbance estimator reacting within a sample or two. A PID with a larger integral gain would close part of the gap, at the price of noise sensitivity and overshoot (see the noise scenario).
- Where the drive's limits dominate (`voltage_saturation`, `current_protection`) the controllers are close, because the actuator, not the algorithm, sets the best achievable response.
- The weights, horizon and observer gain are hand-set; no stability proof is claimed. Parameters are illustrative.
- Under ±20 % winding-resistance error the drive's current limit can be exceeded transiently (peak 9.1 A against an 8 A limit in the low-resistance corner) before feedback backs the voltage off.

All metrics (rise time, steady-state error, ITAE, RMS current, energy, motor and drive efficiency, recovery time, …) are in `results/metrics_summary.json` and `results/<scenario>_metrics.md`. Per-scenario figures are `results/<scenario>.png`.

| Speed tracking | Load step | Current protection |
| :---: | :---: | :---: |
| <img src="results/speed_tracking.png" width="280" alt="Speed tracking"> | <img src="results/load_step.png" width="280" alt="Load step"> | <img src="results/current_protection.png" width="280" alt="Current protection"> |

## How it works

```text
 encoder (+noise) ──┐
 current sensor ────┼─► offset-free MPC (SciPy SLSQP, [i, ω] model + torque/voltage estimates)
                    │           │ V_cmd                 PID / optimised PID ◄─ speed
                    ▼           ▼                              │
              ┌──────────────── motor drive ◄──────────────────┘
              │   enable · slew limit · ±V_max · current protection
              ▼ V_a
        PMDC motor twin  (L di/dt, J dω/dt, RK4 at 1 ms; controller every 10 ms)
```

Plain story: [`docs/EXPLAINER.md`](docs/EXPLAINER.md) · Maths and modelling: [`docs/THEORY.md`](docs/THEORY.md) · Engineering notes: [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md) · Course write-up: [`report/report.pdf`](report/report.pdf) · source [`report/main.tex`](report/main.tex) · notes [`report/README.md`](report/README.md)

The actual plant, the MPC's prediction model, the drive and the measurement model are four separate pieces of code; `docs/THEORY.md` §5 maps them.

Educational use. Licences: [`CREDITS.md`](CREDITS.md).

# How DriveBench works: controllers, drive and motor twin

British spelling. Numbers below come from the source or from the unit tests;
nothing here invents a plant value. Equations and derivations are in
[docs/THEORY.md](docs/THEORY.md).

## Big picture

```text
 encoder (+noise) ─┐                     ┌─ PID / optimised PID ─┐
 current sensor ───┼─► controller ──V_cmd┤                       ├─► motor drive ──V_a──► PMDC motor twin
                   ├─► LQR (LQI) ────────┤
                   └─► offset-free MPC ──┘                       │   (V sat, slew,        (RK4, 1 ms)
                        (SciPy SLSQP)                            │    current protection)
                                                                 └─ same drive, plant, inputs for all four
```

Four things, kept separate in code:

| Piece | File | Notes |
| --- | --- | --- |
| Actual plant | `twin/pmdc.py`, `sim/plant.py` | `PMDCParams` is the only home of motor numbers. CasADi RK4 step plus a scalar Python RK4 that tests prove identical. |
| Prediction model | `identified.py` (`MotorStateSpaceModel`) | 2-state `[i_a, omega]` ZOH model of the **nominal** motor. |
| Drive | `sim/drive.py` | Enable/e-stop, slew limit, voltage saturation, current protection. Shared by every controller. |
| Measurement | `sim/simulate.py` (`build_inputs`) | Speed with seeded Gaussian noise; ideal current sensor. |

## Timing

The controller runs every 10 ms (`DemoConfig.dt_s`). The plant integrates with
RK4 at 1 ms (`plant_dt_s`), 10 sub-steps per sample, holding the applied voltage.
`DemoConfig.__post_init__` requires `dt_s` to be an integer multiple of `plant_dt_s`.

## The MPC (`mpc.py`, `mpc_motor.py`)

`mpc.solve(...)` accepts two model types. `IdentifiedLinearModel` is the original
SISO first-order ARX (kept for the generic tests). `MotorStateSpaceModel`
dispatches to `mpc_motor.solve_motor`:

- **Model.** `x+ = Ad x + Bd (V + d_v) + Ed d_t`, state `[i_a, omega]`, from the
  nominal motor by matrix exponential. Prediction matrices are built once per
  (motor, horizon) and cached.
- **Observer.** `refresh_torque` maps the one-step current and speed innovations to a
  load-torque estimate `d_hat` and an armature-voltage estimate `d_v` with scalar
  gain `observer_gain`. Both are needed: torque alone leaves an offset under
  resistance mismatch.
- **Decisions.** `control_horizon` voltage moves with block lengths 1, 2, 4, … and a
  long last block (`blocking_matrix`). Horizon default 60 samples (0.6 s).
- **Cost.** `q Σ(ω−r)² + q_T (ω_N−r_N)² + r Σ ΔV²` in RPM² and V², with reference
  preview (`y_ref_traj`). Defaults: `q = 1`, `q_T = 50`, `r = 5000`.
- **Constraints.** Voltage box; voltage change between moves ≤ `max_step`
  (slew × Ts); predicted `|i_a| ≤ i_max` over the whole horizon. They are linear, so
  SLSQP gets exact Jacobians. If the current bound is infeasible from the present
  state, the solver drops it and the drive's protection acts.
- **Numerics.** The objective is scaled by `1e-6`; without it SLSQP's line search
  fails on RPM²-sized costs next to O(1) constraints.
- `MpcTimedOut` still guards the wall-clock budget (`solver_time_limit_s`).

Typical solve time is 1–5 ms.

## The drive (`sim/drive.py`)

Order each sample: enable/e-stop → slew limit → ±`V_max`·bus level → current window.
The window keeps the exact one-sample electrical response inside `±I_max` using
the drive's nominal `R_a`, `K_e` and the measured current and speed; a measured-excess
feedback term backs off further if the real winding differs. `MotorDrive` also
exposes `enable()`, `disable()` (ramped), `emergency_stop()` (latched) and `reset()`.
`DriveFlags` (`v_saturated`, `i_limited`, `slew_limited`) feed the metrics.

## PID (`sim/pid.py`) and optimised PID (`sim/pid_tune.py`)

Positional PID, RPM in, volts out. Filtered derivative on the measurement.
Back-calculation anti-windup against the voltage the drive actually applied.
`tune_pid_gains` runs L-BFGS-B (three scaled starts, coarse finite-difference step)
on the composite objective in `TuneWeights` (IAE, overshoot, settling, effort,
voltage-saturation time, current-limit time). `playground.baseline_optimized_pid`
tunes once on `speed_tracking` and freezes the result in `data/ui/optimized_pid.json`.

## LQR (`sim/lqr.py`)

Integral-augmented LQR on the nominal motor, discretised at the controller period,
gain from `solve_discrete_are`, anti-windup against the applied voltage. Details and
the design checks are in [docs/LQR.md](docs/LQR.md). `lqr_step` is a pure function like `pid_step`.

## Simulation (`sim/simulate.py`)

`run_closed_loop(scenario, controller, cfg, options=...)` is the only closed-loop
path. It builds the reference, load, bus and noise arrays once (`build_inputs`),
starts the plant in steady state at the scenario's initial speed and load, and
loops: measure → controller → drive → RK4 sub-steps. `RunOptions` can override noise
and plant scaling. Controllers always use `cfg.model`, the nominal motor.
`CONTROLLER_IDS = ("pid", "optimized_pid", "lqr", "mpc")`; every run fills the same
`SimulationResult` (requested and applied voltage, torque, power, flags, per-sample execution time,
controller config). `run_mpc_step_log` records predictions for the MPC Prediction Explorer.

## Scenarios and the bench

`sim/scenarios.py` holds the ten named scenarios and profile builders
(`piecewise`, `sinusoid`, `bounded_random`, `add`). `sim/playground.py` turns the
Experiment Bench settings (`PlaygroundParams`, including the LQR weights) into a scenario, defines the
preset buttons and `run_bench`, which returns a `ControllerRuns` mapping in controller order.

## UI

`app.py` is a thin `st.navigation` entry point over six pages in `ui_pages/`: overview, bench,
LQR studio, MPC explorer, performance and plant model. Theme tokens are in `sim/theme.py`,
CSS in `sim/ui.py`, SVG diagrams in `sim/diagrams.py`, shared state in `sim/ui_state.py`. Pages read
precomputed JSON from `data/ui/` (`sim/ui_cache.py`, per-controller keys: changing the LQR
weights only recomputes LQR); a cache miss, such as custom motor parameters, simulates live. `sim/motor_view.py` builds the self-contained
2D shaft animation (HTML/SVG/JS); `sim/plotly_charts.py` the figures.
`scripts/precompute_ui_data.py` regenerates all cached data and re-tunes and
freezes the optimised PID.

## Tuning knobs

| Knob | Where | Effect |
| --- | --- | --- |
| `horizon_steps`, `control_horizon` | `DemoConfig` | Look-ahead (samples of 10 ms) and number of free moves |
| `tracking_weight`, `terminal_weight`, `move_weight` | `DemoConfig` | Speed error vs smoothness |
| `observer_gain` | `DemoConfig` | Load-step recovery vs encoder-noise sensitivity (default 0.1) |
| `DriveConfig` | `sim/drive.py` | `V_max`, `I_max`, slew, converter efficiency |
| `TuneWeights` | `sim/pid_tune.py` | What "optimised" means for the PID |

## How to run

```bash
pip install -r requirements.txt && pip install -e ".[dev]"
python -m pytest -q
python examples/run_simulations.py        # all scenarios -> results/
python scripts/precompute_ui_data.py      # UI cache + frozen PID gains
streamlit run app.py
```

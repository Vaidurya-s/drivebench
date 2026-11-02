"""User-facing strings for DriveBench (PMDC motor control and analysis studio)."""

from __future__ import annotations

APP_NAME = "DriveBench"
APP_SUBTITLE = "PMDC Motor Control & Analysis Studio"

OVERVIEW_TITLE = "System overview"
OVERVIEW_LEDE = (
    "A permanent-magnet DC (PMDC) motor holds shaft speed against a changing load. Four "
    "controllers (PID, optimised PID, LQR and MPC) drive the same simulated motor through the "
    "same voltage drive, so differences in the results come from the control law alone."
)
OVERVIEW_PAGES = (
    ("Experiment Bench", "Set speed, load, drive and sensor conditions, then compare all four controllers."),
    ("LQR Design Studio", "Choose the LQR weights, see the gain, closed-loop poles and Riccati checks."),
    ("MPC Prediction Explorer", "Step through what MPC predicts and plans at each sample."),
    ("Performance Review", "Compare response, current, voltage, energy and execution time across scenarios."),
    ("Plant Model", "Motor equations, state-space matrices, parameters, limits and assumptions."),
)

FAIRNESS_NOTE = (
    "All four controllers share the same motor, initial state, speed reference, load torque, "
    "sensor noise, drive limits and 10 ms controller period. LQR and MPC use the measured armature "
    "current; the PID loops use speed only. The LQR weights and MPC settings were set by hand "
    "while looking at these scenarios."
)

LQR_NOTE = (
    "LQR here is the integral-augmented design (LQI): an extra integral-of-speed-error state "
    "gives zero steady-state speed error under constant load."
)

SAFETY_NOTE = (
    "MPC respects voltage, voltage-rate and predicted-current limits inside its optimisation. "
    "The drive's protection layer (saturation, slew limit, current window) acts on every "
    "controller regardless, and is the last line of defence."
)

BENCH_TITLE = "Experiment Bench"
BENCH_LEDE = (
    "Configure a run on the left. All four controllers see exactly the same reference, load "
    "and measurement noise."
)
BENCH_CAPTION = (
    "Shaded bands mark the drive limits. Dotted vertical lines mark disturbance events. "
    "Optimised PID uses the same gains in every run: the ones found once on speed tracking."
)

LQR_TITLE = "LQR Design Studio"
LQR_LEDE = (
    "Choose how strongly the controller penalises current, speed error, integrated error and "
    "voltage. The gain is recomputed from the discrete algebraic Riccati equation each time."
)

MPC_TITLE = "MPC Prediction Explorer"
MPC_LEDE = "See what MPC predicts over its horizon and which limits shape the plan, one sample at a time."

PERF_TITLE = "Performance Review"
PERF_LEDE = (
    "Same motor, same drive, same inputs for every controller. Pick a scenario to compare "
    "response, electrical and mechanical quantities, energy and execution time."
)

PLANT_TITLE = "Plant Model"
PLANT_LEDE = "The simulated motor: equations, matrices, parameters, limits and what the model leaves out."

MOTOR_CONFIG_NOTE = (
    "Custom motor parameters are simulated live. The optimised PID gains were tuned on the "
    "default motor and are not retuned unless you ask."
)

PLANT_LIMITATIONS = (
    "Linear motor with constant parameters: no brush drop, magnetic saturation, temperature "
    "drift, Coulomb friction or cogging.",
    "Ideal current sensor; the speed encoder has Gaussian noise only (no quantisation).",
    "The drive is a voltage source with a slew limit and an ideal current window, not a "
    "switching converter model.",
    "Load torque keeps its sign at standstill.",
    "Efficiency figures use an illustrative 0.95 power-stage efficiency.",
    "No stability proof is claimed for any controller under saturation.",
)

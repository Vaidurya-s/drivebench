"""User-facing UI strings for the Industrial DC Motor Control Lab."""

from __future__ import annotations

SIDEBAR_BRAND = "DC Motor Control Lab"

OVERVIEW_TITLE = "Industrial DC Motor Control Lab"
OVERVIEW_LEDE = (
    "Compare MPC and PID on a permanent-magnet DC motor drive: the kind that turns "
    "conveyors, pumps and machine axes."
)
OVERVIEW_MPC_BLURB = (
    "The controller adjusts the armature voltage to hold the shaft speed. MPC runs a "
    "model of the motor forward over a horizon, picks a voltage plan that respects the "
    "voltage, slew and current limits, applies the first move, then re-plans from the "
    "measured speed and current. PID only reacts to the speed error it sees now. "
    "All three controllers drive the same simulated motor through the same drive "
    "(voltage saturation, slew limit, current protection)."
)
OVERVIEW_PAGES = (
    ("Playground", "Set speed, load and drive conditions, then compare the controllers and watch the motor."),
    ("Step-through", "Watch MPC plan speed and current one horizon at a time."),
    ("Scorecard", "Compare rise, settling, current, energy and efficiency across ten scenarios."),
)

PLAYGROUND_TITLE = "Playground"
PLAYGROUND_LEDE = (
    "Opens on a step in load torque at constant speed. Watch how fast each controller "
    "restores the speed, and what armature current and voltage it uses to do it."
)
PLAYGROUND_CAPTION = (
    "Dashed lines in the current and voltage panels are the drive limits. Optimised PID "
    "uses the same gains in every preset: the ones found once on the speed-tracking "
    "scenario. MPC uses the same planner throughout."
)

STEP_TITLE = "Step-through"
STEP_LEDE = "See how MPC plans each voltage move and what current it expects."

SCORECARD_TITLE = "Scorecard"
SCORECARD_LEDE = (
    "Same motor, same drive, same inputs for every controller. Optimised PID keeps the "
    "gains from the speed-tracking scenario. Pick a scenario to compare its metrics."
)

MOTOR_CONFIG_NOTE = (
    "Custom motor parameters are simulated live. The optimised PID gains were tuned on "
    "the default motor and are not retuned unless you ask."
)

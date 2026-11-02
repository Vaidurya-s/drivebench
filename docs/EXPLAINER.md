# What this project is doing (plain explainer)

> **Companion:** maths and industrial-control detail → [THEORY.md](THEORY.md)
> Short engineering reference → [HOW-IT-WORKS.md](../HOW-IT-WORKS.md) · Results narrative → [report/report.md](../report/report.md)

All numbers in this lab are **illustrative coursework values**, not a real customer motor.

---

## In one sentence

Ten times a second, the controller uses a model of the motor to imagine the next few tenths of a second, tries voltage plans that respect the drive's limits, picks the plan whose predicted speed stays closest to the target, applies **only the first step** of that plan, then measures the real speed and current and does it again.

## The picture to hold

Think of a conveyor belt that must run at a steady speed while boxes are loaded on and off. Loading boxes is extra drag (load torque): the belt slows down unless the controller gives the motor more voltage. A simple speed controller (PID) only reacts after the belt has already slowed. MPC is more like a driver who watches the road ahead: it knows how the motor responds, so it can plan the voltage, and it knows the drive will not allow more than 8 A, so it never asks for a plan that would hit that wall.

That look-ahead loop is **model predictive control** (MPC).

---

## The boxes on the infographic

The repo banner diagram is the same story in engineering boxes. Walk them in the order the controller thinks.

### 1. Optimisation (the decision box)

Scores many candidate voltage plans and picks the best one that still obeys the rules.

**Rules here:** armature voltage stays within ±24 V, it cannot change faster than the slew limit, and the predicted armature current must stay below 8 A. The "score" is how far the *predicted* speed would sit from the speed you asked for, over a horizon of 0.6 s.

**In this project:** SciPy's SLSQP does the search inside [`mpc_motor.py`](../src/mpc_core/mpc_motor.py). It never touches the real motor, only the model below.

### 2. Simulation model (the imagination)

Answers "if I apply this voltage sequence, what current and speed do I get?"

| Piece | Role | Code |
| --- | --- | --- |
| **MPC prediction model** | Small, fast model of the *nominal* motor used inside the optimiser | `MotorStateSpaceModel` in `identified.py` |
| **Plant (motor twin)** | The stand-in for the real motor in the closed-loop demo, possibly with different resistance, inertia or friction | `twin/pmdc.py`, `sim/plant.py` |
| **Drive** | The power electronics: voltage ceiling, slew limit, current protection. Sits between every controller and the motor. | `sim/drive.py` |
| **Measurement** | Encoder (noisy speed) and current sensor | `sim/simulate.py` |

The optimiser plans with the nominal model; the demo then runs it on a plant that may be different. That mismatch is intentional: real controllers rarely get a perfect model.

### 3. Input prediction (planned voltage over the horizon)

A sequence of future voltage values the optimiser is considering: fine steps right now, coarser steps later. Only the **first** value is sent to the drive. The rest is thrown away and recomputed next sample. That discard-and-replan habit is the **receding horizon**.

### 4. State prediction (planned speed and current)

What the model expects if that voltage plan were followed. The Step-through page shows these predictions for one MPC tick: the speed curve and the armature current, which is kept under the limit.

---

## The loop that never stops

1. **Measure** speed (encoder) and current.
2. **Estimate** what the model is missing: extra load torque, and any electrical error. This is how MPC avoids a lasting speed error even when the load is not what it assumed.
3. **Plan** a voltage sequence for the next 0.6 s.
4. **Apply** the first voltage. The drive trims it if it is too fast, too high or would push the current past the limit.
5. The motor responds; go back to step 1.

---

## PID, without the mystique

PID looks at the speed error now (P), the error summed up over time (I) and how fast the speed is changing (D), and turns that into a voltage. It is simple and reliable, but it does not know about limits until it hits them, and the "I" part can build up while the drive is limiting (**windup**). Here PID has a filtered D term and anti-windup that watches what voltage the drive *actually* applied.

### Optimised PID

The same PID, but the three gains were found by a computer search that scores speed error, overshoot, settling time, voltage effort and time spent in the voltage or current limit. The search ran **once**, on a speed-tracking test, and the gains are then frozen for every comparison. A real engineer does not retune a drive for every load change either.

---

## Explain it to a friend

"The controller is a driver who knows how the motor reacts and sees the speed limit sign ahead. A normal controller steers by what just happened. This one steers by what it expects to happen, and it never plans through a wall the drive would refuse to cross."

## Where the picture breaks

- The motor model is linear, with constant parameters; real motors have brush drop, saturation and temperature effects.
- The drive is ideal apart from its limits and a fixed efficiency.
- MPC here is single-input, single-output with hand-chosen weights.

## Words introduced here

| Word | Meaning |
| --- | --- |
| Horizon | How far ahead the controller imagines (0.6 s here) |
| Receding horizon | Replan every sample, apply only the first move |
| Load torque | The drag the machine puts on the shaft |
| Back EMF | Voltage the spinning motor generates against the supply |
| Current protection | The drive's guard that keeps armature current under the limit |
| Windup | Integral term growing while the output is limited |

## Where to go next

- Maths: [THEORY.md](THEORY.md)
- Knobs and code map: [HOW-IT-WORKS.md](../HOW-IT-WORKS.md)
- Results: [report/report.md](../report/report.md)

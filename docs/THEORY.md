# Industrial control theory for this lab

> **Start here if you want equations.** Plain story with almost no maths → [EXPLAINER.md](EXPLAINER.md)
> Knob list and code map → [HOW-IT-WORKS.md](../HOW-IT-WORKS.md) · Scenario results → [report/report.md](../report/report.md)

British spelling. Symbols match what the code implements. Motor numbers are **illustrative coursework values**, a self-consistent baseline and not a commercial motor.

---

## 1. The industrial job

A permanent-magnet DC (PMDC) motor with a controlled armature voltage is a standard industrial drive. It turns conveyor belts, pumps, automated manufacturing equipment, material-handling systems, mechanical actuators and general machinery. The control job is to **hold a commanded shaft speed** while the mechanical load changes, the supply wobbles, the sensor is noisy and the drive protects itself (voltage ceiling, slew limit, current limit).

This lab compares three ways of choosing the armature voltage each 10 ms: offset-free **MPC**, a hand-tuned **PID**, and an **optimised PID** (same PID law, gains found offline once and then frozen).

## 2. Physical structure of the PMDC motor

Stator permanent magnets give a fixed field. The rotor carries the armature winding with resistance \(R_a\) and inductance \(L_a\); a commutator feeds current \(i_a\) to it. Current in the field produces torque \(K_t i_a\). The spinning winding generates a back EMF \(K_e \omega\) that opposes the applied voltage \(V_a\). The shaft drives the load through inertia \(J\) with viscous friction \(B\) and an external load torque \(T_L\). A motor drive supplies the voltage; a speed sensor (encoder) and a current sensor close the loop.

## 3. Electrical and mechanical modelling

Electrical (Kirchhoff on the armature loop):

\[ L_a \frac{di_a}{dt} = V_a - R_a i_a - K_e \omega \]

Mechanical (Newton on the shaft):

\[ J \frac{d\omega}{dt} = K_t i_a - B\omega - T_L, \qquad \frac{d\theta}{dt} = \omega \]

Monitored quantities: torque \(T_{em}=K_t i_a\), back EMF \(E=K_e\omega\), electrical power \(V_a i_a\), mechanical output \(T_{em}\omega - B\omega^2\) (shaft) and \(T_L\omega\) (into the load).

SI units are used internally. Speed is shown in RPM in the UI (\(\omega = 2\pi\,\mathrm{rpm}/60\)).

| Parameter | Symbol | Baseline | Unit |
| --- | --- | ---: | --- |
| Rated / maximum drive voltage | \(V_{rated}, V_{max}\) | 24 | V |
| Armature resistance | \(R_a\) | 1.0 | Ω |
| Armature inductance | \(L_a\) | 0.010 | H |
| Torque constant | \(K_t\) | 0.050 | N·m/A |
| Back-EMF constant | \(K_e\) | 0.050 | V·s/rad |
| Inertia | \(J\) | 0.002 | kg·m² |
| Viscous friction | \(B\) | 0.001 | N·m·s/rad |
| Nominal load torque | \(T_L\) | 0.050 | N·m |
| Maximum current | \(I_{max}\) | 8 | A |
| Maximum speed | \(\omega_{max}\) | 3000 | RPM |
| Plant step / controller period | \(dt,\;T_s\) | 1 ms / 10 ms | |

All of these live in `PMDCParams` (`twin/pmdc.py`) and are validated against physical ranges. Nothing else hardcodes a motor number.

## 4. State space and transfer function

With \(x=[i_a,\omega,\theta]^\top\), \(u=V_a\), \(d=T_L\): \(\dot x = Ax + Bu + Ed\), with

\[ A=\begin{bmatrix}-R_a/L_a & -K_e/L_a & 0\\ K_t/J & -B/J & 0\\ 0&1&0\end{bmatrix},\quad B=\begin{bmatrix}1/L_a\\0\\0\end{bmatrix},\quad E=\begin{bmatrix}0\\-1/J\\0\end{bmatrix}. \]

For the baseline: \(A=\begin{bmatrix}-100&-5&0\\25&-0.5&0\\0&1&0\end{bmatrix}\), \(B=[100,0,0]^\top\), \(E=[0,-500,0]^\top\) (asserted in `tests/test_pmdc_plant.py`).

Speed from voltage (no load change):

\[ \frac{\Omega(s)}{V_a(s)} = \frac{K_t}{L_aJ\,s^2 + (L_aB + R_aJ)\,s + (R_aB + K_eK_t)}. \]

Baseline poles are \(s\approx -98.7\) and \(-1.75\ \mathrm{s^{-1}}\): an electrical mode (\(\tau_e = L_a/R_a = 10\) ms) and a mechanical mode (\(\tau_m\approx 0.57\) s). DC gain \(K_t/(R_aB+K_eK_t)\approx 14.3\) rad/s per volt (≈136 RPM/V).

Steady state (used for initial conditions and tests):

\[ V_a = R_a i_a + K_e\omega, \qquad K_t i_a = B\omega + T_L. \]

At 1000 RPM and 0.05 N·m this is \(i_a\approx 3.09\) A, \(V_a\approx 8.33\) V; at 2500 RPM, ≈6.2 A and ≈19.3 V. A load of 0.10 N·m at 3000 RPM would need ≈8.3 A, more than \(I_{max}\), so that corner is infeasible by design.

## 5. Four different models (do not mix them up)

| Model | What it is | Where |
| --- | --- | --- |
| **Actual plant** | The simulated truth: PMDC equations, RK4, possibly mismatched parameters | `twin/pmdc.py`, `sim/plant.py` |
| **Controller prediction model** | 2-state \([i_a,\omega]\) zero-order-hold discretisation of the *nominal* motor at \(T_s\), plus two disturbance estimates | `identified.py` (`MotorStateSpaceModel`) |
| **Simulated motor drive** | Voltage saturation, slew limit, current protection, enable/e-stop | `sim/drive.py` |
| **Measurement model** | Ideal current sensor; encoder speed with Gaussian noise of configurable σ | `sim/simulate.py` (`build_inputs`) |

Model-mismatch experiments change only the *plant* parameters; the MPC, the drive's own current estimate and the PID design always use nominal values.

## 6. Simulation and numerical integration

The controller runs every \(T_s=10\) ms and holds its output (zero-order hold). The plant is integrated with fixed-step RK4 at \(dt=1\) ms (10 sub-steps per sample), because \(\tau_e=10\) ms would be badly resolved by a 10 ms step. `tests/test_pmdc_plant.py` checks: RK4 against the exact matrix-exponential solution of the linear system, fourth-order convergence under step refinement, agreement between the Python RK4 and the CasADi twin, agreement with the analytic transfer-function step response, and the steady-state equations above.

## 7. Drive constraints

Every controller's command passes through the same `MotorDrive`, in this order:

1. enable / emergency-stop gate (e-stop is latched and forces 0 V);
2. slew limit (default 1200 V/s = 12 V per sample);
3. saturation at \(\pm V_{max}\cdot\) bus level (the DC bus can sag);
4. **current protection**.

Current protection is a current-limited voltage drive, not a clip of the simulated current. The exact one-sample electrical response is

\[ i_{k+1} = \alpha\, i_k + (1-\alpha)\frac{V - K_e\omega}{R_a},\qquad \alpha=e^{-T_s/\tau_e}. \]

Requiring \(|i_{k+1}|\le I_{max}\) gives a voltage window \(K_e\omega + \tfrac{R_a}{1-\alpha}(\pm I_{max}-\alpha i_k)\) that the command is clamped to, using the drive's own nominal \(R_a,K_e\) and the measured \(i_a\) and \(\omega\). If the true winding differs, a feedback term backs the voltage off in proportion to the measured excess current, so a ±20 % resistance error produces a bounded transient overshoot of the limit (see Limitations).

Efficiency bookkeeping uses an illustrative converter efficiency `power_stage_efficiency` (default 0.95) that does not alter the applied voltage.

## 8. PID

Positional PID in RPM-in, volts-out form (`sim/pid.py`):

\[ u = K_p e + I - K_d\,\dot y_f,\qquad I \mathrel{+}= K_i e\,T_s + \tfrac{T_s}{T_t}(u_{applied,prev}-u_{cmd,prev}). \]

- derivative on the **measurement**, low-pass filtered (\(\tau_f=20\) ms), so reference steps cause no kick;
- anti-windup by back-calculation against the voltage the **drive actually applied**, so slew, voltage and current limiting all unwind the integrator (\(T_t=50\) ms), plus a conditional clamp when the output saturates;
- output clipped to \(\pm V_{max}\).

## 9. MPC

**Prediction model.** \(x_{k+1} = A_d x_k + B_d(V_k + \hat d_V) + E_d\hat d_T\) with \(x=[i_a,\omega]\), discretised exactly by a matrix exponential at \(T_s\) (`MotorStateSpaceModel`). The condensed prediction \(y = \Phi x_0 + \Gamma v + \ldots\) is built once per model and horizon.

**Decision variables.** \(n_u=6\) voltage moves with growing block lengths 1, 2, 4, … samples (the last block is long), over a horizon \(N=60\) samples (0.6 s, about one mechanical time constant). The first move is applied; the rest are re-planned next sample.

**Cost.** In RPM and volts:

\[ J = q\sum_k (\omega_k-r_k)^2 + q_T(\omega_N-r_N)^2 + r_{\Delta}\sum_j \Delta V_j^2, \]

with reference preview \(r_k\) (future reference samples), tracking weight \(q\), terminal weight \(q_T=50\), and move weight \(r_\Delta=5000\).

**Constraints** (all linear in the decision variables, so SLSQP gets analytic Jacobians):

- voltage box \(|V|\le V_{max}\cdot\) (as set on the drive);
- voltage rate between moves \(|\Delta V|\le \dot V_{max}T_s\);
- predicted armature current \(|i_{a,k}|\le I_{max}\) for the whole horizon.

If the current bound is infeasible from the present state the solver falls back to the rate-only problem and the drive's protection acts; the loop never stalls.

**Offset-free disturbance estimate.** Each sample the one-step innovations of current and speed are mapped to two disturbances through \([B_d\ E_d]\):

\[ \begin{bmatrix}\Delta\hat d_V\\ \Delta\hat d_T\end{bmatrix}= g\,[B_d\ E_d]^{-1}\left(\begin{bmatrix}i_{meas}\\ \omega_{meas}\end{bmatrix}-A_d\begin{bmatrix}i_{prev}\\ \omega_{prev}\end{bmatrix}-B_d(V_{applied}+\hat d_V)-E_d\hat d_T\right). \]

The torque estimate \(\hat d_T\) absorbs load and friction error. The voltage estimate \(\hat d_V\) absorbs electrical error (a wrong \(R_a\) or \(K_e\)); a torque-only estimate cannot, and leaves a speed offset under resistance mismatch (observed during development, fixed by estimating both). With both estimated, the model's two steady-state equations hold at the measured steady state, so the plan that drives the predicted speed to the reference drives the true speed there too (Pannocchia and Rawlings, 2003). Observer gain \(g=0.1\) trades load-step recovery against encoder-noise sensitivity.

**Solver.** `scipy.optimize.minimize` SLSQP, objective scaled by \(10^{-6}\) so RPM² costs sit next to O(1) constraints.

## 10. PID optimisation

`pid_tune.py` runs L-BFGS-B on \((K_p,K_i,K_d)\) from three scaled starts, using a coarse finite-difference step because the objective has kinks. The objective of one closed-loop run is dimensionless:

\[ J = 3\,\tfrac{\mathrm{IAE}}{T\cdot 1000} + 1\cdot\tfrac{\mathrm{OS}\%}{100} + 1\cdot\tfrac{t_s}{T} + 0.05\,\tfrac{\mathrm{rms}(\Delta V)}{0.1V_{max}} + 1\cdot\tfrac{t_{V\,sat}}{T} + 0.25\,\tfrac{t_{I\,lim}}{T}, \]

(tracking error, overshoot, settling time, control effort, voltage-saturation time, current-limit time). Weights are in `TuneWeights`. Gains are tuned **once** on the `speed_tracking` scenario and **frozen** (`data/ui/optimized_pid.json`); every comparison reuses them. The hand-tuned PID is a deliberately conservative engineer's guess.

## 11. Disturbance modelling

| Disturbance | Implementation |
| --- | --- |
| Load step up / removal | `piecewise` torque profile (0.05↔0.10 N·m) |
| Periodic load | \(T_L=T_0+A\sin 2\pi f t\) |
| Random load | seeded, bounded, piecewise-linear |
| Parameter mismatch | plant \(R_a, L_a, J, B\) scaled; controller keeps nominal |
| Sensor noise | seeded Gaussian on measured speed |
| DC-bus variation | bus level profile scales \(V_{max}\) |

## 12. Scenarios

All reproducible; every controller sees identical reference, load, bus and noise arrays and initial state.

| Key | Test |
| --- | --- |
| `motor_startup` | 0 → 1000 RPM at nominal load |
| `speed_tracking` | 1000 / 2000 / 1500 / 2500 RPM every 5 s |
| `load_step` | 2000 RPM, 0.05 → 0.10 N·m at 5 s |
| `load_removal` | 2000 RPM, 0.10 → 0.05 N·m at 5 s |
| `voltage_saturation` | 2900 RPM reference, bus sags to 85 % at 8 s |
| `current_protection` | 2500 RPM, load 0.10 → 0.14 N·m (needs more than 8 A) |
| `model_mismatch` | \(R_a\) +20 %, \(J\) +30 %, \(B\) +25 %, load step at 8 s (and the opposite corner) |
| `sensor_noise` | 15 RPM encoder noise during a 1000 → 1500 RPM step |
| `variable_load` | 0.5 Hz sinusoid plus bounded random torque at 1500 RPM |
| `reverse_operation` | +1000 → −1000 → +1000 RPM |

## 13. Metrics (as coded in `sim/metrics.py`)

Speed regulation: rise time (10→90 % of the last reference step), settling time (2 % band, last reference segment), overshoot (% of step), steady-state error (mean over the last 10 %), max / mean absolute error, IAE, ISE, ITAE, speed-recovery time after a load change. Electrical: peak and RMS current, mean and peak voltage, voltage-saturation time, current-limit time, electrical energy \(\int V_a i_a\,dt\). Mechanical: peak torque, mean load torque, mean shaft power, mechanical energy.

Efficiency is energy-weighted and returns *none* at zero input:

- **Motor efficiency** = shaft output energy / terminal electrical energy (copper and viscous-friction losses).
- **Drive (overall) efficiency** = useful load energy (\(T_L\omega\)) / supply energy (terminal energy ÷ converter efficiency), so it is lower than the motor figure by the converter loss.

## 14. Simulation assumptions

- Linear PMDC model with constant parameters; ideal brushes and commutation (no brush drop).
- Load torque is a constant-sign external torque, also at standstill (an "active" load such as a hoist). A passive load with stiction would behave differently near zero speed.
- Ideal current sensor; encoder noise is white Gaussian; no sensor quantisation or delay.
- Ideal bidirectional power stage with a fixed illustrative efficiency; regeneration is allowed and not counted as energy returned.
- Controllers and the drive are evaluated at \(T_s=10\) ms with no computation delay.

## 15. Limitations

- Armature reaction, magnetic saturation, temperature dependence of \(R_a\), Coulomb friction, backlash and shaft compliance are not modelled.
- Under ±20 % resistance error the drive's current limit can be exceeded transiently (up to ~14 % over in the worst corner) before feedback backs the voltage off.
- The optimised PID is optimised on one scenario; its advantage elsewhere is whatever carries over, which is the point of freezing it.
- The MPC is SISO with hand-set weights, horizon and move blocking; no stability proof is claimed. Solve time (about 1–5 ms) leaves margin at 10 ms but is not hard-real-time.
- Parameters are illustrative; do not cite them as data for a real motor.

---

## Symbols

| Symbol / term | Meaning |
| --- | --- |
| \(R_a,L_a,K_t,K_e,J,B\) | Motor parameters |
| \(i_a,V_a,\omega,\theta\) | Armature current, voltage, shaft speed, angle |
| \(T_L,\hat d_T,\hat d_V\) | Load torque; estimated torque and voltage disturbances |
| \(T_s, N, n_u\) | Sample period, prediction horizon, number of free moves |
| \(q,q_T,r_\Delta\) | Tracking, terminal and move weights |
| \(K_p,K_i,K_d\) | PID gains |
| IAE / ISE / ITAE | Integrated absolute / squared / time-weighted absolute error |

## References

1. Pannocchia, G. and Rawlings, J. B. (2003). Disturbance models for offset-free model-predictive control. *AIChE Journal*, 49(2), 426–437. (Offset-free idea; the implementation is the innovation update in `mpc_motor.py`.)
2. Implementation notes: [HOW-IT-WORKS.md](../HOW-IT-WORKS.md)
3. Experimental narrative: [report/report.md](../report/report.md)
4. Plain explainer: [EXPLAINER.md](EXPLAINER.md)

# Model predictive control and LQR for an industrial DC motor drive

British spelling. All numbers here come from `scripts/rebuild_report_metrics.py`
(`metrics_summary.json`); the full generated table is
[`results_tables.md`](results_tables.md). Parameters are illustrative.

## Abstract

We compare four controllers regulating the speed of a permanent-magnet DC (PMDC) motor: a
hand-tuned PID, an optimised PID, an integral-augmented LQR (LQI) and an offset-free MPC. All
four command the armature voltage through the same simulated drive (voltage saturation, slew
limit, current protection) and face identical references, load torques, bus profiles and encoder
noise across ten scenarios. The optimised PID is tuned once on speed tracking and frozen. MPC has
the lowest error and the fastest settling in most scenarios; LQR is best on startup settling and
on load disturbances; where the drive's limits decide the outcome, the controllers are close.

## 1. What we built

- **Plant.** The coupled PMDC equations, integrated with RK4 at 1 ms under a 10 ms controller
  (`twin/pmdc.py`, `sim/plant.py`). Baseline: R 1 Ω, L 10 mH, K_t = K_e 0.05, J 0.002 kg·m²,
  B 0.001 N·m·s/rad, V_max 24 V, I_max 8 A, 3000 RPM. Poles at −98.7 and −1.75 s⁻¹.
- **Drive.** Enable and e-stop, slew limit (1200 V/s), saturation with bus sag, and current
  protection as a voltage window (`sim/drive.py`).
- **MPC.** Two-state `[i_a, ω]` model of the nominal motor, 60-sample horizon with six blocked
  voltage moves, voltage, rate and predicted-current constraints, SLSQP, and a joint load-torque
  and armature-voltage disturbance estimate (`mpc_motor.py`).
- **LQR (LQI).** State feedback on `[i_a, ω, ξ]` with `ξ̇ = ω − r`, gain from the discrete algebraic
  Riccati equation at the 10 ms controller period, normalised weights, back-calculation
  anti-windup against the applied voltage (`sim/lqr.py`, `docs/LQR.md`).
- **PID.** Positional, filtered derivative on measurement, anti-windup against the applied
  voltage. The optimised PID minimises a composite of IAE, overshoot, settling, effort, voltage
  saturation and current limiting (`sim/pid_tune.py`).

Maths and assumptions: [`docs/THEORY.md`](../docs/THEORY.md), [`docs/LQR.md`](../docs/LQR.md).

## 2. Why these controllers for this drive?

A speed PID acts on the error it already has. A drive with a hard 8 A current limit and a slew
limit punishes that: the controller keeps asking for a voltage the drive will not deliver, and
the integral builds up while it waits. LQR feeds back the armature current as well as the speed
and adds an integrator, so it is stiffer against load changes, but it has no knowledge of the
limits. MPC plans the voltage over 0.6 s knowing the limits, and its disturbance estimate absorbs
load changes without waiting for the speed error to grow.

## 3. Experimental setup

Ten scenarios (see `sim/scenarios.py`): startup, four-step speed tracking, sudden load, load
removal, voltage saturation (2900 RPM with a bus sag to 85 %), current protection (a load that
needs more than 8 A), model mismatch (R +20 %, J +30 %, B +25 %, plus the opposite corner),
encoder noise (15 RPM), variable load (0.5 Hz sinusoid plus bounded random torque), and reversal.
Noise is seeded, so every controller sees the same realisation. Settling uses a 2 % band on the
last reference segment; IAE is in RPM·s.

## 4. Results

Selected rows (IAE in RPM·s unless stated; lower is better):

| Scenario | PID | Opt. PID | LQR | MPC |
| --- | ---: | ---: | ---: | ---: |
| Startup, settling [s] | 1.84 | 0.92 | 0.71 | 0.76 |
| Speed tracking, IAE | 1854 | 1660 | 1608 | 1071 |
| Sudden load, IAE | 35 | 8 | 1.2 | 3.2 |
| Variable load, IAE | 275 | 96 | 18 | 45 |
| Encoder noise, IAE | 181 | 160 | 173 | 103 |
| Reversal, settling [s] | 2.37 | 1.44 | 1.24 | 0.69 |
| Plant mismatch (+), IAE | 1794 | 1700 | 1676 | 1290 |
| Voltage saturation, IAE | 4122 | 4092 | 4072 | 3307 |
| Current protection, time current-limited [s] | 9.18 | 9.71 | 10.05 | 4.34 |

Observations:

1. **Tracking and startup.** MPC leads on tracking and reversal (it previews the reference); LQR
   and MPC are within 0.05 s on startup settling.
2. **Load changes.** LQR has the smallest error on sudden and variable load (IAE 1.2 and 18),
   ahead of MPC (3.2 and 45): current feedback plus an integrator reacts as fast as MPC's
   estimator. Both are far ahead of the PID variants.
3. **Drive limits.** Under voltage saturation and current protection the actuator sets the best
   achievable response and the controllers end close together (current-protection IAE 3678,
   3635, 3616, 3626). MPC spends about half as long in current limit (4.34 s) because it plans
   along the bound; LQR spends the longest (10.05 s).
4. **Noise.** With a 15 RPM encoder the MPC keeps the lowest IAE after the observer gain was set
   to 0.1; at gain 1 it amplified the noise into the voltage and lost to the PID. LQR (173) sits
   between the PID variants.
5. **Mismatch.** MPC stays offset-free with both a torque and a voltage disturbance estimate. The
   frozen optimised PID has IAE 1700 and a PID retuned on the mismatched plant 1706, against 1290
   for MPC and 1676 for LQR.
6. **Execution time.** LQR and PID take about 0.01 ms per sample; MPC takes about 3–6 ms.

The full technical report is [`drivebench_report.pdf`](drivebench_report.pdf); its figures are in
[`figures/`](figures/).

## 5. Limitations

The MPC and LQR use the measured current and a nominal model that matches the plant when no
mismatch is applied, the PID loops are single speed loops, and the MPC weights, horizon and
observer gain and the LQR weights were hand-set while looking at these scenarios. The motor model
is linear with constant parameters (no brush drop, saturation, temperature or Coulomb friction),
the load keeps its sign at standstill, the current sensor is ideal, and under ±20 % resistance
error the drive's current limit can be exceeded transiently (9.1 A against 8 A in the
low-resistance corner). The efficiency figures use an illustrative 0.95 converter efficiency. No
stability proof is claimed under saturation.

## 6. Conclusion

For this drive, offset-free MPC is the better choice when constraints, previewed references and
disturbances matter, at the cost of a numerical optimisation each sample. An integral-augmented
LQR is a cheap, strong alternative for load disturbances but does not respect the current limit
by itself. Where the limits decide the outcome, a well-tuned PID is close.

## References

1. G. Pannocchia and J. B. Rawlings, "Disturbance models for offset-free model predictive control," *AIChE Journal*, 49(2), 426–437, 2003.
2. J. B. Rawlings, D. Q. Mayne and M. Diehl, *Model Predictive Control: Theory, Computation, and Design*, 2nd ed., Nob Hill, 2017.
3. E. F. Camacho and C. Bordons, *Model Predictive Control*, 2nd ed., Springer, 2013.
4. K. J. Åström and T. Hägglund, *Advanced PID Control*, ISA, 2006.
5. B. D. O. Anderson and J. B. Moore, *Optimal Control: Linear Quadratic Methods*, Prentice Hall, 1990.

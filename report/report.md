# Model predictive control for an industrial DC motor drive

British spelling. All numbers here come from `scripts/rebuild_report_metrics.py`
(`metrics_summary.json`); the full generated table is
[`results_tables.md`](results_tables.md). Parameters are illustrative.

## Abstract

We compare an offset-free MPC, a hand-tuned PID and an optimised PID regulating the speed of a
permanent-magnet DC (PMDC) motor. All three command the armature voltage through the same
simulated drive (voltage saturation, slew limit, current protection) and face identical
references, load torques, bus profiles and encoder noise across ten scenarios. The optimised PID
is tuned once on speed tracking and frozen. MPC has the lowest error and the fastest settling in
most scenarios; where the drive's limits decide the outcome, the controllers are close.

## 1. What we built

- **Plant.** The coupled PMDC equations, integrated with RK4 at 1 ms under a 10 ms controller
  (`twin/pmdc.py`, `sim/plant.py`). Baseline: R 1 Ω, L 10 mH, K_t = K_e 0.05, J 0.002 kg·m²,
  B 0.001 N·m·s/rad, V_max 24 V, I_max 8 A, 3000 RPM. Poles at −98.7 and −1.75 s⁻¹.
- **Drive.** Enable and e-stop, slew limit (1200 V/s), saturation with bus sag, and current
  protection as a voltage window (`sim/drive.py`).
- **MPC.** Two-state `[i_a, ω]` model of the nominal motor, 60-sample horizon with six blocked
  voltage moves, voltage, rate and predicted-current constraints, SLSQP, and a joint load-torque
  and armature-voltage disturbance estimate (`mpc_motor.py`).
- **PID.** Positional, filtered derivative on measurement, anti-windup against the applied
  voltage. The optimised PID minimises a composite of IAE, overshoot, settling, effort, voltage
  saturation and current limiting (`sim/pid_tune.py`).

Maths and assumptions: [`docs/THEORY.md`](../docs/THEORY.md).

## 2. Why MPC for this drive?

A speed PID acts on the error it already has. A drive with a hard 8 A current limit and a slew
limit punishes that: the controller keeps asking for a voltage the drive will not deliver, and
the integral builds up while it waits. MPC plans the voltage over 0.6 s knowing the limits, and
its disturbance estimate absorbs load changes without waiting for the speed error to grow.

## 3. Experimental setup

Ten scenarios (see `sim/scenarios.py`): startup, four-step speed tracking, sudden load, load
removal, voltage saturation (2900 RPM with a bus sag to 85 %), current protection (a load that
needs more than 8 A), model mismatch (R +20 %, J +30 %, B +25 %, plus the opposite corner),
encoder noise (15 RPM), variable load (0.5 Hz sinusoid plus bounded random torque), and reversal.
Noise is seeded, so every controller sees the same realisation. Settling uses a 2 % band on the
last reference segment; IAE is in RPM·s.

## 4. Results

Selected rows (IAE in RPM·s unless stated; lower is better):

| Scenario | MPC | PID | Opt. PID |
| --- | ---: | ---: | ---: |
| Startup, settling [s] | 0.76 | 1.84 | 0.92 |
| Speed tracking, IAE | 1071 | 1854 | 1660 |
| Sudden load, IAE | 3 | 35 | 8 |
| Variable load, IAE | 45 | 275 | 96 |
| Encoder noise, IAE | 103 | 181 | 160 |
| Reversal, settling [s] | 0.69 | 2.37 | 1.44 |
| Plant mismatch (+), IAE | 1290 | 1794 | 1700 |
| Voltage saturation, IAE | 3307 | 4122 | 4092 |
| Current protection, time current-limited [s] | 4.34 | 9.18 | 9.71 |

Observations:

1. **Tracking and load changes.** The MPC leads on startup, tracking, load step and removal. Much
   of the load-step gap is the estimator reacting within a sample or two; a PID with a larger
   integral gain could narrow it at the cost of noise sensitivity and overshoot.
2. **Drive limits.** Under voltage saturation and current protection the actuator sets the best
   achievable response and the controllers end close together (current-protection IAE 3626,
   3678, 3635). MPC spends about half the time in current limit because it plans along the bound.
3. **Noise.** With a 15 RPM encoder the MPC keeps the lowest IAE after the observer gain was set
   to 0.1; at gain 1 it amplified the noise into the voltage and lost to the PID.
4. **Mismatch.** MPC stays offset-free with both a torque and a voltage disturbance estimate. A
   torque-only estimate left a ≈44 RPM offset under +20 % resistance (seen during development).
   The frozen optimised PID has IAE 1700 and a PID retuned on the mismatched plant 1706, against
   1290 for MPC.

Figures are in [`figures/`](figures/): per-scenario traces (`<scenario>.png`), `iae_bars.png`,
`current_limit_bars.png`, `robustness_bars.png`, `architecture.png`.

## 5. Limitations

The MPC uses the measured current and a nominal model that matches the plant when no mismatch is
applied, the PID loops are single speed loops, and the MPC weights, horizon and observer gain were
hand-set while looking at these scenarios. The motor model is linear with constant parameters (no
brush drop, saturation, temperature or Coulomb friction), the load keeps its sign at standstill,
the current sensor is ideal, and under ±20 % resistance error the drive's current limit can be
exceeded transiently (9.1 A against 8 A in the low-resistance corner). The efficiency figures
use an illustrative 0.95 converter efficiency. No stability proof is claimed.

## 6. Conclusion

For this drive, offset-free MPC is the better choice when constraints and disturbances matter. It
does not need retuning when the load or plant change. Where the limits decide the outcome, a
well-tuned PID is close.

## References

1. G. Pannocchia and J. B. Rawlings, "Disturbance models for offset-free model predictive control," *AIChE Journal*, 49(2), 426–437, 2003.
2. J. B. Rawlings, D. Q. Mayne and M. Diehl, *Model Predictive Control: Theory, Computation, and Design*, 2nd ed., Nob Hill, 2017.
3. E. F. Camacho and C. Bordons, *Model Predictive Control*, 2nd ed., Springer, 2013.
4. K. J. Åström and T. Hägglund, *Advanced PID Control*, ISA, 2006.

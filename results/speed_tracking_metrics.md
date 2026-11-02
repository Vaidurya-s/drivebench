# Speed-reference tracking

Reference staircase 1000 / 2000 / 1500 / 2500 RPM every 5 s. Compares rise, overshoot and settling for each step.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 1.07e+03 | 1.85e+03 | 1.66e+03 |
| Rise time [s] | 0.76 | 1.28 | 1.24 |
| Settling time [s] | 0.87 | 1.58 | 1.49 |
| Overshoot [%] | 0.00427 | 0.987 | 0.0576 |
| Max current [A] | 7.99 | 7.99 | 7.99 |
| Current-limit active [s] | 3.05 | 1.81 | 2.65 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 1.57e+03 | 1.49e+03 | 1.5e+03 |
| Drive efficiency | 0.109 | 0.112 | 0.11 |

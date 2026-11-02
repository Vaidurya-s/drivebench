# Load removal

Running at 2000 RPM with 0.10 N m, the load drops to 0.05 N m at 5 s. Measures speed overshoot and recovery.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 3.21 | 34.7 | 7.65 |
| Rise time [s] | — | — | — |
| Settling time [s] | 0 | 0 | 0 |
| Overshoot [%] | 0 | 0 | 0 |
| Max current [A] | 6.19 | 6.19 | 6.19 |
| Current-limit active [s] | 0 | 0 | 0 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 1.08e+03 | 1.09e+03 | 1.09e+03 |
| Drive efficiency | 0.156 | 0.156 | 0.156 |

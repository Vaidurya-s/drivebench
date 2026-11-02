# Voltage saturation

A near-maximum 2900 RPM reference, then the DC bus sags to 85 % at 8 s so the available voltage can no longer hold the speed.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 3.31e+03 | 4.12e+03 | 4.09e+03 |
| Rise time [s] | 2.04 | 2.46 | 2.46 |
| Settling time [s] | — | — | — |
| Overshoot [%] | 0.0023 | 0.273 | 0.0159 |
| Max current [A] | 8 | 7.99 | 8 |
| Current-limit active [s] | 3.84 | 3 | 3.53 |
| Voltage saturation [s] | 6 | 6 | 6 |
| Electrical energy [J] | 1.9e+03 | 1.81e+03 | 1.81e+03 |
| Drive efficiency | 0.0888 | 0.0897 | 0.0896 |

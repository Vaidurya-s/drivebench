# Variable load

Constant 1500 RPM against a sinusoidal 0.5 Hz torque plus bounded random variation.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 45.1 | 275 | 96.3 |
| Rise time [s] | — | — | — |
| Settling time [s] | 0 | 11.7 | 0 |
| Overshoot [%] | 0 | 0 | 0 |
| Max current [A] | 5.48 | 5.32 | 5.5 |
| Current-limit active [s] | 0 | 0 | 0 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 677 | 677 | 677 |
| Drive efficiency | 0.184 | 0.183 | 0.184 |

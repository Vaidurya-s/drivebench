# Current protection

Start to 2500 RPM under 0.10 N m, then raise the load to 0.14 N m at 6 s. Holding speed would need more than the 8 A limit, so the drive's current protection engages.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 3.63e+03 | 3.68e+03 | 3.64e+03 |
| Rise time [s] | 2.91 | 2.91 | 2.91 |
| Settling time [s] | 3.89 | 3.92 | 3.89 |
| Overshoot [%] | 0.00172 | 0.171 | 0.00999 |
| Max current [A] | 8 | 8 | 8 |
| Current-limit active [s] | 4.34 | 9.18 | 9.71 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 1.83e+03 | 1.83e+03 | 1.83e+03 |
| Drive efficiency | 0.176 | 0.176 | 0.176 |

# Model mismatch

The plant has R_a +20 %, inertia +30 % and friction +25 % versus the controllers' nominal model; a load step arrives at 8 s.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 1.29e+03 | 1.79e+03 | 1.7e+03 |
| Rise time [s] | 1.76 | 2.19 | 2.19 |
| Settling time [s] | 2.08 | 2.69 | 2.67 |
| Overshoot [%] | 0.315 | 1.36 | 0.387 |
| Max current [A] | 7.14 | 7.23 | 7.36 |
| Current-limit active [s] | 4.47 | 4.1 | 4.25 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 1.58e+03 | 1.54e+03 | 1.54e+03 |
| Drive efficiency | 0.105 | 0.106 | 0.106 |

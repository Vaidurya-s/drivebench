# Model mismatch (low R, J, B)

The plant has R_a +20 %, inertia +30 % and friction +25 % versus the controllers' nominal model; a load step arrives at 8 s.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 468 | 756 | 615 |
| Rise time [s] | 0.2 | 0.81 | 0.61 |
| Settling time [s] | 0.33 | 1.17 | 0.87 |
| Overshoot [%] | 0.000236 | 0 | 0 |
| Max current [A] | 8.98 | 9.1 | 9.1 |
| Current-limit active [s] | 0.39 | 0.25 | 0.5 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 842 | 817 | 825 |
| Drive efficiency | 0.203 | 0.206 | 0.205 |

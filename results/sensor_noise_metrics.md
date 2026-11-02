# Sensor noise

Encoder speed noise (15 RPM standard deviation) while stepping from 1000 to 1500 RPM.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 103 | 181 | 160 |
| Rise time [s] | 0.21 | 0.56 | 0.5 |
| Settling time [s] | 0.25 | 0.68 | 0.63 |
| Overshoot [%] | 2.25 | 4.97 | 1.84 |
| Max current [A] | 7.98 | 7.98 | 7.99 |
| Current-limit active [s] | 0.16 | 0.08 | 0.22 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 439 | 431 | 431 |
| Drive efficiency | 0.147 | 0.149 | 0.149 |

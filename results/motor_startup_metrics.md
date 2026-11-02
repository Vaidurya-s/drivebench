# Motor startup

Start from rest to 1000 RPM at nominal load. Startup current is limited by the drive, so the first second is a current-limited ramp.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 351 | 414 | 364 |
| Rise time [s] | 0.57 | 0.72 | 0.62 |
| Settling time [s] | 0.76 | 1.84 | 0.92 |
| Overshoot [%] | 0.00464 | 2.79 | 0.16 |
| Max current [A] | 7.98 | 7.97 | 7.99 |
| Current-limit active [s] | 0.6 | 0.2 | 0.45 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 196 | 192 | 194 |
| Drive efficiency | 0.143 | 0.146 | 0.145 |

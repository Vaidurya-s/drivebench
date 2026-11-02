# Reverse operation

The bidirectional drive reverses from +1000 to -1000 RPM at 3 s and back at 9 s. Compares braking and reversal transients.

Optimised PID gains (frozen): Kp=0.0326, Ki=0.131, Kd=0

| Metric | MPC | PID | Opt. PID |
| --- | --- | --- | --- |
| IAE [RPM s] | 1.13e+03 | 2.2e+03 | 2.08e+03 |
| Rise time [s] | 0.49 | 1.05 | 0.98 |
| Settling time [s] | 0.69 | 2.37 | 1.44 |
| Overshoot [%] | 0.00228 | 1.37 | 0.0801 |
| Max current [A] | 7.98 | 7.97 | 7.97 |
| Current-limit active [s] | 1.62 | 1.1 | 1.65 |
| Voltage saturation [s] | 0 | 0 | 0 |
| Electrical energy [J] | 350 | 343 | 348 |
| Drive efficiency | 0.105 | 0.106 | 0.105 |

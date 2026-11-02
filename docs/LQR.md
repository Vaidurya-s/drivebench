# LQR with integral action (LQI) for the PMDC motor

Implementation: `src/mpc_core/sim/lqr.py` (no Streamlit import). Tests: `tests/test_lqr.py`,
`tests/test_four_controller.py`. Interactive design: the **LQR Design Studio** page.

## Model

States \(x=[i_a,\omega]^T\) (A, rad/s), input \(V_a\), controlled output \(\omega\):

\[
A=\begin{bmatrix}-R_a/L_a & -K_e/L_a\\ K_t/J & -B/J\end{bmatrix},\quad
B=\begin{bmatrix}1/L_a\\0\end{bmatrix},\quad C=[0\;1],\quad D=0 .
\]

Integral state \(\dot\xi=\omega-r\) gives

\[
A_{aug}=\begin{bmatrix}A&0\\C&0\end{bmatrix},\quad
B_{aug}=\begin{bmatrix}B\\0\end{bmatrix},\quad
B_{ref}=\begin{bmatrix}0\\0\\-1\end{bmatrix}.
\]

Sign convention: \(\xi\) integrates *speed minus reference*, so a positive speed error pushes
\(\xi\) up and the law \(u=-K_\xi\xi\) must lower the voltage; therefore \(K_\xi>0\). A test pins this.

## Discretisation

The plant is discretised exactly (zero-order hold, `scipy.linalg.expm`) at **\(T_s=10\) ms, the
period the loop actually runs at**. The integrator uses the same forward-Euler update the
controller executes, \(\xi_{k+1}=\xi_k+T_s(\omega_k-r_k)\). This differs slightly from a ZOH of
the augmented continuous model, but it means the Riccati design certifies the implemented loop.
Test: plant poles equal \(e^{\lambda T_s}\).

## Cost and gain

\(J=\sum_k x_{aug}^TQx_{aug}+u^TRu\) with normalised weights

\[
Q=\mathrm{diag}\!\left(\tfrac{q_i}{I_{max}^2},\tfrac{q_\omega}{\omega_{max}^2},\tfrac{q_\xi}{(\omega_{max}\cdot0.5\,\mathrm s)^2}\right),\quad
R=\tfrac{r_v}{V_{max}^2}.
\]

The dimensionless weights `q_current, q_speed, q_integral, r_voltage` are validated (finite,
\(10^{-4}\)–\(10^{4}\)). \(P\) comes from `scipy.linalg.solve_discrete_are`, then
\(K=(R+B_d^TPB_d)^{-1}B_d^TPA_d\) is evaluated with `numpy.linalg.solve` (no explicit inverse).

Recommended weights (`LqrWeights.recommended()`): `q_current=0.1, q_speed=300, q_integral=10000,
r_voltage=1`. They were chosen by a small sweep on a 1000 RPM startup (about 0.7 s settling, no
overshoot, current at the 8 A limit). **They are hand-set while looking at these scenarios**, in
the same way the MPC weights are; do not read the comparison as a neutral tuning contest.

## Control law and execution

\[
u=u_{ff}(r)-K_x\,(x-x_{eq}(r))-K_\xi\,\xi
\]

with \(x_{eq}(r),u_{ff}(r)\) the zero-load equilibrium at speed \(r\) (`ff_enabled=False` gives
exactly \(u=-Kx_{aug}\)). A constant load is rejected by \(\xi\); there is no disturbance
estimator (unlike the MPC). The controller runs every 10 ms with the output held between
updates. Measurements are the encoder speed (with the shared noise) and the armature current.

## Anti-windup and limits

- Back-calculation: \(\xi\) is moved so that \(-K_\xi\xi\) shifts the command toward the voltage the
  drive *actually applied* last sample (time constant `t_track_s`, default 0.1 s).
- Hard integral limit \(\pm V_{max}/K_\xi\); bumpless start (\(\xi\) chosen so the first raw
  command equals the applied voltage).
- Saturation, slew and current protection are in the common `MotorDrive`; LQR never touches them.

## Diagnostics and failure handling

`design_lqr` returns an `LqrDesign` with controllability rank (must be 3), \(K\), \(P\),
closed-loop eigenvalues of \(A_d-B_dK\), Riccati residual, weights and design time. It raises
`LqrDesignError` for non-finite or out-of-range weights, rank deficiency, a Riccati failure or
\(\max|\lambda|\ge1\). The studio shows the error and uses no gain in that case.

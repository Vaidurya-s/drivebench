"""Emit C for the PMDC motor RK4 step (one shared formula).

The generated files can be checked into an embedded runtime tree so a target
build does not need Python or CasADi. Regenerating and diffing is a dev step.
"""

from __future__ import annotations

from pathlib import Path

from mpc_core.twin.pmdc import pmdc_step_function

# Header kept stable so a C/C++ runtime can include it without CasADi.
_ABI_HEADER = """\
/* Generated ABI for the PMDC motor RK4 step.
 * Do not hand-edit the formula body: regenerate via
 *   python -c "from pathlib import Path; from mpc_core.twin.codegen import write_pmdc_step_c; write_pmdc_step_c(Path('...'))"
 * Parameters are always passed in; nothing physical is hardcoded.
 */
#ifndef PMDC_STEP_H
#define PMDC_STEP_H

#ifdef __cplusplus
extern "C" {
#endif

/* p = {R_a, L_a, K_t, K_e, J, B}; x = {i_a, omega, theta}. */
void pmdc_step(const double x[3], double V_a, double T_L, double dt_s,
               const double p[6], double x_next[3]);

#ifdef __cplusplus
}
#endif

#endif /* PMDC_STEP_H */
"""

_HAND_C = """\
/* Checked-in C matching mpc_core.twin.pmdc.pmdc_step_function (one RK4 step).
 * L di/dt = V - R i - Ke w ; J dw/dt = Kt i - B w - T_L ; dtheta/dt = w
 * All coefficients come from p[]; this file invents no plant numbers.
 */
#include "pmdc/pmdc_step.h"

static void rhs(const double s[3], double V, double TL, const double p[6],
                double d[3]) {
  d[0] = (V - p[0] * s[0] - p[3] * s[1]) / p[1];
  d[1] = (p[2] * s[0] - p[5] * s[1] - TL) / p[4];
  d[2] = s[1];
}

void pmdc_step(const double x[3], double V_a, double T_L, double dt_s,
               const double p[6], double x_next[3]) {
  double k1[3], k2[3], k3[3], k4[3], s[3];
  int n;
  rhs(x, V_a, T_L, p, k1);
  for (n = 0; n < 3; ++n) s[n] = x[n] + 0.5 * dt_s * k1[n];
  rhs(s, V_a, T_L, p, k2);
  for (n = 0; n < 3; ++n) s[n] = x[n] + 0.5 * dt_s * k2[n];
  rhs(s, V_a, T_L, p, k3);
  for (n = 0; n < 3; ++n) s[n] = x[n] + dt_s * k3[n];
  rhs(s, V_a, T_L, p, k4);
  for (n = 0; n < 3; ++n)
    x_next[n] = x[n] + dt_s / 6.0 * (k1[n] + 2.0 * k2[n] + 2.0 * k3[n] + k4[n]);
}
"""


def generate_pmdc_step_c() -> str:
    """Return the checked-in C body (same formula as the CasADi Function).

    CasADi's own generate() emits a larger runtime-dependent file. For the
    coursework stub we keep a minimal ABI that links cleanly, and Python tests
    prove numerical parity with CasADi.
    """
    _ = pmdc_step_function()
    return _HAND_C


def write_pmdc_step_c(runtime_generated_dir: Path) -> None:
    """Write `pmdc_step.h` and `pmdc_step.c` under a twin-runtime layout."""
    runtime_generated_dir.mkdir(parents=True, exist_ok=True)
    include_dir = runtime_generated_dir.parent / "include" / "pmdc"
    include_dir.mkdir(parents=True, exist_ok=True)
    (include_dir / "pmdc_step.h").write_text(_ABI_HEADER)
    (runtime_generated_dir / "pmdc_step.c").write_text(generate_pmdc_step_c())

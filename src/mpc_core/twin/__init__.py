"""CasADi PMDC motor twin (RK4 step in twin/pmdc.py)."""

from mpc_core.twin.codegen import generate_pmdc_step_c, write_pmdc_step_c
from mpc_core.twin.pmdc import (
    PARAM_RANGES,
    PMDC_PARAM_NAMES,
    InvalidMotorParameter,
    PMDCParams,
    pmdc_step_function,
    rad_s_to_rpm,
    rpm_to_rad_s,
    step_pmdc,
)

__all__ = [
    "PARAM_RANGES",
    "PMDC_PARAM_NAMES",
    "InvalidMotorParameter",
    "PMDCParams",
    "generate_pmdc_step_c",
    "pmdc_step_function",
    "rad_s_to_rpm",
    "rpm_to_rad_s",
    "step_pmdc",
    "write_pmdc_step_c",
]

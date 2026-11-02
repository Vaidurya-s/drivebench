"""Offset-free MPC and CasADi PMDC motor twin for coursework simulations.

MPC quadratic programme: SciPy SLSQP (see mpc.py and mpc_motor.py).
Plant twin authoring: CasADi (see twin/pmdc.py).
"""

from mpc_core.identified import IdentifiedLinearModel, MotorStateSpaceModel
from mpc_core.model_card import HeldOutMetrics, ModelCard
from mpc_core.mpc import MpcResult, MpcState, MpcTimedOut, refresh_disturbance, solve
from mpc_core.thresholds import SetpointLimits

__all__ = [
    "HeldOutMetrics",
    "IdentifiedLinearModel",
    "MotorStateSpaceModel",
    "ModelCard",
    "MpcResult",
    "MpcState",
    "MpcTimedOut",
    "SetpointLimits",
    "refresh_disturbance",
    "solve",
]

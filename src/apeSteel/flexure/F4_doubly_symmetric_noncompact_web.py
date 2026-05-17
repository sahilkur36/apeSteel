"""Backward-compatible re-export of the unified F4 module (Phase 9b).

Phase 9a shipped this module under the doubly-symmetric-specific name.
Phase 9b consolidated F4 into a single ``apeSteel.flexure.F4`` module
that handles both doubly- and singly-symmetric I-sections through one
public facade ``compute_flexural_strength_F4``.

This shim preserves the Phase 9a import path so existing tests and
external callers continue to work unchanged.  New code should import
from ``apeSteel.flexure.F4`` or the top-level ``apeSteel`` package.
"""

from __future__ import annotations

from apeSteel.flexure.F4 import (
    F4_CFLB_ELASTIC_COEFFICIENT_0p9,
    F4_FCR_J_COEFFICIENT_0p078,
    F4_FL_FRACTION_OF_FY_0p7,
    F4_IYC_OVER_IY_THRESHOLD_0p23,
    F4_LP_COEFFICIENT_1p1,
    F4_LR_COEFFICIENT_1p95,
    F4_LR_INSIDE_SQRT_6p76,
    F4_MP_CAP_FY_SX_COEFFICIENT_1p6,
    F4_RT_AW_DIVISOR_6,
    F4_RT_DENOMINATOR_COEFFICIENT_12,
    FlexureF4Report,
    compute_aw_for_F4,
    compute_compression_flange_local_buckling_moment_Mn_F4_13,
    compute_compression_flange_local_buckling_moment_Mn_F4_14,
    compute_Fcr_for_F4,
    compute_FL_for_F4,
    compute_flexural_strength_F4,
    compute_flexural_strength_F4_doubly_symmetric_noncompact_web,
    compute_inelastic_LTB_moment_Mn_F4_2,
    compute_Lp_for_F4,
    compute_Lr_for_F4,
    compute_rt_for_F4,
    compute_tension_flange_plastification_factor_Rpt,
    compute_web_plastification_factor_Rpc,
)

__all__ = [
    "F4_CFLB_ELASTIC_COEFFICIENT_0p9",
    "F4_FCR_J_COEFFICIENT_0p078",
    "F4_FL_FRACTION_OF_FY_0p7",
    "F4_IYC_OVER_IY_THRESHOLD_0p23",
    "F4_LP_COEFFICIENT_1p1",
    "F4_LR_COEFFICIENT_1p95",
    "F4_LR_INSIDE_SQRT_6p76",
    "F4_MP_CAP_FY_SX_COEFFICIENT_1p6",
    "F4_RT_AW_DIVISOR_6",
    "F4_RT_DENOMINATOR_COEFFICIENT_12",
    "FlexureF4Report",
    "compute_FL_for_F4",
    "compute_Fcr_for_F4",
    "compute_Lp_for_F4",
    "compute_Lr_for_F4",
    "compute_aw_for_F4",
    "compute_compression_flange_local_buckling_moment_Mn_F4_13",
    "compute_compression_flange_local_buckling_moment_Mn_F4_14",
    "compute_flexural_strength_F4",
    "compute_flexural_strength_F4_doubly_symmetric_noncompact_web",
    "compute_inelastic_LTB_moment_Mn_F4_2",
    "compute_rt_for_F4",
    "compute_tension_flange_plastification_factor_Rpt",
    "compute_web_plastification_factor_Rpc",
]

"""Flexure - AISC 360 Chapter F.

Currently shipped:
* F2 - compact doubly-symmetric I
* F3 - non-compact / slender flange + compact web
* F4 - doubly-symmetric I with non-compact web (Phase 9a) +
       singly-symmetric I with compact or non-compact web (Phase 9b)
* F5 - slender web plate girder (doubly-symmetric)
* Shared primitives: Lp, Lr, Mp, Mcr, F2-2 interp, F3-1/2 FLB,
  F4 Rpc/Rpt/rt/aw/FL, F4-13/14 CFLB, F4-15 TFY, Rpg, rt(F5)
"""

from apeSteel.flexure.cb import compute_Cb_from_quarter_point_moments
from apeSteel.flexure.F2_compact_doubly_symmetric import (
    FlexureF2Report,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)
from apeSteel.flexure.F3_noncompact_flange import (
    FlexureF3Report,
    compute_flexural_strength_F3_noncompact_or_slender_flange,
)
from apeSteel.flexure.F4 import (
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
from apeSteel.flexure.F5_slender_web_plate_girder import (
    FlexureF5Report,
    compute_aw_for_F5,
    compute_flexural_strength_F5_slender_web_plate_girder,
    compute_Rpg,
    compute_rt_for_F5,
)
from apeSteel.flexure.flange_local_buckling import (
    compute_flange_local_buckling_moment_Mn_F3_1,
    compute_flange_local_buckling_moment_Mn_F3_2,
)
from apeSteel.flexure.lateral_torsional_buckling import (
    compute_elastic_LTB_critical_moment_Mcr,
    compute_inelastic_LTB_moment_Mn_F2_2,
    compute_limiting_length_inelastic_LTB_Lr,
    compute_limiting_length_plastic_Lp,
    compute_plastic_moment_Mp,
)

__all__ = [
    "FlexureF2Report",
    "FlexureF3Report",
    "FlexureF4Report",
    "FlexureF5Report",
    "compute_Cb_from_quarter_point_moments",
    "compute_FL_for_F4",
    "compute_Fcr_for_F4",
    "compute_Lp_for_F4",
    "compute_Lr_for_F4",
    "compute_Rpg",
    "compute_aw_for_F4",
    "compute_aw_for_F5",
    "compute_compression_flange_local_buckling_moment_Mn_F4_13",
    "compute_compression_flange_local_buckling_moment_Mn_F4_14",
    "compute_elastic_LTB_critical_moment_Mcr",
    "compute_flange_local_buckling_moment_Mn_F3_1",
    "compute_flange_local_buckling_moment_Mn_F3_2",
    "compute_flexural_strength_F2_compact_doubly_symmetric",
    "compute_flexural_strength_F3_noncompact_or_slender_flange",
    "compute_flexural_strength_F4",
    "compute_flexural_strength_F4_doubly_symmetric_noncompact_web",
    "compute_flexural_strength_F5_slender_web_plate_girder",
    "compute_inelastic_LTB_moment_Mn_F2_2",
    "compute_inelastic_LTB_moment_Mn_F4_2",
    "compute_limiting_length_inelastic_LTB_Lr",
    "compute_limiting_length_plastic_Lp",
    "compute_plastic_moment_Mp",
    "compute_rt_for_F4",
    "compute_rt_for_F5",
    "compute_tension_flange_plastification_factor_Rpt",
    "compute_web_plastification_factor_Rpc",
]

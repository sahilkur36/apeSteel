"""Flexure - AISC 360 Chapter F (the **full** chapter, Phase F).

Shipped:
* F2  - compact doubly-symmetric I **& channels (major axis, Eq.
        F2-8b ``c``)**
* F3  - non-compact / slender flange + compact web (DS I)
* F4  - doubly-symmetric I with non-compact web (Phase 9a) +
        singly-symmetric I with compact or non-compact web (Phase 9b)
* F5  - slender web plate girder (doubly- *and* singly-symmetric)
* F6  - I-shapes & **channels** bent about their minor axis
* F7  - square / rectangular HSS & box (either axis)
* F8  - round HSS / Pipe
* F9  - tees & double angles in the plane of symmetry
* F10 - single angles (principal / geometric axis)
* F11 - rectangular bars & rounds
* F12 - unsymmetrical shapes (elastic ``Fn*Smin`` catch-all)
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
from apeSteel.flexure.F6_minor_axis import (
    FlexureF6Report,
    compute_flexural_strength_F6_minor_axis,
    compute_flexural_strength_F6_minor_axis_channel,
)
from apeSteel.flexure.F7_rect_hss import (
    FlexureF7Report,
    compute_flexural_strength_F7_rect_hss,
)
from apeSteel.flexure.F8_round_hss import (
    FlexureF8Report,
    compute_flexural_strength_F8_round_hss,
)
from apeSteel.flexure.F9_tee_double_angle import (
    FlexureF9Report,
    compute_flexural_strength_F9_tee_double_angle,
)
from apeSteel.flexure.F10_single_angle import (
    FlexureF10Report,
    SingleAngleBendingMode,
    SingleAngleToeState,
    compute_flexural_strength_F10_single_angle,
)
from apeSteel.flexure.F11_F12_bar_unsymmetric import (
    FlexureF11Report,
    FlexureF12Report,
    compute_flexural_strength_F11_bar,
    compute_flexural_strength_F12_unsymmetric,
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
    "FlexureF6Report",
    "FlexureF7Report",
    "FlexureF8Report",
    "FlexureF9Report",
    "FlexureF10Report",
    "FlexureF11Report",
    "FlexureF12Report",
    "SingleAngleBendingMode",
    "SingleAngleToeState",
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
    "compute_flexural_strength_F6_minor_axis",
    "compute_flexural_strength_F6_minor_axis_channel",
    "compute_flexural_strength_F7_rect_hss",
    "compute_flexural_strength_F8_round_hss",
    "compute_flexural_strength_F9_tee_double_angle",
    "compute_flexural_strength_F10_single_angle",
    "compute_flexural_strength_F11_bar",
    "compute_flexural_strength_F12_unsymmetric",
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

"""Shear - AISC 360 Chapter G.

Currently shipped:
* G2 - doubly-symmetric I (Cv1 three-regime, kv unstiffened / stiffened,
  phi=1.00 stocky-rolled exception).

Future:
* G3 - tension-field action.
* G4 - rectangular HSS.

See docs/design_notes/05_shear_G2.md.
"""

from apeSteel.shear.G2_doubly_symmetric import (
    PHI_SHEAR_LRFD_GENERAL,
    PHI_SHEAR_LRFD_STOCKY_ROLLED,
    UNSTIFFENED_WEB_KV_AISC_360_22,
    UNSTIFFENED_WEB_KV_LEGACY,
    ShearG2Report,
    ShearRegime,
    compute_Cv1_three_regime,
    compute_kv_for_stiffened_web,
    compute_shear_strength_G2_doubly_symmetric,
)

__all__ = [
    "PHI_SHEAR_LRFD_GENERAL",
    "PHI_SHEAR_LRFD_STOCKY_ROLLED",
    "UNSTIFFENED_WEB_KV_AISC_360_22",
    "UNSTIFFENED_WEB_KV_LEGACY",
    "ShearG2Report",
    "ShearRegime",
    "compute_Cv1_three_regime",
    "compute_kv_for_stiffened_web",
    "compute_shear_strength_G2_doubly_symmetric",
]

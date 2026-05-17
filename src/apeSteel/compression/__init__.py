"""AISC 360-22 Chapter E - compression member design.

Pure-function calculators (one module per AISC section) plus the
:func:`compute_compression_strength` facade, mirroring the structure of
:mod:`apeSteel.flexure`.

* ``effective_length_E2``       - §E2 ``Lc = K L``, ``Lc/r``, advisory.
* ``flexural_buckling_E3``      - §E3 ``Fe`` / ``Fcr`` / ``Pn``.
* ``torsional_flexural_E4``     - §E4 torsional / flexural-torsional.
* ``single_angle_E5``           - §E5 modified slenderness.
* ``built_up_E6``               - §E6 built-up modified slenderness.
* ``slender_elements_E7``       - §E7 effective-width area reduction.
* ``compression_strength``      - the orchestrating facade.

The universal input contract is
:class:`apeSteel.sections.compression_properties.CompressionSectionProperties`.
"""

from apeSteel.compression._common import (
    OMEGA_COMPRESSION_ASD,
    PHI_COMPRESSION_LRFD,
    BucklingRegime,
    CompressionLimitState,
)
from apeSteel.compression.capacity_curve import (
    CapacityCurvePoint,
    compute_phi_Pn_vs_length,
)
from apeSteel.compression.compression_strength import (
    CompressionStrengthReport,
    compute_compression_strength,
    compute_compression_strength_from_K_L,
)
from apeSteel.compression.flexural_buckling_E3 import (
    CriticalStressE3,
    compute_flexural_buckling_critical_stress_E3,
)
from apeSteel.compression.single_angle_E5 import (
    SingleAngleE5Case,
    compute_modified_slenderness_E5,
)
from apeSteel.compression.slender_elements_E7 import (
    EffectiveAreaResult,
    compute_effective_area_Ae,
    compute_effective_width_be,
)

__all__ = [
    "OMEGA_COMPRESSION_ASD",
    "PHI_COMPRESSION_LRFD",
    "BucklingRegime",
    "CapacityCurvePoint",
    "CompressionLimitState",
    "CompressionStrengthReport",
    "CriticalStressE3",
    "EffectiveAreaResult",
    "SingleAngleE5Case",
    "compute_compression_strength",
    "compute_compression_strength_from_K_L",
    "compute_effective_area_Ae",
    "compute_effective_width_be",
    "compute_flexural_buckling_critical_stress_E3",
    "compute_modified_slenderness_E5",
    "compute_phi_Pn_vs_length",
]

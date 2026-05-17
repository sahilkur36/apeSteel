"""AISC 360-22 Chapter H - combined forces and torsion.

Pure-function interaction calculators (one module per AISC clause) plus
the :func:`compute_combined_strength` facade, mirroring the structure of
:mod:`apeSteel.compression`.

* ``flexure_axial_H1_1``   - §H1.1 Eq. H1-1a / H1-1b (flexure + comp.).
* ``flexure_tension_H1_2`` - §H1.2 (flexure + tension; Cb amplifier).
* ``single_axis_H1_3``     - §H1.3 in-plane + out-of-plane (Eq. H1-2).
* ``unsymmetric_H2``       - §H2 Eq. H2-1 elastic-stress interaction.
* ``torsion_H3``           - §H3.1/§H3.2/§H3.3 torsion + combined.
* ``combined_strength``    - the orchestrating facade.

Chapter H is a *consumer* layer: it composes the available strengths
produced by Chapter D (tension), Chapter E (``phi*Pn``), Chapter F
(``phi*Mn``) and Chapter G (``phi*Vn``).  The only nominal strength that
*originates* here is the §H3.1 HSS torsional ``Tn``.

H-0 status: scaffold only - every calculator below raises
``NotImplementedError`` pointing at ``docs/design_notes/09_combined_H.md``;
real implementations land across phases H-1..H-7.
"""

from apeSteel.combined._common import (
    OMEGA_TORSION_ASD,
    PHI_TORSION_LRFD,
    CombinedLimitState,
)
from apeSteel.combined.combined_strength import compute_combined_strength
from apeSteel.combined.flexure_axial_H1_1 import (
    CombinedH1Report,
    compute_combined_strength_H1_1,
)
from apeSteel.combined.flexure_tension_H1_2 import (
    compute_Cb_amplification_factor_H1_2,
    compute_combined_strength_H1_2,
)
from apeSteel.combined.single_axis_H1_3 import compute_combined_strength_H1_3
from apeSteel.combined.torsion_H3 import (
    compute_combined_strength_H3_2,
    compute_torsional_strength_rect_HSS_H3_1,
    compute_torsional_strength_round_HSS_H3_1,
)
from apeSteel.combined.unsymmetric_H2 import compute_combined_strength_H2

__all__ = [
    "OMEGA_TORSION_ASD",
    "PHI_TORSION_LRFD",
    "CombinedH1Report",
    "CombinedLimitState",
    "compute_Cb_amplification_factor_H1_2",
    "compute_combined_strength",
    "compute_combined_strength_H1_1",
    "compute_combined_strength_H1_2",
    "compute_combined_strength_H1_3",
    "compute_combined_strength_H2",
    "compute_combined_strength_H3_2",
    "compute_torsional_strength_rect_HSS_H3_1",
    "compute_torsional_strength_round_HSS_H3_1",
]

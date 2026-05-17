"""Shared primitives for AISC 360 Chapter F (flexure) calculators.

Three concerns live here:

1. The `FlexuralLimitState` literal that names each F2 / F3 / F5
   governing regime ("yielding", "inelastic_LTB", "elastic_LTB",
   "flange_local_buckling", "web_local_buckling", "compression_flange_yielding").
2. The standard AISC LRFD / ASD strength factors for flexure
   (phi_b = 0.90, omega_b = 1.67).
3. The base citation tuple every Chapter-F report carries.
"""

from __future__ import annotations

from typing import Literal

from apeSteel.core.result_types import AISCClauseReference

#: Names of the governing limit state for any Chapter-F calculator.
#: Each subclass of FlexureReport uses the subset that applies to it.
FlexuralLimitState = Literal[
    "yielding",
    "inelastic_LTB",
    "elastic_LTB",
    "flange_local_buckling",
    "web_local_buckling",
    "compression_flange_yielding",
    "tension_flange_yielding",
]


#: AISC 360 Section F1 LRFD strength reduction factor for flexure.
PHI_FLEXURE_LRFD: float = 0.90

#: AISC 360 Section F1 ASD safety factor for flexure.
OMEGA_FLEXURE_ASD: float = 1.67


#: Common citation block for AISC 360 Chapter F.  Subclasses extend
#: this with the specific equations they implement.
CITATIONS_AISC_360_CHAPTER_F: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="AISC 360-22",
        section="F1",
        equation=None,
        page="16.1-47",
    ),
)


__all__ = [
    "CITATIONS_AISC_360_CHAPTER_F",
    "OMEGA_FLEXURE_ASD",
    "PHI_FLEXURE_LRFD",
    "FlexuralLimitState",
]

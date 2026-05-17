"""Shared primitives for AISC 360-22 Chapter E (compression) calculators.

Mirrors :mod:`apeSteel.flexure._common`:

1. :data:`CompressionLimitState` - names the governing buckling mode.
2. :data:`BucklingRegime` - inelastic vs elastic (the E3-2 / E3-3 branch).
3. The AISC LRFD / ASD strength factors for compression
   (``phi_c = 0.90``, ``Omega_c = 1.67``; AISC 360-22 Section E1).
4. The base Chapter-E citation block.
5. Table B4.1a non-slender limit coefficients for every Chapter-E
   element type (centralised so the §E7 effective-width calculator and
   the per-section geometries cite one source).
6. Table E7.1 effective-width imperfection constants ``c1, c2``.

References
----------
.. [1] AISC 360-22, "Specification for Structural Steel Buildings",
       Chapter E "Design of Members for Compression", pp. 16.1-37 -
       16.1-43; Table B4.1a, pp. 16.1-13 - 16.1-14; Table E7.1,
       p. 16.1-43. American Institute of Steel Construction, 2022.
"""

from __future__ import annotations

from typing import Literal

from apeSteel.core.result_types import AISCClauseReference

#: Governing compression limit state (buckling mode) for any Chapter-E
#: calculator.  Each report uses the subset that applies to its section.
CompressionLimitState = Literal[
    "flexural_buckling",  # §E3 (governs about the weak principal axis)
    "torsional_buckling",  # §E4, doubly-symmetric about the z (long.) axis
    "flexural_torsional_buckling",  # §E4, singly-symmetric / unsymmetric
    "single_angle_flexural",  # §E5 (single angle, modified Lc/r)
]

#: The §E3 / §E4 critical-stress branch.
BucklingRegime = Literal["inelastic", "elastic"]

#: AISC 360-22 §E1 LRFD strength reduction factor for compression.
PHI_COMPRESSION_LRFD: float = 0.90

#: AISC 360-22 §E1 ASD safety factor for compression.
OMEGA_COMPRESSION_ASD: float = 1.67

#: AISC 360-22 §E3 slenderness limit separating inelastic (Eq. E3-2)
#: from elastic (Eq. E3-3) flexural buckling: Lc/r <= 4.71*sqrt(E/Fy),
#: equivalently Fy/Fe <= 2.25.
E3_SLENDERNESS_LIMIT_COEFF: float = 4.71

#: Eq. E3-2 base of the inelastic exponential, Fcr = 0.658^(Fy/Fe) * Fy.
E3_INELASTIC_BASE_0p658: float = 0.658

#: Eq. E3-3 elastic-buckling reduction, Fcr = 0.877 * Fe.
E3_ELASTIC_FACTOR_0p877: float = 0.877

#: Serviceable / preferred member slenderness advisory (AISC 360-22
#: §E2 user note): Lc/r preferably <= 200.  Not a strength limit.
SLENDERNESS_ADVISORY_LIMIT: float = 200.0


# ---------------------------------------------------------------------------
# Table B4.1a non-slender limits (axial compression).  lambda_r = COEFF *
# sqrt(E/Fy) unless noted; round HSS is COEFF * E/Fy on D/t.
# ---------------------------------------------------------------------------
#: Case 1 - flanges of rolled I, channels, tees (unstiffened): 0.56.
B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF: float = 0.56
#: Case 2 - flanges of built-up I (unstiffened, with kc): 0.64 (x sqrt(kc E/Fy)).
B4_1A_UNSTIFFENED_BUILTUP_FLANGE_COEFF: float = 0.64
#: Case 3 - legs of single angles / double angles / stems-of-tees-like
#: projecting unstiffened elements: 0.45.
B4_1A_UNSTIFFENED_ANGLE_LEG_COEFF: float = 0.45
#: Case 4 - stems of tees (unstiffened): 0.75.
B4_1A_UNSTIFFENED_TEE_STEM_COEFF: float = 0.75
#: Case 5 - webs of doubly-symmetric I and channels (stiffened): 1.49.
B4_1A_STIFFENED_WEB_COEFF: float = 1.49
#: Case 6 - walls of rectangular HSS and box (stiffened): 1.40.
B4_1A_STIFFENED_HSS_WALL_COEFF: float = 1.40
#: Case 9 - round HSS, D/t limit: 0.11 * E/Fy  (NOT times sqrt).
B4_1A_ROUND_HSS_DT_COEFF: float = 0.11


# ---------------------------------------------------------------------------
# Table E7.1 - effective-width imperfection adjustment factors (c1, c2).
# AISC 360-22 p. 16.1-43.  be = b*(1 - c1*sqrt(Fel/Fcr))*sqrt(Fel/Fcr),
# Fel = (c2*lambda_r / lambda)^2 * Fy.
# ---------------------------------------------------------------------------
#: Unstiffened elements: c1 = 0.22, c2 = 1.49.
E7_UNSTIFFENED_C1: float = 0.22
E7_UNSTIFFENED_C2: float = 1.49
#: Stiffened elements, except walls of square/rect HSS: c1 = 0.18, c2 = 1.31.
E7_STIFFENED_C1: float = 0.18
E7_STIFFENED_C2: float = 1.31
#: Walls of square / rectangular HSS: c1 = 0.20, c2 = 1.38.
E7_HSS_WALL_C1: float = 0.20
E7_HSS_WALL_C2: float = 1.38


#: Common citation block for AISC 360-22 Chapter E.  Each calculator
#: extends this with the specific equations it implements.
CITATIONS_AISC_360_CHAPTER_E: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="AISC 360-22",
        section="E1",
        equation=None,
        page="16.1-37",
    ),
)


__all__ = [
    "B4_1A_ROUND_HSS_DT_COEFF",
    "B4_1A_STIFFENED_HSS_WALL_COEFF",
    "B4_1A_STIFFENED_WEB_COEFF",
    "B4_1A_UNSTIFFENED_ANGLE_LEG_COEFF",
    "B4_1A_UNSTIFFENED_BUILTUP_FLANGE_COEFF",
    "B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF",
    "B4_1A_UNSTIFFENED_TEE_STEM_COEFF",
    "CITATIONS_AISC_360_CHAPTER_E",
    "E3_SLENDERNESS_LIMIT_COEFF",
    "E7_HSS_WALL_C1",
    "E7_HSS_WALL_C2",
    "E7_STIFFENED_C1",
    "E7_STIFFENED_C2",
    "E7_UNSTIFFENED_C1",
    "E7_UNSTIFFENED_C2",
    "OMEGA_COMPRESSION_ASD",
    "PHI_COMPRESSION_LRFD",
    "SLENDERNESS_ADVISORY_LIMIT",
    "BucklingRegime",
    "CompressionLimitState",
    "E3_ELASTIC_FACTOR_0p877",
    "E3_INELASTIC_BASE_0p658",
]

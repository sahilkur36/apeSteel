"""Shared primitives for AISC 360-22 Chapter H (combined forces) calculators.

Mirrors :mod:`apeSteel.compression._common`:

1. :data:`CombinedLimitState` - names the governing interaction equation.
2. The AISC literal coefficients of Chapter H (the ``0.2`` axial-ratio
   break, the ``8/9`` factor of Eq. H1-1a, the ``1.5``/``0.5`` of the
   §H1.3 out-of-plane Eq. H1-2, the §H1.2 ``alpha``, the §H3.1 HSS
   torsional ``Fcr`` coefficients, the §H3.2 ``0.2*Tc`` torsion-neglect
   break, and the §H3.3 ``0.6`` shear-yield coefficient).
3. The AISC LRFD / ASD strength factors that *originate* in Chapter H:
   the torsional ``phi_T = 0.90`` / ``Omega_T = 1.67`` of §H3.1.  (The
   H1/H2 interaction equations carry no extra factor - the resistance
   factors live inside the supplied ``Pc``/``Mc``/``Vc``/``Tc``.)
4. The base Chapter-H citation block.

Note - resistance factors.  Chapter H §H1/§H2 are pure interaction
checks: ``Pc = phi_c*Pn``, ``Mc = phi_b*Mn``, ``Vc = phi_v*Vn`` are
already factored by their own chapters, so the interaction itself has
no further ``phi``.  Only §H3.1 (HSS torsion) introduces a new nominal
strength and therefore a new ``phi_T``.

References
----------
.. [1] AISC 360-22, "Specification for Structural Steel Buildings",
       Chapter H "Design of Members for Combined Forces and Torsion",
       pp. 16.1-83 - 16.1-88.  American Institute of Steel Construction,
       2022.
"""

from __future__ import annotations

from typing import Literal

from apeSteel.core.result_types import AISCClauseReference

#: Governing Chapter-H interaction equation for any combined-force
#: report.  Each report uses the subset that applies to its clause.
CombinedLimitState = Literal[
    "H1-1a",  # §H1.1 / §H1.2, Pr/Pc >= 0.2
    "H1-1b",  # §H1.1 / §H1.2, Pr/Pc <  0.2
    "H1-2",  # §H1.3 out-of-plane / LTB
    "H2-1",  # §H2 elastic stress interaction
    "H3-6",  # §H3.2 HSS combined torsion
    "torsion_negligible_H1",  # §H3.2, Tr <= 0.2*Tc -> revert to §H1
]

# ---------------------------------------------------------------------------
# §H1.1 - Eq. H1-1a / H1-1b literals
# ---------------------------------------------------------------------------
#: Axial-ratio break between Eq. H1-1a (>=) and Eq. H1-1b (<).
H1_AXIAL_RATIO_BREAK: float = 0.2
#: Eq. H1-1a moment-term factor, 8/9.
H1_1A_MOMENT_FACTOR: float = 8.0 / 9.0
#: Eq. H1-1b axial-term divisor, Pr/(2*Pc).
H1_1B_AXIAL_DIVISOR: float = 2.0

# ---------------------------------------------------------------------------
# §H1.2 - Cb amplification sqrt(1 + alpha*Pr/Pey)
# ---------------------------------------------------------------------------
#: §H1.2 ``alpha`` for LRFD (1.0) and ASD (1.6).
H1_2_ALPHA_LRFD: float = 1.0
H1_2_ALPHA_ASD: float = 1.6

# ---------------------------------------------------------------------------
# §H1.3 - out-of-plane Eq. H1-2 literals
# ---------------------------------------------------------------------------
#: Eq. H1-2 axial-term: Pr/Pcy*(1.5 - 0.5*Pr/Pcy).
H1_2_OUT_OF_PLANE_LEAD: float = 1.5
H1_2_OUT_OF_PLANE_QUAD: float = 0.5

# ---------------------------------------------------------------------------
# §H3.1 - round HSS torsional Fcr (Eq. H3-2a / H3-2b)
# ---------------------------------------------------------------------------
#: Eq. H3-2a coefficient (1.23) and Eq. H3-2b coefficient (0.60).
H3_ROUND_H3_2A_COEFF: float = 1.23
H3_ROUND_H3_2B_COEFF: float = 0.60
#: §H3.1 shear-yield cap on Fcr: 0.6*Fy (round and rectangular HSS).
H3_FCR_SHEAR_YIELD_FRACTION: float = 0.6

# ---------------------------------------------------------------------------
# §H3.1 - rectangular HSS torsional Fcr (Eq. H3-3 .. H3-5)
# ---------------------------------------------------------------------------
#: h/t break #1: 2.45*sqrt(E/Fy) (below -> Fcr = 0.6*Fy).
H3_RECT_HT_LIMIT_1_COEFF: float = 2.45
#: h/t break #2: 3.07*sqrt(E/Fy) (Eq. H3-4 valid between the two).
H3_RECT_HT_LIMIT_2_COEFF: float = 3.07
#: Eq. H3-5 elastic-buckling coefficient (0.458) and absolute h/t ceiling.
H3_RECT_H3_5_COEFF: float = 0.458
H3_RECT_HT_ABSOLUTE_MAX: float = 260.0

# ---------------------------------------------------------------------------
# §H3.2 - torsion-neglect break (Eq. H3-6 precondition)
# ---------------------------------------------------------------------------
#: Torsion may be neglected (revert to §H1) when Tr <= 0.2*Tc.
H3_2_TORSION_NEGLECT_RATIO: float = 0.2

# ---------------------------------------------------------------------------
# §H3.3 - non-HSS limiting nominal stresses (Eq. H3-7/8/9)
# ---------------------------------------------------------------------------
#: Eq. H3-8 shear-yield fraction of Fy.
H3_3_SHEAR_YIELD_FRACTION: float = 0.6

# ---------------------------------------------------------------------------
# §H3.1 - HSS torsion resistance / safety factors (the only factors that
# originate in Chapter H).
# ---------------------------------------------------------------------------
#: AISC 360-22 §H3.1 LRFD torsional resistance factor.
PHI_TORSION_LRFD: float = 0.90
#: AISC 360-22 §H3.1 ASD torsional safety factor.
OMEGA_TORSION_ASD: float = 1.67


#: Common citation block for AISC 360-22 Chapter H.  Each calculator
#: extends this with the specific equations it implements.
CITATIONS_AISC_360_CHAPTER_H: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="AISC 360-22",
        section="H1",
        equation=None,
        page="16.1-83",
    ),
)


__all__ = [
    "CITATIONS_AISC_360_CHAPTER_H",
    "H1_1A_MOMENT_FACTOR",
    "H1_1B_AXIAL_DIVISOR",
    "H1_2_ALPHA_ASD",
    "H1_2_ALPHA_LRFD",
    "H1_2_OUT_OF_PLANE_LEAD",
    "H1_2_OUT_OF_PLANE_QUAD",
    "H1_AXIAL_RATIO_BREAK",
    "H3_2_TORSION_NEGLECT_RATIO",
    "H3_3_SHEAR_YIELD_FRACTION",
    "H3_FCR_SHEAR_YIELD_FRACTION",
    "H3_RECT_H3_5_COEFF",
    "H3_RECT_HT_ABSOLUTE_MAX",
    "H3_RECT_HT_LIMIT_1_COEFF",
    "H3_RECT_HT_LIMIT_2_COEFF",
    "H3_ROUND_H3_2A_COEFF",
    "H3_ROUND_H3_2B_COEFF",
    "OMEGA_TORSION_ASD",
    "PHI_TORSION_LRFD",
    "CombinedLimitState",
]

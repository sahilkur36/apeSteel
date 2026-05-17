"""Shared classification primitives used across B4.1a, B4.1b, and 341 D1.1.

Three concerns live here:

1. Type aliases for the literal-string classifications used throughout
   the AISC code:
   - `compact` / `non_compact` / `slender` (flexure, Table B4.1b)
   - `non_slender` / `slender` (axial compression, Table B4.1a)
   - `highly_ductile` / `moderately_ductile` (seismic, AISC 341 D1.1)
2. The `PlateElementClassification` frozen dataclass that every
   classifier produces, one per plate element (flange or web).
3. The `compute_kc_for_built_up_flange` helper that returns the
   plate-buckling coefficient used in AISC 360 Cases 2 and 11 for
   welded built-up I-shape flanges.

All values are in apeSteel's canonical N-mm-tonne-s base units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Literal type aliases
# ---------------------------------------------------------------------------
#: Outcome of AISC 360 §B4.1b (flexure) plate-element classification.
FlexuralPlateClass = Literal["compact", "non_compact", "slender"]

#: Outcome of AISC 360 §B4.1a (axial compression) plate-element classification.
AxialPlateClass = Literal["non_slender", "slender"]

#: AISC 341 §D1.1 ductility level.
DuctilityLevel = Literal["highly_ductile", "moderately_ductile"]

#: AISC 341 code edition the seismic classifier should use. Different
#: editions use different λ coefficients and different denominators
#: (E/Fy vs E/(Ry·Fy)). The default is the current code-of-record.
SeismicCodeEdition = Literal["AISC 341-22", "AISC 341-16", "AISC 341-10"]

#: How the doubly-symmetric I was fabricated. Affects which Case in
#: Table B4.1a / B4.1b applies (rolled W → Cases 1 and 10; welded
#: built-up I → Cases 2 and 11, both of which use the `kc` factor).
SectionConstruction = Literal["rolled", "welded"]


# ---------------------------------------------------------------------------
# PlateElementClassification frozen dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PlateElementClassification:
    """Single plate-element classification result.

    Attributes
    ----------
    element_name : str
        Free-form name of the plate element, e.g. ``"flange"`` or
        ``"web"``.  Used only for display / debugging.
    aisc_case : str
        AISC 360 Table reference identifying which Case in
        Table B4.1a / B4.1b was applied, e.g. ``"B4.1b Case 11"``.
        For seismic classification this is the corresponding AISC 341
        Table D1.1 case.
    slenderness_ratio_lambda : float
        The actual plate-element slenderness ratio for this element
        (e.g. ``bf/(2*tf)`` for flange, ``h/tw`` for web).
    compact_limit_lambda_p : float | None
        The compact limit :math:`\\lambda_p`.  ``None`` for axial
        compression (where only ``λr`` exists) and for AISC 341 (where
        only the seismic limit exists).
    noncompact_limit_lambda_r : float
        The non-compact (or non-slender) limit :math:`\\lambda_r`.
        For flexure: the boundary between non-compact and slender.
        For axial compression: the boundary between non-slender and
        slender.
        For AISC 341: this slot carries the seismic limit
        :math:`\\lambda_{hd}` or :math:`\\lambda_{md}`.
    classification : str
        The resulting class label.  One of:
        - For flexural Table B4.1b: ``"compact"``, ``"non_compact"``,
          ``"slender"``.
        - For axial Table B4.1a: ``"non_slender"``, ``"slender"``.
        - For AISC 341 D1.1: ``"acceptable"`` if the element meets the
          chosen ductility limit, otherwise ``"unacceptable"``.
    """

    element_name: str
    aisc_case: str
    slenderness_ratio_lambda: float
    compact_limit_lambda_p: float | None
    noncompact_limit_lambda_r: float
    classification: str


# ---------------------------------------------------------------------------
# kc helper for built-up I-shape flanges
# ---------------------------------------------------------------------------
#: Lower bound on kc per AISC 360 Table B4.1b note [c].
KC_LOWER_BOUND: float = 0.35

#: Upper bound on kc per AISC 360 Table B4.1b note [c].
KC_UPPER_BOUND: float = 0.76


def compute_kc_for_built_up_flange(
    web_height_to_thickness_ratio_h_tw: float,
) -> float:
    """Return the AISC kc factor for a welded built-up I-shape flange.

    AISC 360 Table B4.1b note [c] / Table B4.1a note [a]::

        kc = 4 / sqrt(h / tw),  bounded   0.35 <= kc <= 0.76

    The factor adjusts the flange-buckling stress when the flange is
    welded to a (relatively flexible) web; rolled W shapes do not use
    this factor (they use the bare numerical coefficient 1.0 or 0.56
    instead).

    Parameters
    ----------
    web_height_to_thickness_ratio_h_tw : float
        :math:`h / t_w` for the web.  Dimensionless.

    Returns
    -------
    float
        The bounded :math:`k_c` value.
    """
    h_tw = web_height_to_thickness_ratio_h_tw
    kc_unbounded = 4.0 / math.sqrt(h_tw)
    return max(KC_LOWER_BOUND, min(KC_UPPER_BOUND, kc_unbounded))


__all__ = [
    "KC_LOWER_BOUND",
    "KC_UPPER_BOUND",
    "AxialPlateClass",
    "DuctilityLevel",
    "FlexuralPlateClass",
    "PlateElementClassification",
    "SectionConstruction",
    "SeismicCodeEdition",
    "compute_kc_for_built_up_flange",
]

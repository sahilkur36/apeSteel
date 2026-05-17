"""AISC 360 Table B4.1a - axial-compression slenderness classification.

Classifies the flange and web of a doubly-symmetric I (rolled or
welded built-up) per AISC 360 Table B4.1a.  Unlike flexure, axial
compression has only one limit lambda_r: elements are either
"non_slender" (lambda <= lambda_r, full Ag effective) or "slender"
(lambda > lambda_r, must reduce Ag via the AISC Chapter E.7 effective-
area procedure).

* Flange Case 1 (rolled) or Case 2 (built-up): lambda = bf/(2*tf)
* Web Case 5 (doubly-symmetric I): lambda = h/tw

References
----------
.. [1] AISC 360-22, "Specification for Structural Steel Buildings",
       Table B4.1a "Width-to-Thickness Ratios: Compression Elements
       Members Subject to Axial Compression", pp. 16.1-13 - 16.1-14.
       American Institute of Steel Construction, 2022.
.. [2] AISC 360-22 Section E7 ("Members with Slender Elements") for the
       effective-area treatment of slender members.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification._common import (
    AxialPlateClass,
    PlateElementClassification,
    SectionConstruction,
    compute_kc_for_built_up_flange,
)
from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 Table B4.1a numerical coefficients
# ---------------------------------------------------------------------------
# Case 1 (rolled I flange, axial compression): lambda_r = 0.56 sqrt(E/Fy).
B4_1A_ROLLED_FLANGE_NONSLENDER_LIMIT_COEFF: float = 0.56

# Case 2 (welded built-up I flange, axial compression):
# lambda_r = 0.64 sqrt(kc * E / Fy).
B4_1A_WELDED_FLANGE_NONSLENDER_LIMIT_COEFF: float = 0.64

# Case 5 (doubly-symmetric I web, axial compression):
# lambda_r = 1.49 sqrt(E/Fy).
B4_1A_WEB_NONSLENDER_LIMIT_COEFF: float = 1.49


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AxialCompressionClassificationReport(Report):
    """Flange + web classification per AISC 360 Table B4.1a.

    Attributes
    ----------
    flange : PlateElementClassification
        Result of applying Case 1 (rolled) or Case 2 (welded).
        ``compact_limit_lambda_p`` is ``None`` (Table B4.1a has no
        compact regime).
    web : PlateElementClassification
        Result of applying Case 5.
    section_has_slender_element : bool
        True iff *any* plate element is slender. Triggers AISC E.7
        effective-area treatment in the downstream compression
        calculator.
    construction : str
        Echo of the input construction.
    """

    flange: PlateElementClassification = None  # type: ignore[assignment]
    web: PlateElementClassification = None  # type: ignore[assignment]
    section_has_slender_element: bool = False
    construction: SectionConstruction = "welded"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _classify_one_axial_plate_element(
    element_name: str,
    aisc_case: str,
    slenderness_ratio_lambda: float,
    nonslender_limit_lambda_r: float,
) -> PlateElementClassification:
    """Apply the non-slender / slender decision for axial compression."""
    if slenderness_ratio_lambda <= nonslender_limit_lambda_r:
        classification: AxialPlateClass = "non_slender"
    else:
        classification = "slender"
    return PlateElementClassification(
        element_name=element_name,
        aisc_case=aisc_case,
        slenderness_ratio_lambda=slenderness_ratio_lambda,
        compact_limit_lambda_p=None,  # Table B4.1a has no lambda_p
        noncompact_limit_lambda_r=nonslender_limit_lambda_r,
        classification=classification,
    )


# ---------------------------------------------------------------------------
# Public classifier
# ---------------------------------------------------------------------------
_CITED_CLAUSES_B4_1A: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="AISC 360-22",
        section="B4.1a",
        equation=None,
        page="16.1-11",
    ),
    AISCClauseReference(
        specification="AISC 360-22",
        section="Table B4.1a",
        equation="Cases 1, 2, 5",
        page="16.1-13",
    ),
    AISCClauseReference(
        specification="AISC 360-22",
        section="E7",
        equation=None,
        page="16.1-43",
    ),
)


def classify_axial_compression_B4_1a(
    section_properties: SectionProperties,
    material: SteelMaterial,
    construction: SectionConstruction = "welded",
) -> AxialCompressionClassificationReport:
    """Classify a doubly-symmetric I in axial compression per Table B4.1a.

    Parameters
    ----------
    section_properties : SectionProperties
    material : SteelMaterial
    construction : {"rolled", "welded"}, optional
        Default ``"welded"``.

    Returns
    -------
    AxialCompressionClassificationReport
    """
    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    sqrt_E_over_Fy: float = math.sqrt(E / Fy)

    # --- Flange (Case 1 rolled OR Case 2 welded) ---
    lambda_flange: float = section_properties.flange_width_to_thickness_ratio_bf_2tf
    if construction == "rolled":
        flange_case = "B4.1a Case 1"
        lambda_rf: float = B4_1A_ROLLED_FLANGE_NONSLENDER_LIMIT_COEFF * sqrt_E_over_Fy
    elif construction == "welded":
        flange_case = "B4.1a Case 2"
        kc: float = compute_kc_for_built_up_flange(
            section_properties.web_height_to_thickness_ratio_h_tw
        )
        lambda_rf = B4_1A_WELDED_FLANGE_NONSLENDER_LIMIT_COEFF * math.sqrt(kc * E / Fy)
    else:  # pragma: no cover
        raise ValueError(f"unknown construction {construction!r}")

    flange_classification = _classify_one_axial_plate_element(
        element_name="flange",
        aisc_case=flange_case,
        slenderness_ratio_lambda=lambda_flange,
        nonslender_limit_lambda_r=lambda_rf,
    )

    # --- Web (Case 5) ---
    lambda_web: float = section_properties.web_height_to_thickness_ratio_h_tw
    lambda_rw: float = B4_1A_WEB_NONSLENDER_LIMIT_COEFF * sqrt_E_over_Fy
    web_classification = _classify_one_axial_plate_element(
        element_name="web",
        aisc_case="B4.1a Case 5",
        slenderness_ratio_lambda=lambda_web,
        nonslender_limit_lambda_r=lambda_rw,
    )

    section_has_slender_element: bool = (
        flange_classification.classification == "slender"
        or web_classification.classification == "slender"
    )

    return AxialCompressionClassificationReport(
        cited_clauses=_CITED_CLAUSES_B4_1A,
        governing_limit_state="axial_plate_element_slenderness",
        phi_LRFD=1.0,
        omega_ASD=1.0,
        nominal_strength=0.0,
        phi_strength_LRFD=0.0,
        omega_strength_ASD=0.0,
        flange=flange_classification,
        web=web_classification,
        section_has_slender_element=section_has_slender_element,
        construction=construction,
    )


__all__ = [
    "B4_1A_ROLLED_FLANGE_NONSLENDER_LIMIT_COEFF",
    "B4_1A_WEB_NONSLENDER_LIMIT_COEFF",
    "B4_1A_WELDED_FLANGE_NONSLENDER_LIMIT_COEFF",
    "AxialCompressionClassificationReport",
    "classify_axial_compression_B4_1a",
]

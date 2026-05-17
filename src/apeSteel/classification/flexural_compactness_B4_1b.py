"""AISC 360 Table B4.1b - flexural compactness classification.

Classifies the flange and web of a doubly-symmetric I (rolled or
welded built-up) per AISC 360 Table B4.1b:

* Flange Case 10 (rolled) or Case 11 (built-up)
* Web Case 15 (doubly-symmetric I in flexure)

For each plate element the classifier returns:

* slenderness ratio lambda
* compact limit lambda_p  (separates compact from non-compact)
* non-compact limit lambda_r  (separates non-compact from slender)
* classification: "compact" | "non_compact" | "slender"

The section's overall classification is the worst of the flange and
web classifications.

References
----------
.. [1] AISC 360-22, "Specification for Structural Steel Buildings",
       Table B4.1b "Width-to-Thickness Ratios: Compression Elements
       Members Subject to Flexure", pp. 16.1-15 - 16.1-16. American
       Institute of Steel Construction, 2022.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification._common import (
    FlexuralPlateClass,
    PlateElementClassification,
    SectionConstruction,
    compute_kc_for_built_up_flange,
)
from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 Table B4.1b numerical coefficients
# ---------------------------------------------------------------------------
# Case 10 (rolled I flange, flexure): lambda_p = 0.38 sqrt(E/Fy),
# lambda_r = 1.0 sqrt(E/Fy).
B4_1B_ROLLED_FLANGE_COMPACT_LIMIT_COEFF: float = 0.38
B4_1B_ROLLED_FLANGE_NONCOMPACT_LIMIT_COEFF: float = 1.00

# Case 11 (welded built-up I flange, flexure): lambda_p = 0.38 sqrt(E/Fy),
# lambda_r = 0.95 sqrt(kc * E / FL), with FL = 0.7 Fy for doubly-symmetric
# I sections in major-axis flexure.
B4_1B_WELDED_FLANGE_COMPACT_LIMIT_COEFF: float = 0.38
B4_1B_WELDED_FLANGE_NONCOMPACT_LIMIT_COEFF: float = 0.95
B4_1B_WELDED_FLANGE_FL_FRACTION_OF_FY: float = 0.7  # FL = 0.7 Fy (Eq. F3-1 background)

# Case 15 (doubly-symmetric I web, flexure): lambda_p = 3.76 sqrt(E/Fy),
# lambda_r = 5.70 sqrt(E/Fy).
B4_1B_WEB_COMPACT_LIMIT_COEFF: float = 3.76
B4_1B_WEB_NONCOMPACT_LIMIT_COEFF: float = 5.70

# Case 16 (singly-symmetric I web, flexure) numerical constants:
# lambda_pw = (hc/hp) sqrt(E/Fy) / (0.54 Mp/My - 0.09)^2  <=  lambda_rw,
# lambda_rw = 5.70 sqrt(E/Fy).
B4_1B_CASE16_MP_MY_COEFF: float = 0.54
B4_1B_CASE16_MP_MY_OFFSET: float = 0.09


def compute_singly_symmetric_web_lambda_pw_case16(
    web_compression_depth_hc: float,
    web_plastic_depth_hp: float,
    plastic_moment_Mp: float,
    yield_moment_My: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> float:
    """Return the §B4.1b **Case 16** web compact limit ``lambda_pw``.

    Singly-symmetric I-shaped members in flexure (AISC 360-22
    Table B4.1b, Case 16, p. 16.1-17)::

        lambda_pw = ( (hc/hp) * sqrt(E/Fy) )
                    / (0.54 * Mp/My - 0.09)^2     <=  lambda_rw

    with ``lambda_rw = 5.70 sqrt(E/Fy)`` (same as Case 15).  For a
    doubly-symmetric I this reduces to the Case 15 ``3.76 sqrt(E/Fy)``;
    the doubly-symmetric path keeps using Case 15 directly.

    Parameters
    ----------
    web_compression_depth_hc : float
        ``hc`` - 2 x (elastic NA -> inside face of compression flange) (mm).
    web_plastic_depth_hp : float
        ``hp`` - 2 x (plastic NA -> inside face of compression flange) (mm).
        Must be > 0.
    plastic_moment_Mp : float
        ``Mp = Fy * Zx`` (N*mm).
    yield_moment_My : float
        Yield moment ``My = Fy * Sxc`` to the compression flange (N*mm).
        Must be > 0.
    elastic_modulus_E, yield_stress_Fy : float
        ``E``, ``Fy`` (MPa).

    Returns
    -------
    float
        ``lambda_pw`` per Case 16, capped at ``lambda_rw``.

    Raises
    ------
    ValueError
        If ``hp <= 0`` or ``My <= 0`` (degenerate geometry).
    """
    if web_plastic_depth_hp <= 0.0:
        raise ValueError(f"web_plastic_depth_hp must be positive, got {web_plastic_depth_hp!r}")
    if yield_moment_My <= 0.0:
        raise ValueError(f"yield_moment_My must be positive, got {yield_moment_My!r}")
    sqrt_E_over_Fy = math.sqrt(elastic_modulus_E / yield_stress_Fy)
    lambda_rw = B4_1B_WEB_NONCOMPACT_LIMIT_COEFF * sqrt_E_over_Fy
    denominator = (
        B4_1B_CASE16_MP_MY_COEFF * (plastic_moment_Mp / yield_moment_My) - B4_1B_CASE16_MP_MY_OFFSET
    )
    # For any real I-shape Mp/My >= ~1 so the denominator is > 0; guard
    # the pathological case by falling back to the slender limit.
    if denominator <= 0.0:
        return lambda_rw
    lambda_pw = (
        (web_compression_depth_hc / web_plastic_depth_hp) * sqrt_E_over_Fy
    ) / denominator**2
    return min(lambda_pw, lambda_rw)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexuralCompactnessReport(Report):
    """Flange + web classification per AISC 360 Table B4.1b.

    Attributes
    ----------
    flange : PlateElementClassification
        Result of applying Case 10 (rolled) or Case 11 (welded).
    web : PlateElementClassification
        Result of applying Case 15.
    section_classification : str
        Worst of the two plate classifications. One of "compact",
        "non_compact", or "slender". Drives downstream routing in the
        flexural strength facade (F2 / F3 / F5).
    construction : str
        Echo of the input construction (``"rolled"`` or ``"welded"``).
    """

    flange: PlateElementClassification = None  # type: ignore[assignment]
    web: PlateElementClassification = None  # type: ignore[assignment]
    section_classification: FlexuralPlateClass = "compact"
    construction: SectionConstruction = "welded"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _classify_one_flexural_plate_element(
    element_name: str,
    aisc_case: str,
    slenderness_ratio_lambda: float,
    compact_limit_lambda_p: float,
    noncompact_limit_lambda_r: float,
) -> PlateElementClassification:
    """Apply the standard compact / non-compact / slender decision."""
    if slenderness_ratio_lambda <= compact_limit_lambda_p:
        classification: FlexuralPlateClass = "compact"
    elif slenderness_ratio_lambda <= noncompact_limit_lambda_r:
        classification = "non_compact"
    else:
        classification = "slender"
    return PlateElementClassification(
        element_name=element_name,
        aisc_case=aisc_case,
        slenderness_ratio_lambda=slenderness_ratio_lambda,
        compact_limit_lambda_p=compact_limit_lambda_p,
        noncompact_limit_lambda_r=noncompact_limit_lambda_r,
        classification=classification,
    )


def _worst_flexural_classification(
    flange_classification: FlexuralPlateClass,
    web_classification: FlexuralPlateClass,
) -> FlexuralPlateClass:
    """Return the worse (less-favourable) of two flexural classes.

    Ordering: compact (best) < non_compact < slender (worst).
    """
    rank: dict[FlexuralPlateClass, int] = {
        "compact": 0,
        "non_compact": 1,
        "slender": 2,
    }
    if rank[web_classification] > rank[flange_classification]:
        return web_classification
    return flange_classification


# ---------------------------------------------------------------------------
# Public classifier
# ---------------------------------------------------------------------------
_CITED_CLAUSES_B4_1B: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="AISC 360-22",
        section="B4.1b",
        equation=None,
        page="16.1-11",
    ),
    AISCClauseReference(
        specification="AISC 360-22",
        section="Table B4.1b",
        equation="Cases 10, 11, 15",
        page="16.1-15",
    ),
)


def classify_flexural_compactness_B4_1b(
    section_properties: SectionProperties,
    material: SteelMaterial,
    construction: SectionConstruction = "welded",
) -> FlexuralCompactnessReport:
    """Classify a doubly-symmetric I per AISC 360 Table B4.1b.

    Parameters
    ----------
    section_properties : SectionProperties
        Output of `DoublySymmetricISection.compute_section_properties()`
        or any catalog adapter producing the same fields.
    material : SteelMaterial
        Steel grade.  Only Fy and E are read.
    construction : {"rolled", "welded"}, optional
        Whether the section is a rolled W (Case 10 flange) or a welded
        built-up I (Case 11 flange with kc).  Default ``"welded"`` to
        match the spreadsheet's plate-built sections.

    Returns
    -------
    FlexuralCompactnessReport
    """
    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    sqrt_E_over_Fy: float = math.sqrt(E / Fy)

    # --- Flange (Case 10 rolled OR Case 11 welded) ---
    lambda_flange: float = section_properties.flange_width_to_thickness_ratio_bf_2tf
    lambda_pf: float = (
        B4_1B_ROLLED_FLANGE_COMPACT_LIMIT_COEFF * sqrt_E_over_Fy
    )  # same in both cases

    if construction == "rolled":
        flange_case = "B4.1b Case 10"
        lambda_rf = B4_1B_ROLLED_FLANGE_NONCOMPACT_LIMIT_COEFF * sqrt_E_over_Fy
    elif construction == "welded":
        flange_case = "B4.1b Case 11"
        kc: float = compute_kc_for_built_up_flange(
            section_properties.web_height_to_thickness_ratio_h_tw
        )
        FL: float = B4_1B_WELDED_FLANGE_FL_FRACTION_OF_FY * Fy
        lambda_rf = B4_1B_WELDED_FLANGE_NONCOMPACT_LIMIT_COEFF * math.sqrt(kc * E / FL)
    else:  # pragma: no cover - guarded by Literal
        raise ValueError(f"unknown construction {construction!r}")

    flange_classification = _classify_one_flexural_plate_element(
        element_name="flange",
        aisc_case=flange_case,
        slenderness_ratio_lambda=lambda_flange,
        compact_limit_lambda_p=lambda_pf,
        noncompact_limit_lambda_r=lambda_rf,
    )

    # --- Web (Case 15: same for rolled and welded) ---
    lambda_web: float = section_properties.web_height_to_thickness_ratio_h_tw
    lambda_pw: float = B4_1B_WEB_COMPACT_LIMIT_COEFF * sqrt_E_over_Fy
    lambda_rw: float = B4_1B_WEB_NONCOMPACT_LIMIT_COEFF * sqrt_E_over_Fy
    web_classification = _classify_one_flexural_plate_element(
        element_name="web",
        aisc_case="B4.1b Case 15",
        slenderness_ratio_lambda=lambda_web,
        compact_limit_lambda_p=lambda_pw,
        noncompact_limit_lambda_r=lambda_rw,
    )

    section_classification: FlexuralPlateClass = _worst_flexural_classification(
        flange_classification.classification,  # type: ignore[arg-type]
        web_classification.classification,  # type: ignore[arg-type]
    )

    return FlexuralCompactnessReport(
        cited_clauses=_CITED_CLAUSES_B4_1B,
        governing_limit_state="flexural_plate_element_slenderness",
        phi_LRFD=1.0,
        omega_ASD=1.0,
        nominal_strength=0.0,
        phi_strength_LRFD=0.0,
        omega_strength_ASD=0.0,
        flange=flange_classification,
        web=web_classification,
        section_classification=section_classification,
        construction=construction,
    )


__all__ = [
    "B4_1B_CASE16_MP_MY_COEFF",
    "B4_1B_CASE16_MP_MY_OFFSET",
    "B4_1B_ROLLED_FLANGE_COMPACT_LIMIT_COEFF",
    "B4_1B_ROLLED_FLANGE_NONCOMPACT_LIMIT_COEFF",
    "B4_1B_WEB_COMPACT_LIMIT_COEFF",
    "B4_1B_WEB_NONCOMPACT_LIMIT_COEFF",
    "B4_1B_WELDED_FLANGE_COMPACT_LIMIT_COEFF",
    "B4_1B_WELDED_FLANGE_FL_FRACTION_OF_FY",
    "B4_1B_WELDED_FLANGE_NONCOMPACT_LIMIT_COEFF",
    "FlexuralCompactnessReport",
    "classify_flexural_compactness_B4_1b",
    "compute_singly_symmetric_web_lambda_pw_case16",
]

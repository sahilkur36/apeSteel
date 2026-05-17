"""AISC 341 Table D1.1 - seismic compactness classification.

Classifies the flange and web of a doubly-symmetric I against the
"highly ductile" (lambda_hd) or "moderately ductile" (lambda_md)
slenderness limits required for fuse elements in seismic-force-
resisting systems (SMF/IMF beams, SCBF braces, EBF links, BRBF
gusset-to-brace plates, etc.).

The web limit varies with axial demand Ca = Pu / (phi_c * Py) (LRFD)
or Ca = Omega * Pa / Py (ASD); for pure-flexure elements Ca = 0 and
the formulas simplify.

Three code editions are supported:

* "AISC 341-22" (default; current code) - uses E / (Ry * Fy).
* "AISC 341-16" - similar to 22, slightly different web coefficients.
* "AISC 341-10" - uses E / Fy (no Ry factor). This matches the
  original spreadsheet `Vigas - Seccion I - Diseno LTB.xlsx` and
  legacy 2010-era designs.

References
----------
.. [1] AISC 341-22, "Seismic Provisions for Structural Steel Buildings",
       Section D1.1 and Table D1.1. American Institute of Steel
       Construction, 2022.
.. [2] AISC 341-10, "Seismic Provisions for Structural Steel Buildings",
       Section D1.1 and Table D1.1. American Institute of Steel
       Construction, 2010.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification._common import (
    DuctilityLevel,
    PlateElementClassification,
    SeismicCodeEdition,
)
from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from collections.abc import Mapping

    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

# ---------------------------------------------------------------------------
# Per-edition coefficients
# ---------------------------------------------------------------------------
# The seismic compactness limits all have the form
#     lambda_lim = COEFF * sqrt(E / D_FY)
# where D_FY is either Fy (legacy) or Ry*Fy (AISC 341-22).  The web
# limits additionally depend on the axial demand ratio Ca = Pu/(phi_c*Py).

#: Per-edition flange coefficients for HIGHLY ductile elements.
_FLANGE_COEFF_HIGHLY_DUCTILE: Mapping[SeismicCodeEdition, float] = {
    "AISC 341-22": 0.32,
    "AISC 341-16": 0.30,
    "AISC 341-10": 0.30,
}

#: Per-edition flange coefficients for MODERATELY ductile elements.
_FLANGE_COEFF_MODERATELY_DUCTILE: Mapping[SeismicCodeEdition, float] = {
    "AISC 341-22": 0.40,
    "AISC 341-16": 0.38,
    "AISC 341-10": 0.38,
}

#: Per-edition WEB coefficient at Ca = 0 (the base coefficient that
#: multiplies sqrt(E / D_Fy) at zero axial demand).  Highly ductile.
_WEB_BASE_COEFF_HIGHLY_DUCTILE: Mapping[SeismicCodeEdition, float] = {
    "AISC 341-22": 2.57,
    "AISC 341-16": 2.57,
    "AISC 341-10": 2.45,  # matches the original spreadsheet
}

#: Per-edition WEB coefficient at Ca = 0.  Moderately ductile.
_WEB_BASE_COEFF_MODERATELY_DUCTILE: Mapping[SeismicCodeEdition, float] = {
    "AISC 341-22": 3.96,
    "AISC 341-16": 3.96,
    "AISC 341-10": 3.76,
}

#: Per-edition Ca-correction factor for HIGHLY ductile web at low Ca
#: (Ca <= 0.114): lambda = COEFF * sqrt(E/D_Fy) * (1 - CA_FACTOR * Ca).
#: AISC 341-10 does not include a Ca correction at the low-axial branch
#: when applied to flexural beams (Ca = 0 is the only mode anyway), so
#: the legacy edition keeps the simple formula.
_WEB_CA_FACTOR_LOW_HIGHLY_DUCTILE: Mapping[SeismicCodeEdition, float] = {
    "AISC 341-22": 1.04,
    "AISC 341-16": 1.04,
    "AISC 341-10": 0.0,
}

_WEB_CA_FACTOR_LOW_MODERATELY_DUCTILE: Mapping[SeismicCodeEdition, float] = {
    "AISC 341-22": 3.04,
    "AISC 341-16": 3.04,
    "AISC 341-10": 0.0,
}

#: Threshold Ca below which the "low Ca" branch applies.  Same for
#: every edition that uses the Ca correction.
_WEB_CA_TRANSITION: float = 0.114

#: Floor on the high-Ca branch of the web limit (AISC 341-22 D1.1).
_WEB_HIGH_CA_FLOOR_COEFF: float = 1.57


def _denominator_stress_for_edition(
    yield_stress_Fy: float,
    expected_yield_ratio_Ry: float,
    code_edition: SeismicCodeEdition,
) -> float:
    """Return the denominator stress used inside sqrt(E / *).

    AISC 341-22 / 341-16 use the *expected* yield stress Ry * Fy.
    AISC 341-10 uses the nominal Fy.
    """
    if code_edition == "AISC 341-10":
        return yield_stress_Fy
    return expected_yield_ratio_Ry * yield_stress_Fy


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SeismicCompactnessReport(Report):
    """Flange + web seismic-compactness classification per AISC 341 D1.1.

    Attributes
    ----------
    code_edition : str
        Echo of the input edition.
    ductility_level : str
        "highly_ductile" or "moderately_ductile".
    axial_demand_ratio_Ca : float
        Pu/(phi_c*Py) (LRFD) or Omega*Pa/Py (ASD).  Defaults to 0.0 for
        pure flexure.
    flange : PlateElementClassification
        lambda, lambda_seismic, "acceptable" / "unacceptable".
    web : PlateElementClassification
    is_seismically_compact_section : bool
        True iff BOTH flange and web meet the seismic limit.
    """

    code_edition: SeismicCodeEdition = "AISC 341-22"
    ductility_level: DuctilityLevel = "highly_ductile"
    axial_demand_ratio_Ca: float = 0.0
    flange: PlateElementClassification = None  # type: ignore[assignment]
    web: PlateElementClassification = None  # type: ignore[assignment]
    is_seismically_compact_section: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _classify_one_seismic_plate_element(
    element_name: str,
    aisc_case: str,
    slenderness_ratio_lambda: float,
    seismic_limit_lambda: float,
) -> PlateElementClassification:
    """Apply the acceptable / unacceptable decision for AISC 341 D1.1."""
    classification = (
        "acceptable" if slenderness_ratio_lambda <= seismic_limit_lambda else "unacceptable"
    )
    return PlateElementClassification(
        element_name=element_name,
        aisc_case=aisc_case,
        slenderness_ratio_lambda=slenderness_ratio_lambda,
        compact_limit_lambda_p=None,  # AISC 341 has only one limit
        noncompact_limit_lambda_r=seismic_limit_lambda,
        classification=classification,
    )


def _compute_flange_seismic_limit_lambda(
    sqrt_E_over_DFy: float,
    ductility_level: DuctilityLevel,
    code_edition: SeismicCodeEdition,
) -> float:
    """Return lambda_hd (or lambda_md) for the flange of an I-shape."""
    if ductility_level == "highly_ductile":
        coeff = _FLANGE_COEFF_HIGHLY_DUCTILE[code_edition]
    else:
        coeff = _FLANGE_COEFF_MODERATELY_DUCTILE[code_edition]
    return coeff * sqrt_E_over_DFy


def _compute_web_seismic_limit_lambda(
    sqrt_E_over_DFy: float,
    axial_demand_ratio_Ca: float,
    ductility_level: DuctilityLevel,
    code_edition: SeismicCodeEdition,
) -> float:
    """Return lambda_hd (or lambda_md) for the web of an I-shape."""
    if ductility_level == "highly_ductile":
        base_coeff = _WEB_BASE_COEFF_HIGHLY_DUCTILE[code_edition]
        ca_factor_low = _WEB_CA_FACTOR_LOW_HIGHLY_DUCTILE[code_edition]
        high_branch_factor = 0.88
        high_branch_offset = 2.68
    else:
        base_coeff = _WEB_BASE_COEFF_MODERATELY_DUCTILE[code_edition]
        ca_factor_low = _WEB_CA_FACTOR_LOW_MODERATELY_DUCTILE[code_edition]
        high_branch_factor = 1.29
        high_branch_offset = 2.12

    if code_edition == "AISC 341-10":
        # Legacy edition: no Ca dependence, simple formula.
        return base_coeff * sqrt_E_over_DFy

    # AISC 341-22 / -16 two-branch formula.
    if axial_demand_ratio_Ca <= _WEB_CA_TRANSITION:
        return base_coeff * sqrt_E_over_DFy * (1.0 - ca_factor_low * axial_demand_ratio_Ca)
    high_branch_value = (
        high_branch_factor * sqrt_E_over_DFy * (high_branch_offset - axial_demand_ratio_Ca)
    )
    floor_value = _WEB_HIGH_CA_FLOOR_COEFF * sqrt_E_over_DFy
    return max(high_branch_value, floor_value)


# ---------------------------------------------------------------------------
# Public classifier
# ---------------------------------------------------------------------------
_CITED_CLAUSES_341_D1: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="AISC 341-22",
        section="D1.1",
        equation=None,
        page="9.1-19",
    ),
    AISCClauseReference(
        specification="AISC 341-22",
        section="Table D1.1",
        equation=None,
        page="9.1-20",
    ),
)


def classify_seismic_compactness_341_D1(
    section_properties: SectionProperties,
    material: SteelMaterial,
    ductility_level: DuctilityLevel,
    axial_demand_ratio_Ca: float = 0.0,
    code_edition: SeismicCodeEdition = "AISC 341-22",
) -> SeismicCompactnessReport:
    """Classify per AISC 341 Table D1.1 for a doubly-symmetric I.

    Parameters
    ----------
    section_properties : SectionProperties
    material : SteelMaterial
        Reads Fy, E, and Ry.
    ductility_level : {"highly_ductile", "moderately_ductile"}
    axial_demand_ratio_Ca : float, optional
        Ca = Pu/(phi_c*Py) for LRFD or Omega*Pa/Py for ASD.  Default 0.0
        (pure flexure).
    code_edition : {"AISC 341-22", "AISC 341-16", "AISC 341-10"}, optional
        Default "AISC 341-22" (current code-of-record).

    Returns
    -------
    SeismicCompactnessReport
    """
    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    Ry: float = material.expected_yield_ratio_Ry

    denominator_stress = _denominator_stress_for_edition(
        yield_stress_Fy=Fy,
        expected_yield_ratio_Ry=Ry,
        code_edition=code_edition,
    )
    sqrt_E_over_DFy: float = math.sqrt(E / denominator_stress)

    # --- Flange (Case BH-1 / BH-2 in AISC 341-22 Table D1.1) ---
    lambda_flange: float = section_properties.flange_width_to_thickness_ratio_bf_2tf
    flange_limit = _compute_flange_seismic_limit_lambda(
        sqrt_E_over_DFy=sqrt_E_over_DFy,
        ductility_level=ductility_level,
        code_edition=code_edition,
    )
    flange_classification = _classify_one_seismic_plate_element(
        element_name="flange",
        aisc_case=f"341 D1.1 flange ({ductility_level})",
        slenderness_ratio_lambda=lambda_flange,
        seismic_limit_lambda=flange_limit,
    )

    # --- Web (Case BH-9 / etc.) ---
    lambda_web: float = section_properties.web_height_to_thickness_ratio_h_tw
    web_limit = _compute_web_seismic_limit_lambda(
        sqrt_E_over_DFy=sqrt_E_over_DFy,
        axial_demand_ratio_Ca=axial_demand_ratio_Ca,
        ductility_level=ductility_level,
        code_edition=code_edition,
    )
    web_classification = _classify_one_seismic_plate_element(
        element_name="web",
        aisc_case=f"341 D1.1 web ({ductility_level})",
        slenderness_ratio_lambda=lambda_web,
        seismic_limit_lambda=web_limit,
    )

    is_seismically_compact_section: bool = (
        flange_classification.classification == "acceptable"
        and web_classification.classification == "acceptable"
    )

    return SeismicCompactnessReport(
        cited_clauses=_CITED_CLAUSES_341_D1,
        governing_limit_state="seismic_plate_element_slenderness",
        phi_LRFD=1.0,
        omega_ASD=1.0,
        nominal_strength=0.0,
        phi_strength_LRFD=0.0,
        omega_strength_ASD=0.0,
        code_edition=code_edition,
        ductility_level=ductility_level,
        axial_demand_ratio_Ca=axial_demand_ratio_Ca,
        flange=flange_classification,
        web=web_classification,
        is_seismically_compact_section=is_seismically_compact_section,
    )


__all__ = [
    "SeismicCompactnessReport",
    "classify_seismic_compactness_341_D1",
]

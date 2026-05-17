"""AISC 360 §G2 - shear strength of doubly-symmetric I-shapes.

Three-regime Cv1 decision tree per §G2.1(b):

    lambda_w = h / tw

    1) Yielding (Eq. G2-3):
           lambda_w <= 1.10 * sqrt(kv * E / Fy)
           Cv1 = 1.0

    2) Inelastic web buckling (Eq. G2-4):
           1.10 * sqrt(kv*E/Fy) < lambda_w <= 1.37 * sqrt(kv*E/Fy)
           Cv1 = 1.10 * sqrt(kv*E/Fy) / lambda_w

    3) Elastic web buckling (Eq. G2-5):
           lambda_w > 1.37 * sqrt(kv*E/Fy)
           Cv1 = 1.51 * E * kv / (lambda_w^2 * Fy)

Nominal shear strength (Eq. G2-1 / G2-2):
    Vn = 0.6 * Fy * Aw * Cv1

Web area Aw = d * tw (overall depth times web thickness) per AISC §G2.

Plate-buckling coefficient kv:
    * Unstiffened webs (no transverse stiffeners): kv = 5.34
      (AISC 360-22 §G2.1(b)(i)) - though for typical h/tw < 260, the
      yielding regime governs and the value is irrelevant.  The legacy
      kv = 5.0 from older editions and from the spreadsheet is also
      supported for back-compatibility; the user picks via
      `unstiffened_web_kv` parameter.

    * Stiffened webs with transverse stiffener spacing `a`:
          kv = 5 + 5 / (a/h)^2         when a/h <= 3 and a/h <= (260/(h/tw))^2
          kv = 5                       otherwise
      (AISC 360-22 §G2.1(b)(ii))

phi factor:
    * Rolled doubly-symmetric I-shapes with h/tw <= 2.24*sqrt(E/Fy):
      phi = 1.00 (no buckling, Eq. G2-2)
    * All other cases: phi = 0.90

References
----------
.. [1] AISC 360-22 §G2 "I-Shaped Members and Channels", p. 16.1-65.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PHI_SHEAR_LRFD_STOCKY_ROLLED: float = 1.00
PHI_SHEAR_LRFD_GENERAL: float = 0.90
OMEGA_SHEAR_ASD_STOCKY_ROLLED: float = 1.50
OMEGA_SHEAR_ASD_GENERAL: float = 1.67

# AISC G2-1 base coefficient: Vn = 0.6 * Fy * Aw * Cv1
G2_NOMINAL_SHEAR_STRESS_COEFFICIENT_0p6: float = 0.6

# Yielding-regime upper bound (Eq. G2-3 LHS): 1.10 * sqrt(kv*E/Fy)
G2_YIELDING_LIMIT_COEFFICIENT_1p10: float = 1.10
# Inelastic-regime upper bound (Eq. G2-4 LHS): 1.37 * sqrt(kv*E/Fy)
G2_INELASTIC_LIMIT_COEFFICIENT_1p37: float = 1.37
# Elastic-regime Cv1 coefficient (Eq. G2-5): Cv1 = 1.51 * kv * E / (lambda^2 * Fy)
G2_ELASTIC_BUCKLING_COEFFICIENT_1p51: float = 1.51
# Stocky-web exception limit for phi = 1.0: h/tw <= 2.24*sqrt(E/Fy)
G2_STOCKY_WEB_LIMIT_COEFFICIENT_2p24: float = 2.24
# Default kv for unstiffened webs in AISC 360-22 (was 5.0 in older editions).
UNSTIFFENED_WEB_KV_AISC_360_22: float = 5.34
UNSTIFFENED_WEB_KV_LEGACY: float = 5.0


ShearRegime = Literal["yielding", "inelastic_buckling", "elastic_buckling"]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ShearG2Report(Report):
    """AISC §G2 shear-strength result for a doubly-symmetric I-shape.

    Attributes
    ----------
    construction : {"rolled", "welded"}
        Drives the stocky-rolled phi = 1.00 exception.
    transverse_stiffener_spacing_a : float or None
        Stiffener spacing (mm).  None for unstiffened webs.
    web_slenderness_ratio_lambda_w : float
        h/tw.
    web_plate_buckling_coefficient_kv : float
        kv per AISC §G2.1(b).
    yielding_limit_lambda_1 : float
        1.10 * sqrt(kv*E/Fy).  Below this, Cv1 = 1.0.
    inelastic_limit_lambda_2 : float
        1.37 * sqrt(kv*E/Fy).  Between lambda_1 and lambda_2, Cv1 < 1.0.
    web_shear_strength_coefficient_Cv1 : float
    web_area_Aw : float
        Aw = d * tw (mm^2).
    nominal_shear_strength_Vn : float
        Vn = 0.6 * Fy * Aw * Cv1 (N).
    phi_shear_strength_phi_Vn_LRFD : float
        phi * Vn (N).
    governing_shear_regime : str
        "yielding", "inelastic_buckling", or "elastic_buckling".
    is_qualified_for_phi_1p00_stocky_rolled_exception : bool
        True when construction == "rolled" and h/tw <= 2.24*sqrt(E/Fy).
    """

    construction: SectionConstruction = "welded"
    transverse_stiffener_spacing_a: float | None = None
    web_slenderness_ratio_lambda_w: float = 0.0
    web_plate_buckling_coefficient_kv: float = 0.0
    yielding_limit_lambda_1: float = 0.0
    inelastic_limit_lambda_2: float = 0.0
    web_shear_strength_coefficient_Cv1: float = 0.0
    web_area_Aw: float = 0.0
    nominal_shear_strength_Vn: float = 0.0
    phi_shear_strength_phi_Vn_LRFD: float = 0.0
    governing_shear_regime: ShearRegime = "yielding"
    is_qualified_for_phi_1p00_stocky_rolled_exception: bool = False


_CITATIONS_G2: tuple[AISCClauseReference, ...] = (
    AISCClauseReference("AISC 360-22", "G1", None, "16.1-65"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-1", "16.1-65"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-2", "16.1-65"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-3", "16.1-66"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-4", "16.1-66"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-5", "16.1-66"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def compute_kv_for_stiffened_web(
    web_slenderness_ratio_h_over_tw: float,
    transverse_stiffener_spacing_a: float,
    web_clear_height_h: float,
) -> float:
    """Return kv per AISC §G2.1(b)(ii) for a transversely-stiffened web.

    kv = 5 + 5/(a/h)^2  when a/h <= 3 AND a/h <= (260/(h/tw))^2
    kv = 5              otherwise
    """
    a_over_h = transverse_stiffener_spacing_a / web_clear_height_h
    upper_bound_for_h_tw_ratio = (260.0 / web_slenderness_ratio_h_over_tw) ** 2
    if a_over_h <= 3.0 and a_over_h <= upper_bound_for_h_tw_ratio:
        return 5.0 + 5.0 / (a_over_h**2)
    return 5.0


def compute_Cv1_three_regime(
    web_slenderness_ratio_lambda_w: float,
    web_plate_buckling_coefficient_kv: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> tuple[float, ShearRegime, float, float]:
    """Return (Cv1, regime, lambda_1, lambda_2) for the AISC §G2.1(b) tree.

    lambda_1 = 1.10*sqrt(kv*E/Fy)   yielding/inelastic boundary
    lambda_2 = 1.37*sqrt(kv*E/Fy)   inelastic/elastic boundary
    """
    lam_w = web_slenderness_ratio_lambda_w
    kv = web_plate_buckling_coefficient_kv
    E = elastic_modulus_E
    Fy = yield_stress_Fy

    sqrt_kvE_over_Fy = math.sqrt(kv * E / Fy)
    lam_1 = G2_YIELDING_LIMIT_COEFFICIENT_1p10 * sqrt_kvE_over_Fy
    lam_2 = G2_INELASTIC_LIMIT_COEFFICIENT_1p37 * sqrt_kvE_over_Fy

    if lam_w <= lam_1:
        return 1.0, "yielding", lam_1, lam_2
    if lam_w <= lam_2:
        return lam_1 / lam_w, "inelastic_buckling", lam_1, lam_2
    Cv1 = G2_ELASTIC_BUCKLING_COEFFICIENT_1p51 * kv * E / (lam_w**2 * Fy)
    return Cv1, "elastic_buckling", lam_1, lam_2


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------
def compute_shear_strength_G2_doubly_symmetric(
    section_properties: SectionProperties,
    material: SteelMaterial,
    construction: SectionConstruction = "welded",
    transverse_stiffener_spacing_a: float | None = None,
    unstiffened_web_kv: float = UNSTIFFENED_WEB_KV_AISC_360_22,
) -> ShearG2Report:
    """Return Vn per AISC §G2 for a doubly-symmetric I-shape.

    Parameters
    ----------
    section_properties : SectionProperties
        Reads `overall_depth_d` (for Aw),
        `web_height_to_thickness_ratio_h_tw`, and indirectly the web
        clear height (needed only when stiffened).
    material : SteelMaterial
    construction : {"rolled", "welded"}, optional
        Default "welded".  Affects the phi = 1.00 exception for stocky-
        web rolled sections.
    transverse_stiffener_spacing_a : float or None, optional
        Transverse-stiffener spacing in mm.  None means unstiffened web
        (default).
    unstiffened_web_kv : float, optional
        kv for an unstiffened web.  AISC 360-22 uses 5.34 (default);
        legacy editions and the original spreadsheet use 5.0.

    Returns
    -------
    ShearG2Report
    """
    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    d: float = section_properties.overall_depth_d
    lambda_w: float = section_properties.web_height_to_thickness_ratio_h_tw
    # Aw = d * tw (AISC §G2 convention).  We back out tw from h/tw and h,
    # but since both are inputs already, the simpler form: web_clear_height
    # is not directly stored; reconstruct tw from
    # Aw_via_props.web_height_to_thickness_ratio_h_tw is the ratio so:
    # we know Aw = d * tw.  Properties expose Ag, Ix, ... but not tw
    # directly.  We can read web_thickness from the geometry if available
    # via the source field, but more robustly compute tw indirectly.
    # Actually SectionProperties stores web_height_to_thickness_ratio_h_tw
    # (= hw/tw) -- and we know hw + 2*tf = d.  We can't recover tw without
    # tf.  Therefore: take Aw as d * tw, with tw = hw / (h/tw) only if
    # we know hw.  Easier path: require the caller to derive Aw outside, OR
    # add Aw as an explicit property of SectionProperties.
    # Pragmatic Phase-5 solution: assume Aw = d * d / lambda_w * (lambda_w / d)
    # ...no, just compute it from the geometry directly when available.
    # The cleanest fix: SectionProperties does NOT currently store the
    # web area or web thickness explicitly.  For Phase 5 we add a small
    # derivation: hw = lambda_w * tw and d = hw + 2*tf, but we don't have
    # tf either.  So we add `web_thickness_tw` to SectionProperties.
    # That's a backwards-compatible additive change.

    # Compute Aw = d * tw using the new field we will add to SectionProperties.
    tw: float = section_properties.web_thickness_tw
    Aw: float = d * tw

    # kv
    if transverse_stiffener_spacing_a is None:
        kv = unstiffened_web_kv
    else:
        # Need hw (web clear height) for a/h.  Recover hw = lambda_w * tw.
        hw = lambda_w * tw
        kv = compute_kv_for_stiffened_web(
            web_slenderness_ratio_h_over_tw=lambda_w,
            transverse_stiffener_spacing_a=transverse_stiffener_spacing_a,
            web_clear_height_h=hw,
        )

    # Cv1 + regime
    Cv1, regime, lam_1, lam_2 = compute_Cv1_three_regime(
        web_slenderness_ratio_lambda_w=lambda_w,
        web_plate_buckling_coefficient_kv=kv,
        elastic_modulus_E=E,
        yield_stress_Fy=Fy,
    )

    Vn: float = G2_NOMINAL_SHEAR_STRESS_COEFFICIENT_0p6 * Fy * Aw * Cv1

    # phi: 1.00 only for ROLLED doubly-symmetric I with h/tw <= 2.24*sqrt(E/Fy)
    stocky_limit = G2_STOCKY_WEB_LIMIT_COEFFICIENT_2p24 * math.sqrt(E / Fy)
    is_stocky_rolled = (construction == "rolled") and (lambda_w <= stocky_limit)
    if is_stocky_rolled:
        phi = PHI_SHEAR_LRFD_STOCKY_ROLLED
        omega = OMEGA_SHEAR_ASD_STOCKY_ROLLED
    else:
        phi = PHI_SHEAR_LRFD_GENERAL
        omega = OMEGA_SHEAR_ASD_GENERAL

    return ShearG2Report(
        cited_clauses=_CITATIONS_G2,
        governing_limit_state=regime,
        phi_LRFD=phi,
        omega_ASD=omega,
        nominal_strength=Vn,
        phi_strength_LRFD=phi * Vn,
        omega_strength_ASD=Vn / omega,
        construction=construction,
        transverse_stiffener_spacing_a=transverse_stiffener_spacing_a,
        web_slenderness_ratio_lambda_w=lambda_w,
        web_plate_buckling_coefficient_kv=kv,
        yielding_limit_lambda_1=lam_1,
        inelastic_limit_lambda_2=lam_2,
        web_shear_strength_coefficient_Cv1=Cv1,
        web_area_Aw=Aw,
        nominal_shear_strength_Vn=Vn,
        phi_shear_strength_phi_Vn_LRFD=phi * Vn,
        governing_shear_regime=regime,
        is_qualified_for_phi_1p00_stocky_rolled_exception=is_stocky_rolled,
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

"""Issue #2: bind §F5 flange handling and the SS web limit to AISC 360-22.

Hand-calc anchors (reviewer-signable, independent of the implementation
helpers): the §B4.1b **Case 16** singly-symmetric web ``lambda_pw``
arithmetic, the corrected AISC ``hp`` definition, and the §F5 fix that
uses the *stored* compression-flange dimensions rather than back-solving
from ``Ag`` (which would fold a rolled section's fillet area in).
"""

from __future__ import annotations

import math

from apeSteel import A992
from apeSteel.classification.flexural_compactness_B4_1b import (
    compute_singly_symmetric_web_lambda_pw_case16,
)
from apeSteel.core import units as u
from apeSteel.flexure import compute_flexural_strength_F5_slender_web_plate_girder
from apeSteel.sections.geometry import SinglySymmetricISection
from apeSteel.sections.properties import SectionProperties

_FY = A992.yield_stress_Fy
_E = A992.elastic_modulus_E
_SQRT_E_FY = math.sqrt(_E / _FY)  # ~ 24.083 for A992 (50 ksi)


# ---------------------------------------------------------------------------
# Item 2 - Table B4.1b Case 16 (AISC 360-22 p. 16.1-17)
#   lambda_pw = (hc/hp) sqrt(E/Fy) / (0.54 Mp/My - 0.09)^2  <=  lambda_rw
# ---------------------------------------------------------------------------
def test_case16_lambda_pw_hand_calc() -> None:
    # Hand inputs (kN-mm); arbitrary but representative SS web.
    hc, hp = 880.0, 760.0
    Mp, My = 1.20e9, 1.05e9  # Mp/My = 1.142857...
    # By hand, with the literal AISC constants:
    den = 0.54 * (Mp / My) - 0.09  # = 0.54*1.142857 - 0.09 = 0.527143
    expected = (hc / hp) * _SQRT_E_FY / den**2  # (1.157895)*24.0832/0.277880
    lambda_rw = 5.70 * _SQRT_E_FY
    expected = min(expected, lambda_rw)
    got = compute_singly_symmetric_web_lambda_pw_case16(
        web_compression_depth_hc=hc,
        web_plastic_depth_hp=hp,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
        elastic_modulus_E=_E,
        yield_stress_Fy=_FY,
    )
    assert math.isclose(got, expected, rel_tol=1e-12)
    # Spot value (sign-able): den=0.527143, den^2=0.277880,
    # (880/760)=1.157895, *24.0832=27.884, /0.277880 = 100.35.
    assert math.isclose(got, 100.35, rel_tol=2e-3)


def test_case16_capped_at_lambda_rw() -> None:
    # Tiny hc/hp-driven denominator -> formula explodes -> must cap at lrw.
    lrw = 5.70 * _SQRT_E_FY
    got = compute_singly_symmetric_web_lambda_pw_case16(
        web_compression_depth_hc=2000.0,
        web_plastic_depth_hp=50.0,
        plastic_moment_Mp=1.0e9,
        yield_moment_My=0.99e9,
        elastic_modulus_E=_E,
        yield_stress_Fy=_FY,
    )
    assert math.isclose(got, lrw, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Item 2 - corrected AISC hp = 2 x (PNA -> inside face of compression flange)
# ---------------------------------------------------------------------------
def test_corrected_hp_definition_matches_independent_PNA() -> None:
    bft, tft = 220.0, 16.0
    bfb, tfb = 360.0, 24.0
    hw, tw = 900.0, 11.0
    ss = SinglySymmetricISection(
        top_flange_width_bf_top=bft * u.mm,
        top_flange_thickness_tf_top=tft * u.mm,
        bot_flange_width_bf_bot=bfb * u.mm,
        bot_flange_thickness_tf_bot=tfb * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )
    sp_top = ss.compute_section_properties("top")
    # Independent PNA from area balance (PNA in the web):
    Ag = bft * tft + hw * tw + bfb * tfb
    Ab = bfb * tfb
    dpna = tfb + (Ag / 2.0 - Ab) / tw  # from bottom fibre
    # Top compression: inside face of the top flange is at (tfb + hw).
    hp_expected = 2.0 * abs((hw + tfb) - dpna)
    assert math.isclose(sp_top.plastic_neutral_axis_depth_hp, hp_expected, rel_tol=1e-12)
    # It must NOT equal the old (wrong) 2*|y_c - dPNA| centroid form.
    bad_old = 2.0 * abs(
        # elastic centroid:
        (bft * tft * (tfb + hw + tft / 2.0) + hw * tw * (tfb + hw / 2.0) + bfb * tfb * (tfb / 2.0))
        / Ag
        - dpna
    )
    assert not math.isclose(sp_top.plastic_neutral_axis_depth_hp, bad_old, rel_tol=1e-6)


def test_DS_equivalent_SS_has_hp_equal_hc_equal_hw() -> None:
    """For equal flanges the elastic NA = plastic NA = mid-depth, so the
    corrected hp and hc both equal the web clear height hw."""
    leg = dict(
        top_flange_width_bf_top=300.0 * u.mm,
        top_flange_thickness_tf_top=20.0 * u.mm,
        bot_flange_width_bf_bot=300.0 * u.mm,
        bot_flange_thickness_tf_bot=20.0 * u.mm,
        web_clear_height_hw=600.0 * u.mm,
        web_thickness_tw=12.0 * u.mm,
    )
    sp = SinglySymmetricISection(**leg).compute_section_properties("top")
    assert math.isclose(sp.plastic_neutral_axis_depth_hp, 600.0 * u.mm, rel_tol=1e-9)
    assert math.isclose(sp.compression_zone_depth_hc, 600.0 * u.mm, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Item 1 - §F5 uses the STORED compression-flange dims, not an Ag back-solve
# ---------------------------------------------------------------------------
def _slender_web_props_with_fillet(fillet_area: float) -> SectionProperties:
    """A doubly-symmetric slender-web SectionProperties whose Ag carries
    an extra fillet/k area (Ag > 2*bf*tf + hw*tw), with the *true* flange
    dims stored explicitly (as catalog adapters do)."""
    bf, tf = 250.0, 16.0
    hw, tw = 1700.0, 8.0  # h/tw = 212.5 -> slender web (A992)
    Ag = 2.0 * bf * tf + hw * tw + fillet_area
    Ix = (bf * tf**3 / 12.0 + bf * tf * ((hw + tf) / 2.0) ** 2) * 2.0 + tw * hw**3 / 12.0
    Sx = Ix / ((hw + 2.0 * tf) / 2.0)
    return SectionProperties(
        overall_depth_d=hw + 2.0 * tf,
        gross_area_Ag=Ag,
        nominal_weight_per_unit_length_w=0.0,
        moment_of_inertia_strong_axis_Ix=Ix,
        elastic_section_modulus_strong_axis_Sx=Sx,
        plastic_section_modulus_strong_axis_Zx=bf * tf * (hw + tf) + tw * hw**2 / 4.0,
        radius_of_gyration_strong_axis_rx=math.sqrt(Ix / Ag),
        moment_of_inertia_weak_axis_Iy=2.0 * tf * bf**3 / 12.0,
        elastic_section_modulus_weak_axis_Sy=2.0 * tf * bf**3 / 12.0 / (bf / 2.0),
        plastic_section_modulus_weak_axis_Zy=tf * bf**2 / 2.0,
        radius_of_gyration_weak_axis_ry=10.0,
        torsional_constant_J=1.0e6,
        warping_constant_Cw=1.0e12,
        distance_between_flange_centroids_ho=hw + tf,
        effective_radius_of_gyration_for_LTB_rts=30.0,
        flange_width_to_thickness_ratio_bf_2tf=bf / (2.0 * tf),
        web_height_to_thickness_ratio_h_tw=hw / tw,
        web_thickness_tw=tw,
        flange_width_bf=bf,  # the TRUE flange (no fillet)
        flange_thickness_tf=tf,
    )


def test_F5_uses_stored_flange_not_Ag_backsolve() -> None:
    bf_true, tf_true = 250.0, 16.0
    hw, tw = 1700.0, 8.0
    no_fillet = _slender_web_props_with_fillet(0.0)
    with_fillet = _slender_web_props_with_fillet(fillet_area=4000.0)  # +k area

    r0 = compute_flexural_strength_F5_slender_web_plate_girder(no_fillet, A992, 4000.0, 1.0)
    rf = compute_flexural_strength_F5_slender_web_plate_girder(with_fillet, A992, 4000.0, 1.0)

    # AISC-correct aw = hc*tw/(bfc*tfc) with the TRUE flange; independent
    # of the extra Ag fillet area -> identical with and without fillet.
    aw_true = min((hw * tw) / (bf_true * tf_true), 10.0)
    assert math.isclose(r0.web_to_flange_area_ratio_aw, aw_true, rel_tol=1e-12)
    assert math.isclose(rf.web_to_flange_area_ratio_aw, aw_true, rel_tol=1e-12)
    # The OLD back-solve would have inflated bf from the fillet area, so
    # the with-fillet result would have differed; bind-to-code => same Mn.
    assert math.isclose(
        r0.nominal_flexural_strength_Mn,
        rf.nominal_flexural_strength_Mn,
        rel_tol=1e-12,
    )

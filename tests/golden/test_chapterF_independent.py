"""Independent correctness anchor for the AISC Chapter-F facades.

This is the test the review identified as missing: it pins
``compute_flexural_strength_F2/F3/F4/F5`` to a from-scratch AISC 360-22
re-derivation (:mod:`tests.golden._chapterF_aisc_oracle`) that imports
nothing from :mod:`apeSteel.flexure`.  Section properties come from the
apeSteel *geometry* layer (independently cross-checked against scipy
numerical integration in the geometry unit tests); only the Chapter-F
strength composition -- the part the regression snapshots cannot
validate because they snapshot their own output -- is checked here.

A disagreement means either the library or the oracle implements an
AISC equation wrong.  Agreement is expected to be bit-exact: both sides
implement the same closed-form spec equations, but from independently
written source, so the test catches transcription/constant errors, not
floating-point divergence.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

from apeSteel import (
    A992,
    S355,
    Bracing,
    DoublySymmetricISection,
    SinglySymmetricISection,
)
from apeSteel.core import units as u
from apeSteel.element import Element
from tests.golden._chapterF_aisc_oracle import (
    OracleProps,
    mn_F2,
    mn_F3,
    mn_F4,
    mn_F5,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

REL_TOL = 1e-9


def _props(sp: SectionProperties, material: SteelMaterial) -> OracleProps:
    return OracleProps(
        Fy=material.yield_stress_Fy,
        E=material.elastic_modulus_E,
        Sx=sp.elastic_section_modulus_strong_axis_Sx,
        Zx=sp.plastic_section_modulus_strong_axis_Zx,
        ry=sp.radius_of_gyration_weak_axis_ry,
        rts=sp.effective_radius_of_gyration_for_LTB_rts,
        ho=sp.distance_between_flange_centroids_ho,
        J=sp.torsional_constant_J,
        tw=sp.web_thickness_tw,
        lam_w=sp.web_height_to_thickness_ratio_h_tw,
        lam_f=sp.flange_width_to_thickness_ratio_bf_2tf,
        bfc=sp.resolved_compression_flange_width_bfc(),
        tfc=sp.resolved_compression_flange_thickness_tfc(),
        Sxc=sp.resolved_Sxc(),
        Sxt=sp.resolved_Sxt(),
        iyc_over_iy=sp.resolved_iyc_over_iy(),
        hc=sp.resolved_hc(),
        Ag=sp.gross_area_Ag,
        hp=sp.plastic_neutral_axis_depth_hp,
    )


def _ds(bf: float, tf: float, hw: float, tw: float) -> DoublySymmetricISection:
    return DoublySymmetricISection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )


def _ss(
    bft: float, tft: float, bfb: float, tfb: float, hw: float, tw: float
) -> SinglySymmetricISection:
    return SinglySymmetricISection(
        top_flange_width_bf_top=bft * u.mm,
        top_flange_thickness_tf_top=tft * u.mm,
        bot_flange_width_bf_bot=bfb * u.mm,
        bot_flange_thickness_tf_bot=tfb * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )


# Compact DS (bf/2tf=7.5, h/tw=35.7)  -> F2
_F2_SEC = _ds(300, 20, 500, 14)
# Compact web, non-compact welded flange (bf/2tf=12.5, h/tw=35.7) -> F3
_F3_SEC = _ds(300, 12, 500, 14)
# Non-compact web (h/tw=110), non-compact flange (bf/2tf=12.5) -> F4 (DS)
_F4_DS_SEC = _ds(300, 12, 1100, 10)
# Singly-symmetric, unequal flanges -> F4 (SS)
_F4_SS_SEC = _ss(250, 16, 400, 25, 1000, 10)
# Slender web (h/tw=170) -> F5
_F5_SEC = _ds(300, 20, 1700, 10)


_F2_CASES = [
    ("F2 yielding A992", _F2_SEC, A992, 0.5),
    ("F2 inelastic A992", _F2_SEC, A992, 3.0),
    ("F2 elastic A992", _F2_SEC, A992, 12.0),
    ("F2 inelastic S355", _F2_SEC, S355, 3.0),
]

_F3_CASES = [
    ("F3 inelastic", _F3_SEC, A992, 3.0),
    ("F3 elastic", _F3_SEC, A992, 12.0),
    ("F3 short/FLB", _F3_SEC, A992, 0.4),
    ("F3 S355 inelastic", _F3_SEC, S355, 3.0),
]

_F5_CASES = [
    ("F5 short", _F5_SEC, A992, 1.0),
    ("F5 inelastic", _F5_SEC, A992, 5.0),
    ("F5 elastic", _F5_SEC, A992, 16.0),
]

# (id, section, material, side, Lb_m)
_F4_CASES = [
    ("F4 DS inelastic", _F4_DS_SEC, A992, "top", 3.0),
    ("F4 DS elastic", _F4_DS_SEC, A992, "top", 14.0),
    ("F4 DS short", _F4_DS_SEC, A992, "top", 0.5),
    ("F4 SS top Lb=3", _F4_SS_SEC, A992, "top", 3.0),
    ("F4 SS bot Lb=3", _F4_SS_SEC, A992, "bot", 3.0),
    ("F4 SS top Lb=16", _F4_SS_SEC, A992, "top", 16.0),
    ("F4 SS bot S355", _F4_SS_SEC, S355, "bot", 4.0),
]


def _element(
    section: DoublySymmetricISection | SinglySymmetricISection,
    material: SteelMaterial,
    Lb_m: float,
) -> Element:
    lb = Lb_m * u.m
    return Element.from_section(
        section,
        material,
        "welded",
        Bracing(lb, lb, lateral_torsional_buckling_modification_factor_Cb=1.0),
    )


@pytest.mark.parametrize(
    ("name", "section", "material", "Lb_m"), _F2_CASES, ids=[c[0] for c in _F2_CASES]
)
def test_F2_matches_independent_AISC(
    name: str,
    section: DoublySymmetricISection,
    material: SteelMaterial,
    Lb_m: float,
) -> None:
    el = _element(section, material, Lb_m)
    r = el.flexural_strength_F2_top_flange()
    oracle = mn_F2(_props(el.section_properties, material), Lb_m * u.m, 1.0)
    assert math.isclose(r.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert r.governing_limit_state == oracle.governing


@pytest.mark.parametrize(
    ("name", "section", "material", "Lb_m"), _F3_CASES, ids=[c[0] for c in _F3_CASES]
)
def test_F3_matches_independent_AISC(
    name: str,
    section: DoublySymmetricISection,
    material: SteelMaterial,
    Lb_m: float,
) -> None:
    el = _element(section, material, Lb_m)
    r = el.flexural_strength_F3_top_flange()
    oracle = mn_F3(_props(el.section_properties, material), Lb_m * u.m, 1.0, "welded")
    assert math.isclose(r.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    o_family = (
        "flange_local_buckling"
        if oracle.governing == "flange_local_buckling"
        else "lateral_torsional_buckling"
    )
    assert r.governing_flexural_limit_state == o_family


@pytest.mark.parametrize(
    ("name", "section", "material", "side", "Lb_m"),
    _F4_CASES,
    ids=[c[0] for c in _F4_CASES],
)
def test_F4_matches_independent_AISC(
    name: str,
    section: DoublySymmetricISection | SinglySymmetricISection,
    material: SteelMaterial,
    side: str,
    Lb_m: float,
) -> None:
    el = _element(section, material, Lb_m)
    if side == "top":
        r = el.flexural_strength_F4_top_flange()
    else:
        r = el.flexural_strength_F4_bot_flange()
    sp = el.section_properties_for(side)  # type: ignore[arg-type]
    oracle = mn_F4(_props(sp, material), Lb_m * u.m, 1.0, "welded")
    assert math.isclose(r.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    # The F4 facade's governing token set is identical to the oracle's.
    assert r.governing_F4_limit_state == oracle.governing


@pytest.mark.parametrize(
    ("name", "section", "material", "Lb_m"), _F5_CASES, ids=[c[0] for c in _F5_CASES]
)
def test_F5_matches_independent_AISC(
    name: str,
    section: DoublySymmetricISection,
    material: SteelMaterial,
    Lb_m: float,
) -> None:
    el = _element(section, material, Lb_m)
    r = el.flexural_strength_F5_top_flange()
    oracle = mn_F5(_props(el.section_properties, material), Lb_m * u.m, 1.0, "welded")
    assert math.isclose(r.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)

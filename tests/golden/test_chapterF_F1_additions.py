"""Independent + golden anchors for the Phase F-1 *new* §F behaviours.

Phase F-1 added two behaviours on top of the bit-exact F2-F5
data-model refactor (which is regression-pinned by the *unchanged*
``test_chapterF_independent.py`` / ``test_flexure_F*_golden.py`` /
``test_catalog_flexure_F2_golden.py`` / the §F2 Excel anchor):

1. **Channel section constant ``c`` - AISC 360-22 Eq. F2-8b**
   ``c = (ho/2) * sqrt(Iy/Cw)`` (spec_chapterF.txt printed 16.1-54).
   §F2 previously hard-coded Eq. F2-8a ``c = 1`` (doubly-symmetric I).
   ``c`` enters only ``Lr`` (Eq. F2-6) and ``Mcr`` (Eq. F2-4), so a
   channel case is taken in the inelastic- and elastic-LTB regimes
   where ``c`` actually moves the answer.

2. **Singly-symmetric slender-web §F5**
   AISC 360-22 §F5 covers DS *and* SS slender-web I-shapes
   (spec_chapterF.txt printed 16.1-60/61).  The shipped code raised
   ``NotImplementedError`` for SS; F-1 implements Eq. F5-1/2/7/10 with
   ``Sxc``/``Sxt`` and the §F5.4 tension-flange-yielding limit state.

Both are anchored bit-exact (``rel_tol = 1e-9``) to the independent
AISC re-derivation in :mod:`tests.golden._chapterF_aisc_oracle` (which
imports **nothing** from :mod:`apeSteel.flexure`), exactly as the F2-F5
suite is.  This file is the *primary* (tier-1) anchor for the two new
behaviours; the corresponding golden snapshots are pinned inline.

Manual (tier-2) anchor availability
-----------------------------------
The AISC v15.1 Companion has channel §F2 worked examples (F.2-1A/1B,
F.2-2A/2B - C15x33.9, A36) and a plate-girder §F5 example (F.15), but
both are *catalog-shape* examples that need the C / built-up-plate
catalog wired into the flexure currency - that is Phase F-8, not F-1
(the channel/plate-girder geometry classes emit only
``CompressionSectionProperties`` today).  Per design note 10 §6 the
F-1 contract therefore anchors these two additive behaviours on the
independent stdlib oracle + a documented closed-form hand-calc (the
explicit Eq. F2-8b ``c`` check below), which is the §6 tier-2 fallback.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

from apeSteel import (
    A36,
    A992,
    S355,
    Bracing,
    SinglySymmetricISection,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)
from apeSteel.core import units as u
from apeSteel.sections.flexural_properties import FlexuralSectionProperties
from apeSteel.sections.properties import SectionProperties
from tests.golden._chapterF_aisc_oracle import OracleProps, mn_F2, mn_F5

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial

REL_TOL = 1e-9


# ===========================================================================
# 1. Channel section constant c - AISC 360-22 Eq. F2-8b
# ===========================================================================
# Closed-form plate-built channel section constants, derived here from
# the plate dimensions independently of apeSteel (the same standard
# open-thin-walled-channel formulas the validated ``ChannelSection``
# uses; transcribed with their workbook provenance).  Re-deriving them
# in-test keeps this anchor independent of the library geometry layer.
def _channel_constants(bf: float, tf: float, d: float, tw: float) -> dict[str, float]:
    """Return ``Ag, Ix, Sx, Zx, rx, Iy, ry, J, Cw, ho`` for a channel.

    AISC open-section closed forms (Galambos, *Structural Stability of
    Steel*; AISC Design Guide 9).  ``ho = d - tf`` is the distance
    between the flange centroids (the Eq. F2-8b ``ho``).
    """
    clear_web = d - 2.0 * tf
    Ag = bf * tf * 2.0 + clear_web * tw

    # Strong axis x (axis of symmetry of a channel).
    Ix = (bf * tf**3 / 12.0 + bf * tf * ((d / 2.0) - (tf / 2.0)) ** 2) * 2.0 + (
        tw * clear_web**3 / 12.0
    )
    Sx = Ix / (d / 2.0)
    # Plastic modulus about x (PNA at mid-depth by symmetry).
    Zx = 2.0 * (bf * tf * ((d - tf) / 2.0)) + tw * clear_web**2 / 4.0
    rx = math.sqrt(Ix / Ag)

    # Centroid x from the back of the web.
    xbar = (bf * tf * (bf / 2.0) * 2.0 + clear_web * tw * (tw / 2.0)) / Ag

    # Weak axis y.
    Iy = (
        (tf * bf**3 / 12.0 + bf * tf * (bf / 2.0 - xbar) ** 2) * 2.0
        + clear_web * tw**3 / 12.0
        + clear_web * tw * (xbar - tw / 2.0) ** 2
    )
    ry = math.sqrt(Iy / Ag)

    # Channel torsion / warping (DG 9 closed forms).
    b60 = d - tf  # distance between flange centroids = ho
    b61 = bf - tw / 2.0
    b62 = 1.0 / (2.0 + (d - tf) * tw / (3.0 * (bf - tw / 2.0) * tf))
    Cw = (
        b60**2
        * b61**3
        * tf
        * ((1.0 - 3.0 * b62) / 6.0 + b62**2 / 2.0 * (1.0 + b60 * tw / (6.0 * b61 * tf)))
    )
    J = (2.0 * (bf - tw / 2.0) * tf**3 + (d - tf) * tw**3) / 3.0
    return {
        "Ag": Ag,
        "Ix": Ix,
        "Sx": Sx,
        "Zx": Zx,
        "rx": rx,
        "Iy": Iy,
        "ry": ry,
        "J": J,
        "Cw": Cw,
        "ho": b60,
    }


def _channel_section_properties(
    bf: float, tf: float, d: float, tw: float
) -> tuple[SectionProperties, float]:
    """Build the flexure currency for a channel + its Eq. F2-8b ``c``.

    ``rts`` is taken from Eq. F2-7 ``rts^2 = sqrt(Iy*Cw)/Sx`` (the same
    definition the I-shape geometry uses); ``c`` is Eq. F2-8b
    ``(ho/2)*sqrt(Iy/Cw)``.
    """
    g = _channel_constants(bf, tf, d, tw)
    rts = math.sqrt(math.sqrt(g["Iy"] * g["Cw"]) / g["Sx"])
    c_eq_f2_8b = (g["ho"] / 2.0) * math.sqrt(g["Iy"] / g["Cw"])
    clear_web = d - 2.0 * tf
    sp = SectionProperties(
        overall_depth_d=d,
        gross_area_Ag=g["Ag"],
        nominal_weight_per_unit_length_w=0.0,
        moment_of_inertia_strong_axis_Ix=g["Ix"],
        elastic_section_modulus_strong_axis_Sx=g["Sx"],
        plastic_section_modulus_strong_axis_Zx=g["Zx"],
        radius_of_gyration_strong_axis_rx=g["rx"],
        moment_of_inertia_weak_axis_Iy=g["Iy"],
        elastic_section_modulus_weak_axis_Sy=g["Iy"] / bf,
        plastic_section_modulus_weak_axis_Zy=0.0,
        radius_of_gyration_weak_axis_ry=g["ry"],
        torsional_constant_J=g["J"],
        warping_constant_Cw=g["Cw"],
        distance_between_flange_centroids_ho=g["ho"],
        effective_radius_of_gyration_for_LTB_rts=rts,
        flange_width_to_thickness_ratio_bf_2tf=bf / tf,  # channel flange b/t
        web_height_to_thickness_ratio_h_tw=clear_web / tw,
        web_thickness_tw=tw,
        flange_width_bf=bf,
        flange_thickness_tf=tf,
    )
    return sp, c_eq_f2_8b


# A compact plate-built channel (bf=80, tf=12, d=300, tw=8), A36, that
# is *not* continuously braced so the inelastic / elastic LTB regimes
# (where c enters Lr and Mcr) are exercised.
_CHANNEL_BF, _CHANNEL_TF, _CHANNEL_D, _CHANNEL_TW = 80.0, 12.0, 300.0, 8.0


def _channel_oracle_props(sp: SectionProperties, mat: SteelMaterial, c: float) -> OracleProps:
    return OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
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
        section_c=c,
    )


def test_channel_F2_8b_c_is_not_unity_and_matches_closed_form() -> None:
    """Library ``from_legacy`` Eq. F2-8b ``c`` == independent closed form.

    AISC 360-22 Eq. F2-8b ``c = (ho/2)*sqrt(Iy/Cw)`` for channels is of
    order 1.0-1.2 for ordinary proportions (it is **not** ``< 1`` - e.g.
    C15x33.9 ~= 1.08; the hand-verified value for this plate-built
    channel is ~= 1.194638).  The binding check is the *library*
    ``FlexuralSectionProperties.from_legacy`` channel ``c`` against the
    in-test independent (Galambos / DG 9) closed form at ``rel_tol=1e-9``,
    with the value pinned so any ``from_legacy`` drift is caught.  (The
    earlier ``0 < c < 1`` premise was a wrong engineering assumption and
    the check was tautological - it never exercised the library.)
    """
    sp, c_closed_form = _channel_section_properties(
        _CHANNEL_BF, _CHANNEL_TF, _CHANNEL_D, _CHANNEL_TW
    )
    fsp = FlexuralSectionProperties.from_legacy(
        sp, kind="channel", symmetry="singly_symmetric", construction="rolled"
    )
    assert math.isclose(fsp.section_constant_c, c_closed_form, rel_tol=REL_TOL)
    assert math.isclose(fsp.section_constant_c, 1.1946384452397494, rel_tol=REL_TOL)
    assert fsp.section_constant_c > 1.0  # channel c is O(1.0-1.2), not < 1
    assert not math.isclose(fsp.section_constant_c, 1.0, rel_tol=1e-3)


@pytest.mark.parametrize(
    ("name", "Lb_m", "Cb"),
    [
        ("channel F2 inelastic-LTB", 3.0, 1.0),
        ("channel F2 elastic-LTB", 9.0, 1.0),
        ("channel F2 inelastic-LTB Cb=1.3", 4.0, 1.3),
    ],
)
def test_channel_F2_matches_independent_AISC_with_Eq_F2_8b_c(
    name: str, Lb_m: float, Cb: float
) -> None:
    """§F2 with ``section_kind='channel'`` reproduces the oracle bit-exact.

    The oracle is fed the *same* Eq. F2-8b ``c`` (re-derived in-test
    from the spec), so agreement proves §F2 reads
    ``fsp.section_constant_c`` correctly and the Eq. F2-8b lift in
    ``FlexuralSectionProperties.from_legacy`` is right.
    """
    sp, c = _channel_section_properties(_CHANNEL_BF, _CHANNEL_TF, _CHANNEL_D, _CHANNEL_TW)
    Lb = Lb_m * u.m
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        sp, A36, Lb, Cb, section_kind="channel"
    )
    oracle = mn_F2(_channel_oracle_props(sp, A36, c), Lb, Cb)
    assert math.isclose(r.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert r.governing_limit_state == oracle.governing
    # The unbraced lengths chosen above are all well past Lp, so c
    # genuinely enters via Lr (Eq. F2-6) / Mcr (Eq. F2-4) - not the
    # Lb<=Lp yielding plateau where c is irrelevant.
    assert r.governing_limit_state != "yielding"


def test_channel_F2_default_kind_keeps_c_equal_one() -> None:
    """Omitting ``section_kind`` (the shipped call) keeps Eq. F2-8a c=1.

    This is the bit-exactness guard: the *only* way a channel ``c`` is
    used is by explicitly passing ``section_kind='channel'``; the
    default path is byte-for-byte the shipped doubly-symmetric I §F2.
    """
    sp, _c = _channel_section_properties(_CHANNEL_BF, _CHANNEL_TF, _CHANNEL_D, _CHANNEL_TW)
    Lb = 9.0 * u.m
    r_default = compute_flexural_strength_F2_compact_doubly_symmetric(sp, A36, Lb, 1.0)
    # c = 1.0 oracle (section_c defaults to 1.0 in OracleProps).
    oracle_c1 = mn_F2(_channel_oracle_props(sp, A36, 1.0), Lb, 1.0)
    assert math.isclose(r_default.nominal_flexural_strength_Mn, oracle_c1.Mn, rel_tol=REL_TOL)


# ===========================================================================
# 2. Singly-symmetric slender-web §F5
# ===========================================================================
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


def _ss_props(sp: SectionProperties, mat: SteelMaterial) -> OracleProps:
    return OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
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


# Singly-symmetric, unequal flanges, very tall thin web -> slender web
# (hc/tw >> 5.70 sqrt(E/Fy)).  Small top flange, large bottom flange.
_F5_SS_SEC = _ss(220, 16, 420, 28, 1800, 9)


@pytest.mark.parametrize(
    ("name", "side", "Lb_m", "material"),
    [
        ("F5 SS top short", "top", 1.0, A992),
        ("F5 SS top inelastic", "top", 5.0, A992),
        ("F5 SS top elastic", "top", 16.0, A992),
        ("F5 SS bot short", "bot", 1.0, A992),
        ("F5 SS bot inelastic", "bot", 6.0, A992),
        ("F5 SS bot S355", "bot", 4.0, S355),
    ],
)
def test_F5_SS_matches_independent_AISC(
    name: str, side: str, Lb_m: float, material: SteelMaterial
) -> None:
    """SS slender-web §F5 reproduces the independent oracle bit-exact."""
    el = _F5_SS_SEC.element(
        material=material,
        construction="welded",
        bracing=Bracing(
            Lb_m * u.m,
            Lb_m * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        ),
    )
    if side == "top":
        r = el.flexural_strength_F5_top_flange()
    else:
        r = el.flexural_strength_F5_bot_flange()
    sp = el.section_properties_for(side)  # type: ignore[arg-type]
    oracle = mn_F5(_ss_props(sp, material), Lb_m * u.m, 1.0, "welded")
    assert math.isclose(r.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)


def test_F5_SS_web_is_actually_slender_and_routes_via_full_check() -> None:
    """The chosen SS section is genuinely slender-web and routes to F5."""
    el = _F5_SS_SEC.element(
        material=A992,
        construction="welded",
        bracing=Bracing(
            3.0 * u.m,
            3.0 * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        ),
    )
    classification = el.classify_flexural()
    assert classification.web.classification == "slender"
    full = el.run_full_check()
    assert full.routed_flexure_chapter == "F5"
    assert full.governing_flexural_phi_Mn > 0.0
    assert full.shear is None  # G2 is DS-only


def test_F5_SS_tension_flange_yielding_is_an_active_limit_state() -> None:
    """§F5.4 Eq. F5-10 (Sxt < Sxc) is a live candidate on the bot side.

    Bottom-compression puts the *large* bottom flange in compression
    (Sxc, referred to the near compression fibre, is large) and the
    small top flange in tension (Sxt small), so ``Sxt < Sxc`` and the
    §F5.4 tension-flange-yielding limit state ``Mn = Fy*Sxt`` (Eq.
    F5-10) is evaluated.  Assert it is genuinely active *and* that the
    library still matches the independent oracle (whose candidate set
    also includes ``Fy*Sxt``) bit-exact.
    """
    sp_bot_dir = _F5_SS_SEC.compute_section_properties("bot")
    assert sp_bot_dir.resolved_Sxt() < sp_bot_dir.resolved_Sxc()  # F5-10 active

    el = _F5_SS_SEC.element(
        material=A992,
        construction="welded",
        bracing=Bracing(
            1.0 * u.m,
            1.0 * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        ),
    )
    r_bot = el.flexural_strength_F5_bot_flange()
    oracle = mn_F5(_ss_props(sp_bot_dir, A992), 1.0 * u.m, 1.0, "welded")
    assert math.isclose(r_bot.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)

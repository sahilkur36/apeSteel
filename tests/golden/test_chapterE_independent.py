"""Independent correctness anchor for the AISC 360-22 Chapter-E facade.

Pins ``compute_compression_strength`` to a from-scratch AISC 360-22
re-derivation (:mod:`tests.golden._chapterE_aisc_oracle`) that imports
nothing from :mod:`apeSteel.compression`.  Section properties come from
the apeSteel geometry layer; only the Chapter-E strength composition is
checked here.  Agreement is expected bit-exact (same spec equations,
independently written source).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

from apeSteel import A36, A992, S355, S460
from apeSteel.compression import compute_compression_strength
from apeSteel.core import units as u
from apeSteel.sections.geometry import DoublySymmetricISection
from apeSteel.sections.geometry.channel_section import ChannelSection
from apeSteel.sections.geometry.double_angle_section import DoubleAngleSection
from apeSteel.sections.geometry.rectangular_hss import RectangularHSS
from apeSteel.sections.geometry.round_hss import RoundHSS
from apeSteel.sections.geometry.single_angle_section import SingleAngleSection
from apeSteel.sections.geometry.tee_section import TeeSection
from tests.golden._chapterE_aisc_oracle import (
    OracleElement,
    OracleProps,
    chapter_E_strength,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.compression_properties import CompressionSectionProperties

REL_TOL = 1e-9


def _to_oracle(sp: CompressionSectionProperties, mat: SteelMaterial) -> OracleProps:
    ro = sp.polar_radius_about_shear_centre_ro_bar
    ro2 = (
        ro**2
        if ro > 0.0
        else sp.shear_centre_x_xo**2
        + sp.shear_centre_y_yo**2
        + (sp.moment_of_inertia_x_Ix + sp.moment_of_inertia_y_Iy) / sp.gross_area_Ag
    )
    return OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        G=mat.shear_modulus_G,
        Ag=sp.gross_area_Ag,
        rx=sp.radius_of_gyration_x_rx,
        ry=sp.radius_of_gyration_y_ry,
        Ix=sp.moment_of_inertia_x_Ix,
        Iy=sp.moment_of_inertia_y_Iy,
        J=sp.torsional_constant_J,
        Cw=sp.warping_constant_Cw,
        xo=sp.shear_centre_x_xo,
        yo=sp.shear_centre_y_yo,
        ro_bar2=ro2,
        H=sp.flexural_constant_H,
        symmetry=sp.symmetry,
        section_kind=sp.section_kind,
        elements=tuple(
            OracleElement(
                kind=pe.kind,
                b=pe.width_b,
                t=pe.thickness_t,
                lam=pe.slenderness_ratio_lambda,
                lam_r=pe.nonslender_limit_lambda_r,
            )
            for pe in sp.plate_elements
        ),
        D=sp.diameter_D,
        t_wall=sp.wall_thickness_t,
        component_ri=sp.component_min_radius_of_gyration_ri,
    )


# Non-slender stocky W (flange & web non-slender) and a slender-web W,
# across short / intermediate / long lengths and several grades.
_NONSLENDER = DoublySymmetricISection(
    flange_width_bf=300 * u.mm,
    flange_thickness_tf=20 * u.mm,
    web_clear_height_hw=400 * u.mm,
    web_thickness_tw=16 * u.mm,
)
_SLENDER_WEB = DoublySymmetricISection(
    flange_width_bf=191 * u.mm,
    flange_thickness_tf=14.5 * u.mm,
    web_clear_height_hw=457 * u.mm,
    web_thickness_tw=9 * u.mm,
)

_CASES = [
    ("nonsl A992 short", _NONSLENDER, A992, 1.5),
    ("nonsl A992 inter", _NONSLENDER, A992, 6.0),
    ("nonsl A992 long", _NONSLENDER, A992, 12.0),
    ("nonsl S355 inter", _NONSLENDER, S355, 6.0),
    ("nonsl S460 long", _NONSLENDER, S460, 14.0),
    ("nonsl A36 inter", _NONSLENDER, A36, 6.0),
    ("slender-web A992 short", _SLENDER_WEB, A992, 1.5),
    ("slender-web A992 inter", _SLENDER_WEB, A992, 5.0),
    ("slender-web A992 long", _SLENDER_WEB, A992, 11.0),
    ("slender-web S355 inter", _SLENDER_WEB, S355, 5.0),
]


@pytest.mark.parametrize(("name", "section", "material", "L_m"), _CASES, ids=[c[0] for c in _CASES])
def test_W_compression_matches_independent_AISC(
    name: str,
    section: DoublySymmetricISection,
    material: SteelMaterial,
    L_m: float,
) -> None:
    sp = section.compute_compression_properties(material, "welded")
    lc = L_m * u.m  # K = 1 all axes
    r = compute_compression_strength(sp, material, lc, lc, lc)
    o = chapter_E_strength(_to_oracle(sp, material), lc, lc, lc)

    assert math.isclose(r.governing_critical_stress_Fcr, o.Fcr, rel_tol=REL_TOL)
    assert math.isclose(r.effective_area_Ae, o.Ae, rel_tol=REL_TOL)
    assert math.isclose(r.nominal_compressive_strength_Pn, o.Pn, rel_tol=REL_TOL)
    assert r.governing_compression_limit_state == o.governing


# --- Closed HSS (§E3 only; round HSS exercises §E7.2(c)) -------------------
_RECT_HSS = RectangularHSS(depth_H=250 * u.mm, width_B=150 * u.mm, wall_thickness_t=8 * u.mm)
_RECT_HSS_SLEND = RectangularHSS(depth_H=400 * u.mm, width_B=400 * u.mm, wall_thickness_t=6 * u.mm)
_ROUND_HSS = RoundHSS(outside_diameter_D=150 * u.mm, wall_thickness_t=8 * u.mm)
_ROUND_HSS_SLEND = RoundHSS(outside_diameter_D=500 * u.mm, wall_thickness_t=5 * u.mm)

_HSS_CASES = [
    ("rectHSS A992 short", _RECT_HSS, A992, 2.0),
    ("rectHSS A992 long", _RECT_HSS, A992, 8.0),
    ("rectHSS-slender A992", _RECT_HSS_SLEND, A992, 5.0),
    ("rectHSS-slender S355", _RECT_HSS_SLEND, S355, 7.0),
    ("roundHSS A992 short", _ROUND_HSS, A992, 2.0),
    ("roundHSS A992 long", _ROUND_HSS, A992, 7.0),
    ("roundHSS-slender A992", _ROUND_HSS_SLEND, A992, 6.0),
    ("roundHSS-slender S460", _ROUND_HSS_SLEND, S460, 6.0),
]


@pytest.mark.parametrize(
    ("name", "section", "material", "L_m"), _HSS_CASES, ids=[c[0] for c in _HSS_CASES]
)
def test_HSS_compression_matches_independent_AISC(
    name: str,
    section: RectangularHSS | RoundHSS,
    material: SteelMaterial,
    L_m: float,
) -> None:
    sp = section.compute_compression_properties(material, "welded")
    lc = L_m * u.m
    r = compute_compression_strength(sp, material, lc, lc, lc)
    o = chapter_E_strength(_to_oracle(sp, material), lc, lc, lc)
    assert math.isclose(r.governing_critical_stress_Fcr, o.Fcr, rel_tol=REL_TOL)
    assert math.isclose(r.effective_area_Ae, o.Ae, rel_tol=REL_TOL)
    assert math.isclose(r.nominal_compressive_strength_Pn, o.Pn, rel_tol=REL_TOL)
    assert r.governing_compression_limit_state == "flexural_buckling"


# --- Singly-symmetric §E4-3 flexural-torsional: tee & channel --------------
_TEE = TeeSection(
    flange_width_bf=150 * u.mm,
    flange_thickness_tf=8 * u.mm,
    overall_depth_d=200 * u.mm,
    stem_thickness_tw=8 * u.mm,
)
_CHANNEL = ChannelSection(
    flange_width_bf=60 * u.mm,
    flange_thickness_tf=5 * u.mm,
    overall_depth_d=200 * u.mm,
    web_thickness_tw=5 * u.mm,
)

_FT_CASES = [
    ("tee A36 short", _TEE, A36, 2.0),
    ("tee A36 inter", _TEE, A36, 4.0),
    ("tee A992 inter", _TEE, A992, 4.0),
    ("tee A992 long", _TEE, A992, 9.0),
    ("tee S355 inter", _TEE, S355, 5.0),
    ("channel A36 short", _CHANNEL, A36, 1.5),
    ("channel A36 inter", _CHANNEL, A36, 4.0),
    ("channel A992 inter", _CHANNEL, A992, 4.0),
    ("channel A992 long", _CHANNEL, A992, 8.0),
    ("channel S460 inter", _CHANNEL, S460, 5.0),
]


@pytest.mark.parametrize(
    ("name", "section", "material", "L_m"), _FT_CASES, ids=[c[0] for c in _FT_CASES]
)
def test_singly_symmetric_FT_matches_independent_AISC(
    name: str,
    section: TeeSection | ChannelSection,
    material: SteelMaterial,
    L_m: float,
) -> None:
    sp = section.compute_compression_properties(material, "welded")
    lc = L_m * u.m  # K = 1 all axes
    r = compute_compression_strength(sp, material, lc, lc, lc)
    o = chapter_E_strength(_to_oracle(sp, material), lc, lc, lc)

    assert math.isclose(r.governing_critical_stress_Fcr, o.Fcr, rel_tol=REL_TOL)
    assert math.isclose(r.effective_area_Ae, o.Ae, rel_tol=REL_TOL)
    assert math.isclose(r.nominal_compressive_strength_Pn, o.Pn, rel_tol=REL_TOL)
    assert r.governing_compression_limit_state == o.governing


# --- Single angle (§E5 modified Lc/r, and §E3+§E4) ; double angle (§E6) ----
_ANGLE = SingleAngleSection(leg_length=75 * u.mm, thickness=6 * u.mm)
_ANGLE_THICK = SingleAngleSection(leg_length=100 * u.mm, thickness=10 * u.mm)
_DBL_ANGLE = DoubleAngleSection(leg_length=75 * u.mm, thickness=6 * u.mm, back_separation=10 * u.mm)


@pytest.mark.parametrize(
    ("name", "section", "material", "L_m", "e5"),
    [
        ("angle A36 noE5", _ANGLE, A36, 2.0, None),
        ("angle A36 E5a", _ANGLE, A36, 3.0, "a"),
        ("angle A36 E5b", _ANGLE, A36, 3.0, "b"),
        ("angle A992 E5a", _ANGLE_THICK, A992, 4.0, "a"),
        ("angle A992 noE5 long", _ANGLE_THICK, A992, 6.0, None),
        ("angle S355 E5b", _ANGLE, S355, 2.5, "b"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_single_angle_matches_independent_AISC(
    name: str,
    section: SingleAngleSection,
    material: SteelMaterial,
    L_m: float,
    e5: str | None,
) -> None:
    sp = section.compute_compression_properties(material, "welded")
    lc = L_m * u.m
    r = compute_compression_strength(
        sp,
        material,
        lc,
        lc,
        lc,
        single_angle_E5_case=e5,  # type: ignore[arg-type]
        single_angle_E5_length_L=lc if e5 is not None else None,
    )
    o = chapter_E_strength(_to_oracle(sp, material), lc, lc, lc, e5_case=e5, e5_L=lc)
    assert math.isclose(r.governing_critical_stress_Fcr, o.Fcr, rel_tol=REL_TOL)
    assert math.isclose(r.nominal_compressive_strength_Pn, o.Pn, rel_tol=REL_TOL)
    assert r.governing_compression_limit_state == o.governing


@pytest.mark.parametrize(
    ("name", "material", "L_m", "a_mm", "conn"),
    [
        ("dbl A36 snug short", A36, 2.0, 600.0, "snug_bolted"),
        ("dbl A36 snug long", A36, 5.0, 800.0, "snug_bolted"),
        ("dbl A992 welded", A992, 4.0, 500.0, "welded_or_pretensioned"),
        ("dbl A992 welded close", A992, 4.0, 150.0, "welded_or_pretensioned"),
        ("dbl S355 snug", S355, 3.0, 700.0, "snug_bolted"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_double_angle_E6_matches_independent_AISC(
    name: str,
    material: SteelMaterial,
    L_m: float,
    a_mm: float,
    conn: str,
) -> None:
    sp = _DBL_ANGLE.compute_compression_properties(material, "welded")
    lc = L_m * u.m
    r = compute_compression_strength(
        sp,
        material,
        lc,
        lc,
        lc,
        builtup_connector_spacing_a=a_mm * u.mm,
        builtup_connector_type=conn,  # type: ignore[arg-type]
    )
    o = chapter_E_strength(_to_oracle(sp, material), lc, lc, lc, a6=a_mm * u.mm, connector6=conn)
    assert math.isclose(r.governing_critical_stress_Fcr, o.Fcr, rel_tol=REL_TOL)
    assert math.isclose(r.nominal_compressive_strength_Pn, o.Pn, rel_tol=REL_TOL)
    assert r.governing_compression_limit_state == o.governing

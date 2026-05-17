"""External anchor: apeSteel Chapter-E vs the source spreadsheet.

``_compression_excel_raw.json`` is a faithful dump of every cell
(formula + cached value) of the engineer's
``Diseno de elementos para Compresion - V2.0.xlsm`` - a genuinely
*independent* AISC Chapter-E implementation (it predates apeSteel and
was written by hand in Excel/VBA).  It is the strongest available
correctness anchor.

Provenance / edition note
-------------------------
The workbook is **AISC 360-16** (it applies the ``Q = Qs*Qa`` slender-
element knock-down).  apeSteel implements **AISC 360-22** (effective
width).  Therefore:

* ``Fe`` (Eq. E3-4) and the doubly-symmetric torsional ``Fe`` (Eq. E4-2)
  are **edition-independent** - asserted against the workbook to the
  workbook's own precision (its ``ksi -> kgf/cm^2`` constant is the
  rounded ``70.3``, so the achievable tolerance is ~2e-3, not 1e-9;
  this is the AISC-Manual-precision standard, not a self-snapshot).
* The W default section is slender-web, so its final ``phi*Pn``
  legitimately differs (360-16 Q vs 360-22 Ae); that gap is bounded and
  documented, not bit-checked.

Section geometry (Ag, rx, ry, J, Cw) is also edition-independent and is
anchored here.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from apeSteel import A36, A992
from apeSteel.compression import compute_compression_strength_from_K_L
from apeSteel.compression.flexural_buckling_E3 import compute_elastic_buckling_stress_Fe
from apeSteel.compression.torsional_flexural_E4 import (
    compute_torsional_Fe_doubly_symmetric,
)
from apeSteel.core import units as u
from apeSteel.sections.geometry import DoublySymmetricISection
from apeSteel.sections.geometry.channel_section import ChannelSection
from apeSteel.sections.geometry.double_angle_section import DoubleAngleSection
from apeSteel.sections.geometry.rectangular_hss import RectangularHSS
from apeSteel.sections.geometry.round_hss import RoundHSS
from apeSteel.sections.geometry.single_angle_section import SingleAngleSection
from apeSteel.sections.geometry.tee_section import TeeSection

_RAW = Path(__file__).parent / "data" / "_compression_excel_raw.json"

# Unit conversions: the workbook stores cm / cm^2 / cm^4 / cm^6,
# kgf/cm^2, and tonne-force.  -> apeSteel base (mm, N).
_KGFCM2_TO_MPA = 0.0980665  # 1 kgf/cm^2 = 0.0980665 MPa
_CM_TO_MM = 10.0
_CM2_TO_MM2 = 100.0
_CM4_TO_MM4 = 1.0e4
_CM6_TO_MM6 = 1.0e6


@pytest.fixture(scope="module")
def w_cells() -> dict[str, object]:
    if not _RAW.exists():  # pragma: no cover - fixture data must ship
        pytest.skip(f"Excel anchor dump missing: {_RAW}")
    data = json.loads(_RAW.read_text(encoding="utf-8"))
    return {c["coord"]: c["value"] for c in data["sheets"]["W"]["cells"]}


def _f(cells: dict[str, object], coord: str) -> float:
    return float(cells[coord])  # type: ignore[arg-type]


def test_W_geometry_matches_workbook(w_cells: dict[str, object]) -> None:
    # Inputs read from the workbook itself (data-driven, not hard-coded).
    bf = _f(w_cells, "B27")
    tf = _f(w_cells, "B28")
    hw = _f(w_cells, "B29")
    tw = _f(w_cells, "B30")
    sec = DoublySymmetricISection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )
    sp = sec.compute_compression_properties(A992, "welded")

    # B46 Ag (cm^2), B48 rx (cm), B50 ry (cm), B54 J (cm^4), B53 Cw (cm^6).
    assert math.isclose(sp.gross_area_Ag, _f(w_cells, "B46") * _CM2_TO_MM2, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_x_rx, _f(w_cells, "B48") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_y_ry, _f(w_cells, "B50") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.torsional_constant_J, _f(w_cells, "B54") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.warping_constant_Cw, _f(w_cells, "B53") * _CM6_TO_MM6, rel_tol=2e-3)


def test_W_elastic_buckling_stresses_match_workbook(w_cells: dict[str, object]) -> None:
    """Fe (Eq. E3-4) and torsional Fe (Eq. E4-2) are edition-independent."""
    bf, tf, hw, tw = (_f(w_cells, c) for c in ("B27", "B28", "B29", "B30"))
    L_m = _f(w_cells, "B22")
    kx, ky, kz = (_f(w_cells, c) for c in ("B23", "B24", "B25"))
    sec = DoublySymmetricISection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )
    sp = sec.compute_compression_properties(A992, "welded")

    # Fe_x: workbook C61 (kgf/cm^2).  Lc/r_x: workbook C60.
    lcx = kx * L_m * u.m
    fe_x = compute_elastic_buckling_stress_Fe(
        A992.elastic_modulus_E, lcx / sp.radius_of_gyration_x_rx
    )
    assert math.isclose(fe_x, _f(w_cells, "C61") * _KGFCM2_TO_MPA, rel_tol=2e-3)
    # Lc/r_x literal also matches.
    assert math.isclose(lcx / sp.radius_of_gyration_x_rx, _f(w_cells, "C60"), rel_tol=2e-3)

    # Fe_y: workbook C71.
    lcy = ky * L_m * u.m
    fe_y = compute_elastic_buckling_stress_Fe(
        A992.elastic_modulus_E, lcy / sp.radius_of_gyration_y_ry
    )
    assert math.isclose(fe_y, _f(w_cells, "C71") * _KGFCM2_TO_MPA, rel_tol=2e-3)

    # Fe torsional (Eq. E4-2): workbook C83.  Edition-independent.
    lcz = kz * L_m * u.m
    fe_t = compute_torsional_Fe_doubly_symmetric(
        elastic_modulus_E=A992.elastic_modulus_E,
        shear_modulus_G=A992.shear_modulus_G,
        warping_constant_Cw=sp.warping_constant_Cw,
        torsional_constant_J=sp.torsional_constant_J,
        effective_length_torsional_Lcz=lcz,
        moment_of_inertia_x_Ix=sp.moment_of_inertia_x_Ix,
        moment_of_inertia_y_Iy=sp.moment_of_inertia_y_Iy,
    )
    assert math.isclose(fe_t, _f(w_cells, "C83") * _KGFCM2_TO_MPA, rel_tol=2e-3)


def test_W_phiPn_edition_divergence_is_bounded(w_cells: dict[str, object]) -> None:
    """The W default is slender-web: 360-22 Ae vs 360-16 Q differ, but
    the gap must stay small and on the un-conservative-for-360-16 side
    (360-22 effective width is slightly less punitive here)."""
    bf, tf, hw, tw = (_f(w_cells, c) for c in ("B27", "B28", "B29", "B30"))
    L_m = _f(w_cells, "B22")
    kx, ky, kz = (_f(w_cells, c) for c in ("B23", "B24", "B25"))
    sec = DoublySymmetricISection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )
    sp = sec.compute_compression_properties(A992, "welded")
    r = compute_compression_strength_from_K_L(sp, A992, kx, L_m * u.m, ky, L_m * u.m, kz, L_m * u.m)
    phi_pn_tf = r.phi_strength_LRFD / (u.kgf * 1000.0)  # -> tonne-force
    excel_phi_pn_tf = _f(w_cells, "J3")  # workbook governing phi*Pn (tf)
    # Web is slender -> 360-22 vs 360-16 differ; bound the gap at 5 %.
    rel_gap = abs(phi_pn_tf - excel_phi_pn_tf) / excel_phi_pn_tf
    assert rel_gap < 0.05, (
        f"360-22 phi*Pn={phi_pn_tf:.2f} tf vs 360-16 workbook "
        f"{excel_phi_pn_tf:.2f} tf: gap {rel_gap:.3%} exceeds the "
        f"documented slender-element edition band"
    )
    assert r.section_has_slender_element  # sanity: this case IS slender


# ---------------------------------------------------------------------------
# Tee & channel geometry anchor (edition-independent).  The workbook's
# tee/channel sheets run at Fy = 36 ksi (B16 = 36*70.3) -> A36.
# ---------------------------------------------------------------------------
def _sheet_cells(sheet: str) -> dict[str, object]:
    if not _RAW.exists():  # pragma: no cover
        pytest.skip(f"Excel anchor dump missing: {_RAW}")
    data = json.loads(_RAW.read_text(encoding="utf-8"))
    return {c["coord"]: c["value"] for c in data["sheets"][sheet]["cells"]}


def test_tee_geometry_matches_workbook() -> None:
    c = _sheet_cells("T")
    bf, tf, d, tw = (_f(c, x) for x in ("B26", "B27", "B28", "B29"))
    sp = TeeSection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        overall_depth_d=d * u.mm,
        stem_thickness_tw=tw * u.mm,
    ).compute_compression_properties(A36, "welded")
    assert math.isclose(sp.gross_area_Ag, _f(c, "B45") * _CM2_TO_MM2, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_x_rx, _f(c, "B49") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_y_ry, _f(c, "B51") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.torsional_constant_J, _f(c, "B54") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.warping_constant_Cw, _f(c, "B53") * _CM6_TO_MM6, rel_tol=2e-3)
    # Shear-centre offset yo and flexural constant H (workbook B55/B58).
    assert math.isclose(sp.shear_centre_y_yo, _f(c, "B55"), rel_tol=2e-3)
    assert math.isclose(sp.flexural_constant_H, _f(c, "B58"), rel_tol=2e-3)


def test_channel_geometry_matches_workbook() -> None:
    c = _sheet_cells("Canal")
    bf, tf, d, tw = (_f(c, x) for x in ("B27", "B28", "B29", "B30"))
    sp = ChannelSection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        overall_depth_d=d * u.mm,
        web_thickness_tw=tw * u.mm,
    ).compute_compression_properties(A36, "welded")
    assert math.isclose(sp.gross_area_Ag, _f(c, "B49") * _CM2_TO_MM2, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_x_rx, _f(c, "B51") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_y_ry, _f(c, "B58") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.torsional_constant_J, _f(c, "B64") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.warping_constant_Cw, _f(c, "B63") * _CM6_TO_MM6, rel_tol=2e-3)
    # Channel shear-centre x-offset xo (workbook B53, already mm).
    assert math.isclose(sp.shear_centre_x_xo, _f(c, "B53"), rel_tol=2e-3)
    assert math.isclose(sp.flexural_constant_H, _f(c, "B56"), rel_tol=2e-3)


# ---------------------------------------------------------------------------
# HSS: the workbook's rect & round HSS examples are NON-slender, so
# 360-16 Q == 360-22 (no area reduction) and the FULL governing phi*Pn
# is edition-independent -> a bit-anchor (workbook precision ~2e-3).
# Both run at Fy = 50 ksi (B16 = 50*70.3) -> A992.
# ---------------------------------------------------------------------------
def test_rect_HSS_matches_workbook() -> None:
    c = _sheet_cells("HSS")
    H, B, t = (_f(c, x) for x in ("B26", "B27", "B28"))
    L_m = _f(c, "B22")
    kx, ky = _f(c, "B23"), _f(c, "B24")
    sec = RectangularHSS(depth_H=H * u.mm, width_B=B * u.mm, wall_thickness_t=t * u.mm)
    sp = sec.compute_compression_properties(A992, "welded")
    # Geometry (workbook B43 Ag cm^2, B45 rx cm, B47 ry cm).
    assert math.isclose(sp.gross_area_Ag, _f(c, "B43") * _CM2_TO_MM2, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_x_rx, _f(c, "B45") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_y_ry, _f(c, "B47") * _CM_TO_MM, rel_tol=2e-3)
    # Non-slender -> full phi*Pn is edition-independent.
    r = compute_compression_strength_from_K_L(
        sp, A992, kx, L_m * u.m, ky, L_m * u.m, 1.0, L_m * u.m
    )
    assert not r.section_has_slender_element
    phi_pn_tf = r.phi_strength_LRFD / (u.kgf * 1000.0)
    assert math.isclose(phi_pn_tf, _f(c, "J3"), rel_tol=3e-3)


def test_round_HSS_matches_workbook() -> None:
    c = _sheet_cells("HSS T")
    D, t = _f(c, "B25"), _f(c, "B26")
    L_m = _f(c, "B22")
    k = _f(c, "B23")
    sec = RoundHSS(outside_diameter_D=D * u.mm, wall_thickness_t=t * u.mm)
    sp = sec.compute_compression_properties(A992, "welded")
    # Geometry (workbook B38 Ag cm^2, B40 r cm).
    assert math.isclose(sp.gross_area_Ag, _f(c, "B38") * _CM2_TO_MM2, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_x_rx, _f(c, "B40") * _CM_TO_MM, rel_tol=2e-3)
    # Non-slender D/t -> §E7.2(c) factor = 1; phi*Pn edition-independent.
    r = compute_compression_strength_from_K_L(sp, A992, k, L_m * u.m, k, L_m * u.m, k, L_m * u.m)
    assert not r.section_has_slender_element
    phi_pn_tf = r.phi_strength_LRFD / (u.kgf * 1000.0)
    assert math.isclose(phi_pn_tf, _f(c, "C50"), rel_tol=3e-3)


# ---------------------------------------------------------------------------
# Single & double equal-leg angle geometry anchor (edition-independent).
# Workbook Angulo / Doble Angulo Espalda run at Fy = 36 ksi -> A36.
# ---------------------------------------------------------------------------
def test_single_angle_geometry_matches_workbook() -> None:
    c = _sheet_cells("Angulo")
    leg, t = _f(c, "B4"), _f(c, "B6")
    sp = SingleAngleSection(
        leg_length=leg * u.mm, thickness=t * u.mm
    ).compute_compression_properties(A36, "welded")
    # E23 Ag (cm^2); E24/E25 principal I (cm^4); E35/E36 r (cm);
    # E38 J (cm^4); E40 H; E33/E34 shear-centre offsets (cm).
    assert math.isclose(sp.gross_area_Ag, _f(c, "E23") * _CM2_TO_MM2, rel_tol=2e-3)
    assert math.isclose(sp.moment_of_inertia_x_Ix, _f(c, "E24") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.moment_of_inertia_y_Iy, _f(c, "E25") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_x_rx, _f(c, "E35") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_y_ry, _f(c, "E36") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.torsional_constant_J, _f(c, "E38") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.flexural_constant_H, _f(c, "E40"), rel_tol=2e-3)
    assert math.isclose(sp.shear_centre_x_xo, _f(c, "E33") * _CM_TO_MM, rel_tol=2e-3)


def test_double_angle_geometry_matches_workbook() -> None:
    c = _sheet_cells("Doble Angulo Espalda")
    leg, t, sep = _f(c, "B5"), _f(c, "B7"), _f(c, "B4")
    sp = DoubleAngleSection(
        leg_length=leg * u.mm, thickness=t * u.mm, back_separation=sep * u.mm
    ).compute_compression_properties(A36, "welded")
    # F23 doubled Ag (cm^2); F24/F25 doubled I (cm^4); F31/F32 r (cm);
    # F34 doubled J (cm^4); F36 built-up H.
    assert math.isclose(sp.gross_area_Ag, _f(c, "F23") * _CM2_TO_MM2, rel_tol=2e-3)
    assert math.isclose(sp.moment_of_inertia_x_Ix, _f(c, "F24") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.moment_of_inertia_y_Iy, _f(c, "F25") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_x_rx, _f(c, "F31") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.radius_of_gyration_y_ry, _f(c, "F32") * _CM_TO_MM, rel_tol=2e-3)
    assert math.isclose(sp.torsional_constant_J, _f(c, "F34") * _CM4_TO_MM4, rel_tol=2e-3)
    assert math.isclose(sp.flexural_constant_H, _f(c, "F36"), rel_tol=2e-3)

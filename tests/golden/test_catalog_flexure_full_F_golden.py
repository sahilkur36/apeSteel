"""Catalog-anchored golden for the Phase-F-8 non-I §F path.

The Phase-6 ``test_catalog_flexure_F2_golden`` pins the AISC v16
**I-shape** catalog path (W24X94 -> legacy ``SectionProperties`` ->
§F2).  This file is its Phase-F-8 **non-I** sibling: it drives
:meth:`AISCv16Catalog.get_flexural_section_properties` for
representative **non-I** shapes through the matching shipped §F engine
and cross-checks ``phi*Mn`` (and every printed intermediate) against
the independent stdlib §F oracle - fed the **same catalog-published
properties** - at ``rel_tol = 1e-9`` (design note 10 §6 tier 1: the
documented rolled-vs-plate ``k``-radius gap would swamp a
plate-reconstruction comparison, so the catalog values are used
verbatim and the oracle re-derives only the §F strength composition).

Two shapes per the F-8 contract (≥ 2 representative non-I; an HSS and
a WT):

* **HSS12X8X1/2** -> §F7 (rectangular HSS).  ``phi*Mn`` and the
  governing limit state cross-checked bit-exactly vs
  :func:`tests.golden._chapterF_F7_oracle.mn_F7` on the catalog row's
  own ``Z``/``S``/``I``/``J``.
* **WT5X6** -> §F9 (tee, the Manual Ex. F.10 shape).  ``phi*Mn``
  cross-checked bit-exactly vs
  :func:`tests.golden._chapterF_F9_oracle.mn_F9`, **plus** the AISC
  Manual v15.1 Ex. F.10 printed sig-fig values: the Manual prints (for
  ``WT56``/WT5X6, ASTM A992 ``Fy = 50 ksi``) ``Sx = 1.22 in.^3``,
  ``Sxc = Ix/y = 3.20 in.^3`` and ``My = Fy*Sx = 61.0 kip-in.`` -
  asserting the catalog ``Sxc`` derivation (``Ix/(d - Ix/Sx)``) and
  the §F9 ``My`` reproduce the Manual to its 3 printed sig figs.
  (``manual_F9_examples.txt`` PDF p.192-193, staged verbatim - no
  number invented.)

SCOPE: the bit-exact oracle cross-check is the correctness pin (the §F
math is independently anchored by the per-section oracle suites); this
file additionally proves the **catalog adapter** populates the
generalized ``FlexuralSectionProperties`` correctly for the non-I
families.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

from apeSteel.core import units as u
from apeSteel.core.materials import A992, SteelMaterial
from apeSteel.flexure.F7_rect_hss import compute_flexural_strength_F7_rect_hss
from apeSteel.flexure.F9_tee_double_angle import (
    compute_flexural_strength_F9_tee_double_angle,
)
from apeSteel.sections.catalog import AISCv16Catalog
from tests.golden._chapterF_F7_oracle import F7OracleProps, mn_F7
from tests.golden._chapterF_F9_oracle import F9OracleProps, mn_F9

if TYPE_CHECKING:
    from apeSteel.sections.flexural_properties import BendingAxis

REL_TOL = 1e-9
_PHI_B = 0.90
_OMEGA_B = 1.67


@pytest.fixture(scope="module")
def catalog() -> AISCv16Catalog:
    return AISCv16Catalog()


# ===========================================================================
# HSS12X8X1/2  ->  §F7 (rectangular HSS), bit-exact vs the §F7 oracle
# ===========================================================================
@pytest.mark.regression
@pytest.mark.parametrize(
    ("bending_axis", "Lb_m", "Cb"),
    [
        ("major", None, 1.0),
        ("major", 3.0, 1.0),
        ("minor", None, 1.0),
    ],
)
def test_catalog_HSS_F7_matches_independent_oracle(
    catalog: AISCv16Catalog,
    bending_axis: BendingAxis,
    Lb_m: float | None,
    Cb: float,
) -> None:
    """Catalog HSS -> §F7 ``phi*Mn`` == independent §F7 oracle (1e-9)."""
    fsp = catalog.get_flexural_section_properties("HSS12X8X1/2")
    assert fsp.section_kind == "rectangular_HSS"
    material: SteelMaterial = A992
    Lb: float | None = None if Lb_m is None else Lb_m * u.m

    report = compute_flexural_strength_F7_rect_hss(
        fsp,
        material,
        bending_axis=bending_axis,
        unbraced_length_Lb=Lb,
        Cb=Cb,
    )

    # Lift the *catalog* fsp into the independent oracle's inputs (the
    # oracle imports nothing from apeSteel.flexure; it re-derives only
    # the §F7 strength composition on the catalog's own Z/S/I/J).
    t = fsp.wall_thickness_t
    walls = {e.name: e for e in fsp.plate_elements}
    flat_B = walls["wall_B"].slenderness_ratio_lambda * t
    flat_H = walls["wall_H"].slenderness_ratio_lambda * t
    H = fsp.overall_depth_d
    B = walls["wall_B"].slenderness_ratio_lambda * t + 2.0 * t
    if bending_axis == "major":
        z_mod, s_mod, i_axis = (
            fsp.plastic_modulus_Zx,
            fsp.elastic_modulus_Sx,
            fsp.moment_of_inertia_Ix,
        )
        section_depth = H
        flange_flat, web_flat = flat_B, flat_H
    else:
        z_mod, s_mod, i_axis = (
            fsp.plastic_modulus_Zy,
            fsp.elastic_modulus_Sy,
            fsp.moment_of_inertia_Iy,
        )
        section_depth = B
        flange_flat, web_flat = flat_H, flat_B
    oracle = mn_F7(
        F7OracleProps(
            Fy=material.yield_stress_Fy,
            E=material.elastic_modulus_E,
            B=B,
            H=H,
            t=t,
            Z=z_mod,
            S=s_mod,
            I_axis=i_axis,
            ry_minor=fsp.radius_of_gyration_ry,
            Ag=fsp.gross_area_Ag,
            J=fsp.torsional_constant_J,
            bending_axis=bending_axis,
            section_depth=section_depth,
            flange_flat=flange_flat,
            web_flat=web_flat,
            Lb=Lb,
            Cb=Cb,
        )
    )

    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_Mp, oracle.Mp, rel_tol=REL_TOL)
    assert math.isclose(report.Mn_flange_local_buckling, oracle.Mn_flb, rel_tol=REL_TOL)
    assert math.isclose(report.Mn_web_local_buckling, oracle.Mn_wlb, rel_tol=REL_TOL)
    assert math.isclose(report.Mn_lateral_torsional_buckling, oracle.Mn_ltb, rel_tol=REL_TOL)
    assert report.governing_limit_state == oracle.governing
    assert report.flange_classification == oracle.flange_class
    assert report.web_classification == oracle.web_class
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


# ===========================================================================
# WT5X6  ->  §F9 (tee).  Bit-exact vs the §F9 oracle, PLUS the AISC
# Manual v15.1 Ex. F.10 printed sig-fig anchor (Sx / Sxc / My).
# ===========================================================================
def _wt_oracle_props(
    catalog: AISCv16Catalog,
    mat: SteelMaterial,
    *,
    Lb: float,
    Cb: float,
    stem_in_tension: bool,
) -> F9OracleProps:
    fsp = catalog.get_flexural_section_properties("WT5X6")
    row = catalog.get_row("WT5X6")
    assert row.bf is not None
    assert row.tf is not None
    assert row.d is not None
    assert row.tw is not None
    return F9OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        section_kind="tee",
        Zx=fsp.plastic_modulus_Zx,
        Sx=fsp.elastic_modulus_Sx,
        Sxc=fsp.elastic_modulus_compression_flange_Sxc,
        d=fsp.overall_depth_d,
        Iy=fsp.moment_of_inertia_Iy,
        J=fsp.torsional_constant_J,
        ry=fsp.radius_of_gyration_ry,
        flange_lambda=(row.bf / 2.0) / row.tf,
        stem_lambda=row.d / row.tw,
        Lb=Lb,
        Cb=Cb,
        stem_in_tension=stem_in_tension,
    )


@pytest.mark.regression
@pytest.mark.parametrize("stem_in_tension", [True, False])
def test_catalog_WT_F9_matches_independent_oracle(
    catalog: AISCv16Catalog, stem_in_tension: bool
) -> None:
    """Catalog WT5X6 -> §F9 ``phi*Mn`` == independent §F9 oracle (1e-9)."""
    fsp = catalog.get_flexural_section_properties("WT5X6")
    row = catalog.get_row("WT5X6")
    assert fsp.section_kind == "tee"
    assert row.bf is not None
    assert row.tf is not None
    assert row.d is not None
    assert row.tw is not None
    Lb = 2.0 * u.m
    report = compute_flexural_strength_F9_tee_double_angle(
        fsp,
        A992,
        unbraced_length_Lb=Lb,
        flange_slenderness_bf_2tf=(row.bf / 2.0) / row.tf,
        stem_slenderness_d_tw=row.d / row.tw,
        lateral_torsional_buckling_factor_Cb=1.0,
        stem_in_tension=stem_in_tension,
    )
    oracle = mn_F9(_wt_oracle_props(catalog, A992, Lb=Lb, Cb=1.0, stem_in_tension=stem_in_tension))

    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_Mp, oracle.Mp, rel_tol=REL_TOL)
    assert math.isclose(report.yield_moment_My, oracle.My, rel_tol=REL_TOL)
    assert math.isclose(report.critical_moment_Mcr, oracle.Mcr, rel_tol=REL_TOL)
    assert report.governing_limit_state == oracle.governing
    assert report.section_kind == "tee"
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_catalog_WT5X6_reproduces_manual_v15_1_example_F10_sig_figs() -> None:
    """AISC Manual v15.1 Ex. F.10 (WT5X6 / "WT56", A992) sig-fig anchor.

    The Manual (``manual_F9_examples.txt`` PDF p.192-193, staged
    verbatim) prints, from AISC Manual Table 1-8 for WT56 (= WT5X6):

    * ``Sx  = 1.22 in.^3``           (elastic modulus to the stem tip)
    * ``Sxc = Ix/y = 3.20 in.^3``    (to the flange / compression fibre)
    * ``My  = Fy*Sx = 50 ksi * 1.22 in.^3 = 61.0 kip-in.``
      (Spec. Eq. F9-3)

    The catalog adapter derives ``Sxc = Ix/(d - Ix/Sx)`` from the
    *published* full-precision ``Ix``/``Sx``/``d`` (the Manual's
    ``Sxc = Ix/y`` with ``y`` the centroid depth from the flange face);
    assert it reproduces the Manual's printed 3-sig-fig ``Sx``/``Sxc``
    and that §F9's ``My`` matches ``61.0 kip-in.`` - no AISC value
    invented (all printed verbatim in the staged extract).
    """
    catalog = AISCv16Catalog()
    fsp = catalog.get_flexural_section_properties("WT5X6")

    kip_in = u.kip * u.inches
    in3 = u.inches**3

    # Manual: Sx = 1.22 in^3 (to stem tip); Sxc = 3.20 in^3 (to flange).
    manual_rel_tol = 5e-3  # the Manual prints 3 sig figs
    assert math.isclose(fsp.elastic_modulus_Sx / in3, 1.22, rel_tol=manual_rel_tol)
    assert math.isclose(
        fsp.elastic_modulus_compression_flange_Sxc / in3, 3.20, rel_tol=manual_rel_tol
    )

    # §F9 Eq. F9-3: My = Fy*Sx = 61.0 kip-in. (A992, Fy = 50 ksi).
    report = compute_flexural_strength_F9_tee_double_angle(
        fsp,
        A992,
        unbraced_length_Lb=1.0,  # continuously braced -> LTB N/A
        flange_slenderness_bf_2tf=9.43,  # Manual-printed WT5X6 bf/2tf
        stem_slenderness_d_tw=10.0,
        lateral_torsional_buckling_factor_Cb=1.0,
        stem_in_tension=True,
    )
    assert math.isclose(report.yield_moment_My / kip_in, 61.0, rel_tol=manual_rel_tol)

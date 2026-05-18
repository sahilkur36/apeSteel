"""Phase F-3 anchors for AISC 360-22 §F7 (square/rect HSS & box).

Two-tier anchor per design note 10 §6:

**Tier 1 (primary, bit-exact ``rel_tol=1e-9``):** the library
``compute_flexural_strength_F7_rect_hss`` is pinned to the independent
standalone stdlib oracle :mod:`tests.golden._chapterF_F7_oracle` (which
imports **nothing** from :mod:`apeSteel.flexure`), across the §F7
flange-local-buckling regimes (compact / noncompact / slender flange),
the web-local-buckling regimes, and the lateral-torsional-buckling
regimes (``Lb<=Lp`` / ``Lp<Lb<=Lr`` / ``Lb>Lr``), for **both bending
axes**, and ``>= 2`` steel grades.  A disagreement means the library or
the oracle transcribed a §F7 equation / constant wrong; agreement is
bit-exact because both implement the same closed forms from
independently written source.  Hard literal snapshots (governing limit
state, flange/web classification) are pinned inline as well so any
drift is caught even if the oracle moved in lock-step.

**Tier 2 (external authority - AISC Manual v15.1):** the library §F7
path is driven on the Manual's **published** section values for two
fully worked §F7 examples staged verbatim at
``docs/design_notes/_aisc_src_extract/manual_F7_F8_examples.txt``:

* **Example F.7B** (HSS10x6x3/8, ASTM A500 Gr. C, ``Fy = 50 ksi``;
  Manual pp. F-34..F-36, PDF p.181-184) - a *rectangular* HSS with a
  **noncompact flange** + compact web, exercising Eq. F7-2 (FLB) and
  the §F7.4 LTB path (Eq. F7-10/F7-12/F7-13).  Governing: FLB
  ``Mn = 796 kip-in = 66.4 kip-ft``; ``phi*Mn = 59.8 kip-ft``.
* **Example F.8B** (HSS8x8x0.174, ASTM A500 Gr. C, ``Fy = 50 ksi``;
  Manual pp. F-39..F-41, PDF p.186-188) - a *square* HSS with a
  **slender flange** + compact web, exercising Eq. F7-3/F7-4 (the
  effective-width ``Se``) and the §F7.4 square-HSS LTB *exclusion*.
  Governing: slender-flange FLB ``Mn = 605 kip-in = 50.4 kip-ft``;
  ``phi*Mn = 45.4 kip-ft``.

Every Manual number asserted is quoted from the staged extract (see the
PROVENANCE BOUNDARY comment before the tier-2 tests) - nothing is
invented.  The library carries full precision while the Manual prints
3 sig figs (and rounds intermediate ``Se``/``be``), so the
Manual-result comparisons use a documented ``rel_tol`` loose enough for
the printed rounding but tight enough to catch a wrong §F7 equation;
the closed-form ``Mn`` is *also* pinned bit-exactly against the
recomputed equation so the formula is locked independently of that
tolerance.  ENGINEER-CONFIRM **F7-EC-1 / F7-EC-2** (the Table B4.1b
HSS-flange / HSS-web *case numbers* - the Manual prints "Case 17" /
"Case 19") are noted; the numeric limits do not depend on the label
and the oracle re-derives them numerically, so the §F7 strength
anchors do not rest on the unconfirmed case-number page label.

Full AISC-v16-catalog wiring of HSS shapes is Phase F-8; §F7 ships here
as geometry method + pure calculator + oracle + golden only (no facade
/ ``Element`` wiring).
"""

from __future__ import annotations

import math
import re

import pytest

from apeSteel.core import units as u
from apeSteel.core.materials import A36, A992, S355, S460, SteelMaterial
from apeSteel.flexure.F7_rect_hss import compute_flexural_strength_F7_rect_hss
from apeSteel.sections.flexural_properties import (
    BendingAxis,
    FlexuralPlateElement,
    FlexuralSectionProperties,
)
from apeSteel.sections.geometry.rectangular_hss import RectangularHSS
from tests.golden._chapterF_F7_oracle import F7OracleProps, mn_F7

REL_TOL = 1e-9

# AISC §F1 strength factors (independent literals, not imported from the
# library, so a typo in apeSteel surfaces here).
_PHI_B = 0.90
_OMEGA_B = 1.67


def _oracle_props(
    rhss: RectangularHSS,
    mat: SteelMaterial,
    *,
    bending_axis: BendingAxis,
    Lb: float | None,
    Cb: float = 1.0,
) -> F7OracleProps:
    """Lift the geometry snapshot into the independent oracle's inputs.

    ``Z``/``S``/``I``/``r``/``Ag``/``J`` come from the apeSteel geometry
    layer (whose hollow-rectangle closed forms are cross-checked against
    the compression path's ``Ag``/``I`` in the geometry tests); the
    oracle re-derives only the §F7 strength composition, so this is
    still an independent anchor of the Chapter-F math.
    """
    fsp = rhss.compute_section_properties()
    t = fsp.wall_thickness_t
    walls = {e.name: e for e in fsp.plate_elements}
    flat_B = walls["wall_B"].slenderness_ratio_lambda * t  # B-wall flat (B-2t)
    flat_H = walls["wall_H"].slenderness_ratio_lambda * t  # H-wall flat (H-2t)
    H = fsp.overall_depth_d
    B = walls["wall_B"].slenderness_ratio_lambda * t + 2.0 * t
    if bending_axis == "major":
        z_mod, s_mod, I_axis = (
            fsp.plastic_modulus_Zx,
            fsp.elastic_modulus_Sx,
            fsp.moment_of_inertia_Ix,
        )
        section_depth = H
        flange_flat, web_flat = flat_B, flat_H
    else:
        z_mod, s_mod, I_axis = (
            fsp.plastic_modulus_Zy,
            fsp.elastic_modulus_Sy,
            fsp.moment_of_inertia_Iy,
        )
        section_depth = B
        flange_flat, web_flat = flat_H, flat_B
    return F7OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        B=B,
        H=H,
        t=t,
        Z=z_mod,
        S=s_mod,
        I_axis=I_axis,
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


# ===========================================================================
# Geometry sanity: the flexure snapshot shares Ag / I / J with the
# (frozen, untouched) compression snapshot bit-for-bit.
# ===========================================================================
def test_F7_geometry_shares_gross_props_with_compression_path() -> None:
    """``compute_section_properties`` must not perturb the §E numbers.

    ``RectangularHSS.compute_compression_properties`` is frozen
    (Phase E).  The new flexure method re-uses the *identical* ``Ag`` /
    ``Ix`` / ``Iy`` / ``J`` closed forms; assert they coincide exactly
    so the additive flexure path provably did not disturb the verified
    compression path.
    """
    rhss = RectangularHSS(depth_H=250.0 * u.mm, width_B=150.0 * u.mm, wall_thickness_t=8.0 * u.mm)
    comp = rhss.compute_compression_properties(A992)
    flex = rhss.compute_section_properties()

    assert flex.gross_area_Ag == comp.gross_area_Ag
    assert flex.moment_of_inertia_Ix == comp.moment_of_inertia_x_Ix
    assert flex.moment_of_inertia_Iy == comp.moment_of_inertia_y_Iy
    assert flex.torsional_constant_J == comp.torsional_constant_J
    assert flex.radius_of_gyration_rx == comp.radius_of_gyration_x_rx
    assert flex.radius_of_gyration_ry == comp.radius_of_gyration_y_ry
    assert flex.section_kind == "rectangular_HSS"
    assert flex.symmetry == "doubly_symmetric"


def test_F7_geometry_closed_forms_pinned() -> None:
    """Pin the hollow-rectangle ``Z``/``S`` closed forms inline.

    Independent re-derivation for ``H=300, B=200, t=10`` (mm)
    (``Hi=280, Bi=180``):

    * ``Ag = 2 B t + 2 (H - 2 t) t``
    * ``Ix = (B H^3 - Bi Hi^3)/12``;   ``Sx = 2 Ix / H``
    * ``Iy = (H B^3 - Hi Bi^3)/12``;   ``Sy = 2 Iy / B``
    * ``Zx = (B H^2 - Bi Hi^2)/4``;    ``Zy = (H B^2 - Hi Bi^2)/4``
    """
    H, B, t = 300.0, 200.0, 10.0
    Hi, Bi = H - 2.0 * t, B - 2.0 * t
    rhss = RectangularHSS(depth_H=H * u.mm, width_B=B * u.mm, wall_thickness_t=t * u.mm)
    flex = rhss.compute_section_properties()

    expected_Ag = 2.0 * B * t + 2.0 * (H - 2.0 * t) * t
    expected_Ix = (B * H**3 - Bi * Hi**3) / 12.0
    expected_Iy = (H * B**3 - Hi * Bi**3) / 12.0
    expected_Zx = (B * H**2 - Bi * Hi**2) / 4.0
    expected_Zy = (H * B**2 - Hi * Bi**2) / 4.0

    assert math.isclose(flex.gross_area_Ag, expected_Ag, rel_tol=REL_TOL)
    assert math.isclose(flex.moment_of_inertia_Ix, expected_Ix, rel_tol=REL_TOL)
    assert math.isclose(flex.moment_of_inertia_Iy, expected_Iy, rel_tol=REL_TOL)
    assert math.isclose(flex.elastic_modulus_Sx, 2.0 * expected_Ix / H, rel_tol=REL_TOL)
    assert math.isclose(flex.elastic_modulus_Sy, 2.0 * expected_Iy / B, rel_tol=REL_TOL)
    assert math.isclose(flex.plastic_modulus_Zx, expected_Zx, rel_tol=REL_TOL)
    assert math.isclose(flex.plastic_modulus_Zy, expected_Zy, rel_tol=REL_TOL)
    # Hard literal snapshot (closed-form exact rationals):
    #   Zx = (200*300^2 - 180*280^2)/4 = (18,000,000-14,112,000)/4
    #      = 3,888,000/4 = 972,000
    #   Zy = (300*200^2 - 280*180^2)/4 = (12,000,000- 9,072,000)/4
    #      = 2,928,000/4 = 732,000
    assert math.isclose(flex.plastic_modulus_Zx, 972_000.0, rel_tol=REL_TOL)
    assert math.isclose(flex.plastic_modulus_Zy, 732_000.0, rel_tol=REL_TOL)
    # Flat walls carried for the §F7 calculator (welded-box clear width).
    walls = {e.name: e for e in flex.plate_elements}
    assert set(walls) == {"wall_B", "wall_H"}
    assert math.isclose(walls["wall_B"].slenderness_ratio_lambda, Bi / t, rel_tol=REL_TOL)
    assert math.isclose(walls["wall_H"].slenderness_ratio_lambda, Hi / t, rel_tol=REL_TOL)
    assert flex.wall_thickness_t == t
    assert flex.overall_depth_d == H


def test_F7_square_hss_axisymmetric_moduli_equal() -> None:
    """A square HSS has ``Zx==Zy``, ``Sx==Sy``, ``Ix==Iy`` exactly."""
    rhss = RectangularHSS(depth_H=200.0 * u.mm, width_B=200.0 * u.mm, wall_thickness_t=10.0 * u.mm)
    flex = rhss.compute_section_properties()
    assert flex.moment_of_inertia_Ix == flex.moment_of_inertia_Iy
    assert flex.elastic_modulus_Sx == flex.elastic_modulus_Sy
    assert flex.plastic_modulus_Zx == flex.plastic_modulus_Zy
    assert flex.radius_of_gyration_rx == flex.radius_of_gyration_ry


# ===========================================================================
# Tier 1 - library vs independent §F7 oracle, all regimes, both axes,
# >= 2 grades.
# ===========================================================================
# Geometry is plate-built (welded-box clear width b/t = (dim-2t)/t).  For
# A992 / S355 / S460 / A36, sqrt(E/Fy) differs, so the same geometry
# lands in different Table B4.1b bands across grades.  flange lambda_p =
# 1.12 sqrt(E/Fy), lambda_r = 1.40 sqrt(E/Fy); web lambda_p =
# 2.42 sqrt(E/Fy), lambda_r = 5.70 sqrt(E/Fy).  The expected flange /
# web class is *re-derived in-test* from these literal coefficients (NOT
# imported from the library classifier, so a coefficient typo there
# surfaces here); the geometry+grade combinations are chosen to span
# compact / noncompact / slender flange, compact / noncompact web, both
# bending axes, and the LTB regimes.
_REGIME_CASES: tuple[
    tuple[str, float, float, float, SteelMaterial, BendingAxis, float | None, float], ...
] = (
    # name, H, B, t (mm), material, axis, Lb (mm | None), Cb
    ("A992 sq compact major", 200.0, 200.0, 16.0, A992, "major", 2000.0, 1.0),
    ("S355 sq compact minor", 200.0, 200.0, 16.0, S355, "minor", None, 1.0),
    ("A992 rect NC-flange major", 300.0, 200.0, 6.0, A992, "major", 12000.0, 1.0),
    ("S460 rect slender-flange major", 300.0, 200.0, 6.0, S460, "major", 12000.0, 1.0),
    ("A992 rect slender-flange major", 360.0, 220.0, 4.0, A992, "major", 14000.0, 1.0),
    ("S355 sq slender-flange major", 300.0, 300.0, 4.0, S355, "major", 8000.0, 1.0),
    # compact flange + noncompact web, short Lb -> WLB (Eq. F7-6) governs.
    ("A992 NC-web governs major", 700.0, 250.0, 10.0, A992, "major", 2000.0, 1.0),
    ("A36 rect NC-flange minor", 300.0, 200.0, 6.0, A36, "minor", None, 1.0),
    # Lp < Lb <= Lr -> inelastic LTB (Eq. F7-10) governs.
    ("A36 rect inelastic-LTB major", 400.0, 100.0, 8.0, A36, "major", 9000.0, 1.0),
    # Lb > Lr -> elastic LTB (Eq. F7-11).  A closed HSS has an
    # intrinsically huge Lr (the §F7.4 User Note's point), so an
    # extreme Lb is required purely to exercise the Eq. F7-11 code path.
    ("A36 rect elastic-LTB major", 400.0, 100.0, 8.0, A36, "major", 120000.0, 1.0),
    ("A992 sq LTB-excluded major", 250.0, 250.0, 12.0, A992, "major", 40000.0, 1.0),
    ("A36 rect minor LTB-excluded", 400.0, 100.0, 8.0, A36, "minor", 40000.0, 1.0),
)


def _expected_class(lam: float, lam_p: float, lam_r: float) -> str:
    if lam <= lam_p:
        return "compact"
    if lam <= lam_r:
        return "non_compact"
    return "slender"


@pytest.mark.parametrize("case", _REGIME_CASES, ids=[c[0] for c in _REGIME_CASES])
def test_F7_matches_independent_oracle_all_regimes(
    case: tuple[str, float, float, float, SteelMaterial, BendingAxis, float | None, float],
) -> None:
    """Library §F7 ``Mn`` == independent oracle, bit-exact, every regime.

    The bit-exact library-vs-oracle agreement is the primary regression
    pin.  The flange / web classification the library used is *also*
    cross-checked against an in-test first-principles re-derivation of
    the Table B4.1b limits (literal coefficients, not imported), and the
    governing limit state is asserted to agree with the independent
    oracle - so a wrong regime split is caught even though both
    implementations would still "agree" with each other on a wrong Mn
    only if they shared the identical bug (they are independently
    written).
    """
    _name, H_mm, B_mm, t_mm, material, bending_axis, Lb_mm, Cb = case
    rhss = RectangularHSS(depth_H=H_mm * u.mm, width_B=B_mm * u.mm, wall_thickness_t=t_mm * u.mm)
    fsp = rhss.compute_section_properties()
    Lb = None if Lb_mm is None else Lb_mm * u.mm

    report = compute_flexural_strength_F7_rect_hss(
        fsp, material, bending_axis=bending_axis, unbraced_length_Lb=Lb, Cb=Cb
    )
    oracle = mn_F7(_oracle_props(rhss, material, bending_axis=bending_axis, Lb=Lb, Cb=Cb))

    # Primary bit-exact pin (library vs the independent stdlib oracle).
    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_Mp, oracle.Mp, rel_tol=REL_TOL)
    assert math.isclose(report.Mn_flange_local_buckling, oracle.Mn_flb, rel_tol=REL_TOL)
    assert math.isclose(report.Mn_web_local_buckling, oracle.Mn_wlb, rel_tol=REL_TOL)
    assert math.isclose(report.Mn_lateral_torsional_buckling, oracle.Mn_ltb, rel_tol=REL_TOL)
    assert math.isclose(report.limiting_length_Lp, oracle.Lp, rel_tol=REL_TOL)
    assert math.isclose(report.limiting_length_Lr, oracle.Lr, rel_tol=REL_TOL)
    assert math.isclose(report.effective_section_modulus_Se, oracle.Se, rel_tol=REL_TOL)

    # Library classification == in-test first-principles re-derivation
    # (literal Table B4.1b coefficients, independent of the classifier).
    s = math.sqrt(material.elastic_modulus_E / material.yield_stress_Fy)
    exp_flange = _expected_class(report.flange_slenderness_b_t, 1.12 * s, 1.40 * s)
    exp_web = _expected_class(report.web_slenderness_h_t, 2.42 * s, 5.70 * s)
    assert report.flange_classification == exp_flange == oracle.flange_class
    assert report.web_classification == exp_web == oracle.web_class
    # Governing limit state agrees with the independent oracle.
    assert report.governing_limit_state == oracle.governing
    # §F7.4 User Note: LTB never applies to a square section or
    # minor-axis bending, regardless of Lb.
    walls_equal = math.isclose(
        report.flange_slenderness_b_t, report.web_slenderness_h_t, rel_tol=1e-12
    )
    is_square = walls_equal and B_mm == H_mm
    if is_square or bending_axis == "minor":
        assert report.lateral_torsional_buckling_applies is False
        assert report.governing_limit_state != "lateral_torsional_buckling"

    # phi / Omega plumbing (independent literals).
    assert report.phi_LRFD == _PHI_B
    assert report.omega_ASD == _OMEGA_B
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_F7_regime_coverage_is_complete() -> None:
    """The tier-1 case matrix genuinely spans every §F7 limit state.

    Guards against the regime cases silently all collapsing to one
    branch (e.g. a classifier change making every flange compact): the
    matrix must, in aggregate, exercise compact + noncompact + slender
    flange, compact + noncompact web, both bending axes, the LTB
    inelastic *and* elastic branches, and the §F7.4 square / minor-axis
    LTB exclusion.
    """
    flange_classes: set[str] = set()
    web_classes: set[str] = set()
    governing: set[str] = set()
    axes: set[str] = set()
    ltb_applies_seen = False
    ltb_excluded_seen = False
    elastic_ltb_seen = False
    inelastic_ltb_seen = False
    for _name, H_mm, B_mm, t_mm, material, bending_axis, Lb_mm, Cb in _REGIME_CASES:
        rhss = RectangularHSS(
            depth_H=H_mm * u.mm, width_B=B_mm * u.mm, wall_thickness_t=t_mm * u.mm
        )
        fsp = rhss.compute_section_properties()
        Lb = None if Lb_mm is None else Lb_mm * u.mm
        rep = compute_flexural_strength_F7_rect_hss(
            fsp, material, bending_axis=bending_axis, unbraced_length_Lb=Lb, Cb=Cb
        )
        flange_classes.add(rep.flange_classification)
        web_classes.add(rep.web_classification)
        governing.add(rep.governing_limit_state)
        axes.add(rep.bending_axis)
        if rep.lateral_torsional_buckling_applies:
            ltb_applies_seen = True
            if rep.unbraced_length_Lb > rep.limiting_length_Lr:
                elastic_ltb_seen = True
            elif rep.unbraced_length_Lb > rep.limiting_length_Lp:
                inelastic_ltb_seen = True
        if (B_mm == H_mm or bending_axis == "minor") and Lb is not None:
            ltb_excluded_seen = ltb_excluded_seen or (
                rep.lateral_torsional_buckling_applies is False
            )

    assert {"compact", "non_compact", "slender"} <= flange_classes
    assert {"compact", "non_compact"} <= web_classes
    assert {"major", "minor"} <= axes
    assert "yielding" in governing
    assert "flange_local_buckling" in governing
    assert "web_local_buckling" in governing
    assert ltb_applies_seen
    assert elastic_ltb_seen
    assert inelastic_ltb_seen
    assert ltb_excluded_seen


def test_F7_slender_web_branch_eq_F7_7() -> None:
    """Eq. F7-7 slender-web branch: ``Mn = Rpg*Fy*S`` (Eq. F5-6 ``Rpg``).

    The §F7.3 User Note states *there are no HSS with slender webs*, so
    this branch is only reachable by a (box) section with a very deep
    thin web; none of the tier-1 regime cases hit it.  This focused
    case (A992, deep thin section: web ``h/t`` past
    ``lambda_rw = 5.70 sqrt(E/Fy)``) exercises Eq. F7-7 and pins the
    library to the independent oracle bit-exactly, and to an in-test
    re-derivation of Eq. F5-6 ``Rpg`` (``aw = 2 h t/(b t)``, capped at
    10) so the slender-web composition is locked independently.
    """
    rhss = RectangularHSS(depth_H=900.0 * u.mm, width_B=200.0 * u.mm, wall_thickness_t=6.0 * u.mm)
    fsp = rhss.compute_section_properties()
    rep = compute_flexural_strength_F7_rect_hss(
        fsp, A992, bending_axis="major", unbraced_length_Lb=3000.0 * u.mm
    )
    oracle = mn_F7(_oracle_props(rhss, A992, bending_axis="major", Lb=3000.0 * u.mm))

    assert rep.web_classification == "slender"
    assert math.isclose(rep.Mn_web_local_buckling, oracle.Mn_wlb, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)

    # In-test Eq. F5-6 Rpg re-derivation (literal constants).
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    s = math.sqrt(E / Fy)
    t = fsp.wall_thickness_t
    walls = {e.name: e for e in fsp.plate_elements}
    h_flat = walls["wall_H"].slenderness_ratio_lambda * t  # web flat (major)
    b_flat = walls["wall_B"].slenderness_ratio_lambda * t  # flange flat (major)
    h_tw = h_flat / t
    aw = min(2.0 * h_flat * t / (b_flat * t), 10.0)
    rpg = min(1.0 - (aw / (1200.0 + 300.0 * aw)) * (h_tw - 5.7 * s), 1.0)
    expected_wlb = rpg * Fy * fsp.elastic_modulus_Sx
    assert math.isclose(rep.Mn_web_local_buckling, expected_wlb, rel_tol=REL_TOL)


def test_F7_regime_formulae_pinned_inline() -> None:
    """Inline closed-form pins for a representative of each §F7 branch.

    Re-derives Eq. F7-1 / F7-2 / F7-3+F7-4 / F7-6 / F7-10 from scratch
    (independent of both the library and the oracle) and pins the
    library output to them, so a coordinated library+oracle drift is
    still caught.
    """
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    s = math.sqrt(E / Fy)
    lpf, lrf = 1.12 * s, 1.40 * s
    lpw, lrw = 2.42 * s, 5.70 * s

    # -- Eq. F7-1 yielding: compact section, short Lb -> Mn = Mp = Fy*Zx --
    r1 = RectangularHSS(depth_H=200.0 * u.mm, width_B=200.0 * u.mm, wall_thickness_t=16.0 * u.mm)
    f1 = r1.compute_section_properties()
    rep1 = compute_flexural_strength_F7_rect_hss(f1, A992, bending_axis="major")
    expected1 = Fy * f1.plastic_modulus_Zx
    assert math.isclose(rep1.nominal_flexural_strength_Mn, expected1, rel_tol=REL_TOL)

    # -- Eq. F7-2 noncompact flange (compact web), major axis --
    r2 = RectangularHSS(depth_H=300.0 * u.mm, width_B=200.0 * u.mm, wall_thickness_t=6.0 * u.mm)
    f2 = r2.compute_section_properties()
    walls2 = {e.name: e for e in f2.plate_elements}
    lam_fl = walls2["wall_B"].slenderness_ratio_lambda  # flange (major) = B-wall
    Mp2 = Fy * f2.plastic_modulus_Zx
    FyS2 = Fy * f2.elastic_modulus_Sx
    expected2 = min(Mp2 - (Mp2 - FyS2) * (lam_fl - lpf) / (lrf - lpf), Mp2)
    rep2 = compute_flexural_strength_F7_rect_hss(
        f2, A992, bending_axis="major", unbraced_length_Lb=2000.0 * u.mm
    )
    assert lpf < lam_fl <= lrf  # genuinely in the noncompact band
    assert math.isclose(rep2.Mn_flange_local_buckling, expected2, rel_tol=REL_TOL)
    assert math.isclose(rep2.nominal_flexural_strength_Mn, expected2, rel_tol=REL_TOL)

    # -- Eq. F7-3 + F7-4 slender flange, square (web compact) -> Se --
    # 180/180/4: flat b/t = h/t = 43.0; flange slender (43 > 1.40*s),
    # web compact (43 <= 2.42*s); square -> §F7.4 LTB excluded, so the
    # slender-flange Mn = Fy*Se is the sole governing reduction.
    r3 = RectangularHSS(depth_H=180.0 * u.mm, width_B=180.0 * u.mm, wall_thickness_t=4.0 * u.mm)
    f3 = r3.compute_section_properties()
    t3 = f3.wall_thickness_t
    walls3 = {e.name: e for e in f3.plate_elements}
    b_flat3 = walls3["wall_B"].slenderness_ratio_lambda * t3  # flange flat
    bt3 = b_flat3 / t3
    be3 = min(1.92 * t3 * s * (1.0 - 0.38 / bt3 * s), b_flat3)
    ineff3 = b_flat3 - be3
    H3 = f3.overall_depth_d
    arm3 = (H3 - t3) / 2.0
    Ieff3 = f3.moment_of_inertia_Ix - 2.0 * (ineff3 * t3**3 / 12.0 + ineff3 * t3 * arm3**2)
    Se3 = Ieff3 / (H3 / 2.0)
    expected3 = Fy * Se3
    rep3 = compute_flexural_strength_F7_rect_hss(f3, A992, bending_axis="major")
    assert rep3.flange_classification == "slender"
    assert math.isclose(rep3.effective_section_modulus_Se, Se3, rel_tol=REL_TOL)
    assert math.isclose(rep3.nominal_flexural_strength_Mn, expected3, rel_tol=REL_TOL)

    # -- Eq. F7-6 noncompact web governs (deep narrow, compact flange) --
    r4 = RectangularHSS(depth_H=700.0 * u.mm, width_B=250.0 * u.mm, wall_thickness_t=10.0 * u.mm)
    f4 = r4.compute_section_properties()
    walls4 = {e.name: e for e in f4.plate_elements}
    lam_web4 = walls4["wall_H"].slenderness_ratio_lambda  # web (major) = H-wall
    Mp4 = Fy * f4.plastic_modulus_Zx
    FyS4 = Fy * f4.elastic_modulus_Sx
    expected4 = min(Mp4 - (Mp4 - FyS4) * (lam_web4 - lpw) / (lrw - lpw), Mp4)
    rep4 = compute_flexural_strength_F7_rect_hss(
        f4, A992, bending_axis="major", unbraced_length_Lb=2000.0 * u.mm
    )
    assert lpw < lam_web4 <= lrw
    assert math.isclose(rep4.Mn_web_local_buckling, expected4, rel_tol=REL_TOL)
    assert math.isclose(rep4.nominal_flexural_strength_Mn, expected4, rel_tol=REL_TOL)


def test_F7_monotonic_in_unbraced_length() -> None:
    """phi*Mn must not increase as the unbraced length grows.

    Sanity guard independent of the oracle: for a rectangular HSS bent
    about its strong axis, a longer unbraced span is never stronger.
    """
    rhss = RectangularHSS(depth_H=400.0 * u.mm, width_B=100.0 * u.mm, wall_thickness_t=8.0 * u.mm)
    fsp = rhss.compute_section_properties()
    prev = math.inf
    for Lb_m in (2.0, 6.0, 9.0, 15.0, 25.0, 40.0):
        phi_mn = compute_flexural_strength_F7_rect_hss(
            fsp, A992, bending_axis="major", unbraced_length_Lb=Lb_m * 1000.0 * u.mm
        ).phi_strength_LRFD
        assert phi_mn <= prev + 1.0  # +1 N*mm slack for float noise
        prev = phi_mn


# ===========================================================================
# Guard rails
# ===========================================================================
def test_F7_rejects_non_rectangular_hss_kind() -> None:
    """A non-rect-HSS snapshot must be refused (no silent wrong number)."""
    bogus = FlexuralSectionProperties(
        section_kind="round_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=300.0,
        gross_area_Ag=1.0,
        moment_of_inertia_Ix=1.0,
        elastic_modulus_Sx=1.0,
        plastic_modulus_Zx=1.0,
        radius_of_gyration_rx=1.0,
        moment_of_inertia_Iy=1.0,
        elastic_modulus_Sy=1.0,
        plastic_modulus_Zy=1.0,
        radius_of_gyration_ry=1.0,
    )
    with pytest.raises(ValueError, match="rectangular/square HSS"):
        compute_flexural_strength_F7_rect_hss(bogus, A992)


def test_F7_rejects_bad_plate_elements() -> None:
    """A rect-HSS snapshot lacking the two flat walls must be refused."""
    bogus = FlexuralSectionProperties(
        section_kind="rectangular_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=300.0,
        gross_area_Ag=1.0,
        moment_of_inertia_Ix=1.0,
        elastic_modulus_Sx=1.0,
        plastic_modulus_Zx=1.0,
        radius_of_gyration_rx=1.0,
        moment_of_inertia_Iy=1.0,
        elastic_modulus_Sy=1.0,
        plastic_modulus_Zy=1.0,
        radius_of_gyration_ry=1.0,
        wall_thickness_t=8.0,
        plate_elements=(
            FlexuralPlateElement(
                name="wall_X",
                role="hss_flange",
                aisc_b4_1b_case="B4.1b Case ?",
                slenderness_ratio_lambda=20.0,
                compact_limit_lambda_p=0.0,
                noncompact_limit_lambda_r=0.0,
            ),
        ),
    )
    with pytest.raises(ValueError, match=re.escape("flat walls {'wall_B', 'wall_H'}")):
        compute_flexural_strength_F7_rect_hss(bogus, A992)


def test_F7_rejects_nonpositive_Lb() -> None:
    """A supplied non-positive ``Lb`` must raise."""
    rhss = RectangularHSS(depth_H=400.0 * u.mm, width_B=100.0 * u.mm, wall_thickness_t=8.0 * u.mm)
    fsp = rhss.compute_section_properties()
    with pytest.raises(ValueError, match="unbraced_length_Lb"):
        compute_flexural_strength_F7_rect_hss(
            fsp, A992, bending_axis="major", unbraced_length_Lb=-1.0
        )


def test_F7_square_and_minor_axis_have_no_LTB() -> None:
    """§F7.4 User Note: LTB N/A to square HSS / minor-axis bending.

    Even with an extreme unbraced length, a square HSS (and any HSS bent
    about its minor axis) must report ``lateral_torsional_buckling_applies
    is False`` and ``Mn`` unreduced by LTB.
    """
    # Square HSS, very long Lb -> LTB still excluded.
    sq = RectangularHSS(depth_H=250.0 * u.mm, width_B=250.0 * u.mm, wall_thickness_t=12.0 * u.mm)
    fsq = sq.compute_section_properties()
    rep_sq = compute_flexural_strength_F7_rect_hss(
        fsq, A992, bending_axis="major", unbraced_length_Lb=50_000.0 * u.mm
    )
    assert rep_sq.lateral_torsional_buckling_applies is False
    assert math.isclose(
        rep_sq.Mn_lateral_torsional_buckling, rep_sq.plastic_moment_Mp, rel_tol=REL_TOL
    )
    assert rep_sq.governing_limit_state == "yielding"

    # Rectangular HSS, minor-axis bending, very long Lb -> LTB excluded.
    rect = RectangularHSS(depth_H=400.0 * u.mm, width_B=120.0 * u.mm, wall_thickness_t=8.0 * u.mm)
    frect = rect.compute_section_properties()
    rep_minor = compute_flexural_strength_F7_rect_hss(
        frect, A992, bending_axis="minor", unbraced_length_Lb=50_000.0 * u.mm
    )
    assert rep_minor.lateral_torsional_buckling_applies is False
    assert math.isclose(
        rep_minor.Mn_lateral_torsional_buckling,
        rep_minor.plastic_moment_Mp,
        rel_tol=REL_TOL,
    )


def test_F7_cites_spec_equations() -> None:
    """Citations must pin §F7 Eq. F7-1..F7-13 + the B4.1b HSS rows.

    Provenance gate: equation numbers / page verbatim from
    ``spec_chapterF.txt`` (§F7 @ printed 16.1-63..65); the Table B4.1b
    HSS flange/web *case numbers* are ENGINEER-CONFIRM F7-EC-1/EC-2 and
    carry ``page=None``, ``equation="Case ?"`` - never invented.
    """
    rhss = RectangularHSS(depth_H=300.0 * u.mm, width_B=200.0 * u.mm, wall_thickness_t=8.0 * u.mm)
    rep = compute_flexural_strength_F7_rect_hss(
        rhss.compute_section_properties(), A992, bending_axis="major"
    )
    pairs = {(c.section, c.equation) for c in rep.cited_clauses}
    for sec, eq in (
        ("F7.1", "F7-1"),
        ("F7.2", "F7-2"),
        ("F7.2", "F7-3"),
        ("F7.2", "F7-4"),
        ("F7.2", "F7-5"),
        ("F7.3", "F7-6"),
        ("F7.3", "F7-7"),
        ("F7.4", "F7-10"),
        ("F7.4", "F7-11"),
        ("F7.4", "F7-12"),
        ("F7.4", "F7-13"),
        ("F5.2", "F5-6"),
    ):
        assert (sec, eq) in pairs
    assert ("Table B4.1b", "Case ?") in pairs
    f7_pages = {c.page for c in rep.cited_clauses if c.section.startswith("F7")}
    assert f7_pages == {"16.1-63", "16.1-64"}
    # B4.1b HSS case label intentionally unconfirmed (F7-EC-1/EC-2).
    b4 = next(c for c in rep.cited_clauses if c.equation == "Case ?")
    assert b4.page is None


def test_F7_flags_F13_1_hole_rupture_not_covered() -> None:
    """§F7 does not invoke §F13.1 - the report must say so explicitly.

    Per design note 10 §1 a standalone net-flexural-rupture calculator
    is a separate add; §F7 applies no hole reduction itself, so the flag
    is always ``True`` and no numeric reduction is applied here.
    """
    rhss = RectangularHSS(depth_H=300.0 * u.mm, width_B=200.0 * u.mm, wall_thickness_t=8.0 * u.mm)
    rep = compute_flexural_strength_F7_rect_hss(
        rhss.compute_section_properties(), A992, bending_axis="major"
    )
    assert rep.tension_flange_hole_rupture_check_required is True


# ===========================================================================
# Tier 2 - AISC Manual v15.1 Examples F.7B & F.8B, printed sig-figs
# ===========================================================================
# PROVENANCE BOUNDARY (read before changing these numbers):
#
# Both worked examples are staged verbatim at
# ``docs/design_notes/_aisc_src_extract/manual_F7_F8_examples.txt``
# (AISC Manual v15.1 Vol.1, Design Examples).  Every number asserted
# below is quoted from that staged extract - nothing is invented or
# re-derived from a plate-built section:
#
# --- Example F.7B (rectangular HSS, noncompact flange) ---  (PDF p.181-184)
#   "EXAMPLE F.7B RECTANGULAR HSS FLEXURAL MEMBER WITH NONCOMPACT
#    FLANGES"                                                  (p.181)
#   "ASTM A500 Grade C, rectangular HSS  Fy = 50 ksi  Fu = 62 ksi"
#   "From AISC Manual Table 1-11 ... HSS106x  Ag = 5.37 in.2
#    Zx = 18.0 in.3  Sx = 14.9 in.3  ry = 2.52 in.
#    J = 73.8 in.4  b/t = 31.5  h/t = 54.5"                    (p.181)
#   Flange: "1.12 sqrt(29,000/50) = 27.0" (lpf),
#           "1.40 sqrt(29,000/50) = 33.7" (lrf),
#           "lpf < l < lrf; therefore, the flange is noncompact and
#            AISC Specification Equation F7-2 applies"          (p.181)
#   Web:    "2.42 sqrt(29,000/50) = 58.3" (lpw),
#           "l < lpw; therefore, the web is compact"            (p.182)
#   "Mp = Fy Zx = 50 ksi (18.0 in.3) = 900 kip-in."            (p.182)
#   Eq. F7-2 -> "796 kip-in. or 66.4 kip-ft"                   (p.182)
#   "Lb = 21 ft (12 in./ft) = 252 in."                         (p.182)
#   Eq. F7-12 -> "Lp = ... = 210 in."                          (p.182)
#   Eq. F7-13 -> "Lr = ... = 5,580 in."                        (p.183)
#   Eq. F1-1  -> "Cb = ... = 1.14"                              (p.183)
#   "Lp < Lb < Lr" ; Eq. F7-10 -> "1,020 kip-in. > 900 kip-in.;
#    therefore Mn = 900 kip-in. or 75.0 kip-ft"                 (p.183)
#   "The nominal strength is controlled by flange local buckling ...
#    Mn = 66.4 kip-ft"                                          (p.183)
#   "phi_b = 0.90 ... phi_b Mn = 0.90 (66.4 kip-ft) = 59.8 kip-ft"
#   "Omega_b = 1.67 ... Mn/Omega_b = 66.4/1.67 = 39.8 kip-ft"   (p.183)
#
# --- Example F.8B (square HSS, slender flange) ---       (PDF p.186-188)
#   "EXAMPLE F.8B SQUARE HSS FLEXURAL MEMBER WITH SLENDER FLANGES"
#   "ASTM A500 Grade C, rectangular HSS  Fy = 50 ksi  Fu = 62 ksi"
#   "From AISC Manual Table 1-12 ... HSS88x  I = 54.4 in.4
#    Z = 15.7 in.3  S = 13.6 in.3  B = 8.00 in.  H = 8.00 in.
#    t = 0.174 in.  b/t = 43.0  h/t = 43.0"                     (p.186)
#   Flange: "1.40 sqrt(29,000/50) = 33.7" (lr),
#           "43.0 > lr; therefore, the flange is slender"        (p.186)
#   Web:    "2.42 sqrt(29,000/50) = 58.3" (lp),
#           "43.0 < lp; therefore, the web is compact"           (p.187)
#   "AISC Specification Section F7.2(c) applies ... Mn = Fy Se"  (p.187)
#   "b = 8.00 in. - 3 (0.174 in.) = 7.48 in."                    (p.187)
#   Eq. F7-4 -> "be = ... = 6.33 in."                            (p.187)
#   "Ieff = 54.4 in.4 - 2[ ... ] = 48.3 in.4"                    (p.188)
#   "Se = Ieff/(H/2) = 48.3/(8.00/2) = 12.1 in.3"                (p.188)
#   "Mn = Fy Se = 50 ksi (12.1 in.3) = 605 kip-in. or 50.4 kip-ft"
#   "phi_b Mn = 0.90 (50.4 kip-ft) = 45.4 kip-ft"                (p.188)
#   "Mn/Omega_b = 50.4/1.67 = 30.2 kip-ft"                       (p.188)
#   "lateral-torsional buckling is not applicable to square HSS"  (p.188)
#
# The library carries full precision; the Manual rounds intermediate
# Se/be and prints 3 sig figs, so the Manual-result comparisons use
# ``rel_tol=4e-3`` (catches a wrong §F7 equation; absorbs the Manual's
# rounding of be 6.33 / Se 12.1 / the 3-sig-fig kip-ft display).  The
# closed-form Mn is *also* pinned bit-exactly against the equation
# recomputed in-test (rel_tol=1e-9) so the formula is locked
# independently of the rounding tolerance.  ENGINEER-CONFIRM
# F7-EC-1 / F7-EC-2 (B4.1b "Case 17"/"Case 19" page labels) do NOT
# affect these strength anchors (numeric limits re-derived).
#
# ASTM A500 Gr. C is not a pre-built apeSteel grade; construct it
# locally from the Manual's stated Fy = 50 ksi (Fu only for trace).
_A500_GrC = SteelMaterial(
    name="ASTM A500 Gr. C",
    yield_stress_Fy=50.0 * u.ksi,
    tensile_stress_Fu=62.0 * u.ksi,
    elastic_modulus_E=A992.elastic_modulus_E,  # AISC E = 29,000 ksi
    shear_modulus_G=A992.shear_modulus_G,
    density_rho=A992.density_rho,
    expected_yield_ratio_Ry=1.4,
    expected_tensile_ratio_Rt=1.3,
)

# Manual-display rounding tolerance (3 sig figs + rounded Se/be).
_MANUAL_REL_TOL = 4e-3


def _f7b_published_section() -> FlexuralSectionProperties:
    """The Manual F.7B section from its **published** Table 1-11 values.

    AISC Manual v15.1 Ex. F.7B (PDF p.181) quotes, verbatim from AISC
    Manual Table 1-11 for **HSS10x6x3/8**::

        Ag = 5.37 in.2   Zx = 18.0 in.3   Sx = 14.9 in.3
        ry = 2.52 in.    J  = 73.8 in.4   b/t = 31.5  h/t = 54.5

    The snapshot is built **directly from those published numbers**
    (not re-derived from a plate-built HSS - the documented k/corner
    gap would shift b/t and swamp the Manual comparison).  The two
    flat-wall ``plate_elements`` carry the published ``b/t = 31.5``
    (``wall_B``, the flange in major-axis bending) and ``h/t = 54.5``
    (``wall_H``, the web); ``wall_thickness_t`` is the HSS10x6x3/8
    design wall ``t = 0.349 in.`` so the calculator's flat-flange
    reconstruction equals the published ratio (Eq. F7-2 uses only the
    ratio, so the absolute ``t`` only has to be self-consistent and
    keep ``B != H`` so the section is not mis-flagged square).
    ``overall_depth_d`` is the catalog ``H = 10.0 in.``.
    """
    t = 0.349 * u.inches  # HSS10x6x3/8 design wall thickness
    bt = 31.5  # AISC Manual Table 1-11 (F.7B), published flange b/t
    ht = 54.5  # AISC Manual Table 1-11 (F.7B), published web h/t
    wall_b = FlexuralPlateElement(
        name="wall_B",
        role="hss_flange",
        aisc_b4_1b_case="B4.1b Case ?",  # F7-EC-1 (Manual prints Case 17)
        slenderness_ratio_lambda=bt,
        compact_limit_lambda_p=0.0,
        noncompact_limit_lambda_r=0.0,
    )
    wall_h = FlexuralPlateElement(
        name="wall_H",
        role="hss_web",
        aisc_b4_1b_case="B4.1b Case ?",  # F7-EC-2 (Manual prints Case 19)
        slenderness_ratio_lambda=ht,
        compact_limit_lambda_p=0.0,
        noncompact_limit_lambda_r=0.0,
    )
    return FlexuralSectionProperties(
        section_kind="rectangular_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=10.0 * u.inches,  # catalog H
        gross_area_Ag=5.37 * u.inches**2,  # published
        moment_of_inertia_Ix=1.0,  # not on the FLB/LTB path here (trace)
        elastic_modulus_Sx=14.9 * u.inches**3,  # published
        plastic_modulus_Zx=18.0 * u.inches**3,  # published
        radius_of_gyration_rx=1.0,  # major-axis r unused by §F7
        moment_of_inertia_Iy=1.0,
        elastic_modulus_Sy=14.9 * u.inches**3,
        plastic_modulus_Zy=18.0 * u.inches**3,
        radius_of_gyration_ry=2.52 * u.inches,  # published (Eq. F7-12/13)
        torsional_constant_J=73.8 * u.inches**4,  # published
        wall_thickness_t=t,
        plate_elements=(wall_b, wall_h),
    )


def test_F7_manual_v15_1_F7B_noncompact_flange_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.7B published-result cross-check.

    External-authority anchor.  Drive the library §F7 path on the
    Manual's **published** F.7B section (HSS10x6x3/8; AISC Manual
    Table 1-11 ``Zx = 18.0 in.^3``, ``Sx = 14.9 in.^3``,
    ``ry = 2.52 in.``, ``J = 73.8 in.^4``, ``Ag = 5.37 in.^2``,
    ``b/t = 31.5``, ``h/t = 54.5``; ASTM A500 Gr. C ``Fy = 50 ksi``;
    ``Lb = 252 in.``, ``Cb = 1.14``) and reproduce the Manual's printed
    numbers (AISC Manual v15.1 Vol.1 Ex. F.7B, Manual p. F-34..F-36,
    PDF p.181-184; Spec. Eq. F7-2 / F7-10 / F7-12 / F7-13):

    * flange noncompact (``27.0 < 31.5 < 33.7``) -> Eq. F7-2;
    * web compact (``54.5 < 58.3``);
    * ``Mp = Fy Zx = 900 kip-in.``;
    * Eq. F7-2 -> ``Mn_FLB = 796 kip-in. = 66.4 kip-ft``;
    * ``Lp = 210 in.``, ``Lr = 5,580 in.``; ``Lp < Lb < Lr``;
    * Eq. F7-10 -> ``1,020 kip-in.`` capped at ``Mp`` -> ``75.0 kip-ft``;
    * governing FLB -> ``Mn = 66.4 kip-ft``;
      ``phi*Mn = 59.8 kip-ft``, ``Mn/Omega = 39.8 kip-ft``.

    ``Mn`` is *also* pinned bit-exactly (``rel_tol=1e-9``) against
    Eq. F7-2 recomputed in-test, so the equation is locked independently
    of the Manual rounding tolerance.
    """
    fsp = _f7b_published_section()
    Lb = 252.0 * u.inches
    Cb = 1.14  # Manual Eq. F1-1 result, p.183
    rep = compute_flexural_strength_F7_rect_hss(
        fsp, _A500_GrC, bending_axis="major", unbraced_length_Lb=Lb, Cb=Cb
    )

    Fy = _A500_GrC.yield_stress_Fy
    E = _A500_GrC.elastic_modulus_E
    s = math.sqrt(E / Fy)

    # Classification matches the Manual's regime.
    assert rep.flange_classification == "non_compact"
    assert rep.web_classification == "compact"
    # Manual printed lpf=27.0, lrf=33.7, lpw=58.3.
    assert math.isclose(rep.flange_compact_limit_lambda_p, 27.0, abs_tol=0.05)
    assert math.isclose(rep.flange_noncompact_limit_lambda_r, 33.7, abs_tol=0.05)
    assert math.isclose(rep.web_compact_limit_lambda_p, 58.3, abs_tol=0.05)

    # Mp = Fy*Zx = 900 kip-in (bit-exact vs the closed form).
    Mp_cf = Fy * (18.0 * u.inches**3)
    assert math.isclose(rep.plastic_moment_Mp, Mp_cf, rel_tol=REL_TOL)
    Mp_kipin = rep.plastic_moment_Mp / (u.kip * u.inches)
    assert math.isclose(Mp_kipin, 900.0, rel_tol=_MANUAL_REL_TOL)

    # Eq. F7-2 FLB: recompute the spec interpolation in-test and pin
    # bit-exactly, then check the Manual's printed 66.4 kip-ft.
    lpf, lrf = 1.12 * s, 1.40 * s
    Sx = 14.9 * u.inches**3
    Mp = Fy * (18.0 * u.inches**3)
    expected_flb = min(Mp - (Mp - Fy * Sx) * (31.5 - lpf) / (lrf - lpf), Mp)
    assert math.isclose(rep.Mn_flange_local_buckling, expected_flb, rel_tol=REL_TOL)
    mn_flb_kipft = rep.Mn_flange_local_buckling / u.MOMENT_DISPLAY_UNIT_kip_ft
    assert math.isclose(mn_flb_kipft, 66.4, rel_tol=_MANUAL_REL_TOL)

    # Eq. F7-12 / F7-13: Lp = 210 in, Lr = 5,580 in (Manual printed).
    Lp_in = rep.limiting_length_Lp / u.inches
    Lr_in = rep.limiting_length_Lr / u.inches
    assert math.isclose(Lp_in, 210.0, rel_tol=5e-3)
    assert math.isclose(Lr_in, 5580.0, rel_tol=5e-3)
    # Lp < Lb < Lr -> inelastic LTB branch, but Eq. F7-10 caps at Mp
    # (Manual: "1,020 kip-in. > 900 kip-in.; therefore Mn = 900").
    assert rep.limiting_length_Lp < Lb < rep.limiting_length_Lr
    assert rep.lateral_torsional_buckling_applies is True
    assert math.isclose(rep.Mn_lateral_torsional_buckling, rep.plastic_moment_Mp, rel_tol=REL_TOL)
    mn_ltb_kipft = rep.Mn_lateral_torsional_buckling / u.MOMENT_DISPLAY_UNIT_kip_ft
    assert math.isclose(mn_ltb_kipft, 75.0, rel_tol=_MANUAL_REL_TOL)

    # Governing = FLB; Mn = 66.4 kip-ft; phi*Mn = 59.8; Mn/Omega = 39.8.
    assert rep.governing_limit_state == "flange_local_buckling"
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_flb, rel_tol=REL_TOL)
    mn_kipft = rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft
    phi_mn_kipft = rep.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kip_ft
    omega_mn_kipft = rep.omega_strength_ASD / u.MOMENT_DISPLAY_UNIT_kip_ft
    assert math.isclose(mn_kipft, 66.4, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(phi_mn_kipft, 59.8, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(omega_mn_kipft, 39.8, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(
        rep.phi_strength_LRFD, _PHI_B * rep.nominal_flexural_strength_Mn, rel_tol=REL_TOL
    )
    assert math.isclose(
        rep.omega_strength_ASD,
        rep.nominal_flexural_strength_Mn / _OMEGA_B,
        rel_tol=REL_TOL,
    )


def _f8b_published_section() -> FlexuralSectionProperties:
    """The Manual F.8B section from its **published** Table 1-12 values.

    AISC Manual v15.1 Ex. F.8B (PDF p.186) quotes, verbatim from AISC
    Manual Table 1-12 for **HSS8x8x0.174** (square)::

        I = 54.4 in.4   Z = 15.7 in.3   S = 13.6 in.3
        B = 8.00 in.    H = 8.00 in.    t = 0.174 in.
        b/t = 43.0      h/t = 43.0

    Built directly from those published numbers.  The flat-wall
    ``plate_elements`` carry the published ``b/t = h/t = 43.0`` at the
    published ``t = 0.174 in.`` so the calculator's reconstructed
    flat-flange width ``43.0 * 0.174 = 7.48 in.`` equals the Manual's
    ``b = 8.00 - 3(0.174) = 7.48 in.`` (the AISC HSS rounded-corner
    flat width).  ``overall_depth_d`` is the published ``H = 8.00 in.``
    so the slender-flange ``Se = Ieff/(H/2)`` uses the Manual's
    ``H = 8.00`` (and arm ``(H - t)/2``), reproducing
    ``Ieff = 48.3 in.4`` / ``Se = 12.1 in.3``.  ``b/t == h/t`` makes
    the section correctly square -> §F7.4 LTB excluded (Manual:
    "lateral-torsional buckling is not applicable to square HSS").
    """
    t = 0.174 * u.inches  # published
    bt = 43.0  # published flange b/t == web h/t (square)
    wall_b = FlexuralPlateElement(
        name="wall_B",
        role="hss_flange",
        aisc_b4_1b_case="B4.1b Case ?",  # F7-EC-1 (Manual prints Case 17)
        slenderness_ratio_lambda=bt,
        compact_limit_lambda_p=0.0,
        noncompact_limit_lambda_r=0.0,
    )
    wall_h = FlexuralPlateElement(
        name="wall_H",
        role="hss_web",
        aisc_b4_1b_case="B4.1b Case ?",  # F7-EC-2 (Manual prints Case 19)
        slenderness_ratio_lambda=bt,  # square: h/t == b/t == 43.0
        compact_limit_lambda_p=0.0,
        noncompact_limit_lambda_r=0.0,
    )
    return FlexuralSectionProperties(
        section_kind="rectangular_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=8.00 * u.inches,  # published H
        gross_area_Ag=1.0,  # not on the slender-flange path (trace)
        moment_of_inertia_Ix=54.4 * u.inches**4,  # published
        elastic_modulus_Sx=13.6 * u.inches**3,  # published (trace)
        plastic_modulus_Zx=15.7 * u.inches**3,  # published
        radius_of_gyration_rx=1.0,
        moment_of_inertia_Iy=54.4 * u.inches**4,  # square
        elastic_modulus_Sy=13.6 * u.inches**3,
        plastic_modulus_Zy=15.7 * u.inches**3,
        radius_of_gyration_ry=1.0,  # LTB excluded (square) -> ry unused
        torsional_constant_J=1.0,  # LTB excluded -> J unused
        wall_thickness_t=t,
        plate_elements=(wall_b, wall_h),
    )


def test_F7_manual_v15_1_F8B_slender_flange_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.8B published-result cross-check (Eq. F7-3).

    External-authority anchor for the slender-flange branch + the
    §F7.4 square-HSS LTB *exclusion*.  Drive the library §F7 path on
    the Manual's **published** F.8B section (HSS8x8x0.174; AISC Manual
    Table 1-12 ``I = 54.4 in.^4``, ``Z = 15.7 in.^3``,
    ``S = 13.6 in.^3``, ``B = H = 8.00 in.``, ``t = 0.174 in.``,
    ``b/t = h/t = 43.0``; ASTM A500 Gr. C ``Fy = 50 ksi``) and
    reproduce the Manual's printed numbers (AISC Manual v15.1 Vol.1
    Ex. F.8B, Manual p. F-39..F-41, PDF p.186-188; Spec. Eq. F7-3 /
    F7-4):

    * flange slender (``43.0 > 33.7``) -> Eq. F7-3 ``Mn = Fy*Se``;
    * web compact (``43.0 < 58.3``);
    * Eq. F7-4 effective width ``be = 6.33 in.`` (from ``b = 7.48 in``);
    * ``Ieff = 48.3 in.^4``, ``Se = 12.1 in.^3``;
    * ``Mn = Fy*Se = 605 kip-in. = 50.4 kip-ft``;
    * square HSS -> §F7.4 LTB does **not** apply;
    * governing slender-flange FLB -> ``Mn = 50.4 kip-ft``;
      ``phi*Mn = 45.4 kip-ft``, ``Mn/Omega = 30.2 kip-ft``.

    ``Mn`` is *also* pinned bit-exactly (``rel_tol=1e-9``) against
    Eq. F7-3/F7-4 recomputed in-test (same conservative symmetric
    ``Se`` construction the Manual uses), so the equation is locked
    independently of the Manual's Se/be rounding.
    """
    fsp = _f8b_published_section()
    rep = compute_flexural_strength_F7_rect_hss(
        fsp, _A500_GrC, bending_axis="major", unbraced_length_Lb=50_000.0 * u.mm
    )

    Fy = _A500_GrC.yield_stress_Fy
    E = _A500_GrC.elastic_modulus_E
    s = math.sqrt(E / Fy)

    # Regime: slender flange, compact web; Manual lr=33.7, lpw=58.3.
    assert rep.flange_classification == "slender"
    assert rep.web_classification == "compact"
    assert math.isclose(rep.flange_noncompact_limit_lambda_r, 33.7, abs_tol=0.05)
    assert math.isclose(rep.web_compact_limit_lambda_p, 58.3, abs_tol=0.05)

    # Square HSS -> §F7.4 LTB excluded entirely (even with huge Lb).
    assert rep.lateral_torsional_buckling_applies is False
    assert math.isclose(rep.Mn_lateral_torsional_buckling, rep.plastic_moment_Mp, rel_tol=REL_TOL)

    # Recompute Eq. F7-4 be + the conservative symmetric Se in-test and
    # pin the library bit-exactly, then check the Manual's printed Se.
    t = 0.174 * u.inches
    b_flat = 43.0 * t  # = 7.482 in (Manual b = 7.48 in)
    bt = b_flat / t
    be_cf = min(1.92 * t * s * (1.0 - 0.38 / bt * s), b_flat)
    H = 8.00 * u.inches
    arm = (H - t) / 2.0
    ineff = b_flat - be_cf
    Ieff_cf = (54.4 * u.inches**4) - 2.0 * (ineff * t**3 / 12.0 + ineff * t * arm**2)
    Se_cf = Ieff_cf / (H / 2.0)
    expected_mn = Fy * Se_cf
    Se_cf_in3 = rep.effective_section_modulus_Se / u.inches**3

    # be matches the Manual's printed 6.33 in.
    assert math.isclose(be_cf / u.inches, 6.33, rel_tol=3e-3)
    # Se matches the Manual's printed 12.1 in^3, Ieff its 48.3 in^4.
    assert math.isclose(Ieff_cf / u.inches**4, 48.3, rel_tol=4e-3)
    assert math.isclose(rep.effective_section_modulus_Se, Se_cf, rel_tol=REL_TOL)
    assert math.isclose(Se_cf_in3, 12.1, rel_tol=4e-3)

    # Eq. F7-3: Mn = Fy*Se; bit-exact vs the in-test recomputation,
    # then vs the Manual's printed 50.4 kip-ft.
    assert rep.governing_limit_state == "flange_local_buckling"
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_mn, rel_tol=REL_TOL)
    mn_kipft = rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft
    phi_mn_kipft = rep.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kip_ft
    omega_mn_kipft = rep.omega_strength_ASD / u.MOMENT_DISPLAY_UNIT_kip_ft
    # 50 * 12.075 = 603.7 kip-in -> 50.31 kip-ft; Manual prints "50.4"
    # (from rounded Se=12.1 -> 605 kip-in).  rel_tol=4e-3 absorbs it.
    assert math.isclose(mn_kipft, 50.4, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(phi_mn_kipft, 45.4, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(omega_mn_kipft, 30.2, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(
        rep.phi_strength_LRFD, _PHI_B * rep.nominal_flexural_strength_Mn, rel_tol=REL_TOL
    )

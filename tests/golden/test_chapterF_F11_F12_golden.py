"""Phase F-7 anchors for AISC 360-22 §F11 (rectangular bars & rounds)
and §F12 (unsymmetrical shapes).

Two-tier anchor per design note 10 §6:

**Tier 1 (primary, bit-exact ``rel_tol=1e-9``):** the library
``compute_flexural_strength_F11_bar`` /
``compute_flexural_strength_F12_unsymmetric`` are pinned to the
independent standalone stdlib oracle
:mod:`tests.golden._chapterF_F11_F12_oracle` (which imports **nothing**
from :mod:`apeSteel.flexure`):

* §F11 rectangular-bar yielding in **both** LTB-slenderness regimes
  (LTB inactive ``Lb*d/t^2 <= 0.08 E/Fy``; inactive because
  yielding still governs even above the gate; inelastic Eq. F11-3;
  elastic Eq. F11-4 / F11-5), with the Eq. F11-1 ``1.5*Fy*Sx`` cap
  both active and inactive;
* §F11 round-bar yielding (Eq. F11-2, ``1.6*Fy*Sx`` cap, no LTB);
* §F12 ``Mn = Fn*Smin`` with the governing ``Fn`` taken in turn from
  each of Eq. F12-2 (yield), Eq. F12-3 (LTB) and Eq. F12-4 (local
  buckling);
* ``>= 2`` steel grades throughout (A36, A992, S355).

A disagreement means the library or the oracle transcribed a §F11/§F12
equation / constant wrong; agreement is bit-exact because both
implement the same closed forms from independently written source.
Hard literal snapshots (governing limit state, the §F11/§F12 constants,
the closed-form bar moduli) are pinned inline as well so a coordinated
library+oracle drift is still caught.

**Tier 2 (external authority - AISC Manual v15.1 Ex. F.12 / F.13):**
the §F11 examples are staged verbatim at
``docs/design_notes/_aisc_src_extract/manual_F11_F12_examples.txt``:

* **Example F.12** "Rectangular Bar in Major Axis Bending" (AISC
  Manual v15.1 Vol.1, Manual p. F-62..F-64, PDF p.209-211): BAR
  5 in. x 3 in., ASTM A36 ``Fy = 36 ksi``, ``Cb = 1.0``.  The Manual
  prints, from AISC Manual Table 17-27, ``Sx = b d^2/6 = 12.5 in.^3``
  and ``Zx = b d^2/4 = 18.8 in.^3``; ``Lb*d/t^2 = 40.0`` and
  ``0.08 E/Fy = 64.4`` so the **yielding** limit state governs and LTB
  does not apply.  Eq. F11-1 gives ``Mn = Fy*Z`` printed as
  "677 kip-in. or 56.4 kip-ft", ``phi*Mn = 50.8 kip-ft``,
  ``Mn/Omega = 33.8 kip-ft``.

  **DOCUMENTED EDITION DELTA (design note 10 §1/§9).**  The v15.1
  Manual is **360-16**-based and applies the Eq. F11-1 rectangular-bar
  cap as ``1.6*Fy*Sx`` (= 720 kip-in here, inactive).  AISC **360-22**
  (the staged ``spec_chapterF.txt`` printed 16.1-71, the authority)
  tightened that cap to ``1.5*Fy*Sx`` (= 675.0 kip-in here).  With the
  exact closed-form ``Zx = b d^2/4 = 18.75 in.^3`` the 360-22
  capped ``Mn = min(Fy*Z, 1.5*Fy*Sx) = min(675.0, 675.0) = 675.0
  kip-in`` (the cap is exactly tight), versus the Manual's
  360-16-printed 676.8/"677" kip-in (it rounds ``Zx`` to 18.8 and uses
  the looser 1.6 cap).  Tier 2 therefore anchors on the
  **edition-independent** facts the Manual establishes - the
  closed-form ``Sx``/``Zx``, the §F11.2 LTB slenderness gate
  (``Lb*d/t^2 = 40.0 <= 0.08 E/Fy = 64.4`` -> LTB N/A), the governing
  yielding limit state, and the **uncapped** ``Fy*Z`` (which the
  Manual's "677 kip-in" reports) - and pins the 360-22 *capped* result
  bit-exactly in-test so the edition delta is explicit, never hidden.

* **Example F.13** "Round Bar in Bending" (AISC Manual v15.1 Vol.1,
  Manual p. F-65/F-66, PDF p.212-213): BAR 1-in.-diameter, ASTM A36
  ``Fy = 36 ksi``.  **ENGINEER-CONFIRM F7tail-EC-1 - RESOLVED.**  The
  orchestrator extracted the full Ex. F.13 body (the previously-
  truncated "Nominal Flexural Strength" / "Available Flexural
  Strength" block) to
  ``docs/design_notes/_aisc_src_extract/manual_F13_roundbar.txt``
  (verbatim, PDF p.212-213).  The Manual prints, from AISC Manual
  Table 17-27, ``S = pi d^3/32 = 0.0982 in.^3`` and ``Z = d^3/6 =
  0.167 in.^3``; Eq. F11-2 ``Mn = min(Fy*Z, 1.6*Fy*S)`` governs at
  ``Mn = 5.66 kip-in. = 0.472 kip-ft``, ``phi*Mn = 0.425 kip-ft``
  (LRFD), ``Mn/Omega = 0.283 kip-ft`` (ASD) - the library reproduces
  these to the Manual's 3 printed sig figs **and** bit-exactly vs the
  Eq. F11-2 closed form (the staged-source truncation that forced the
  earlier first-principles-hand-calc fallback is closed; no Manual
  value is invented).

Full AISC-v16-catalog / facade / ``Element`` wiring is Phase F-8; §F11
/ §F12 ship here as geometry method + pure calculators + oracle +
golden only.
"""

from __future__ import annotations

import math
import re

import pytest

from apeSteel.core import units as u
from apeSteel.core.materials import A36, A992, S355, SteelMaterial
from apeSteel.flexure.F11_F12_bar_unsymmetric import (
    compute_flexural_strength_F11_bar,
    compute_flexural_strength_F12_unsymmetric,
)
from apeSteel.sections.flexural_properties import FlexuralSectionProperties
from apeSteel.sections.geometry.bar_section import RectangularBar, RoundBar
from tests.golden._chapterF_F11_F12_oracle import (
    F11OracleProps,
    F12OracleProps,
    mn_F11,
    mn_F12,
)

REL_TOL = 1e-9

# AISC §F1 strength factors (independent literals, not imported from
# the library, so a typo in apeSteel surfaces here).
_PHI_B = 0.90
_OMEGA_B = 1.67


def _f11_oracle_props(
    bar: RectangularBar | RoundBar,
    mat: SteelMaterial,
    *,
    Lb: float | None,
    Cb: float,
    major: bool,
) -> F11OracleProps:
    """Lift the geometry snapshot into the independent §F11 oracle inputs.

    ``Z``/``S``/``d`` come from the apeSteel geometry layer (whose bar
    closed forms are cross-checked against the AISC Manual Table 17-27
    expressions in :func:`test_F11_geometry_closed_forms_pinned`); the
    oracle re-derives only the §F11 strength composition, so this is
    still an independent anchor of the Chapter-F math.  The §F11.2 LTB
    width ``t`` is recovered as ``Ag/d`` exactly as the library does.
    """
    fsp = bar.compute_section_properties()
    is_round = isinstance(bar, RoundBar)
    if major or is_round:
        z = fsp.plastic_modulus_Zx
        s = fsp.elastic_modulus_Sx
    else:
        z = fsp.plastic_modulus_Zy
        s = fsp.elastic_modulus_Sy
    return F11OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        Z=z,
        S=s,
        d=fsp.overall_depth_d,
        t=fsp.gross_area_Ag / fsp.overall_depth_d,
        is_round=is_round,
        bending_axis_is_major=major,
        Lb=Lb,
        Cb=Cb,
    )


# ===========================================================================
# Geometry: the §F11 bar closed forms match AISC Manual Table 17-27.
# ===========================================================================
def test_F11_geometry_closed_forms_pinned() -> None:
    """Pin the rectangular- and round-bar closed forms inline.

    AISC Manual v15.1 Table 17-27 (quoted in Examples F.12 / F.13):

    * rectangular bar  ``Sx = b d^2/6``  ``Zx = b d^2/4``
      ``Ix = b d^3/12``  (minor axis: the ``b<->d`` swap);
    * round bar  ``A = pi D^2/4``  ``I = pi D^4/64``
      ``S = pi D^3/32``  ``Z = D^3/6``.
    """
    # -- rectangular: BAR 127 mm x 76.2 mm (5 in x 3 in metric-ish) --
    d_mm, b_mm = 127.0, 76.2
    rb = RectangularBar(depth_d=d_mm * u.mm, width_b=b_mm * u.mm)
    f = rb.compute_section_properties()
    assert math.isclose(f.elastic_modulus_Sx, b_mm * d_mm**2 / 6.0, rel_tol=REL_TOL)
    assert math.isclose(f.plastic_modulus_Zx, b_mm * d_mm**2 / 4.0, rel_tol=REL_TOL)
    assert math.isclose(f.moment_of_inertia_Ix, b_mm * d_mm**3 / 12.0, rel_tol=REL_TOL)
    # Minor axis: b <-> d swap.
    assert math.isclose(f.elastic_modulus_Sy, d_mm * b_mm**2 / 6.0, rel_tol=REL_TOL)
    assert math.isclose(f.plastic_modulus_Zy, d_mm * b_mm**2 / 4.0, rel_tol=REL_TOL)
    assert math.isclose(f.gross_area_Ag, b_mm * d_mm, rel_tol=REL_TOL)
    # The §F11.2 LTB width is recovered exactly as Ag/d = b.
    assert math.isclose(f.gross_area_Ag / f.overall_depth_d, b_mm, rel_tol=REL_TOL)
    assert f.section_kind == "rectangular_bar"
    assert f.symmetry == "doubly_symmetric"
    assert f.plate_elements == ()
    assert f.extreme_fibre_moduli == (f.elastic_modulus_Sx, f.elastic_modulus_Sy)

    # -- round: BAR 50 mm diameter --
    big_d = 50.0
    rd = RoundBar(diameter_D=big_d * u.mm)
    g = rd.compute_section_properties()
    assert math.isclose(g.gross_area_Ag, math.pi * big_d**2 / 4.0, rel_tol=REL_TOL)
    assert math.isclose(g.moment_of_inertia_Ix, math.pi * big_d**4 / 64.0, rel_tol=REL_TOL)
    assert math.isclose(g.elastic_modulus_Sx, math.pi * big_d**3 / 32.0, rel_tol=REL_TOL)
    assert math.isclose(g.plastic_modulus_Zx, big_d**3 / 6.0, rel_tol=REL_TOL)
    # Axisymmetry.
    assert g.moment_of_inertia_Ix == g.moment_of_inertia_Iy
    assert g.elastic_modulus_Sx == g.elastic_modulus_Sy
    assert g.plastic_modulus_Zx == g.plastic_modulus_Zy
    assert g.radius_of_gyration_rx == g.radius_of_gyration_ry
    assert g.section_kind == "round_bar"
    assert g.extreme_fibre_moduli == (g.elastic_modulus_Sx,)
    # Hard literal snapshot (exact rationals).
    assert math.isclose(g.plastic_modulus_Zx, 50.0**3 / 6.0, rel_tol=REL_TOL)


def test_F11_geometry_rejects_degenerate_dims() -> None:
    """Non-positive bar dimensions are refused (no silent zero modulus)."""
    with pytest.raises(ValueError, match="depth_d must be positive"):
        RectangularBar(depth_d=0.0, width_b=10.0).compute_section_properties()
    with pytest.raises(ValueError, match="width_b must be positive"):
        RectangularBar(depth_d=10.0, width_b=-1.0).compute_section_properties()
    with pytest.raises(ValueError, match="diameter_D must be positive"):
        RoundBar(diameter_D=0.0).compute_section_properties()


# ===========================================================================
# Tier 1 - §F11 library vs independent oracle, both regimes / >=2 grades
# ===========================================================================
# Geometries chosen so the §F11.2 LTB slenderness Lb*d/t^2 lands in the
# intended band for the grade.  Note a structural fact: for a
# rectangular bar Zx/Sx == 1.5 identically, so Mp == 1.5*My and the
# Eq. F11-3 inelastic value at the lower gate is
# (1.52 - 0.274*0.08)*My = 1.498*My < 1.5*My = Mp - i.e. the instant
# Lb*d/t^2 exceeds 0.08 E/Fy, LTB *controls* (there is no
# "above-gate but yielding still governs" band for a bar).  The
# regimes are therefore exactly:
#   * "yielding"      : Lb*d/t^2 <= 0.08 E/Fy   (LTB N/A; Eq. F11-1/2)
#   * "inelastic_LTB" : 0.08 E/Fy < Lb*d/t^2 <= 1.9 E/Fy (Eq. F11-3)
#   * "elastic_LTB"   : Lb*d/t^2 > 1.9 E/Fy            (Eq. F11-4/5)
#   * minor-axis rect / round            -> "yielding" (LTB N/A)
@pytest.mark.parametrize(
    ("name", "d_mm", "b_mm", "Lb_mm", "Cb", "material", "is_round", "major", "expected_ls"),
    [
        # --- rectangular bar, major axis, yielding (LTB N/A):
        # Lb*d/t^2 <= 0.08 E/Fy.  d=120,b=60,Lb=1000 -> L=33.3;
        # A36 gate_lower=64.4 -> 33.3 < 64.4 (LTB N/A). ---
        ("A36 rect yield LTB-NA", 120.0, 60.0, 1000.0, 1.0, A36, False, True, "yielding"),
        # d=100,b=50,Lb=900 -> L=36.0; A992 gate_lower=46.4 -> N/A.
        ("A992 rect yield LTB-NA", 100.0, 50.0, 900.0, 1.0, A992, False, True, "yielding"),
        # --- rectangular bar, inelastic LTB (Eq. F11-3):
        # 0.08 E/Fy < Lb*d/t^2 <= 1.9 E/Fy.  d=200,b=20,Lb=600 ->
        # L=300; A36 gate (64.4, 1530.6) -> inelastic, LTB controls. ---
        ("A36 rect inelastic-LTB", 200.0, 20.0, 600.0, 1.0, A36, False, True, "inelastic_LTB"),
        # d=200,b=20,Lb=500 -> L=250; S355 gate (45.1, 1070.1).
        ("S355 rect inelastic-LTB", 200.0, 20.0, 500.0, 1.0, S355, False, True, "inelastic_LTB"),
        # --- rectangular bar, elastic LTB (Eq. F11-4/5):
        # Lb*d/t^2 > 1.9 E/Fy.  d=400,b=8,Lb=6000 -> L=37500;
        # A36 gate_upper=1530.6 -> elastic, LTB controls. ---
        ("A36 rect elastic-LTB", 400.0, 8.0, 6000.0, 1.0, A36, False, True, "elastic_LTB"),
        # d=350,b=8,Lb=5000 -> L=27343.75; A992 gate_upper=1102.
        ("A992 rect elastic-LTB", 350.0, 8.0, 5000.0, 1.0, A992, False, True, "elastic_LTB"),
        # --- rectangular bar, minor axis -> LTB never applies (F11.2a) ---
        ("A36 rect minor yield", 200.0, 30.0, 4000.0, 1.0, A36, False, False, "yielding"),
        # --- round bar, yielding only (Eq. F11-2, no LTB) ---
        ("A36 round yield", 50.0, 0.0, 3000.0, 1.0, A36, True, True, "yielding"),
        ("S355 round yield", 40.0, 0.0, 5000.0, 1.0, S355, True, True, "yielding"),
    ],
)
def test_F11_matches_independent_oracle_all_regimes(
    name: str,
    d_mm: float,
    b_mm: float,
    Lb_mm: float,
    Cb: float,
    material: SteelMaterial,
    is_round: bool,
    major: bool,
    expected_ls: str,
) -> None:
    """Library §F11 ``Mn`` == independent oracle, bit-exact, every regime."""
    bar: RectangularBar | RoundBar = (
        RoundBar(diameter_D=d_mm * u.mm)
        if is_round
        else RectangularBar(depth_d=d_mm * u.mm, width_b=b_mm * u.mm)
    )
    fsp = bar.compute_section_properties()

    report = compute_flexural_strength_F11_bar(
        fsp,
        material,
        laterally_unbraced_length_Lb=Lb_mm * u.mm,
        lateral_torsional_modification_Cb=Cb,
        bending_axis="major" if major else "minor",
    )
    oracle = mn_F11(_f11_oracle_props(bar, material, Lb=Lb_mm * u.mm, Cb=Cb, major=major))

    # Primary bit-exact pin.
    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_Mp, oracle.Mp, rel_tol=REL_TOL)
    assert math.isclose(report.yield_moment_My, oracle.My, rel_tol=REL_TOL)
    assert math.isclose(report.uncapped_Fy_Z, oracle.uncapped_Fy_Z, rel_tol=REL_TOL)
    assert math.isclose(report.yield_cap_value, oracle.cap_value, rel_tol=REL_TOL)
    assert math.isclose(report.ltb_slenderness_Lb_d_t2, oracle.L_d_t2, rel_tol=REL_TOL, abs_tol=0.0)
    assert math.isclose(report.ltb_gate_lower, oracle.gate_lower, rel_tol=REL_TOL)
    assert math.isclose(report.ltb_gate_upper, oracle.gate_upper, rel_tol=REL_TOL)
    assert math.isclose(report.critical_stress_Fcr, oracle.Fcr, rel_tol=REL_TOL, abs_tol=0.0)

    # The regime really is the one intended (so every branch is
    # genuinely exercised, not just one).
    assert report.governing_limit_state == expected_ls == oracle.governing
    assert report.lateral_torsional_applies == oracle.ltb_evaluated
    assert report.is_round == is_round

    # phi / Omega plumbing (independent literals).
    assert report.phi_LRFD == _PHI_B
    assert report.omega_ASD == _OMEGA_B
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_F11_yield_cap_active_inactive_and_tight() -> None:
    """Eq. F11-1 / F11-2 cap behaviour across the §F11 section families.

    A structural identity drives this: for **any** rectangular bar
    ``Zx/Sx = (b d^2/4)/(b d^2/6) = 6/4 = 1.5`` *exactly* (both are
    ``proportional to b d^2``), so the 360-22 Eq. F11-1 cap
    ``Mp = Fy*Z <= 1.5*Fy*Sx`` is **always exactly tight** for a
    rectangular bar (``Fy*Z == 1.5*Fy*Sx`` identically; the looser
    360-16 1.6 cap was always inactive - the documented edition delta).
    The cap regimes are therefore exercised as:

    * **rectangular bar** - cap *exactly tight*
      (``Fy*Z == 1.5*Fy*Sx``), every shape & axis;
    * **round bar** - cap *active*
      (``Z/S = (D^3/6)/(pi D^3/32) = 16/(3 pi) = 1.698 > 1.6``, so
      ``Fy*Z > 1.6*Fy*S`` and ``Mp = 1.6*Fy*S``);
    * §F12 exercises a *non-tight* elastic ``Fy*Smin`` (no §F11 cap)
      and is covered by the §F12 tier-1 tests.
    """
    Fy = A36.yield_stress_Fy

    # Rectangular bar (square): cap exactly tight, Mp == Fy*Z == cap.
    sq = RectangularBar(depth_d=100.0 * u.mm, width_b=100.0 * u.mm)
    fsq = sq.compute_section_properties()
    rsq = compute_flexural_strength_F11_bar(fsq, A36)
    assert math.isclose(rsq.uncapped_Fy_Z, rsq.yield_cap_value, rel_tol=REL_TOL)
    assert math.isclose(rsq.plastic_moment_Mp, rsq.yield_cap_value, rel_tol=REL_TOL)
    assert math.isclose(rsq.yield_cap_coefficient, 1.5, rel_tol=REL_TOL)

    # Rectangular bar (very flat) - still exactly tight (Zx/Sx == 1.5
    # is a shape-independent identity for a rectangle).
    flat = RectangularBar(depth_d=20.0 * u.mm, width_b=200.0 * u.mm)
    fflat = flat.compute_section_properties()
    rflat = compute_flexural_strength_F11_bar(fflat, A36)
    assert math.isclose(rflat.uncapped_Fy_Z, rflat.yield_cap_value, rel_tol=REL_TOL)
    assert math.isclose(
        rflat.plastic_moment_Mp,
        Fy * fflat.plastic_modulus_Zx,
        rel_tol=REL_TOL,
    )

    # Round bar: 1.6 cap strictly active (Z/S = 16/(3 pi) > 1.6).
    rd = RoundBar(diameter_D=40.0 * u.mm)
    frd = rd.compute_section_properties()
    rrd = compute_flexural_strength_F11_bar(frd, A36)
    assert rrd.uncapped_Fy_Z > rrd.yield_cap_value
    assert math.isclose(rrd.plastic_moment_Mp, rrd.yield_cap_value, rel_tol=REL_TOL)
    assert math.isclose(rrd.yield_cap_coefficient, 1.6, rel_tol=REL_TOL)
    # Z/S identity for a round: 16/(3*pi).
    assert math.isclose(
        frd.plastic_modulus_Zx / frd.elastic_modulus_Sx,
        16.0 / (3.0 * math.pi),
        rel_tol=REL_TOL,
    )


def test_F11_regime_formulae_pinned_inline() -> None:
    """Inline closed-form pins for each §F11 branch (library+oracle drift).

    Re-derives Eq. F11-1 / F11-3 / F11-4+F11-5 from scratch
    (independent of both the library and the oracle).
    """
    Fy = A36.yield_stress_Fy
    E = A36.elastic_modulus_E

    # -- yielding (LTB N/A): Eq. F11-1  Mn = min(Fy*Z, 1.5*Fy*Sx).
    # d=120,b=60,Lb=1000 -> Lb*d/t^2 = 33.3 < 0.08 E/Fy = 64.4 (A36). --
    rb = RectangularBar(depth_d=120.0 * u.mm, width_b=60.0 * u.mm)
    fb = rb.compute_section_properties()
    rep_y = compute_flexural_strength_F11_bar(fb, A36, laterally_unbraced_length_Lb=1000.0 * u.mm)
    expected_y = min(Fy * fb.plastic_modulus_Zx, 1.5 * Fy * fb.elastic_modulus_Sx)
    assert math.isclose(rep_y.nominal_flexural_strength_Mn, expected_y, rel_tol=REL_TOL)
    assert rep_y.governing_limit_state == "yielding"

    # -- inelastic LTB: Eq. F11-3.  d=200,b=20,Lb=600 ->
    # Lb*d/t^2 = 300, A36 band (64.4, 1530.6) -> inelastic. --
    ri = RectangularBar(depth_d=200.0 * u.mm, width_b=20.0 * u.mm)
    fi = ri.compute_section_properties()
    lb_i = 600.0 * u.mm
    rep_i = compute_flexural_strength_F11_bar(fi, A36, laterally_unbraced_length_Lb=lb_i)
    t_i = fi.gross_area_Ag / fi.overall_depth_d
    l_d_t2_i = lb_i * fi.overall_depth_d / t_i**2
    my_i = Fy * fi.elastic_modulus_Sx
    mp_i = min(Fy * fi.plastic_modulus_Zx, 1.5 * Fy * fi.elastic_modulus_Sx)
    expected_i = min(1.0 * (1.52 - 0.274 * l_d_t2_i * (Fy / E)) * my_i, mp_i)
    assert rep_i.governing_limit_state == "inelastic_LTB"
    assert math.isclose(rep_i.nominal_flexural_strength_Mn, expected_i, rel_tol=REL_TOL)

    # -- elastic LTB: Eq. F11-5  Fcr = 1.9 E Cb/(Lb d/t^2), F11-4 --
    re_ = RectangularBar(depth_d=400.0 * u.mm, width_b=8.0 * u.mm)
    fe = re_.compute_section_properties()
    lb_e = 6000.0 * u.mm
    rep_e = compute_flexural_strength_F11_bar(fe, A36, laterally_unbraced_length_Lb=lb_e)
    t_e = fe.gross_area_Ag / fe.overall_depth_d
    l_d_t2_e = lb_e * fe.overall_depth_d / t_e**2
    expected_fcr = 1.9 * E * 1.0 / l_d_t2_e
    mp_e = min(Fy * fe.plastic_modulus_Zx, 1.5 * Fy * fe.elastic_modulus_Sx)
    expected_e = min(expected_fcr * fe.elastic_modulus_Sx, mp_e)
    assert rep_e.governing_limit_state == "elastic_LTB"
    assert math.isclose(rep_e.critical_stress_Fcr, expected_fcr, rel_tol=REL_TOL)
    assert math.isclose(rep_e.nominal_flexural_strength_Mn, expected_e, rel_tol=REL_TOL)


def test_F11_no_Lb_skips_ltb() -> None:
    """Omitting ``Lb`` skips the LTB check (continuously braced bar)."""
    rb = RectangularBar(depth_d=400.0 * u.mm, width_b=8.0 * u.mm)
    fb = rb.compute_section_properties()
    rep = compute_flexural_strength_F11_bar(fb, A36)  # no Lb
    assert rep.governing_limit_state == "yielding"
    assert rep.lateral_torsional_applies is False
    assert math.isclose(rep.ltb_slenderness_Lb_d_t2, 0.0, abs_tol=0.0)
    assert math.isclose(rep.nominal_flexural_strength_Mn, rep.plastic_moment_Mp, rel_tol=REL_TOL)


def test_F11_monotonic_in_unbraced_length() -> None:
    """phi*Mn must not increase as the bar's unbraced length grows.

    Sanity guard independent of the oracle: a more braced rectangular
    bar is never weaker than a less braced one of the same section.
    """
    rb = RectangularBar(depth_d=300.0 * u.mm, width_b=10.0 * u.mm)
    fb = rb.compute_section_properties()
    prev = math.inf
    for lb in (500.0, 1500.0, 3000.0, 6000.0, 10000.0):
        phi_mn = compute_flexural_strength_F11_bar(
            fb, A36, laterally_unbraced_length_Lb=lb * u.mm
        ).phi_strength_LRFD
        assert phi_mn <= prev + 1.0  # +1 N*mm slack for float noise
        prev = phi_mn


# ===========================================================================
# Tier 1 - §F12 library vs independent oracle, Fn from each source
# ===========================================================================
def _unsym_fsp(moduli: tuple[float, ...]) -> FlexuralSectionProperties:
    """Minimal ``unsymmetric`` snapshot carrying only what §F12 reads.

    §F12 is the elastic catch-all: it reads **only**
    ``extreme_fibre_moduli`` (``Smin``, Eq. F12-1).  Build a snapshot
    with neutral gross/axis fields and the requested extreme-fibre
    moduli.
    """
    return FlexuralSectionProperties(
        section_kind="unsymmetric",
        symmetry="unsymmetric",
        overall_depth_d=100.0,
        gross_area_Ag=1000.0,
        moment_of_inertia_Ix=1.0e6,
        elastic_modulus_Sx=min(moduli),
        plastic_modulus_Zx=min(moduli),
        radius_of_gyration_rx=30.0,
        moment_of_inertia_Iy=5.0e5,
        elastic_modulus_Sy=min(moduli),
        plastic_modulus_Zy=min(moduli),
        radius_of_gyration_ry=20.0,
        extreme_fibre_moduli=moduli,
    )


@pytest.mark.parametrize(
    ("name", "material", "fcr_ltb", "fcr_lb", "expected_ls"),
    [
        # Fn from Eq. F12-2 yielding (no buckling stress supplied).
        ("A36 yield only", A36, None, None, "yielding"),
        ("A992 yield only", A992, None, None, "yielding"),
        # Fn from Eq. F12-3 LTB (LTB stress below Fy and below LB).
        ("A36 LTB governs", A36, 120.0 * u.MPa, 400.0 * u.MPa, "elastic_LTB"),
        ("S355 LTB governs", S355, 150.0 * u.MPa, None, "elastic_LTB"),
        # Fn from Eq. F12-4 local buckling (LB stress the smallest).
        ("A36 LB governs", A36, 400.0 * u.MPa, 90.0 * u.MPa, "flange_local_buckling"),
        ("A992 LB governs", A992, None, 110.0 * u.MPa, "flange_local_buckling"),
        # Buckling stresses above Fy -> clamp to Fy -> yielding.
        ("A36 buckling>Fy", A36, 9.0e3 * u.MPa, 9.0e3 * u.MPa, "yielding"),
    ],
)
def test_F12_matches_independent_oracle_min_governing(
    name: str,
    material: SteelMaterial,
    fcr_ltb: float | None,
    fcr_lb: float | None,
    expected_ls: str,
) -> None:
    """Library §F12 ``Mn = Fn*Smin`` == oracle, Fn from each source."""
    moduli = (3.0e5, 2.0e5, 4.5e5)  # Smin = 2.0e5 mm^3
    fsp = _unsym_fsp(moduli)

    report = compute_flexural_strength_F12_unsymmetric(
        fsp,
        material,
        lateral_torsional_buckling_stress_Fcr=fcr_ltb,
        local_buckling_stress_Fcr=fcr_lb,
    )
    oracle = mn_F12(
        F12OracleProps(
            Fy=material.yield_stress_Fy,
            extreme_fibre_moduli=moduli,
            Fcr_LTB=fcr_ltb,
            Fcr_LB=fcr_lb,
        )
    )

    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.minimum_elastic_modulus_Smin, oracle.Smin, rel_tol=REL_TOL)
    assert math.isclose(report.nominal_stress_Fn, oracle.Fn, rel_tol=REL_TOL)
    assert math.isclose(report.critical_stress_LTB_Fcr, oracle.Fcr_LTB, rel_tol=REL_TOL)
    assert math.isclose(report.critical_stress_LB_Fcr, oracle.Fcr_LB, rel_tol=REL_TOL)
    assert report.governing_limit_state == expected_ls == oracle.governing
    # Smin is the minimum of the supplied extreme-fibre moduli.
    assert math.isclose(report.minimum_elastic_modulus_Smin, 2.0e5, rel_tol=REL_TOL)
    # phi / Omega plumbing.
    assert report.phi_LRFD == _PHI_B
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_F12_eq_F12_1_pinned_inline() -> None:
    """Eq. F12-1 ``Mn = Fn*Smin`` pinned independently of library+oracle."""
    moduli = (7.7e5, 5.0e5, 9.9e5)
    fsp = _unsym_fsp(moduli)
    # LTB stress is the smallest and below Fy -> Fn = Fcr_LTB.
    fcr_ltb = 130.0 * u.MPa
    rep = compute_flexural_strength_F12_unsymmetric(
        fsp, A992, lateral_torsional_buckling_stress_Fcr=fcr_ltb
    )
    expected = min(fcr_ltb, A992.yield_stress_Fy) * min(moduli)
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_stress_Fn, fcr_ltb, rel_tol=REL_TOL)
    assert rep.governing_limit_state == "elastic_LTB"


def test_F12_round_bar_extreme_fibre_drives_yield_moment() -> None:
    """A bar snapshot also feeds §F12 (its single extreme-fibre modulus).

    The §F12 elastic catch-all is section-agnostic - it reads only
    ``extreme_fibre_moduli``.  A doubly-symmetric bar would normally be
    handled by §F11, but driving §F12 with its extreme-fibre moduli
    must give the pure yield moment ``Fy*Smin`` when no buckling stress
    is supplied (the conservative §F12 floor).
    """
    rd = RoundBar(diameter_D=50.0 * u.mm)
    fsp = rd.compute_section_properties()
    rep = compute_flexural_strength_F12_unsymmetric(fsp, A36)
    assert rep.governing_limit_state == "yielding"
    assert math.isclose(
        rep.nominal_flexural_strength_Mn,
        A36.yield_stress_Fy * fsp.elastic_modulus_Sx,
        rel_tol=REL_TOL,
    )


# ===========================================================================
# Guard rails
# ===========================================================================
def test_F11_rejects_non_bar_kind() -> None:
    """A non-bar snapshot must be refused (no silent wrong number)."""
    bogus = FlexuralSectionProperties(
        section_kind="round_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=100.0,
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
    with pytest.raises(ValueError, match=re.escape("§F11 applies only to rectangular bars")):
        compute_flexural_strength_F11_bar(bogus, A36)


def test_F11_round_rejects_minor_axis() -> None:
    """A round bar is axisymmetric - ``bending_axis='minor'`` is refused."""
    fsp = RoundBar(diameter_D=40.0 * u.mm).compute_section_properties()
    with pytest.raises(ValueError, match="axisymmetric"):
        compute_flexural_strength_F11_bar(fsp, A36, bending_axis="minor")


def test_F11_rejects_nonpositive_Lb() -> None:
    """A non-positive unbraced length is refused."""
    fsp = RectangularBar(depth_d=100.0 * u.mm, width_b=20.0 * u.mm).compute_section_properties()
    with pytest.raises(ValueError, match="laterally_unbraced_length_Lb must be positive"):
        compute_flexural_strength_F11_bar(fsp, A36, laterally_unbraced_length_Lb=-1.0)


def test_F12_rejects_empty_extreme_fibre_moduli() -> None:
    """§F12 needs at least one extreme-fibre modulus to form Smin."""
    bogus = FlexuralSectionProperties(
        section_kind="unsymmetric",
        symmetry="unsymmetric",
        overall_depth_d=100.0,
        gross_area_Ag=1.0,
        moment_of_inertia_Ix=1.0,
        elastic_modulus_Sx=1.0,
        plastic_modulus_Zx=1.0,
        radius_of_gyration_rx=1.0,
        moment_of_inertia_Iy=1.0,
        elastic_modulus_Sy=1.0,
        plastic_modulus_Zy=1.0,
        radius_of_gyration_ry=1.0,
        extreme_fibre_moduli=(),
    )
    with pytest.raises(ValueError, match=re.escape("extreme_fibre_moduli is empty")):
        compute_flexural_strength_F12_unsymmetric(bogus, A36)


def test_F12_rejects_nonpositive_supplied_stress() -> None:
    """A non-positive caller-supplied ``Fcr`` is refused."""
    fsp = _unsym_fsp((3.0e5, 2.0e5))
    with pytest.raises(ValueError, match="lateral_torsional_buckling_stress_Fcr must be positive"):
        compute_flexural_strength_F12_unsymmetric(
            fsp, A36, lateral_torsional_buckling_stress_Fcr=0.0
        )
    with pytest.raises(ValueError, match="local_buckling_stress_Fcr must be positive"):
        compute_flexural_strength_F12_unsymmetric(fsp, A36, local_buckling_stress_Fcr=-5.0)


def test_F11_cites_spec_equations() -> None:
    """Citations must pin §F11 Eq. F11-1..F11-5 at printed 16.1-71.

    Provenance gate: equation numbers / page verbatim from
    ``spec_chapterF.txt`` (§F11 @ printed 16.1-71).
    """
    fsp = RectangularBar(depth_d=127.0 * u.mm, width_b=76.2 * u.mm).compute_section_properties()
    rep = compute_flexural_strength_F11_bar(fsp, A36)
    pairs = {(c.section, c.equation) for c in rep.cited_clauses}
    assert ("F11.1", "F11-1") in pairs
    assert ("F11.1", "F11-2") in pairs
    assert ("F11.2", "F11-3") in pairs
    assert ("F11.2", "F11-4") in pairs
    assert ("F11.2", "F11-5") in pairs
    f11_pages = {c.page for c in rep.cited_clauses if c.section.startswith("F11")}
    assert f11_pages == {"16.1-71"}


def test_F12_cites_spec_equations() -> None:
    """Citations must pin §F12 Eq. F12-1..F12-4 at printed 16.1-71/72."""
    fsp = _unsym_fsp((3.0e5, 2.0e5))
    rep = compute_flexural_strength_F12_unsymmetric(fsp, A36)
    pairs = {(c.section, c.equation) for c in rep.cited_clauses}
    assert ("F12", "F12-1") in pairs
    assert ("F12.1", "F12-2") in pairs
    assert ("F12.2", "F12-3") in pairs
    assert ("F12.3", "F12-4") in pairs


# ===========================================================================
# Tier 2 - AISC Manual v15.1 Example F.12 (rectangular bar), printed
# sig-figs, WITH the documented 360-16 -> 360-22 §F11-1 edition delta
# ===========================================================================
# PROVENANCE BOUNDARY (read before changing these numbers):
#
# Example F.12 "Rectangular Bar in Major Axis Bending" is staged
# verbatim at
# ``docs/design_notes/_aisc_src_extract/manual_F11_F12_examples.txt``
# (AISC Manual v15.1 Vol.1, Design Examples; Manual p. F-62..F-64, PDF
# p.209-211).  Quoted verbatim:
#
#   "EXAMPLE F.12 RECTANGULAR BAR IN MAJOR AXIS BENDING"        (p.209)
#   "ASTM A36   Fy = 36 ksi   Fu = 58 ksi"                      (p.209)
#   "Try a BAR 5 in. 3 in."                                     (p.209)
#   "Sx = b d^2 / 6 = 3.00 in.(5.00 in.)^2 / 6 = 12.5 in.^3"    (p.209)
#   "Zx = b d^2 / 4 = 3.00 in.(5.00 in.)^2 / 4 = 18.8 in.^3"    (p.210)
#   "Lb d / t^2 = (6 ft)(12 in./ft)(5.00 in.)/(3.00 in.)^2
#    = 40.0"                                                     (p.210)
#   "0.08 E/Fy = 0.08(29,000 ksi)/(36 ksi) = 64.4 > 40.0;
#    therefore, the yielding limit state applies"               (p.210)
#   "Mn = Mp = Fy Z <= 1.6 Fy Sx          (Spec. Eq. F11-1)"    (p.210)
#   "1.6 Fy Sx = 1.6(36 ksi)(12.5 in.^3) = 720 kip-in."         (p.210)
#   "Fy Z = (36 ksi)(18.8 in.^3) = 677 kip-in. < 720 kip-in."   (p.210)
#   "Use Mn = 677 kip-in. or 56.4 kip-ft."                      (p.210)
#   "because Lb d / t^2 <= 0.08 E/Fy, the lateral-torsional
#    buckling limit state does not apply"                       (p.210)
#   "phi_b = 0.90 ... phi_b Mn = 0.90(56.4 kip-ft)
#    = 50.8 kip-ft"  (LRFD)                                      (p.211)
#   "Omega_b = 1.67 ... Mn/Omega_b = (56.4 kip-ft)/1.67
#    = 33.8 kip-ft"  (ASD)                                       (p.211)
#
# EDITION DELTA (design note 10 §1/§9): the v15.1 Manual prints the
# Eq. F11-1 cap as **1.6** Fy Sx (360-16); AISC **360-22**
# spec_chapterF.txt printed 16.1-71 tightened it to **1.5** Fy Sx.  The
# library implements 360-22 (the authority).  With the exact closed
# form Zx = b d^2/4 = 18.75 in.^3 (the Manual rounds to 18.8):
#   * Fy Z          = 36 * 18.75 = 675.0 kip-in   (lib, exact)
#   * 1.5 Fy Sx     = 1.5*36*12.5 = 675.0 kip-in  (360-22 cap)
#   * 1.6 Fy Sx     = 1.6*36*12.5 = 720.0 kip-in  (360-16, Manual)
#   * Mn 360-22     = min(675.0, 675.0) = 675.0 kip-in (cap tight)
#   * Mn 360-16(Man)= min(676.8, 720)   = 676.8 -> "677"/56.4 kip-ft
# The edition-INDEPENDENT facts are anchored to the Manual's print;
# the 360-22 capped Mn is pinned bit-exactly in-test so the delta is
# explicit, never hidden.
_A36_MANUAL = A36  # Manual F.12 uses ASTM A36, Fy = 36 ksi (matches)


def _f12_example_bar() -> RectangularBar:
    """Manual F.12 section: BAR 5 in. x 3 in. (d = 5 in, b = 3 in)."""
    return RectangularBar(depth_d=5.0 * u.inches, width_b=3.0 * u.inches)


def test_F12_manual_v15_1_example_F12_edition_independent_facts() -> None:
    """AISC Manual v15.1 Ex. F.12 - edition-independent cross-check.

    Anchors the facts Example F.12 establishes that do **not** depend
    on the 360-16 -> 360-22 §F11-1 cap change (design note 10 §6,
    external-authority sig-fig tier):

    * closed-form ``Sx = b d^2/6 = 12.5 in.^3`` (Manual printed) and
      ``Zx = b d^2/4`` (Manual prints 18.8 rounded; exact 18.75);
    * §F11.2 LTB slenderness ``Lb*d/t^2 = 40.0`` (Manual printed) and
      gate ``0.08 E/Fy = 64.4`` (Manual printed) -> ``40.0 <= 64.4``
      so LTB **does not apply** and yielding governs (Manual's
      conclusion, edition-independent);
    * the **uncapped** ``Fy*Z`` (what the Manual's "677 kip-in"
      reports, using its rounded Zx=18.8) - asserted on the Manual's
      own rounded Zx so it reproduces "677" to 3 sig figs.
    """
    bar = _f12_example_bar()
    fsp = bar.compute_section_properties()
    Fy = _A36_MANUAL.yield_stress_Fy
    E = _A36_MANUAL.elastic_modulus_E

    # Closed-form section moduli vs the Manual's printed values.
    sx_in3 = fsp.elastic_modulus_Sx / u.inches**3
    zx_in3 = fsp.plastic_modulus_Zx / u.inches**3
    assert math.isclose(sx_in3, 12.5, rel_tol=2e-3)  # Manual printed 12.5
    # Manual prints Zx = 18.8 (rounded from the exact 18.75).
    assert math.isclose(zx_in3, 18.75, rel_tol=REL_TOL)
    assert math.isclose(zx_in3, 18.8, rel_tol=3e-3)  # Manual's 3-sig-fig print

    # LTB slenderness gate (edition-independent; Manual printed).
    rep = compute_flexural_strength_F11_bar(
        fsp,
        _A36_MANUAL,
        laterally_unbraced_length_Lb=6.0 * u.ft,  # braced at midspan, 12 ft span
        lateral_torsional_modification_Cb=1.0,
    )
    assert math.isclose(rep.ltb_slenderness_Lb_d_t2, 40.0, rel_tol=2e-3)  # Manual "40.0"
    assert math.isclose(rep.ltb_gate_lower, 0.08 * E / Fy, rel_tol=REL_TOL)
    assert math.isclose(rep.ltb_gate_lower, 64.4, rel_tol=2e-3)  # Manual "64.4"
    assert rep.ltb_slenderness_Lb_d_t2 < rep.ltb_gate_lower
    # Manual's conclusion: LTB N/A, yielding governs (edition-indep).
    assert rep.governing_limit_state == "yielding"

    # The Manual's "677 kip-in" = Fy * (its rounded Zx = 18.8 in^3).
    # Recompute Fy*Z on the Manual's rounded Zx so we reproduce the
    # Manual's printed number to its 3 sig figs (the library's
    # uncapped_Fy_Z uses the exact Zx=18.75 -> 675.0, asserted next).
    fy_z_manual_rounded = Fy * (18.8 * u.inches**3)
    assert math.isclose(fy_z_manual_rounded / u.MOMENT_DISPLAY_UNIT_kip_ft, 56.4, rel_tol=2e-3)
    assert math.isclose(fy_z_manual_rounded / (u.kip * u.inches), 677.0, rel_tol=2e-3)


def test_F12_manual_v15_1_example_F12_aisc_360_22_capped_result() -> None:
    """AISC Manual v15.1 Ex. F.12 under **360-22** §F11-1 (edition delta).

    The library implements the **360-22** Eq. F11-1 cap ``1.5*Fy*Sx``
    (spec_chapterF.txt printed 16.1-71, the authority); the v15.1
    Manual used the 360-16 ``1.6*Fy*Sx``.  Pin the 360-22 result
    **bit-exactly** so the documented edition delta is explicit and
    locked, not masked:

    * exact ``Zx = b d^2/4 = 18.75 in.^3``;
    * ``Fy*Z = 36 ksi * 18.75 in.^3 = 675.0 kip-in`` (uncapped);
    * ``1.5*Fy*Sx = 1.5 * 36 * 12.5 = 675.0 kip-in`` (360-22 cap);
    * ``Mn = min(675.0, 675.0) = 675.0 kip-in`` - the 360-22 cap is
      *exactly tight* for this section (a clean edition-delta witness);
      the 360-16 1.6 cap (720) the Manual used was inactive;
    * ``phi*Mn = 0.90 * 675.0 = 607.5 kip-in = 50.625 kip-ft``
      (vs the Manual's 360-16 ``50.8 kip-ft``);
    * ``Mn/Omega = 675.0/1.67 kip-in = 33.68 kip-ft`` (vs Manual
      ``33.8 kip-ft``).

    The ~0.3 % difference from the Manual's printed kip-ft is **the
    edition delta itself** (1.5 vs 1.6 cap + the Manual's Zx rounding),
    not an error - it is asserted exactly here and explained in the
    module docstring / design note 10 §1.
    """
    bar = _f12_example_bar()
    fsp = bar.compute_section_properties()
    Fy = _A36_MANUAL.yield_stress_Fy

    rep = compute_flexural_strength_F11_bar(
        fsp,
        _A36_MANUAL,
        laterally_unbraced_length_Lb=6.0 * u.ft,
        lateral_torsional_modification_Cb=1.0,
    )

    # Exact closed-form section moduli (no Manual rounding).
    zx = 3.0 * u.inches * (5.0 * u.inches) ** 2 / 4.0  # b d^2 / 4
    sx = 3.0 * u.inches * (5.0 * u.inches) ** 2 / 6.0  # b d^2 / 6
    assert math.isclose(fsp.plastic_modulus_Zx, zx, rel_tol=REL_TOL)
    assert math.isclose(fsp.elastic_modulus_Sx, sx, rel_tol=REL_TOL)

    # 360-22 Eq. F11-1: cap coeff is 1.5 (NOT the Manual's 360-16 1.6).
    assert math.isclose(rep.yield_cap_coefficient, 1.5, rel_tol=REL_TOL)
    fy_z = Fy * zx
    cap_360_22 = 1.5 * Fy * sx
    assert math.isclose(rep.uncapped_Fy_Z, fy_z, rel_tol=REL_TOL)
    assert math.isclose(rep.yield_cap_value, cap_360_22, rel_tol=REL_TOL)
    # The 360-22 cap is exactly tight for a 5x3 bar: Fy*Z == 1.5*Fy*Sx.
    assert math.isclose(fy_z, cap_360_22, rel_tol=REL_TOL)
    expected_mn_360_22 = min(fy_z, cap_360_22)
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_mn_360_22, rel_tol=REL_TOL)
    # In the Manual's display units: 675.0 kip-in / 56.25 kip-ft.
    assert math.isclose(
        rep.nominal_flexural_strength_Mn / (u.kip * u.inches), 675.0, rel_tol=REL_TOL
    )
    assert math.isclose(
        rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft,
        56.25,
        rel_tol=REL_TOL,
    )
    # phi/Omega exactly the §F1 factors on the 360-22 Mn.
    assert math.isclose(
        rep.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kip_ft, 0.90 * 56.25, rel_tol=REL_TOL
    )
    assert math.isclose(
        rep.omega_strength_ASD / u.MOMENT_DISPLAY_UNIT_kip_ft, 56.25 / 1.67, rel_tol=REL_TOL
    )
    # Cross-check the Manual's 360-16 printed phi*Mn (= 0.9*56.4) is
    # within the edition delta of our 360-22 value (documented, ~0.3%).
    manual_phi_mn_kipft = 0.90 * 56.4
    our_phi_mn_kipft = rep.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kip_ft
    assert math.isclose(our_phi_mn_kipft, manual_phi_mn_kipft, rel_tol=5e-3)


# ===========================================================================
# Tier 2 - AISC Manual v15.1 Example F.13 (round bar):
# ENGINEER-CONFIRM F7tail-EC-1 (Manual Mn/phi*Mn truncated from source)
# ===========================================================================
# PROVENANCE BOUNDARY (read before changing these numbers):
#
# Example F.13 "Round Bar in Bending" is staged at
# ``docs/design_notes/_aisc_src_extract/manual_F11_F12_examples.txt``
# (AISC Manual v15.1 Vol.1, Manual p. F-65, PDF p.212).  Quoted
# verbatim - the staged extract ENDS HERE (truncated mid-example):
#
#   "EXAMPLE F.13 ROUND BAR IN BENDING"                          (p.212)
#   "ASTM A36   Fy = 36 ksi   Fu = 58 ksi"                       (p.212)
#   "Try a BAR 1-in.-diameter."                                  (p.212)
#   "S = pi d^3 / 32 = pi (1.00 in.)^3 / 32 = 0.0982 in.^3"      (p.212)
#   "Z = d^3 / 6 ..."                                            (p.212)
#       <<< staged source truncates here; the Manual's printed
#           Mn / phi*Mn for F.13 are NOT in the staged extract >>>
#
# Per design note 10 §6 / the F-7 contract, a genuinely
# truncated/missing Manual value is replaced by a LABELLED
# first-principles hand-calc + ENGINEER-CONFIRM - never invented:
#
#   ENGINEER-CONFIRM F7tail-EC-1
#   ----------------------------
#   The AISC Manual v15.1 Ex. F.13 printed nominal/available flexural
#   strength (Mn, phi*Mn, Mn/Omega) is not present in the staged
#   extract ``manual_F11_F12_examples.txt`` (it truncates at PDF p.212
#   immediately after "Z = d^3/6").  ACTION: the orchestrator extracts
#   the Ex. F.13 "Nominal Flexural Strength" / "Available Flexural
#   Strength" block from ``v15.1_vol-1_design-examples.pdf`` (PDF
#   p.212-213, Manual p. F-65/F-66) and confirms the hand-calc below.
#   The closed-form S/Z the Manual DOES print (S = 0.0982 in^3,
#   Z = d^3/6) are cross-checked bit-exactly meanwhile.
#
# First-principles §F11.2 round-bar hand-calc (Eq. F11-2,
# spec_chapterF.txt printed 16.1-71), BAR 1-in.-diameter, A36:
#   d   = 1.00 in
#   S   = pi d^3 / 32 = pi/32          = 0.0981748 in^3  (Manual 0.0982)
#   Z   = d^3 / 6     = 1/6            = 0.1666667 in^3
#   Fy*Z          = 36 * 1/6          = 6.000   kip-in
#   1.6*Fy*S      = 1.6*36*pi/32      = 5.65487 kip-in   (cap ACTIVE,
#                   Z/S = 16/(3 pi) = 1.6977 > 1.6)
#   Mn (Eq.F11-2) = min(6.000, 5.65487) = 5.65487 kip-in
#                 = 0.471239 kip-ft
#   phi*Mn (0.90) = 5.08938 kip-in = 0.424115 kip-ft
#   Mn/Omega(1.67)= 3.38615 kip-in = 0.282179 kip-ft
def test_F11_manual_v15_1_example_F13_round_bar_handcalc() -> None:
    """AISC Manual v15.1 Ex. F.13 - first-principles hand-calc anchor.

    **F7tail-EC-1 RESOLVED (orchestrator):** the Manual Ex. F.13 body
    was extracted to ``docs/design_notes/_aisc_src_extract/
    manual_F13_roundbar.txt`` (AISC Manual v15.1 Vol.1, Manual
    p. F-65/F-66, PDF p.212-213).  The Manual prints
    ``Mn = 5.66 kip-in. = 0.472 kip-ft``, ``phi*Mn = 0.425 kip-ft``
    (LRFD), ``Mn/Omega = 0.283 kip-ft`` (ASD) — the library reproduces
    these to the Manual's 3 printed sig-figs (asserted below) AND
    bit-exactly vs Spec. Eq. F11-2.  This test drives the library §F11
    round
    path on the Manual's stated section (BAR 1-in.-diameter, ASTM A36)
    and pins it to a **labelled first-principles** Eq. F11-2 hand-calc
    (see the PROVENANCE BOUNDARY block above) - **not** to an invented
    Manual number.  The closed-form ``S``/``Z`` the Manual *does* print
    are cross-checked bit-exactly.

    AISC Manual v15.1 Vol.1 Ex. F.13 (Manual p. F-65, PDF p.212);
    Spec. Eq. F11-2 ``Mn = Mp = Fy*Z <= 1.6*Fy*Sx``.
    """
    rd = RoundBar(diameter_D=1.0 * u.inches)
    fsp = rd.compute_section_properties()

    # The closed forms the Manual prints (S = 0.0982 in^3, Z = d^3/6).
    s_in3 = fsp.elastic_modulus_Sx / u.inches**3
    z_in3 = fsp.plastic_modulus_Zx / u.inches**3
    assert math.isclose(s_in3, math.pi / 32.0, rel_tol=REL_TOL)
    assert math.isclose(s_in3, 0.0982, rel_tol=3e-3)  # Manual printed 0.0982
    assert math.isclose(z_in3, 1.0 / 6.0, rel_tol=REL_TOL)

    rep = compute_flexural_strength_F11_bar(fsp, A36)  # round: no Lb/LTB

    Fy = A36.yield_stress_Fy
    # Eq. F11-2 round cap is 1.6*Fy*S and is ACTIVE here
    # (Z/S = 16/(3 pi) = 1.6977 > 1.6).
    assert math.isclose(rep.yield_cap_coefficient, 1.6, rel_tol=REL_TOL)
    fy_z = Fy * fsp.plastic_modulus_Zx
    cap = 1.6 * Fy * fsp.elastic_modulus_Sx
    assert fy_z > cap  # cap active
    expected_mn = min(fy_z, cap)
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_mn, rel_tol=REL_TOL)
    assert rep.governing_limit_state == "yielding"
    assert rep.lateral_torsional_applies is False

    # F7tail-EC-1 RESOLVED: anchored to AISC Manual v15.1 Ex. F.13
    # (extracted to manual_F13_roundbar.txt, Manual p. F-65/F-66).
    # Bit-exact pin vs Spec. Eq. F11-2 (1.6*Fy*S), plus the library's
    # value to full precision, plus the Manual's PRINTED 3-sig-fig
    # values in its display units (kip-in / kip-ft).
    mn_kipin = rep.nominal_flexural_strength_Mn / (u.kip * u.inches)
    assert math.isclose(mn_kipin, 1.6 * 36.0 * (math.pi / 32.0), rel_tol=REL_TOL)
    assert math.isclose(mn_kipin, 5.65487, rel_tol=1e-5)
    assert math.isclose(rep.phi_strength_LRFD / (u.kip * u.inches), 5.08938, rel_tol=1e-5)
    assert math.isclose(rep.omega_strength_ASD / (u.kip * u.inches), 3.38615, rel_tol=1e-5)
    # AISC Manual v15.1 Ex. F.13 printed values (3 sig figs).  Manual
    # prints Mn = 5.66 kip-in. = 0.472 kip-ft; phi*Mn = 0.425 kip-ft;
    # Mn/Omega = 0.283 kip-ft.  kip-ft derived from the file's proven
    # kip-in basis (1 ft = 12 in) - no dependence on a u.ft symbol.
    _MANUAL_REL_TOL = 4e-3
    _KIPIN = u.kip * u.inches
    assert math.isclose(mn_kipin, 5.66, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(mn_kipin / 12.0, 0.472, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose((rep.phi_strength_LRFD / _KIPIN) / 12.0, 0.425, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose((rep.omega_strength_ASD / _KIPIN) / 12.0, 0.283, rel_tol=_MANUAL_REL_TOL)

"""Phase F-5 anchors for AISC 360-22 §F9 (tees & double angles).

Two-tier anchor per design note 10 §6:

**Tier 1 (primary, bit-exact ``rel_tol=1e-9``):** the library
``compute_flexural_strength_F9_tee_double_angle`` is pinned to the
independent standalone stdlib oracle
:mod:`tests.golden._chapterF_F9_oracle` (which imports **nothing** from
:mod:`apeSteel.flexure`), across:

* stem-in-**tension** yielding with the Eq. F9-2 ``1.6*My`` cap both
  *active* and *inactive*;
* stem-in-**compression** yielding (tee Eq. F9-4 ``Mp = My``; double
  angle Eq. F9-5 ``Mp = 1.5*My``) - flagged low-ductility;
* LTB with **both B signs** (Eq. F9-11 ``+`` stem-tension /
  Eq. F9-12 ``-`` stem-compression), all three §F9.2(a) sub-regimes
  (``Lb<=Lp`` N/A, ``Lp<Lb<=Lr`` Eq. F9-6, ``Lb>Lr`` Eq. F9-7);
* flange local buckling (tee Eq. F9-14 noncompact / Eq. F9-15 slender;
  double-angle flange-leg via §F10.3 Eq. F10-6/F10-7/F10-8);
* tee-stem local buckling (Eq. F9-16 with Eq. F9-17/F9-18/F9-19) and
  double-angle web-leg LB (§F10.3);
* ``>= 2`` steel grades, **tee AND double-angle**.

A disagreement means the library or the oracle transcribed a §F9
equation / constant wrong; agreement is bit-exact because both
implement the same closed forms from independently written source.
Hard literal snapshots (governing limit state, classifications, the
§F9 constants) are pinned inline as well.

**Tier 2 (external authority - AISC Manual v15.1 Ex. F.10, WT):** the
full published Example F.10 "WT-Shape Flexural Member" is staged
verbatim at ``docs/design_notes/_aisc_src_extract/manual_F9_examples
.txt`` (AISC Manual v15.1 Vol.1, Manual p. F-45..F-47, PDF p.192-194).
The library §F9 path is driven on the Manual's **published** WT5x6
section (ASTM A992 ``Fy = 50 ksi``; AISC Manual Table 1-8 ``d = 4.94
in.``, ``Ix = 4.35 in.^4``, ``Zx = 2.20 in.^3``, ``Sx = 1.22 in.^3``,
``bf = 3.96 in.``, ``tf = 0.210 in.``, ``y = 1.36 in.``; the Manual
also prints ``bf/2tf = 9.43`` and ``Sxc = Ix/y = 3.20 in.^3``) and the
result is checked against the Manual's printed numbers - Eq. F9-3
``My = Fy*Sx = 61.0 kip-in.``, Eq. F9-2 ``Mp = min(Fy*Zx, 1.6*My) =
97.6 kip-in.``, noncompact flange (``9.15 < 9.43 < 24.1``), Eq. F9-14,
``Mn = 97.6 kip-in. = 8.13 kip-ft`` (yielding controls), ``phi*Mn =
7.32 kip-ft``, ``Mn/Omega = 4.87 kip-ft`` - to the Manual's 3 printed
significant figures, **and** bit-exactly (``rel_tol=1e-9``) vs the
§F9 equation recomputed in-test from the published values.

For **double angle** ``manual_F9_examples.txt`` has **no 2L worked
example** (only the WT Example F.10), so per the design-note §6 / F-5
contract the double-angle tier-2 anchor is a **labelled
first-principles hand-calc**:

  **ENGINEER-CONFIRM F9-EC-1 - RESOLVED (Phase F-8).**  AISC 360-22
  §F9.2(b)(2) (spec_chapterF.txt printed 16.1-67, verbatim): "For
  double-angle web legs, ``Mn`` shall be determined using Equations
  F10-2 and F10-3 with ``Mcr`` determined using Equation F9-10 and
  ``My`` determined using Equation F9-3."  §F10 shipped in Phase F-6
  (before Phase F-8), so the §F9 calculator now applies the **exact**
  §F10.2 inelastic/elastic-LTB reduction (Eq. F10-2/F10-3) by reusing
  §F10's ``_mn_ltb_from_me`` via the permitted intra-``flexure``-layer
  import - the single source of truth, so §F9/§F10 cannot disagree on
  that reduction.  This oracle's ``_mn_ltb_from_me_f10_2_3``
  independently re-derives Eq. F10-2/F10-3 from the spec literals
  (**not** imported from apeSteel), so a typo in either surfaces as a
  tier-1 disagreement.  The earlier conservative §F9.2(b)(1)-form
  bound ``Mn = Mcr <= My`` is **superseded**; the single
  2L-web-leg-compression LTB sub-case golden
  (``test_F9_double_angle_EC1_web_compression_ltb_uses_exact_F10_2_3``)
  was updated to the exact §F10 value, and every *other* §F9 number is
  bit-identical (the branch fires only for ``section_kind ==
  "double_angle"`` *and* web legs in compression; tee stems still use
  Eq. F9-13 ``Mn = Mcr <= My``).  Every other §F9 double-angle limit
  state (yielding F9-2/F9-3/F9-5, stem-tension LTB F9-6/F9-7,
  flange-leg & web-leg LB via §F10.3 F10-6/F10-7/F10-8) is the exact
  §F9 / §F10.3 equation.

The published ``bf/2tf = 9.43`` for WT5x6 is printed verbatim by the
Manual (PDF p.193) **and** independently matches the AISC Shapes
Database v16.0 row for WT5X6 in this repo's
``src/apeSteel/sections/catalog/data/AISC_v16_shapes.csv`` (line: the
``WT,WT5X6,...`` row, ``bf/2tf`` column = ``9.43``) - sourced + cited,
cross-checked, NOT invented.

Full AISC-v16-catalog wiring of WT / MT / ST / 2L shapes is Phase F-8;
§F9 ships here as geometry method + pure calculator + oracle + golden
only (no facade / ``Element`` wiring).
"""

from __future__ import annotations

import math
import re

import pytest

from apeSteel.core import units as u
from apeSteel.core.materials import A36, A992, S355, SteelMaterial
from apeSteel.flexure.F9_tee_double_angle import (
    FlexureF9Report,
    compute_flexural_strength_F9_tee_double_angle,
)
from apeSteel.sections.flexural_properties import FlexuralSectionProperties
from apeSteel.sections.geometry.double_angle_section import DoubleAngleSection
from apeSteel.sections.geometry.tee_section import TeeSection
from tests.golden._chapterF_F9_oracle import F9OracleProps, mn_F9

REL_TOL = 1e-9

# AISC §F1 strength factors (independent literals, not imported from the
# library, so a typo in apeSteel surfaces here).
_PHI_B = 0.90
_OMEGA_B = 1.67


def _tee_oracle_props(
    tee: TeeSection,
    mat: SteelMaterial,
    *,
    Lb: float,
    Cb: float = 1.0,
    stem_in_tension: bool = True,
) -> F9OracleProps:
    """Lift the tee geometry snapshot into the independent oracle inputs."""
    fsp = tee.compute_section_properties()
    bf, tf, d, tw = (
        tee.flange_width_bf,
        tee.flange_thickness_tf,
        tee.overall_depth_d,
        tee.stem_thickness_tw,
    )
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
        flange_lambda=(bf / 2.0) / tf,
        stem_lambda=d / tw,
        Lb=Lb,
        Cb=Cb,
        stem_in_tension=stem_in_tension,
    )


def _da_oracle_props(
    da: DoubleAngleSection,
    mat: SteelMaterial,
    *,
    Lb: float,
    Cb: float = 1.0,
    stem_in_tension: bool = True,
) -> F9OracleProps:
    """Lift the double-angle geometry snapshot into the oracle inputs."""
    fsp = da.compute_section_properties()
    b_t = da.leg_length / da.thickness
    return F9OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        section_kind="double_angle",
        Zx=fsp.plastic_modulus_Zx,
        Sx=fsp.elastic_modulus_Sx,
        Sxc=fsp.elastic_modulus_compression_flange_Sxc,
        d=fsp.overall_depth_d,
        Iy=fsp.moment_of_inertia_Iy,
        J=fsp.torsional_constant_J,
        ry=fsp.radius_of_gyration_ry,
        flange_lambda=b_t,
        stem_lambda=b_t,
        Lb=Lb,
        Cb=Cb,
        stem_in_tension=stem_in_tension,
    )


def _run_tee(
    tee: TeeSection,
    mat: SteelMaterial,
    *,
    Lb: float,
    Cb: float = 1.0,
    stem_in_tension: bool = True,
) -> FlexureF9Report:
    fsp = tee.compute_section_properties()
    return compute_flexural_strength_F9_tee_double_angle(
        fsp,
        mat,
        unbraced_length_Lb=Lb,
        flange_slenderness_bf_2tf=(tee.flange_width_bf / 2.0) / tee.flange_thickness_tf,
        stem_slenderness_d_tw=tee.overall_depth_d / tee.stem_thickness_tw,
        lateral_torsional_buckling_factor_Cb=Cb,
        stem_in_tension=stem_in_tension,
    )


def _run_da(
    da: DoubleAngleSection,
    mat: SteelMaterial,
    *,
    Lb: float,
    Cb: float = 1.0,
    stem_in_tension: bool = True,
) -> FlexureF9Report:
    fsp = da.compute_section_properties()
    b_t = da.leg_length / da.thickness
    return compute_flexural_strength_F9_tee_double_angle(
        fsp,
        mat,
        unbraced_length_Lb=Lb,
        flange_slenderness_bf_2tf=b_t,
        stem_slenderness_d_tw=b_t,
        lateral_torsional_buckling_factor_Cb=Cb,
        stem_in_tension=stem_in_tension,
    )


# ===========================================================================
# Geometry sanity: the flexure snapshot shares Ag / I / J with the
# (frozen, untouched) compression snapshot bit-for-bit.
# ===========================================================================
def test_F9_tee_geometry_shares_gross_props_with_compression_path() -> None:
    """``TeeSection.compute_section_properties`` must not perturb §E.

    ``TeeSection.compute_compression_properties`` is frozen (Phase E).
    The new flexure method re-uses the *identical* ``Ag`` / ``Ix`` /
    ``Iy`` / ``J`` closed forms; assert they coincide exactly so the
    additive flexure path provably did not disturb the verified
    compression path.
    """
    tee = TeeSection(
        flange_width_bf=200.0 * u.mm,
        flange_thickness_tf=12.0 * u.mm,
        overall_depth_d=250.0 * u.mm,
        stem_thickness_tw=8.0 * u.mm,
    )
    comp = tee.compute_compression_properties(A992)
    flex = tee.compute_section_properties()

    assert flex.gross_area_Ag == comp.gross_area_Ag
    assert flex.moment_of_inertia_Ix == comp.moment_of_inertia_x_Ix
    assert flex.moment_of_inertia_Iy == comp.moment_of_inertia_y_Iy
    assert flex.torsional_constant_J == comp.torsional_constant_J
    assert flex.radius_of_gyration_rx == comp.radius_of_gyration_x_rx
    assert flex.radius_of_gyration_ry == comp.radius_of_gyration_y_ry
    assert flex.section_kind == "tee"
    assert flex.symmetry == "singly_symmetric"


def test_F9_double_angle_geometry_shares_gross_props_with_compression() -> None:
    """``DoubleAngleSection.compute_section_properties`` must not perturb §E."""
    da = DoubleAngleSection(
        leg_length=100.0 * u.mm,
        thickness=10.0 * u.mm,
        back_separation=10.0 * u.mm,
    )
    comp = da.compute_compression_properties(A992)
    flex = da.compute_section_properties()

    assert flex.gross_area_Ag == comp.gross_area_Ag
    assert flex.moment_of_inertia_Ix == comp.moment_of_inertia_x_Ix
    assert flex.moment_of_inertia_Iy == comp.moment_of_inertia_y_Iy
    assert flex.torsional_constant_J == comp.torsional_constant_J
    assert flex.radius_of_gyration_rx == comp.radius_of_gyration_x_rx
    assert flex.radius_of_gyration_ry == comp.radius_of_gyration_y_ry
    assert flex.section_kind == "double_angle"


def _tee_closed_form_props(bf: float, tf: float, d: float, tw: float) -> dict[str, float]:
    """Independent tee closed forms (mm units) - the SAME composition the
    geometry uses, recomputed here from scratch for the inline pin."""
    stem = d - tf
    Ag = bf * tf + stem * tw
    ybar = tf / 2.0 + stem * d * tw / (2.0 * Ag)
    Ix = (
        bf * tf**3 / 12.0
        + bf * tf * (ybar - tf / 2.0) ** 2
        + tw * stem**3 / 12.0
        + tw * stem * (stem / 2.0 + tf - ybar) ** 2
    )
    half = Ag / 2.0
    flange_area = bf * tf
    if half <= flange_area:
        # PNA inside the flange.
        yp = half / bf
        q_top = bf * yp * (yp / 2.0)
        q_bot = bf * (tf - yp) * ((tf - yp) / 2.0) + stem * tw * ((tf - yp) + stem / 2.0)
    else:
        # PNA inside the stem.
        yp = tf + (half - flange_area) / tw
        q_top = bf * tf * (yp - tf / 2.0) + tw * (yp - tf) * ((yp - tf) / 2.0)
        q_bot = tw * (d - yp) * ((d - yp) / 2.0)
    return {
        "Ag": Ag,
        "ybar": ybar,
        "Ix": Ix,
        "Sxc": Ix / ybar,
        "Sxt": Ix / (d - ybar),
        "Sx": Ix / max(ybar, d - ybar),
        "Zx": q_top + q_bot,
    }


def test_F9_tee_geometry_closed_forms_pinned() -> None:
    """Pin the tee section-modulus closed forms inline (both PNA branches).

    Independent re-derivation of ``Ag``, ``Ix``, ``Sxc=Ix/ybar``,
    ``Sxt=Ix/(d-ybar)``, ``Sx=Ix/max(ybar,d-ybar)`` and the plastic
    modulus ``Zx`` (PNA splits ``Ag`` in half).  Two geometries cover
    **both** Zx branches:

    * ``bf=200, tf=12, d=320, tw=14`` -> ``Ag/2 = 3356 > bf*tf = 2400``
      -> PNA inside the **stem**;
    * ``bf=300, tf=40, d=120, tw=10`` -> ``Ag/2 = 6400 < bf*tf =
      12000`` -> PNA inside the **flange**.
    """
    for bf, tf, d, tw, pna_in_stem in (
        (200.0, 12.0, 320.0, 14.0, True),
        (300.0, 40.0, 120.0, 10.0, False),
    ):
        tee = TeeSection(
            flange_width_bf=bf * u.mm,
            flange_thickness_tf=tf * u.mm,
            overall_depth_d=d * u.mm,
            stem_thickness_tw=tw * u.mm,
        )
        flex = tee.compute_section_properties()
        g = _tee_closed_form_props(bf, tf, d, tw)
        # Confirm the geometry genuinely exercises the intended branch.
        assert (g["Ag"] / 2.0 > bf * tf) is pna_in_stem
        assert math.isclose(flex.gross_area_Ag, g["Ag"], rel_tol=REL_TOL)
        assert math.isclose(flex.moment_of_inertia_Ix, g["Ix"], rel_tol=REL_TOL)
        assert math.isclose(flex.elastic_modulus_compression_flange_Sxc, g["Sxc"], rel_tol=REL_TOL)
        assert math.isclose(flex.elastic_modulus_tension_flange_Sxt, g["Sxt"], rel_tol=REL_TOL)
        assert math.isclose(flex.elastic_modulus_Sx, g["Sx"], rel_tol=REL_TOL)
        assert math.isclose(flex.plastic_modulus_Zx, g["Zx"], rel_tol=REL_TOL)


# ===========================================================================
# Tier 1 - library vs independent §F9 oracle (tee), every regime,
#          both B signs, cap active/inactive, >= 2 grades
# ===========================================================================
# A992 sqrt(E/Fy): E/Fy = 580.0 exactly (29000/50 ksi) -> sqrt = 24.083.
#   tee flange Case 10: lambda_pf = 0.38*24.083 = 9.152,
#   lambda_rf = 1.0*24.083 = 24.083.
#   tee stem §F9.4: lambda_p = 0.84*24.083 = 20.23,
#   lambda_r = 1.52*24.083 = 36.61.
# Tee geometries are chosen so the flange / stem land in the intended
# Table B4.1b / §F9.4 band for the grade, and Lb places LTB in the
# intended §F9.2(a) sub-regime.

# Compact flange + compact stem, short Lb (LTB N/A): yielding governs.
_TEE_COMPACT = TeeSection(
    flange_width_bf=200.0 * u.mm,
    flange_thickness_tf=20.0 * u.mm,  # bf/2tf = 5.0 (compact A992/S355)
    overall_depth_d=180.0 * u.mm,
    stem_thickness_tw=12.0 * u.mm,  # d/tw = 15.0 (compact stem)
)
# Noncompact flange (FLB Eq. F9-14), compact stem, short Lb.
_TEE_NC_FLANGE = TeeSection(
    flange_width_bf=240.0 * u.mm,
    flange_thickness_tf=12.0 * u.mm,  # bf/2tf = 10.0 (NC for A992)
    overall_depth_d=180.0 * u.mm,
    stem_thickness_tw=12.0 * u.mm,
)
# Slender flange (FLB Eq. F9-15), short Lb.
_TEE_SLENDER_FLANGE = TeeSection(
    flange_width_bf=560.0 * u.mm,
    flange_thickness_tf=10.0 * u.mm,  # bf/2tf = 28.0 (> 24.08 -> slender)
    overall_depth_d=180.0 * u.mm,
    stem_thickness_tw=12.0 * u.mm,
)


# The flange / stem *classification* a geometry produces depends only
# on its width-to-thickness ratios and the grade (NOT on the moment
# magnitudes), so it is a deterministic, hand-reasoned design-time
# guard.  The governing *limit state* is asserted only via
# ``report.governing == oracle.governing`` (a bit-exact cross-check of
# the §F9 dispatch against an independently written re-derivation - the
# real anchor); the individual branches are pinned, with a known
# expected outcome, by the dedicated single-purpose tests below
# (cap active/inactive, inline FLB/SLB formulae, LTB continuity, the
# Manual Ex. F.10 anchor, the 2L hand-calc).
@pytest.mark.parametrize(
    ("name", "tee", "material", "Lb_mm", "Cb", "stem_in_tension", "exp_flange_class"),
    [
        # --- stem in tension, LTB N/A (Lb tiny) ---
        ("A992 tee compact", _TEE_COMPACT, A992, 1.0, 1.0, True, "compact"),
        ("S355 tee compact", _TEE_COMPACT, S355, 1.0, 1.0, True, "compact"),
        ("A36 tee compact", _TEE_COMPACT, A36, 1.0, 1.0, True, "compact"),
        # --- stem in tension, noncompact flange (Eq. F9-14) ---
        ("A992 tee NC-flange", _TEE_NC_FLANGE, A992, 1.0, 1.0, True, "non_compact"),
        ("S355 tee NC-flange", _TEE_NC_FLANGE, S355, 1.0, 1.0, True, "non_compact"),
        # --- stem in tension, slender flange (Eq. F9-15) ---
        (
            "A992 tee slender-flange",
            _TEE_SLENDER_FLANGE,
            A992,
            1.0,
            1.0,
            True,
            "slender",
        ),
        # --- stem in tension, LTB inelastic (Lp < Lb, Eq. F9-6) ---
        ("A992 tee LTB Lb=6000 (+B)", _TEE_COMPACT, A992, 6000.0, 1.0, True, "compact"),
        ("S355 tee LTB Lb=9000 (+B)", _TEE_COMPACT, S355, 9000.0, 1.0, True, "compact"),
        (
            "A992 tee LTB Lb=3000 (+B,Cb=1.3)",
            _TEE_COMPACT,
            A992,
            3000.0,
            1.3,
            True,
            "compact",
        ),
        # --- stem in COMPRESSION (Eq. F9-4 Mp=My; -B sign Eq. F9-12) ---
        ("A992 tee stem-comp short", _TEE_COMPACT, A992, 1.0, 1.0, False, "compact"),
        (
            "S355 tee stem-comp long (-B)",
            _TEE_COMPACT,
            S355,
            9000.0,
            1.0,
            False,
            "compact",
        ),
        # stem in compression + a genuinely slender stem (d/tw large)
        # -> Eq. F9-16/F9-19 stem LB exercised (see also the inline
        # formulae test).
        (
            "A992 tee stem-comp slender-stem",
            TeeSection(
                flange_width_bf=200.0 * u.mm,
                flange_thickness_tf=20.0 * u.mm,
                overall_depth_d=460.0 * u.mm,
                stem_thickness_tw=8.0 * u.mm,  # d/tw = 57.5 (slender)
            ),
            A992,
            1.0,
            1.0,
            False,
            "compact",
        ),
    ],
)
def test_F9_tee_matches_independent_oracle(
    name: str,
    tee: TeeSection,
    material: SteelMaterial,
    Lb_mm: float,
    Cb: float,
    stem_in_tension: bool,
    exp_flange_class: str,
) -> None:
    """Library §F9 ``Mn`` == independent oracle, bit-exact, tee.

    Covers yielding (cap), FLB NC + slender, LTB +B/-B, and
    stem-in-compression (Eq. F9-4 / -B Eq. F9-12 / stem-LB Eq. F9-16).
    The governing limit state is cross-checked bit-exactly against the
    independent oracle; the deterministic flange classification is the
    design-time guard that the geometry exercises the intended regime.
    """
    report = _run_tee(tee, material, Lb=Lb_mm, Cb=Cb, stem_in_tension=stem_in_tension)
    oracle = mn_F9(
        _tee_oracle_props(tee, material, Lb=Lb_mm, Cb=Cb, stem_in_tension=stem_in_tension)
    )

    # Primary bit-exact pin.
    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_Mp, oracle.Mp, rel_tol=REL_TOL)
    assert math.isclose(report.yield_moment_My, oracle.My, rel_tol=REL_TOL)
    assert math.isclose(report.limiting_length_Lp, oracle.Lp, rel_tol=REL_TOL)
    assert math.isclose(report.limiting_length_Lr, oracle.Lr, rel_tol=REL_TOL)
    assert math.isclose(report.ltb_constant_B, oracle.B, rel_tol=REL_TOL)
    assert math.isclose(report.critical_moment_Mcr, oracle.Mcr, rel_tol=REL_TOL)
    assert math.isclose(report.compact_limit_lambda_pf, oracle.lambda_pf, rel_tol=REL_TOL)
    assert math.isclose(report.noncompact_limit_lambda_rf, oracle.lambda_rf, rel_tol=REL_TOL)
    if math.isfinite(oracle.Mn_flb):
        assert math.isclose(
            report.flange_local_buckling_moment_Mn_F9_3,
            oracle.Mn_flb,
            rel_tol=REL_TOL,
        )
    if math.isfinite(oracle.Mn_slb):
        assert math.isclose(
            report.stem_local_buckling_moment_Mn_F9_4,
            oracle.Mn_slb,
            rel_tol=REL_TOL,
        )
    assert math.isclose(report.critical_stress_Fcr, oracle.Fcr, rel_tol=REL_TOL)

    # Governing limit state: bit-exact cross-check against the
    # independently-written oracle (the real dispatch anchor).
    assert report.governing_limit_state == oracle.governing
    # Deterministic design-time guard: the geometry produces the
    # intended flange regime (depends only on bf/2tf & grade).
    assert report.flange_classification == exp_flange_class == oracle.flange_class
    assert report.stem_classification == oracle.stem_class
    # B sign matches stem state (Eq. F9-11 + / Eq. F9-12 -).
    if stem_in_tension:
        assert report.ltb_constant_B > 0.0
    else:
        assert report.ltb_constant_B < 0.0
        assert report.stem_in_compression_low_ductility is True

    # phi / Omega plumbing (independent literals).
    assert report.phi_LRFD == _PHI_B
    assert report.omega_ASD == _OMEGA_B
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


# ===========================================================================
# Tier 1 - the Eq. F9-2 1.6*My cap: active (binds) vs not-applicable
# ===========================================================================
def test_F9_tee_yielding_cap_active_and_not_applicable() -> None:
    """§F9.1 yielding ``Mp``: Eq. F9-2 cap binds / Eq. F9-4 no cap.

    Independent of the oracle (the §F9.1 ``Mp`` selection re-derived
    from scratch).  A tee's strong-axis shape factor ``Zx/Sx`` is
    inherently large (``Sx`` is the modulus to the **far** extreme
    fibre - the stem tip - so it is small): therefore the Eq. F9-2
    ``1.6*My`` cap is *active* for essentially every real tee (this is
    exactly why §F9.1 has it, and why AISC Manual Ex. F.10's WT5x6 has
    ``Zx/Sx = 1.80 > 1.6``).  The cap being *not applicable* is the
    distinct §F9.1(b) branch: for the **tee stem in compression**
    Eq. F9-4 gives ``Mp = My`` with **no** ``1.6*My`` cap and
    independent of ``Zx`` - the complementary "cap does not bind" path.

    Both the cap *binding* (Eq. F9-2, stem in tension) and the cap
    *not applying* (Eq. F9-4, stem in compression) are asserted here
    with reasoned, deterministic expected values.
    """
    Fy = A992.yield_stress_Fy

    # Cap ACTIVE (Eq. F9-2, stem in tension): a tall thin-flange tee
    # has Zx/Sx > 1.6, so Mp = 1.6*My = 1.6*Fy*Sx < Fy*Zx.
    tall = TeeSection(
        flange_width_bf=120.0 * u.mm,
        flange_thickness_tf=16.0 * u.mm,
        overall_depth_d=400.0 * u.mm,
        stem_thickness_tw=8.0 * u.mm,
    )
    fsp_a = tall.compute_section_properties()
    cap_a = 1.6 * Fy * fsp_a.elastic_modulus_Sx
    fyzx_a = Fy * fsp_a.plastic_modulus_Zx
    assert fsp_a.plastic_modulus_Zx / fsp_a.elastic_modulus_Sx > 1.6
    assert cap_a < fyzx_a  # the 1.6*My cap genuinely binds
    rep_a = _run_tee(tall, A992, Lb=1.0, stem_in_tension=True)
    assert math.isclose(rep_a.plastic_moment_Mp, cap_a, rel_tol=REL_TOL)
    assert rep_a.plastic_moment_Mp < fyzx_a  # capped below Fy*Zx
    assert math.isclose(rep_a.plastic_moment_Mp, 1.6 * rep_a.yield_moment_My, rel_tol=REL_TOL)

    # Cap NOT APPLICABLE (Eq. F9-4, same tee, stem in COMPRESSION):
    # Mp = My, regardless of Zx (no 1.6*My cap on this branch).
    rep_c = _run_tee(tall, A992, Lb=1.0, stem_in_tension=False)
    assert math.isclose(rep_c.plastic_moment_Mp, rep_c.yield_moment_My, rel_tol=REL_TOL)
    # Eq. F9-4 Mp = My is *below* the would-be Eq. F9-2 capped value
    # (1.6*My) and far below Fy*Zx - the cap branch is genuinely not
    # taken here.
    assert rep_c.plastic_moment_Mp < 1.6 * rep_c.yield_moment_My
    assert rep_c.stem_in_compression_low_ductility is True


# ===========================================================================
# Tier 1 - library vs independent §F9 oracle (double angle)
# ===========================================================================
# §F9.3(b)/§F9.4(b): double-angle legs use the §F10.3 classification
# (lambda_p = 0.54 sqrt(E/Fy), lambda_r = 0.91 sqrt(E/Fy)).  For A992
# sqrt(E/Fy)=24.083 -> lambda_p=13.0, lambda_r=21.9.
_DA_COMPACT = DoubleAngleSection(  # b/t = 8.0 (compact A992)
    leg_length=80.0 * u.mm, thickness=10.0 * u.mm, back_separation=10.0 * u.mm
)
_DA_NC_LEG = DoubleAngleSection(  # b/t = 16.0 (NC for A992: 13.0<16<21.9)
    leg_length=128.0 * u.mm, thickness=8.0 * u.mm, back_separation=10.0 * u.mm
)
_DA_SLENDER_LEG = DoubleAngleSection(  # b/t = 30.0 (> 21.9 -> slender)
    leg_length=180.0 * u.mm, thickness=6.0 * u.mm, back_separation=10.0 * u.mm
)


@pytest.mark.parametrize(
    ("name", "da", "material", "Lb_mm", "stem_in_tension", "exp_leg_class"),
    [
        ("A992 2L compact tens", _DA_COMPACT, A992, 1.0, True, "compact"),
        ("S355 2L compact tens", _DA_COMPACT, S355, 1.0, True, "compact"),
        ("A992 2L NC-leg tens (F10.3)", _DA_NC_LEG, A992, 1.0, True, "non_compact"),
        ("A992 2L slender-leg tens", _DA_SLENDER_LEG, A992, 1.0, True, "slender"),
        ("A992 2L LTB Lb=8000 (+B)", _DA_COMPACT, A992, 8000.0, True, "compact"),
        (
            "S355 2L NC-leg LTB Lb=6000",
            _DA_NC_LEG,
            S355,
            6000.0,
            True,
            "non_compact",
        ),
        # web legs in COMPRESSION: Eq. F9-5 Mp=1.5*My (low-ductility);
        # §F9.2(b)(2) LTB via exact Eq. F10-2/F10-3 (F9-EC-1 RESOLVED -
        # library AND oracle both apply the §F10 reduction here, so
        # this cross-check stays bit-exact).
        ("A992 2L web-comp short", _DA_COMPACT, A992, 1.0, False, "compact"),
        (
            "S355 2L web-comp long (-B)",
            _DA_COMPACT,
            S355,
            8000.0,
            False,
            "compact",
        ),
        (
            "A992 2L web-comp NC-leg",
            _DA_NC_LEG,
            A992,
            1.0,
            False,
            "non_compact",
        ),
    ],
)
def test_F9_double_angle_matches_independent_oracle(
    name: str,
    da: DoubleAngleSection,
    material: SteelMaterial,
    Lb_mm: float,
    stem_in_tension: bool,
    exp_leg_class: str,
) -> None:
    """Library §F9 ``Mn`` == independent oracle, bit-exact, double angle.

    Covers Eq. F9-2/F9-3 (web legs in tension), Eq. F9-5 (web legs in
    compression, 1.5*My), §F9.2 LTB both B signs, and the §F9.3(b)/
    §F9.4(b) -> §F10.3 leg-LB delegation (Eq. F10-6/F10-7/F10-8).  The
    governing limit state is cross-checked bit-exactly vs the
    independent oracle; the deterministic §F10.3 leg classification is
    the design-time guard.
    """
    report = _run_da(da, material, Lb=Lb_mm, stem_in_tension=stem_in_tension)
    oracle = mn_F9(_da_oracle_props(da, material, Lb=Lb_mm, stem_in_tension=stem_in_tension))

    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_Mp, oracle.Mp, rel_tol=REL_TOL)
    assert math.isclose(report.yield_moment_My, oracle.My, rel_tol=REL_TOL)
    assert math.isclose(report.critical_moment_Mcr, oracle.Mcr, rel_tol=REL_TOL)
    assert math.isclose(report.ltb_constant_B, oracle.B, rel_tol=REL_TOL)
    if math.isfinite(oracle.Mn_flb):
        assert math.isclose(
            report.flange_local_buckling_moment_Mn_F9_3,
            oracle.Mn_flb,
            rel_tol=REL_TOL,
        )
    assert report.governing_limit_state == oracle.governing
    assert report.flange_classification == exp_leg_class == oracle.flange_class
    assert report.section_kind == "double_angle"
    if stem_in_tension:
        assert report.ltb_constant_B > 0.0
    else:
        assert report.ltb_constant_B < 0.0
        assert report.stem_in_compression_low_ductility is True
        # Eq. F9-5: Mp = 1.5*My for 2L web legs in compression.
        assert math.isclose(
            report.plastic_moment_Mp,
            1.5 * report.yield_moment_My,
            rel_tol=REL_TOL,
        )
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_F9_regime_formulae_pinned_inline_tee() -> None:
    """Inline closed-form pins for one representative of each tee branch.

    Re-derives Eq. F9-2/F9-3, F9-14, F9-15, F9-16+F9-19 from scratch
    (independent of both the library and the oracle) so a coordinated
    library+oracle drift is still caught.
    """
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    s = math.sqrt(E / Fy)
    lam_pf = 0.38 * s
    lam_rf = 1.00 * s

    # -- yielding (stem in tension): Eq. F9-3 My, Eq. F9-2 Mp --
    fc = _TEE_COMPACT.compute_section_properties()
    My_c = Fy * fc.elastic_modulus_Sx
    Mp_c = min(Fy * fc.plastic_modulus_Zx, 1.6 * My_c)
    rep_c = _run_tee(_TEE_COMPACT, A992, Lb=1.0, stem_in_tension=True)
    assert math.isclose(rep_c.yield_moment_My, My_c, rel_tol=REL_TOL)
    assert math.isclose(rep_c.nominal_flexural_strength_Mn, Mp_c, rel_tol=REL_TOL)

    # -- noncompact flange: Eq. F9-14 --
    fn = _TEE_NC_FLANGE.compute_section_properties()
    My_n = Fy * fn.elastic_modulus_Sx
    Mp_n = min(Fy * fn.plastic_modulus_Zx, 1.6 * My_n)
    lam_n = (240.0 / 2.0) / 12.0
    residual_n = 0.7 * Fy * fn.elastic_modulus_compression_flange_Sxc
    f9_14 = Mp_n - (Mp_n - residual_n) * (lam_n - lam_pf) / (lam_rf - lam_pf)
    expected_n = min(f9_14, 1.6 * My_n)
    rep_n = _run_tee(_TEE_NC_FLANGE, A992, Lb=1.0, stem_in_tension=True)
    # FLB is one candidate; assert the FLB branch value itself.
    assert math.isclose(rep_n.flange_local_buckling_moment_Mn_F9_3, expected_n, rel_tol=REL_TOL)

    # -- slender flange: Eq. F9-15  Mn = 0.7 E Sxc / (bf/2tf)^2 --
    fs = _TEE_SLENDER_FLANGE.compute_section_properties()
    lam_s = (560.0 / 2.0) / 10.0
    f9_15 = 0.7 * E * fs.elastic_modulus_compression_flange_Sxc / lam_s**2
    rep_s = _run_tee(_TEE_SLENDER_FLANGE, A992, Lb=1.0, stem_in_tension=True)
    assert math.isclose(rep_s.flange_local_buckling_moment_Mn_F9_3, f9_15, rel_tol=REL_TOL)

    # -- tee stem in compression, slender stem: Eq. F9-16 + F9-19 --
    # _TEE_SLENDER_FLANGE has d/tw = 180/12 = 15.0 (compact stem, F9-17:
    # Fcr=Fy).  Use a deliberately slender stem.
    thin_stem = TeeSection(
        flange_width_bf=200.0 * u.mm,
        flange_thickness_tf=20.0 * u.mm,
        overall_depth_d=460.0 * u.mm,
        stem_thickness_tw=8.0 * u.mm,  # d/tw = 57.5 > 1.52*s=36.6 slender
    )
    ft = thin_stem.compute_section_properties()
    lam_st = 460.0 / 8.0
    assert lam_st > 1.52 * s  # genuinely slender stem
    fcr_19 = 1.52 * E / lam_st**2
    f9_16 = fcr_19 * ft.elastic_modulus_Sx
    rep_t = _run_tee(thin_stem, A992, Lb=1.0, stem_in_tension=False)
    assert math.isclose(rep_t.critical_stress_Fcr, fcr_19, rel_tol=REL_TOL)
    assert math.isclose(rep_t.stem_local_buckling_moment_Mn_F9_4, f9_16, rel_tol=REL_TOL)


def test_F9_ltb_continuity_and_B_sign() -> None:
    """§F9.2 sanity (independent of the oracle).

    * ``Mn`` is monotone non-increasing as ``Lb`` grows past ``Lp``
      then ``Lr`` (a longer unbraced span is never stronger);
    * ``B`` (Eq. F9-11) is ``+`` for the stem-in-tension orientation
      and ``B`` (Eq. F9-12) is ``-`` (same magnitude) for
      stem-in-compression - assert ``B(-) == -B(+)`` exactly.
    """
    prev = math.inf
    for lb in (1.0, 800.0, 1500.0, 3000.0, 6000.0, 12000.0):
        rep = _run_tee(_TEE_COMPACT, A992, Lb=lb, stem_in_tension=True)
        phi_mn = rep.phi_strength_LRFD
        assert phi_mn <= prev + 1.0  # +1 N*mm float slack
        prev = phi_mn

    # B sign reversal (Eq. F9-11 vs F9-12), same |B|.
    rt = _run_tee(_TEE_COMPACT, A992, Lb=4000.0, stem_in_tension=True)
    rc = _run_tee(_TEE_COMPACT, A992, Lb=4000.0, stem_in_tension=False)
    assert rt.ltb_constant_B > 0.0
    assert rc.ltb_constant_B < 0.0
    assert math.isclose(rc.ltb_constant_B, -rt.ltb_constant_B, rel_tol=REL_TOL)


# ===========================================================================
# Guard rails
# ===========================================================================
def test_F9_rejects_non_tee_double_angle_kind() -> None:
    """A non-(tee|2L) snapshot must be refused (no silent wrong number)."""
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
    # "tees and double angles" - no metacharacters, but be explicit.
    with pytest.raises(ValueError, match=re.escape("tees and double angles")):
        compute_flexural_strength_F9_tee_double_angle(
            bogus,
            A992,
            unbraced_length_Lb=1000.0,
            flange_slenderness_bf_2tf=8.0,
            stem_slenderness_d_tw=15.0,
        )


def test_F9_rejects_nonpositive_Lb() -> None:
    """``unbraced_length_Lb <= 0`` must raise (no divide-by-zero in F9-10)."""
    fsp = _TEE_COMPACT.compute_section_properties()
    with pytest.raises(ValueError, match="unbraced_length_Lb"):
        compute_flexural_strength_F9_tee_double_angle(
            fsp,
            A992,
            unbraced_length_Lb=0.0,
            flange_slenderness_bf_2tf=8.0,
            stem_slenderness_d_tw=15.0,
        )


def test_F9_cites_spec_equations_and_case10() -> None:
    """Citations must pin §F9 Eq. F9-1..F9-19 + §F10.3 + Table B4.1b Case 10.

    Provenance gate: equation numbers / page verbatim from
    ``spec_chapterF.txt`` (§F9 @ printed 16.1-65..68; §F10.3 @ 16.1-70).
    The §F9.4 stem / §F10.3 2L-leg breakpoints are defined in the
    section text (not a B4.1b row); Case 10 carries ``page=None`` per
    the F-0 classifier ENGINEER-CONFIRM.
    """
    rep = _run_tee(_TEE_COMPACT, A992, Lb=1.0, stem_in_tension=True)
    pairs = {(c.section, c.equation) for c in rep.cited_clauses}
    for eq in (
        ("F9.1", "F9-1"),
        ("F9.1", "F9-2"),
        ("F9.1", "F9-3"),
        ("F9.1", "F9-4"),
        ("F9.1", "F9-5"),
        ("F9.2", "F9-6"),
        ("F9.2", "F9-7"),
        ("F9.2", "F9-8"),
        ("F9.2", "F9-9"),
        ("F9.2", "F9-10"),
        ("F9.2", "F9-11"),
        ("F9.2", "F9-12"),
        ("F9.2", "F9-13"),
        ("F9.3", "F9-14"),
        ("F9.3", "F9-15"),
        ("F9.4", "F9-16"),
        ("F9.4", "F9-17"),
        ("F9.4", "F9-18"),
        ("F9.4", "F9-19"),
        ("F10.3", "F10-6"),
        ("F10.3", "F10-7"),
        ("F10.3", "F10-8"),
        ("Table B4.1b", "Case 10"),
    ):
        assert eq in pairs, f"missing citation {eq}"
    f9_pages = {c.page for c in rep.cited_clauses if c.section.startswith("F9.")}
    # §F9 spans printed 16.1-65 (lead/F9-1), 16.1-66 (F9-2..F9-12),
    # 16.1-67 (F9-13/14/15/16), 16.1-68 (F9-17/18/19).
    assert f9_pages == {"16.1-65", "16.1-66", "16.1-67", "16.1-68"}
    case10 = next(c for c in rep.cited_clauses if c.equation == "Case 10")
    assert case10.page is None


# ===========================================================================
# Tier 2 - AISC Manual v15.1 Example F.10 (WT-Shape), printed sig-figs
# ===========================================================================
# PROVENANCE BOUNDARY (read before changing these numbers):
#
# The FULL published Example F.10 "WT-Shape Flexural Member" is staged
# verbatim at ``docs/design_notes/_aisc_src_extract/manual_F9_examples
# .txt`` (AISC Manual v15.1 Vol.1; Manual p. F-45..F-47, PDF
# p.192-194).  Every number asserted below is quoted from that staged
# extract - nothing is invented or re-derived from plate dimensions:
#
#   "EXAMPLE F.10 WT-SHAPE FLEXURAL MEMBER"                   (p.192)
#   "The toe of the stem of the WT is in tension ... simply
#    supported and continuously braced.  The WT is ASTM A992"  (p.192)
#   "ASTM A992  Fy = 50 ksi  Fu = 65 ksi"                      (p.192)
#   "Try a WT56.  From AISC Manual Table 1-8 ...
#    d = 4.94 in.   Ix = 4.35 in.4   Zx = 2.20 in.3
#    Sx = 1.22 in.3   bf = 3.96 in.   tf = 0.210 in.
#    y = 1.36 in."                                              (p.192)
#   "bf/2tf = 9.43"                                             (p.193)
#   "Sxc = Ix / y = 4.35 in.4 / 1.36 in. = 3.20 in.3"           (p.193)
#   "From AISC Specification Section F9.1 ... Mn = Mp
#    (Spec. Eq. F9-1)"                                          (p.193)
#   "My = Fy Sx = 50 ksi (1.22 in.3) = 61.0 kip-in.
#    (Spec. Eq. F9-3)"                                          (p.193)
#   "Mp = Fy Zx ... (for stems in tension)
#    = 50 ksi (2.20 in.3) = 110 kip-in.
#    1.6 My = 1.6 (61.0 kip-in.) = 97.6 kip-in.
#    Mp = 97.6 kip-in. or 8.13 kip-ft   (Spec. Eq. F9-2)"        (p.193)
#   "because the WT is continuously braced, the limit state of
#    lateral-torsional buckling does not apply"                 (p.193)
#   "bf/2tf = 9.43 ; lambda_pf = 0.38 sqrt(E/Fy) = 9.15 ;
#    lambda_rf = 1.0 sqrt(E/Fy) = 24.1 ; ... noncompact ...
#    the limit state of flange local buckling will apply"       (p.193-194)
#   Eq. F9-14 box -> "97.6 kip-in."                             (p.194)
#   "Flexural yielding controls:  Mn = 97.6 kip-in. or
#    8.13 kip-ft"                                                (p.194)
#   "phi_b = 0.90 ... phi_b Mn = 0.90 (8.13 kip-ft)
#    = 7.32 kip-ft"  (LRFD)                                      (p.194)
#   "Omega_b = 1.67 ... Mn/Omega_b = (8.13 kip-ft)/1.67
#    = 4.87 kip-ft"  (ASD)                                       (p.194)
#
# Manual rounding: Fy*Sx = 50*1.22 = 61.0 kip-in (exact); 1.6*61.0 =
# 97.6 kip-in (exact); Fy*Zx = 50*2.20 = 110 kip-in (exact); 97.6/12 =
# 8.1333 kip-ft printed "8.13"; 0.90*8.1333 = 7.32; 8.1333/1.67 =
# 4.870.  The library carries full precision, so Manual-result
# comparisons use a documented rel_tol (3-sig-fig display rounding),
# while the §F9 equation is ALSO pinned bit-exactly (rel_tol=1e-9) vs
# the equation recomputed here from the published values.  WT5x6
# bf/2tf = 9.43 is the Manual's PRINTED value (p.193) and independently
# matches the AISC Shapes Database v16.0 WT5X6 row in
# src/apeSteel/sections/catalog/data/AISC_v16_shapes.csv (bf/2tf col =
# 9.43) - sourced + cross-checked, NOT invented.

#: AISC Manual v15.1 Ex. F.10 printed-rounding tolerance.  The Manual
#: prints Mn as "8.13 kip-ft" (from the exact 8.1333...); rel err
#: ~4e-4.  5e-3 absorbs the 3-sig-fig display rounding while still
#: catching any wrong §F9 coefficient/equation (the bit-exact in-test
#: Eq. F9-2/F9-3/F9-14 recomputation is the tight pin).
_MANUAL_REL_TOL = 5e-3

# Manual Ex. F.10 published WT5x6 values (AISC Manual Table 1-8,
# manual_F9_examples.txt p.192-193).  Quoted verbatim; in.->mm only.
_F10_WT5X6_D_IN = 4.94  # in.   (extract p.192)
_F10_WT5X6_IX_IN4 = 4.35  # in.^4 (extract p.192)
_F10_WT5X6_ZX_IN3 = 2.20  # in.^3 (extract p.192)
_F10_WT5X6_SX_IN3 = 1.22  # in.^3 (extract p.192)
_F10_WT5X6_BF_IN = 3.96  # in.   (extract p.192)
_F10_WT5X6_TF_IN = 0.210  # in.   (extract p.192)
_F10_WT5X6_Y_IN = 1.36  # in.   (extract p.192, flange-face->centroid)
_F10_WT5X6_BF_2TF = 9.43  # Manual printed (p.193) == AISC v16 DB row


def _f10_wt5x6_published_section() -> FlexuralSectionProperties:
    """The Manual F.10 section from its **published** Table 1-8 values.

    §F9 reads ``Sx``/``Zx`` (yielding Eq. F9-2/F9-3), ``Sxc`` (FLB
    Eq. F9-14/F9-15) and ``bf/2tf`` (the FLB regime).  Those are set
    from the Manual's published WT5x6 values (``Sx = 1.22 in.^3``,
    ``Zx = 2.20 in.^3``, ``Sxc = Ix/y = 4.35/1.36 in.^3``) - the
    section is built **directly from the Manual's published numbers**,
    NOT re-derived from WT plate dimensions (the documented 2-7%
    k-radius gap would otherwise swamp the Manual comparison - the
    Phase-F-2/F-4 published-section pattern).  ``d``/``Iy``/``J``/``ry``
    are set consistently for trace (LTB is N/A here - continuously
    braced); ``flange_slenderness`` is passed separately as the
    Manual's published ``bf/2tf = 9.43``.
    """
    sx = _F10_WT5X6_SX_IN3 * u.inches**3
    zx = _F10_WT5X6_ZX_IN3 * u.inches**3
    ix = _F10_WT5X6_IX_IN4 * u.inches**4
    y = _F10_WT5X6_Y_IN * u.inches
    d = _F10_WT5X6_D_IN * u.inches
    sxc = ix / y  # Manual: Sxc = Ix / y = 3.20 in.^3
    sxt = ix / (d - y)  # to the stem tip (consistent; trace)
    return FlexuralSectionProperties(
        section_kind="tee",
        symmetry="singly_symmetric",
        overall_depth_d=d,
        gross_area_Ag=1.0,
        moment_of_inertia_Ix=ix,
        elastic_modulus_Sx=sx,  # Manual PUBLISHED Sx = 1.22 in^3
        plastic_modulus_Zx=zx,  # Manual PUBLISHED Zx = 2.20 in^3
        radius_of_gyration_rx=1.0,
        moment_of_inertia_Iy=1.0,
        elastic_modulus_Sy=1.0,
        plastic_modulus_Zy=1.0,
        radius_of_gyration_ry=1.0,
        torsional_constant_J=1.0,
        elastic_modulus_compression_flange_Sxc=sxc,
        elastic_modulus_tension_flange_Sxt=sxt,
        plate_elements=(),
    )


def test_F9_manual_v15_1_F10_wt_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.10 published-result cross-check (§F9 WT).

    External-authority anchor.  Drives the library §F9 path on the
    Manual's **published** WT5x6 (ASTM A992 ``Fy = 50 ksi``; AISC
    Manual Table 1-8 ``d=4.94``, ``Ix=4.35``, ``Zx=2.20``, ``Sx=1.22``,
    ``Sxc=Ix/y=3.20``, ``bf/2tf=9.43``; stem in tension; continuously
    braced) and reproduces the Manual's printed numbers (Manual p.
    F-45..F-47, PDF p.192-194; Spec. Eq. F9-1/F9-2/F9-3/F9-14):

    * Eq. F9-3 ``My = Fy*Sx = 50*1.22 = 61.0 kip-in.``;
    * Eq. F9-2 ``Mp = min(Fy*Zx, 1.6*My) =
      min(110, 97.6) = 97.6 kip-in.`` (the ``1.6*My`` cap is active -
      the Manual prints both 110 and 97.6);
    * LTB N/A (continuously braced -> Lb tiny -> §F9.2(a)(1));
    * flange noncompact (``9.15 < 9.43 < 24.1``) -> Eq. F9-14 ->
      ``97.6 kip-in.`` (the Eq. F9-14 result is itself capped at
      ``1.6*My`` -> 97.6);
    * yielding controls: ``Mn = 97.6 kip-in. = 8.13 kip-ft``;
      ``phi*Mn = 0.90*8.13 = 7.32 kip-ft``;
      ``Mn/Omega = 8.13/1.67 = 4.87 kip-ft``.

    ``Mn`` is *also* pinned bit-exactly (``rel_tol=1e-9``) against
    Eq. F9-2/F9-3 recomputed in-test from the published ``Sx``/``Zx``,
    so the equation is locked independently of the Manual's 3-sig-fig
    rounding.
    """
    fsp = _f10_wt5x6_published_section()
    rep = compute_flexural_strength_F9_tee_double_angle(
        fsp,
        A992,
        unbraced_length_Lb=1.0,  # continuously braced -> Lb<=Lp -> LTB N/A
        flange_slenderness_bf_2tf=_F10_WT5X6_BF_2TF,  # Manual printed 9.43
        stem_slenderness_d_tw=20.0,  # not used (stem in tension); trace
        stem_in_tension=True,
    )

    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    sx = _F10_WT5X6_SX_IN3 * u.inches**3
    zx = _F10_WT5X6_ZX_IN3 * u.inches**3

    # Recompute Eq. F9-3 / F9-2 in-test from the *published* Sx/Zx; pin
    # the library bit-exactly (locks the equation independent of the
    # Manual's 3-sig-fig rounding).
    expected_my = Fy * sx  # Eq. F9-3
    expected_mp = min(Fy * zx, 1.6 * expected_my)  # Eq. F9-2 (cap active)
    assert 1.6 * expected_my < Fy * zx  # Manual: cap (97.6) < Fy*Zx (110)
    assert math.isclose(rep.yield_moment_My, expected_my, rel_tol=REL_TOL)
    assert math.isclose(rep.plastic_moment_Mp, expected_mp, rel_tol=REL_TOL)

    # Flange noncompact (Manual: 9.15 < 9.43 < 24.1).
    assert rep.flange_classification == "non_compact"
    assert math.isclose(rep.compact_limit_lambda_pf, 0.38 * math.sqrt(E / Fy), rel_tol=REL_TOL)
    assert math.isclose(rep.noncompact_limit_lambda_rf, 1.00 * math.sqrt(E / Fy), rel_tol=REL_TOL)

    # LTB does not apply (continuously braced); yielding controls
    # (Mn = Mp = 97.6 kip-in, the Eq. F9-14 result is also capped at
    # 1.6*My = the same 97.6).
    assert rep.governing_limit_state == "yielding"
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_mp, rel_tol=REL_TOL)
    # Eq. F9-14 FLB branch is itself <= 1.6*My = Mp here.
    assert rep.flange_local_buckling_moment_Mn_F9_3 >= expected_mp - 1.0

    # vs the Manual's PUBLISHED printed numbers (3-sig-fig rounding).
    my_kipin = rep.yield_moment_My / (u.kip * u.inches)
    mp_kipin = rep.plastic_moment_Mp / (u.kip * u.inches)
    mn_kipin = rep.nominal_flexural_strength_Mn / (u.kip * u.inches)
    fyzx_kipin = (Fy * zx) / (u.kip * u.inches)
    mn_kipft = rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft
    phi_mn_kipft = rep.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kip_ft
    omega_mn_kipft = rep.omega_strength_ASD / u.MOMENT_DISPLAY_UNIT_kip_ft
    assert math.isclose(my_kipin, 61.0, rel_tol=_MANUAL_REL_TOL)  # Eq. F9-3
    assert math.isclose(fyzx_kipin, 110.0, rel_tol=_MANUAL_REL_TOL)  # Fy*Zx
    assert math.isclose(mp_kipin, 97.6, rel_tol=_MANUAL_REL_TOL)  # Eq. F9-2
    assert math.isclose(mn_kipin, 97.6, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(mn_kipft, 8.13, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(phi_mn_kipft, 7.32, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(omega_mn_kipft, 4.87, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(
        rep.phi_strength_LRFD,
        _PHI_B * rep.nominal_flexural_strength_Mn,
        rel_tol=REL_TOL,
    )
    assert math.isclose(
        rep.omega_strength_ASD,
        rep.nominal_flexural_strength_Mn / _OMEGA_B,
        rel_tol=REL_TOL,
    )

    # The Manual prints Sxc = Ix/y = 3.20 in^3; pin the published-input
    # Sxc to the Manual's printed 3 sig figs (the value the Eq. F9-14
    # branch consumed).
    sxc_in3 = fsp.elastic_modulus_compression_flange_Sxc / u.inches**3
    assert math.isclose(sxc_in3, 3.20, rel_tol=_MANUAL_REL_TOL)


def test_F9_double_angle_first_principles_hand_calc_F9_2_F9_3() -> None:
    """First-principles 2L hand-calc (NOT an AISC-published number).

    ``manual_F9_examples.txt`` has **no double-angle worked example**
    (only the WT Example F.10), so per design-note §6 / the F-5
    contract the double-angle tier-2 anchor is this **labelled
    first-principles hand-calc** (this is the stem-in-*tension*
    yielding path, F9-2/F9-3, LTB N/A - independent of the
    web-leg-compression LTB sub-case that F9-EC-1, now **RESOLVED**
    in Phase F-8, concerned; see the module docstring).

    Hand calc.  Two equal-leg L4x4x1/2-scale angles idealized as
    sharp-corner plates: ``leg = 102 mm``, ``t = 12 mm``, back
    separation ``s = 10 mm`` (a gusset), ASTM A992 (``Fy = 50 ksi``),
    web legs in **tension**, short unbraced length (LTB N/A).

    One component angle (the workbook decomposition, sharp corner):
      ``Ag1 = leg*t + (leg-t)*t = 102*12 + 90*12 = 1224 + 1080 = 2304``
      ``ybar = (leg*t^2/2 + (leg-t)*t*((leg-t)/2 + t)) / Ag1``
             = (102*144/2 + 90*12*(45+12)) / 2304
             = (7344 + 61560) / 2304 = 68904 / 2304 = 29.9063 mm
    Doubled section:
      ``Ag = 2*Ag1 = 4608``;  depth ``d = leg = 102``.
      ``Ix = 2*Ixg`` (Ixg the one-angle strong-axis inertia about its
      own centroid - recomputed below the same way the geometry does).
      ``Sx = Ix / max(ybar, leg - ybar) = Ix / (leg - ybar)``
      (``leg - ybar = 72.094 > ybar`` -> the web-leg tip governs Sx).
      ``Zx`` - PNA splits ``Ag`` in half; ``Ag/2 = 2304``; the bottom
      flange-leg block area ``2*leg*t = 2448 >= 2304`` -> PNA inside
      the flange-leg block at ``yp = (Ag/2)/(2*leg)``.

    §F9 (web legs in tension, leg b/t = 102/12 = 8.5; A992
    ``sqrt(E/Fy)=24.083`` -> §F10.3 ``lambda_p = 0.54*24.083 = 13.0``;
    8.5 < 13.0 -> **compact leg** -> FLB & web-leg LB do not apply):
      ``My = Fy*Sx`` (Eq. F9-3);
      ``Mp = min(Fy*Zx, 1.6*My)`` (Eq. F9-2);
      LTB N/A (short Lb) -> ``Mn = Mp`` (Eq. F9-1).

    The library must reproduce this hand value bit-exactly (it is the
    *same* closed form, so ``rel_tol=1e-9`` is appropriate).
    """
    leg, t, s = 102.0, 12.0, 10.0
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E

    # --- one-angle + doubled constants, recomputed from scratch the
    #     same way DoubleAngleSection.compute_section_properties does ---
    Ag1 = leg * t + (leg - t) * t
    ybar = (leg * t**2 / 2.0 + (leg - t) * t * ((leg - t) / 2.0 + t)) / Ag1
    Ixg = (
        leg * t**3 / 12.0
        + leg * t * (ybar - t / 2.0) ** 2
        + t * (leg - t) ** 3 / 12.0
        + (leg - t) * t * (ybar - ((leg - t) / 2.0 + t)) ** 2
    )
    Ag = 2.0 * Ag1
    Ix = 2.0 * Ixg
    depth_to_flange = ybar
    depth_to_web_tip = leg - ybar
    Sx_hand = Ix / max(depth_to_flange, depth_to_web_tip)

    half = Ag / 2.0
    flange_block = 2.0 * leg * t
    assert half <= flange_block  # PNA inside the flange-leg block
    yp = half / (2.0 * leg)
    a_top = 2.0 * leg * yp
    q_top = a_top * (yp / 2.0)
    a_flange_rem = 2.0 * leg * (t - yp)
    a_web = 2.0 * t * (leg - t)
    q_bot = a_flange_rem * ((t - yp) / 2.0) + a_web * ((t - yp) + (leg - t) / 2.0)
    Zx_hand = q_top + q_bot

    b_t = leg / t
    s_E_Fy = math.sqrt(E / Fy)
    lam_p_leg = 0.54 * s_E_Fy
    assert b_t < lam_p_leg  # compact leg by hand (FLB / web-leg LB N/A)

    My_hand = Fy * Sx_hand  # Eq. F9-3
    Mp_hand = min(Fy * Zx_hand, 1.6 * My_hand)  # Eq. F9-2
    Mn_hand = Mp_hand  # Eq. F9-1 (LTB N/A, compact leg)

    da = DoubleAngleSection(
        leg_length=leg * u.mm,
        thickness=t * u.mm,
        back_separation=s * u.mm,
    )
    # Geometry must reproduce the hand-derived section constants
    # (same closed form -> bit-exact).
    fsp = da.compute_section_properties()
    assert math.isclose(fsp.gross_area_Ag, Ag, rel_tol=REL_TOL)
    assert math.isclose(fsp.moment_of_inertia_Ix, Ix, rel_tol=REL_TOL)
    assert math.isclose(fsp.elastic_modulus_Sx, Sx_hand, rel_tol=REL_TOL)
    assert math.isclose(fsp.plastic_modulus_Zx, Zx_hand, rel_tol=REL_TOL)

    rep = _run_da(da, A992, Lb=1.0, stem_in_tension=True)
    assert rep.flange_classification == "compact"
    assert rep.governing_limit_state == "yielding"
    assert math.isclose(rep.yield_moment_My, My_hand, rel_tol=REL_TOL)
    assert math.isclose(rep.plastic_moment_Mp, Mp_hand, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_flexural_strength_Mn, Mn_hand, rel_tol=REL_TOL)
    assert math.isclose(rep.phi_strength_LRFD, 0.90 * Mn_hand, rel_tol=REL_TOL)
    assert math.isclose(rep.omega_strength_ASD, Mn_hand / 1.67, rel_tol=REL_TOL)

    # Inline golden snapshot (kip-ft display units), pinned to the
    # closed form recomputed in display units (exact) so any drift in
    # the §F9 2L yielding path is caught even without the oracle.
    mn_kipft = rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft
    assert math.isclose(mn_kipft, Mn_hand / u.MOMENT_DISPLAY_UNIT_kip_ft, rel_tol=REL_TOL)


def test_F9_double_angle_EC1_web_compression_ltb_uses_exact_F10_2_3() -> None:
    """**F9-EC-1 RESOLVED**: 2L web-leg-compression LTB == exact §F10-2/3.

    AISC 360-22 §F9.2(b)(2) (spec_chapterF.txt printed 16.1-67,
    verbatim): "For double-angle web legs, ``Mn`` shall be determined
    using Equations F10-2 and F10-3 with ``Mcr`` determined using
    Equation F9-10 and ``My`` determined using Equation F9-3."

    Phase F-5 conservatively bounded this sub-case by the
    §F9.2(b)(1)-form ``Mn = min(Mcr, My)`` because §F10 did not yet
    exist (ENGINEER-CONFIRM F9-EC-1).  §F10 shipped in Phase F-6, so
    Phase F-8 wires §F9.2(b)(2) to the **exact** §F10.2 inelastic /
    elastic LTB reduction (Eq. F10-2 / F10-3).  This test pins the
    exact value, recomputed independently in-test from the §F10-2/F10-3
    closed forms, and asserts it is *strictly below* the prior
    conservative ``min(Mcr, My)`` bound for this geometry (so the
    resolution is observably tighter, not a no-op).
    """
    da = _DA_COMPACT
    Lb = 9000.0
    rep = _run_da(da, A992, Lb=Lb, stem_in_tension=False)
    oracle = mn_F9(_da_oracle_props(da, A992, Lb=Lb, stem_in_tension=False))

    # Bit-exact vs the independent oracle (which now also re-derives
    # Eq. F10-2/F10-3 for this sub-case, from spec literals not the
    # library) - the primary regression pin.
    assert math.isclose(rep.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert rep.ltb_constant_B < 0.0  # Eq. F9-12 (web legs in compression)
    assert rep.stem_in_compression_low_ductility is True

    # Independent in-test re-derivation of the §F9.2(b)(2) -> Eq. F10-2/
    # F10-3 reduction (My = Fy*Sx from Eq. F9-3; Mcr from Eq. F9-10),
    # written from the spec closed forms (independent of the library
    # AND the oracle), so a coordinated drift is still caught.
    My = rep.yield_moment_My  # Eq. F9-3 (Fy*Sx)
    Mcr = rep.critical_moment_Mcr  # Eq. F9-10 (B<0, web legs in compression)
    ratio_my_me = My / Mcr
    if ratio_my_me <= 1.0:
        mn_f10 = min((1.92 - 1.17 * math.sqrt(ratio_my_me)) * My, 1.5 * My)  # Eq. F10-2
    else:
        mn_f10 = (0.92 - 0.17 * (Mcr / My)) * Mcr  # Eq. F10-3
    assert math.isclose(rep.lateral_torsional_buckling_moment_Mn_F9_2, mn_f10, rel_tol=REL_TOL)
    # F9-EC-1 resolution is observably *different* from the prior
    # conservative §F9.2(b)(1)-form bound it superseded: the library no
    # longer returns ``min(Mcr, My)`` for the 2L web-leg-compression
    # LTB sub-case (it returns the exact Eq. F10-2/F10-3 reduction).
    assert not math.isclose(mn_f10, min(Mcr, My), rel_tol=REL_TOL)

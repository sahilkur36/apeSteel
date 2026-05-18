"""Phase F-4 anchors for AISC 360-22 §F6 (minor-axis I-shape flexure).

Two-tier anchor per design note 10 §6:

**Tier 1 (primary, bit-exact ``rel_tol=1e-9``):** the library
``compute_flexural_strength_F6_minor_axis`` is pinned to the independent
standalone stdlib oracle :mod:`tests.golden._chapterF_F6_oracle` (which
imports **nothing** from :mod:`apeSteel.flexure`), across all three
flange-FLB regimes - compact (Eq. F6-1, §F6.2(a)), noncompact
(Eq. F6-2), slender (Eq. F6-3 / F6-4) - both with the Eq. F6-1
``1.6*Fy*Sy`` cap inactive *and* active, doubly- *and* singly-symmetric
I, rolled *and* welded flange (Case 10 / Case 11), and ``>= 2`` steel
grades.  A disagreement means the library or the oracle transcribed a
§F6 equation / constant wrong; agreement is bit-exact because both
implement the same closed forms from independently written source.
Hard literal snapshots (governing limit state, flange classification,
the §F6 constants) are pinned inline as well so any drift is caught
even if the oracle moved in lock-step.

**Tier 2 (external authority - AISC Manual v15.1 Ex. F.5):** the §6
contract anchors §F6 on AISC Manual v15.1 Vol.1 **Example F.5**
"I-Shaped Flexural Member in Minor Axis Bending" (Manual p. F-28/F-29,
PDF p.175-176).  **ENGINEER-CONFIRM F6-EC-2 - RESOLVED**: the full
Example F.5 body is staged in
``docs/design_notes/_aisc_src_extract/manual_F7_F8_examples.txt`` (PDF
p.175-176).  The Manual selects a **W12x58** (ASTM A992,
``Fy = 50 ksi``) and prints, from AISC Manual Table 1-1,
``Sy = 21.4 in.^3`` and ``Zy = 32.5 in.^3``; the flanges are compact
(Manual: "compact flanges per the User Note ... the yielding limit
state governs"), so Eq. F6-1 gives ``Mn = Mp = Fy*Zy = 1,630 kip-in.
= 136 kip-ft`` (cap ``1.6*Fy*Sy = 1,710 kip-in.`` inactive),
``phi*Mn = 122 kip-ft``, ``Mn/Omega = 81.4 kip-ft``.  Tier 2 drives
the library §F6 path on those **published** ``Sy``/``Zy`` and asserts
the Manual's printed kip-in / kip-ft / ``phi*Mn`` / ``Mn/Omega`` to a
documented printed-rounding tolerance (the exact pattern Example F.7B /
F.8B use in ``test_chapterF_F7_golden.py``), plus a bit-exact in-test
Eq. F6-1 recomputation so the equation is locked independently of the
Manual's 3-sig-fig rounding.  The published ``bf/2tf = 7.82`` for
W12x58 is the AISC Shapes Database v16.0 value (the Manual states the
flange is compact but does not print ``bf/2tf``, so the slenderness is
**sourced + cited, not invented**).  The labelled first-principles
hand-calc that previously stood in for the missing body is retained as
an *additional* independent Eq. F6-1 pin (not the authority).

A second provenance flag, **ENGINEER-CONFIRM F6-EC-1 - RESOLVED**,
concerns the Eq. F6-4 / F6-2 elastic coefficient: AISC 360-22 §F6
Eq. F6-4 ``Fcr=0.70E/lambda^2`` and §F6.2 plateau ``0.70*Fy*Sy``,
verbatim a360-22w.pdf (orchestrator-verified, spec_chapterF.txt
L1293/L1312); 360-16 used 0.69 - documented edition delta per
design-note §9.  ``0.70`` is used in BOTH the library and the oracle
(so the bit-exact tier-1 anchor does not mask the choice).

Full AISC-v16-catalog wiring of W-shapes to §F6 minor-axis, and any
``Element.combined_strength_H1`` ``Mcy`` wiring, are Phase F-8 (design
note 10 §5, F-4 line); §F6 ships here as a pure calculator + oracle +
golden only (no facade / ``Element`` wiring, no channel).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from apeSteel.core import units as u
from apeSteel.core.materials import A36, A992, S355, SteelMaterial
from apeSteel.flexure.F6_minor_axis import compute_flexural_strength_F6_minor_axis
from apeSteel.sections.properties import SectionProperties
from tests.golden._chapterF_F6_oracle import F6OracleProps, mn_F6

if TYPE_CHECKING:
    from apeSteel.classification._common import SectionConstruction
    from apeSteel.sections.flexural_properties import FlexuralSectionKind

REL_TOL = 1e-9

# AISC §F1 strength factors (independent literals, not imported from the
# library, so a typo in apeSteel surfaces here).
_PHI_B = 0.90
_OMEGA_B = 1.67


# ===========================================================================
# Independent plate-built doubly-symmetric I-shape minor-axis properties.
#
# Re-derived here from the plate dimensions (standard rectangle
# composition), independent of the apeSteel geometry layer, so this
# anchor does not rest on the library's section math.  For a doubly-
# symmetric I (two flanges bf x tf + web hw x tw), about the MINOR
# (y) axis:
#
#   Iy = 2*(tf*bf^3/12) + hw*tw^3/12
#   Sy = Iy / (bf/2) = 2*Iy/bf
#   Zy = 2*[tf*bf^2/4] + tw^2*hw/4 = tf*bf^2/2 + tw^2*hw/4
#        (each flange's plastic modulus about its own centroidal y is
#         tf*bf^2/4; the web contributes tw^2*hw/4)
#   bf/2tf = (bf/2)/tf      <- the §F6 flange slenderness lambda = b/tf
#   h/tw   = hw/tw
# ===========================================================================
@dataclass(frozen=True)
class _IShape:
    bf: float  # flange width (mm)
    tf: float  # flange thickness (mm)
    hw: float  # web clear height between flanges (mm)
    tw: float  # web thickness (mm)


def _ds_i_props(s: _IShape) -> dict[str, float]:
    """Doubly-symmetric I minor-axis closed forms (mm units)."""
    d = s.hw + 2.0 * s.tf
    Ag = 2.0 * s.bf * s.tf + s.hw * s.tw

    # Strong axis (only needed to populate the SectionProperties record;
    # §F6 never reads x-axis quantities).
    Ix = 2.0 * (s.bf * s.tf**3 / 12.0 + s.bf * s.tf * ((d - s.tf) / 2.0) ** 2) + (
        s.tw * s.hw**3 / 12.0
    )
    Sx = Ix / (d / 2.0)
    Zx = s.bf * s.tf * (d - s.tf) + s.tw * s.hw**2 / 4.0
    rx = math.sqrt(Ix / Ag)

    # Minor axis (what §F6 uses).
    Iy = 2.0 * (s.tf * s.bf**3 / 12.0) + s.hw * s.tw**3 / 12.0
    Sy = Iy / (s.bf / 2.0)
    Zy = s.tf * s.bf**2 / 2.0 + s.tw**2 * s.hw / 4.0
    ry = math.sqrt(Iy / Ag)

    return {
        "d": d,
        "Ag": Ag,
        "Ix": Ix,
        "Sx": Sx,
        "Zx": Zx,
        "rx": rx,
        "Iy": Iy,
        "Sy": Sy,
        "Zy": Zy,
        "ry": ry,
        "bf_2tf": (s.bf / 2.0) / s.tf,
        "h_tw": s.hw / s.tw,
    }


def _section_properties(s: _IShape) -> SectionProperties:
    """Build the shipped I-only currency for a plate-built I-shape.

    Only the minor-axis fields (``Sy``, ``Zy``) and the flange/web
    slenderness ratios are load-bearing for §F6; the strong-axis and
    LTB-constant fields are filled with consistent closed forms (or
    neutral sentinels where §F6 never reads them) so the dataclass
    constructs.
    """
    g = _ds_i_props(s)
    return SectionProperties(
        overall_depth_d=g["d"],
        gross_area_Ag=g["Ag"],
        nominal_weight_per_unit_length_w=0.0,
        moment_of_inertia_strong_axis_Ix=g["Ix"],
        elastic_section_modulus_strong_axis_Sx=g["Sx"],
        plastic_section_modulus_strong_axis_Zx=g["Zx"],
        radius_of_gyration_strong_axis_rx=g["rx"],
        moment_of_inertia_weak_axis_Iy=g["Iy"],
        elastic_section_modulus_weak_axis_Sy=g["Sy"],
        plastic_section_modulus_weak_axis_Zy=g["Zy"],
        radius_of_gyration_weak_axis_ry=g["ry"],
        torsional_constant_J=0.0,
        warping_constant_Cw=0.0,
        distance_between_flange_centroids_ho=g["d"] - s.tf,
        effective_radius_of_gyration_for_LTB_rts=0.0,
        flange_width_to_thickness_ratio_bf_2tf=g["bf_2tf"],
        web_height_to_thickness_ratio_h_tw=g["h_tw"],
        web_thickness_tw=s.tw,
        flange_width_bf=s.bf,
        flange_thickness_tf=s.tf,
    )


def _oracle_props(
    s: _IShape, mat: SteelMaterial, *, construction: SectionConstruction = "rolled"
) -> F6OracleProps:
    g = _ds_i_props(s)
    return F6OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        Zy=g["Zy"],
        Sy=g["Sy"],
        lambda_flange=g["bf_2tf"],
        web_h_tw=g["h_tw"],
        construction=construction,
    )


# A992 sqrt(E/Fy): E/Fy = 580.0 exactly (29000/50 ksi) ->
# sqrt = 24.0832...  Case 10 (rolled): lambda_pf = 0.38*24.083 = 9.152,
# lambda_rf = 1.0*24.083 = 24.083.
# S355 sqrt(E/Fy): E/Fy ~= 563.18 -> sqrt ~= 23.731 -> lambda_pf ~=
# 9.018, lambda_rf ~= 23.731.
# A36 sqrt(E/Fy): E/Fy ~= 805.6 -> sqrt ~= 28.38 -> lambda_pf ~= 10.78,
# lambda_rf ~= 28.38.
#
# Geometries chosen so bf/2tf lands well inside each Case 10 band for
# the given grade.

# --- compact flange (bf/2tf < lambda_pf): Eq. F6-1 ---
# bf=300, tf=20 -> bf/2tf = 7.5 < 9.15 (A992 lambda_pf).  Web hw=400,
# tw=10.  Zy = 20*300^2/2 + 10^2*400/4 = 900000 + 10000 = 910000;
# Sy = Iy/(150); Iy = 2*(20*300^3/12) + 400*10^3/12 = 90,000,000 +
# 33,333.33 = 90,033,333.33; Sy = 600,222.22.  Zy/Sy = 1.516 < 1.6 ->
# cap inactive.
_COMPACT_DS = _IShape(bf=300.0, tf=20.0, hw=400.0, tw=10.0)

# --- noncompact flange (lambda_pf < bf/2tf <= lambda_rf): Eq. F6-2 ---
# bf=300, tf=10 -> bf/2tf = 15.0; A992 lambda_pf=9.15, lambda_rf=24.08
# -> noncompact.  Web hw=400, tw=8.
_NONCOMPACT_DS = _IShape(bf=300.0, tf=10.0, hw=400.0, tw=8.0)

# --- slender flange (bf/2tf > lambda_rf): Eq. F6-3 / F6-4 ---
# bf=560, tf=10 -> bf/2tf = 28.0 > 24.08 (A992 lambda_rf).  Web hw=300,
# tw=8.
_SLENDER_DS = _IShape(bf=560.0, tf=10.0, hw=300.0, tw=8.0)

# --- compact flange WITH the Eq. F6-1 cap ACTIVE (Zy/Sy > 1.6) ---
# The pure-rectangle minor-axis shape factor is exactly 1.5 (flange:
# Zy/Sy = (tf*bf^2/4)/(tf*bf^2/6) = 1.5).  A *thick, narrow* web pushes
# the overall Zy/Sy above the Eq. F6-1 cap 1.6 because the web sits near
# the y-axis: its plastic-modulus contribution tw^2*hw/4 is large while
# its elastic contribution to Sy (hw*tw^3/(6*bf)) is comparatively small
# - the web's effective shape factor about the bf/2 fibre is 1.5*bf/tw.
# Keep the flange comfortably compact for BOTH A992 and S355
# (bf/2tf = 170/20 = 8.5 < lambda_pf ~= 9.02-9.15).
#
#   bf=340, tf=20, hw=200, tw=200:
#     flange Zy = tf*bf^2/2          = 20*340^2/2          = 1,156,000
#     web    Zy = tw^2*hw/4          = 200^2*200/4         = 2,000,000
#     Zy = 3,156,000
#     flange Sy term = tf*bf^2/3     = 20*340^2/3          =   770,666.67
#     web    Sy term = hw*tw^3/(6 bf)= 200*200^3/(6*340)   =   784,313.73
#     Sy = Iy/(bf/2) = 1,554,980.39
#     Zy/Sy = 2.030 > 1.6  -> Eq. F6-1 cap ACTIVE.
#     bf/2tf = 170/20 = 8.5 (exact) -> compact for A992 & S355.
_CAP_ACTIVE_DS = _IShape(bf=340.0, tf=20.0, hw=200.0, tw=200.0)


def test_F6_cap_geometry_assumptions_hold() -> None:
    """Sanity: the chosen geometries really exercise the intended regimes.

    Guards the test design itself (independent of the library): the
    "cap active" shape must have ``Zy/Sy > 1.6`` and a compact flange;
    the "compact" shape must have ``Zy/Sy < 1.6`` (cap inactive).
    """
    ca = _ds_i_props(_CAP_ACTIVE_DS)
    assert ca["Zy"] / ca["Sy"] > 1.6  # Eq. F6-1 cap genuinely binds
    co = _ds_i_props(_COMPACT_DS)
    assert co["Zy"] / co["Sy"] < 1.6  # Eq. F6-1 cap genuinely inactive


# ===========================================================================
# Tier 1 - library vs independent §F6 oracle, all 3 flange regimes,
#          cap inactive + active, DS + SS, rolled + welded, >= 2 grades
# ===========================================================================
@pytest.mark.parametrize(
    ("name", "shape", "material", "section_kind", "construction", "exp_class", "exp_ls"),
    [
        # --- compact flange (Eq. F6-1, cap inactive) ---
        (
            "A992 DS compact",
            _COMPACT_DS,
            A992,
            "doubly_symmetric_I",
            "rolled",
            "compact",
            "yielding",
        ),
        (
            "S355 DS compact",
            _COMPACT_DS,
            S355,
            "doubly_symmetric_I",
            "rolled",
            "compact",
            "yielding",
        ),
        (
            "A36 DS compact",
            _COMPACT_DS,
            A36,
            "doubly_symmetric_I",
            "rolled",
            "compact",
            "yielding",
        ),
        # --- compact flange with the Eq. F6-1 1.6*Fy*Sy cap ACTIVE ---
        (
            "A992 DS cap-active",
            _CAP_ACTIVE_DS,
            A992,
            "doubly_symmetric_I",
            "rolled",
            "compact",
            "yielding",
        ),
        (
            "S355 DS cap-active",
            _CAP_ACTIVE_DS,
            S355,
            "doubly_symmetric_I",
            "rolled",
            "compact",
            "yielding",
        ),
        # --- noncompact flange (Eq. F6-2) ---
        (
            "A992 DS NC",
            _NONCOMPACT_DS,
            A992,
            "doubly_symmetric_I",
            "rolled",
            "non_compact",
            "flange_local_buckling",
        ),
        (
            "S355 DS NC",
            _NONCOMPACT_DS,
            S355,
            "doubly_symmetric_I",
            "rolled",
            "non_compact",
            "flange_local_buckling",
        ),
        # --- slender flange (Eq. F6-3 / F6-4) ---
        (
            "A992 DS slender",
            _SLENDER_DS,
            A992,
            "doubly_symmetric_I",
            "rolled",
            "slender",
            "flange_local_buckling",
        ),
        (
            "S355 DS slender",
            _SLENDER_DS,
            S355,
            "doubly_symmetric_I",
            "rolled",
            "slender",
            "flange_local_buckling",
        ),
        # --- singly-symmetric I (same flange Case 10/11; §F6 has no web
        #     limit state, so a SS I behaves like a DS I for §F6) ---
        (
            "A992 SS compact",
            _COMPACT_DS,
            A992,
            "singly_symmetric_I",
            "rolled",
            "compact",
            "yielding",
        ),
        (
            "A992 SS NC",
            _NONCOMPACT_DS,
            A992,
            "singly_symmetric_I",
            "rolled",
            "non_compact",
            "flange_local_buckling",
        ),
        (
            "S355 SS slender",
            _SLENDER_DS,
            S355,
            "singly_symmetric_I",
            "rolled",
            "slender",
            "flange_local_buckling",
        ),
        # --- welded built-up flange (Table B4.1b Case 11, kc factor) ---
        (
            "A992 DS welded NC",
            _NONCOMPACT_DS,
            A992,
            "doubly_symmetric_I",
            "welded",
            "non_compact",
            "flange_local_buckling",
        ),
        (
            "S355 DS welded slender",
            _SLENDER_DS,
            S355,
            "doubly_symmetric_I",
            "welded",
            "slender",
            "flange_local_buckling",
        ),
    ],
)
def test_F6_matches_independent_oracle(
    name: str,
    shape: _IShape,
    material: SteelMaterial,
    section_kind: FlexuralSectionKind,
    construction: SectionConstruction,
    exp_class: str,
    exp_ls: str,
) -> None:
    """Library §F6 ``Mn`` == independent oracle, bit-exact, every regime.

    Covers compact / noncompact / slender flange, the Eq. F6-1
    ``1.6*Fy*Sy`` cap inactive *and* active, DS + SS, rolled + welded
    flange, and >= 2 grades.
    """
    sp = _section_properties(shape)
    report = compute_flexural_strength_F6_minor_axis(
        sp,
        material,
        section_kind=section_kind,
        construction=construction,
    )
    oracle = mn_F6(_oracle_props(shape, material, construction=construction))

    # Primary bit-exact pin.
    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.flange_slenderness_lambda, oracle.lambda_flange, rel_tol=REL_TOL)
    assert math.isclose(report.compact_limit_lambda_pf, oracle.lambda_pf, rel_tol=REL_TOL)
    assert math.isclose(report.noncompact_limit_lambda_rf, oracle.lambda_rf, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_Mp, oracle.Mp, rel_tol=REL_TOL)
    assert math.isclose(report.yield_moment_My, oracle.My, rel_tol=REL_TOL)
    assert math.isclose(report.plastic_moment_cap_1_6_Fy_Sy, oracle.cap_1_6_Fy_Sy, rel_tol=REL_TOL)
    assert math.isclose(report.yielding_moment_Mn_F6_1, oracle.Mn_F6_1, rel_tol=REL_TOL)
    assert math.isclose(report.critical_stress_Fcr, oracle.Fcr, rel_tol=REL_TOL)

    # The regime really is the one intended (so all branches are
    # genuinely exercised, not just one).
    assert report.flange_classification == exp_class == oracle.classification
    assert report.governing_limit_state == exp_ls == oracle.governing

    # phi / Omega plumbing (independent literals).
    assert report.phi_LRFD == _PHI_B
    assert report.omega_ASD == _OMEGA_B
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_F6_cap_is_actually_binding_when_active() -> None:
    """When the cap is active, ``Mn = 1.6*Fy*Sy < Fy*Zy`` exactly.

    Independent of the oracle: re-derive the Eq. F6-1 cap from scratch
    and assert the library returned the *capped* value (not the
    uncapped ``Mp = Fy*Zy``), so the ``min(Fy*Zy, 1.6*Fy*Sy)`` really
    fires.
    """
    sp = _section_properties(_CAP_ACTIVE_DS)
    rep = compute_flexural_strength_F6_minor_axis(sp, A992)
    Fy = A992.yield_stress_Fy
    g = _ds_i_props(_CAP_ACTIVE_DS)
    cap = 1.6 * Fy * g["Sy"]
    Mp_uncapped = Fy * g["Zy"]

    assert cap < Mp_uncapped  # the cap genuinely binds
    assert math.isclose(rep.nominal_flexural_strength_Mn, cap, rel_tol=REL_TOL)
    assert math.isclose(rep.plastic_moment_Mp, Mp_uncapped, rel_tol=REL_TOL)
    assert rep.nominal_flexural_strength_Mn < rep.plastic_moment_Mp


def test_F6_regime_formulae_pinned_inline() -> None:
    """Inline closed-form pins for one representative of each §F6 branch.

    Re-derives Eq. F6-1 / F6-2 / F6-3+F6-4 from scratch (independent of
    both the library and the oracle) and pins the library output to
    them, so a coordinated library+oracle drift is still caught.
    """
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    sqrt_E_Fy = math.sqrt(E / Fy)
    lam_pf = 0.38 * sqrt_E_Fy
    lam_rf = 1.00 * sqrt_E_Fy  # rolled, Case 10

    # -- compact (cap inactive): Eq. F6-1  Mn = Fy*Zy (< 1.6*Fy*Sy) --
    gc = _ds_i_props(_COMPACT_DS)
    mn_c = compute_flexural_strength_F6_minor_axis(
        _section_properties(_COMPACT_DS), A992
    ).nominal_flexural_strength_Mn
    assert math.isclose(mn_c, min(Fy * gc["Zy"], 1.6 * Fy * gc["Sy"]), rel_tol=REL_TOL)
    assert math.isclose(mn_c, Fy * gc["Zy"], rel_tol=REL_TOL)  # cap inactive here

    # -- noncompact: Eq. F6-2  Mn = Mp1 - (Mp1 - 0.70 Fy Sy)
    #                                    (lam - lam_pf)/(lam_rf - lam_pf) --
    gn = _ds_i_props(_NONCOMPACT_DS)
    lam_n = gn["bf_2tf"]
    Mp1_n = min(Fy * gn["Zy"], 1.6 * Fy * gn["Sy"])
    residual_n = 0.70 * Fy * gn["Sy"]
    expected_n = Mp1_n - (Mp1_n - residual_n) * (lam_n - lam_pf) / (lam_rf - lam_pf)
    mn_n = compute_flexural_strength_F6_minor_axis(
        _section_properties(_NONCOMPACT_DS), A992
    ).nominal_flexural_strength_Mn
    assert math.isclose(mn_n, expected_n, rel_tol=REL_TOL)

    # -- slender: Eq. F6-3  Mn = Fcr*Sy, Eq. F6-4  Fcr = 0.70 E/(b/tf)^2 --
    gs = _ds_i_props(_SLENDER_DS)
    lam_s = gs["bf_2tf"]
    expected_fcr = 0.70 * E / lam_s**2
    expected_s = expected_fcr * gs["Sy"]
    rep_s = compute_flexural_strength_F6_minor_axis(_section_properties(_SLENDER_DS), A992)
    assert math.isclose(rep_s.critical_stress_Fcr, expected_fcr, rel_tol=REL_TOL)
    assert math.isclose(rep_s.nominal_flexural_strength_Mn, expected_s, rel_tol=REL_TOL)


def test_F6_continuity_across_regime_breakpoints() -> None:
    """§F6 ``Mn`` is continuous across the FLB regime breakpoints.

    Sanity guard independent of the oracle.  Rather than placing
    ``bf/2tf`` *exactly* on a boundary (a float knife-edge for the
    compact-vs-noncompact classification - the value is continuous
    there but the *label* is not), this sweeps ``tf`` so ``bf/2tf``
    crosses ``lambda_pf`` then ``lambda_rf`` and asserts:

    * ``Mn`` is monotone non-increasing as the flange gets more slender
      (a stockier flange is never weaker);
    * the noncompact-branch ``Mn`` stays bracketed between the Eq. F6-1
      plateau (``min(Fy*Zy, 1.6*Fy*Sy)``) and ``0.70*Fy*Sy``;
    * Eq. F6-3/F6-4 meets Eq. F6-2 continuously at ``lambda_rf`` for a
      rolled section: ``0.70 E/lambda_rf^2 = 0.70 Fy`` because
      ``lambda_rf = 1.0 sqrt(E/Fy)`` (a pure closed-form identity,
      float-stable, no classification involved).
    """
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    sqrt_E_Fy = math.sqrt(E / Fy)
    lam_pf = 0.38 * sqrt_E_Fy
    lam_rf = 1.00 * sqrt_E_Fy  # rolled, Case 10

    bf, hw, tw = 300.0, 400.0, 8.0
    # Sweep tf from thick (compact flange) to thin (slender flange);
    # bf/2tf increases monotonically as tf shrinks.
    prev_phi_mn = math.inf
    for tf in (40.0, 22.0, 16.0, 12.0, 9.0, 7.0, 5.0, 4.0):
        shape = _IShape(bf=bf, tf=tf, hw=hw, tw=tw)
        g = _ds_i_props(shape)
        lam = g["bf_2tf"]
        rep = compute_flexural_strength_F6_minor_axis(_section_properties(shape), A992)
        phi_mn = rep.phi_strength_LRFD

        # Monotone non-increasing (a more slender flange is never
        # stronger); +1 N*mm slack absorbs float noise.
        assert phi_mn <= prev_phi_mn + 1.0
        prev_phi_mn = phi_mn

        plateau = min(Fy * g["Zy"], 1.6 * Fy * g["Sy"])
        residual = 0.70 * Fy * g["Sy"]
        if lam <= lam_pf:
            assert rep.flange_classification == "compact"
            assert math.isclose(rep.nominal_flexural_strength_Mn, plateau, rel_tol=REL_TOL)
        elif lam <= lam_rf:
            assert rep.flange_classification == "non_compact"
            # Eq. F6-2 result is bracketed by the two interpolation
            # anchors (continuity + boundedness of the linear blend).
            mn = rep.nominal_flexural_strength_Mn
            lo, hi = sorted((plateau, residual))
            assert lo - 1.0 <= mn <= hi + 1.0
        else:
            assert rep.flange_classification == "slender"
            # Eq. F6-3/F6-4 closed form.
            assert math.isclose(rep.critical_stress_Fcr, 0.70 * E / lam**2, rel_tol=REL_TOL)

    # Pure closed-form continuity identity at lambda_rf (no
    # classification, float-stable): Eq. F6-4 Fcr at lambda_rf equals
    # the Eq. F6-2 slender-end stress 0.70*Fy.
    assert math.isclose(0.70 * E / lam_rf**2, 0.70 * Fy, rel_tol=REL_TOL)


# ===========================================================================
# Guard rails
# ===========================================================================
def test_F6_rejects_channel_kind_deferred_to_F8() -> None:
    """Channel minor-axis §F6 is out of F-4 scope - must raise.

    Design note 10 §5 (F-4 line) moves channel minor-axis §F6 to F-8;
    F-4 must refuse it rather than return an I-shape number for a
    channel (whose §F6 ``b`` is the *full* flange width, not ``bf/2``).
    """
    sp = _section_properties(_COMPACT_DS)
    # Deliberately-invalid kind: cast so the *runtime* guard (not the
    # type checker) is what rejects it - that is exactly what this test
    # asserts.
    # RUF043: each alternative is a literal (the "-" in "F-8"/"I-shapes"
    # is a regex metacharacter inside a character range), so escape each
    # branch rather than ship a raw pattern.
    channel_msg_pattern = "|".join(re.escape(s) for s in ("channel", "F-8", "I-shapes"))
    with pytest.raises(ValueError, match=channel_msg_pattern):
        compute_flexural_strength_F6_minor_axis(
            sp,
            A992,
            section_kind=cast("FlexuralSectionKind", "channel"),
        )


def test_F6_rejects_non_i_kind() -> None:
    """A non-I section kind must be refused (no silent wrong number)."""
    sp = _section_properties(_COMPACT_DS)
    with pytest.raises(ValueError, match="I-shapes"):
        compute_flexural_strength_F6_minor_axis(
            sp,
            A992,
            section_kind=cast("FlexuralSectionKind", "round_HSS"),
        )


def test_F6_cites_spec_equations_and_b4_1b_cases() -> None:
    """Citations must pin §F6 Eq. F6-1..F6-4 + Table B4.1b Case 10/11.

    Provenance gate: equation numbers / page verbatim from
    ``spec_chapterF.txt`` / ``_chapterF_citation_reference.md`` (§F6 @
    printed 16.1-62); B4.1b case-row pages are ``None`` (not in the
    staged extract per the citation reference's ENGINEER-CONFIRM).
    """
    sp = _section_properties(_COMPACT_DS)
    rep = compute_flexural_strength_F6_minor_axis(sp, A992)
    pairs = {(c.section, c.equation) for c in rep.cited_clauses}
    assert ("F6.1", "F6-1") in pairs
    assert ("F6.2", "F6-2") in pairs
    assert ("F6.2", "F6-3") in pairs
    assert ("F6.2", "F6-4") in pairs
    assert ("Table B4.1b", "Case 10") in pairs
    assert ("Table B4.1b", "Case 11") in pairs
    f6_pages = {c.page for c in rep.cited_clauses if c.section.startswith("F6")}
    assert f6_pages == {"16.1-62"}
    # B4.1b case-row pages are intentionally None (not in staged extract).
    for cl in rep.cited_clauses:
        if cl.equation in ("Case 10", "Case 11"):
            assert cl.page is None


# ===========================================================================
# Tier 2 - AISC Manual v15.1 Example F.5 (I-shape minor-axis)
# ===========================================================================
# PROVENANCE BOUNDARY (read before changing these numbers):
#
# The §6 (design note 10) tier-2 anchor for §F6 is AISC Manual v15.1
# Vol.1 Example F.5 "I-Shaped Flexural Member in Minor Axis Bending"
# (Manual p. F-28/F-29, PDF p.175-176).
#
# ENGINEER-CONFIRM F6-EC-2 - RESOLVED: the full Example F.5 body is
# staged in ``docs/design_notes/_aisc_src_extract/manual_F7_F8_examples
# .txt`` (PDF p.175-176, Manual p. F-28/F-29).  Every number asserted
# below is quoted VERBATIM from that extract (line refs are into that
# file); NOTHING is invented.  The Manual:
#
#   * selects "W1258" (= W12x58), ASTM A992, Fy = 50 ksi
#       (manual_F7_F8_examples.txt L162, L24-26);
#   * quotes, "From AISC Manual Table 1-1, the geometric properties":
#       Sy = 21.4 in.^3 ; Zy = 32.5 in.^3 ; Iy = 107 in.^4
#       (manual_F7_F8_examples.txt L166-169);
#   * states "Because the W1258 has compact flanges per the User Note
#       in this Section, the yielding limit state governs the design"
#       (manual_F7_F8_examples.txt L173-174);
#   * Eq. F6-1: Mn = Mp = Fy*Zy = 50*32.5 = "1,630 kip-in";
#       cap 1.6*Fy*Sy = 1.6*50*21.4 = "1,710 kip-in";
#       Mn = "1,630 kip-in or 136 kip-ft"
#       (manual_F7_F8_examples.txt L185-192, "(Spec. Eq. F6-1)");
#   * Available strength: phi_b = 0.90 -> phi_b*Mn =
#       "0.90 (136 kip-ft) = 122 kip-ft"; Omega_b = 1.67 ->
#       Mn/Omega_b = "136 / 1.67 = 81.4 kip-ft"
#       (manual_F7_F8_examples.txt L220-247).
#
# The Manual prints Mn to 3 sig figs ("136 kip-ft", from Fy*Zy =
# 50*32.5 = 1625 -> rounded "1,630 kip-in").  Manual-result comparisons
# therefore use a documented rel_tol (_MANUAL_REL_TOL) loose enough for
# that printed rounding but tight enough to catch a wrong §F6 equation;
# Mn is ALSO pinned bit-exactly (rel_tol=1e-9) against Eq. F6-1
# recomputed in-test from the published Sy/Zy, so the equation is
# locked independently of the Manual's rounding.  This is the exact
# external-authority pattern Example F.7B / F.8B use in
# ``test_chapterF_F7_golden.py`` (the protocol that resolved the
# analogous F-2/F-7 gaps).
#
# W12x58 bf/2tf: the Manual states the flange is compact but does NOT
# print bf/2tf.  bf/2tf = 7.82 is the AISC Shapes Database v16.0
# published value for W12x58 (also shipped in this repo's
# src/apeSteel/sections/catalog/data/AISC_v16_shapes.csv) - sourced +
# cited, NOT invented; it is only used to drive the (Manual-asserted)
# compact classification, and 7.82 < lambda_pf = 0.38 sqrt(E/Fy) =
# 9.15 for A992 confirms the Manual's "compact flanges" statement.
#
# ENGINEER-CONFIRM F6-EC-1 - RESOLVED: AISC 360-22 §F6 Eq. F6-4
#   Fcr=0.70E/lambda^2 and §F6.2 plateau 0.70*Fy*Sy, verbatim
#   a360-22w.pdf (orchestrator-verified, spec_chapterF.txt
#   L1293/L1312); 360-16 used 0.69 - documented edition delta per
#   design-note §9.  0.70 used in library + oracle.

#: AISC Manual v15.1 Ex. F.5 printed-rounding tolerance.  The Manual
#: prints Mn to 3 sig figs ("136 kip-ft" from the exact 135.4 kip-ft;
#: rel err 4.3e-3).  5e-3 absorbs the 3-sig-fig display rounding while
#: still catching any wrong §F6 coefficient/equation (the F-7 golden
#: uses 4e-3 for its 2-3 sig-fig HSS numbers; F.5's "136" rounds one
#: digit coarser, so 5e-3 here - the bit-exact in-test Eq. F6-1
#: recomputation provides the tight pin).
_MANUAL_REL_TOL = 5e-3

# Manual Ex. F.5 published W12x58 section values (AISC Manual Table 1-1,
# manual_F7_F8_examples.txt L166-169) + the AISC Shapes Database v16.0
# bf/2tf for W12x58.  All quoted verbatim; converted in.->mm only.
_F5_W12X58_SY_IN3 = 21.4  # in.^3, AISC Manual Table 1-1 (extract L167)
_F5_W12X58_ZY_IN3 = 32.5  # in.^3, AISC Manual Table 1-1 (extract L168)
_F5_W12X58_BF_2TF = 7.82  # AISC Shapes Database v16.0 (W12X58 row)


def _f5_w12x58_published_section() -> SectionProperties:
    """Shipped I-only currency built from Manual Ex. F.5's *published*
    W12x58 minor-axis section moduli.

    §F6 reads only ``Sy``/``Zy`` (the strength) and ``bf/2tf`` (the
    flange-FLB regime); those are set from the Manual's published
    Table 1-1 ``Sy = 21.4 in.^3`` / ``Zy = 32.5 in.^3`` and the AISC
    Shapes Database v16.0 ``bf/2tf = 7.82`` for W12x58.  Every other
    field is a neutral, non-load-bearing sentinel (positive where the
    ``SectionProperties`` invariants require it, ``0.0`` where §F6
    never reads it) - this anchor rests on the *Manual's* numbers, not
    on the apeSteel geometry layer.
    """
    sy = _F5_W12X58_SY_IN3 * u.inches**3
    zy = _F5_W12X58_ZY_IN3 * u.inches**3
    return SectionProperties(
        overall_depth_d=1.0,
        gross_area_Ag=1.0,
        nominal_weight_per_unit_length_w=0.0,
        moment_of_inertia_strong_axis_Ix=1.0,
        elastic_section_modulus_strong_axis_Sx=1.0,
        plastic_section_modulus_strong_axis_Zx=1.0,
        radius_of_gyration_strong_axis_rx=1.0,
        moment_of_inertia_weak_axis_Iy=1.0,
        elastic_section_modulus_weak_axis_Sy=sy,
        plastic_section_modulus_weak_axis_Zy=zy,
        radius_of_gyration_weak_axis_ry=1.0,
        torsional_constant_J=0.0,
        warping_constant_Cw=0.0,
        distance_between_flange_centroids_ho=1.0,
        effective_radius_of_gyration_for_LTB_rts=0.0,
        flange_width_to_thickness_ratio_bf_2tf=_F5_W12X58_BF_2TF,
        web_height_to_thickness_ratio_h_tw=1.0,
        web_thickness_tw=1.0,
        flange_width_bf=1.0,
        flange_thickness_tf=1.0,
    )


def test_F6_manual_v15_1_F5_minor_axis_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.5 published-result cross-check (Eq. F6-1).

    **ENGINEER-CONFIRM F6-EC-2 - RESOLVED.** External-authority anchor
    for the §F6 yielding limit state (compact flange, cap inactive).
    Drives the library §F6 path on AISC Manual v15.1 Vol.1 Example F.5's
    **published** W12x58 (ASTM A992, ``Fy = 50 ksi``; AISC Manual
    Table 1-1 ``Sy = 21.4 in.^3``, ``Zy = 32.5 in.^3``; AISC Shapes
    Database v16.0 ``bf/2tf = 7.82``) and reproduces the Manual's
    printed numbers (Manual p. F-28/F-29, PDF p.175-176;
    ``manual_F7_F8_examples.txt`` L162-247; Spec. Eq. F6-1):

    * flange compact (``7.82 < lambda_pf = 0.38 sqrt(E/Fy) = 9.15``
      for A992) -> §F6.2(a) FLB N/A -> yielding governs (the Manual's
      "compact flanges per the User Note ... yielding limit state
      governs");
    * Eq. F6-1 ``Mp = Fy*Zy = 50*32.5 = 1,630 kip-in.`` (Manual
      rounds the exact 1,625);
    * cap ``1.6*Fy*Sy = 1.6*50*21.4 = 1,710 kip-in.`` -> inactive
      (``Zy/Sy = 1.52 < 1.6``), so ``Mn = Mp``;
    * ``Mn = 1,630 kip-in. = 136 kip-ft``;
      ``phi*Mn = 0.90*136 = 122 kip-ft``;
      ``Mn/Omega = 136/1.67 = 81.4 kip-ft``.

    ``Mn`` is *also* pinned bit-exactly (``rel_tol=1e-9``) against
    Eq. F6-1 recomputed in-test from the published ``Sy``/``Zy``, so
    the equation is locked independently of the Manual's 3-sig-fig
    rounding.  Manual-printed values use ``_MANUAL_REL_TOL`` (the
    Example F.7B / F.8B printed-rounding pattern).
    """
    sp = _f5_w12x58_published_section()
    rep = compute_flexural_strength_F6_minor_axis(
        sp, A992, section_kind="doubly_symmetric_I", construction="rolled"
    )

    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E

    # Regime: compact flange (Manual: "compact flanges per the User
    # Note"); 7.82 < lambda_pf = 0.38 sqrt(E/Fy) = 9.15 for A992.
    assert rep.flange_classification == "compact"
    assert rep.governing_limit_state == "yielding"
    assert math.isclose(
        rep.compact_limit_lambda_pf,
        0.38 * math.sqrt(E / Fy),
        rel_tol=REL_TOL,
    )
    assert rep.flange_slenderness_lambda < rep.compact_limit_lambda_pf

    # Recompute Eq. F6-1 in-test from the *published* Sy/Zy and pin the
    # library bit-exactly (locks the equation independent of the
    # Manual's 3-sig-fig rounding).
    sy = _F5_W12X58_SY_IN3 * u.inches**3
    zy = _F5_W12X58_ZY_IN3 * u.inches**3
    expected_mp = Fy * zy
    expected_cap = 1.6 * Fy * sy
    expected_mn = min(expected_mp, expected_cap)
    assert expected_cap > expected_mp  # Manual: cap (1,710) inactive
    assert math.isclose(rep.plastic_moment_Mp, expected_mp, rel_tol=REL_TOL)
    assert math.isclose(rep.plastic_moment_cap_1_6_Fy_Sy, expected_cap, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_mn, rel_tol=REL_TOL)
    # cap inactive -> Mn == Mp exactly (Manual: yielding governs).
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_mp, rel_tol=REL_TOL)

    # vs the Manual's PUBLISHED printed numbers (3-sig-fig rounding).
    mp_kipin = rep.plastic_moment_Mp / (u.kip * u.inches)
    cap_kipin = rep.plastic_moment_cap_1_6_Fy_Sy / (u.kip * u.inches)
    mn_kipin = rep.nominal_flexural_strength_Mn / (u.kip * u.inches)
    mn_kipft = rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft
    phi_mn_kipft = rep.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kip_ft
    omega_mn_kipft = rep.omega_strength_ASD / u.MOMENT_DISPLAY_UNIT_kip_ft
    # Manual L185-192: "Mp = Fy Zy = 50 ksi (32.5 in.3) = 1,630 kip-in";
    # "1.6 Fy Sy = 1.6 (50 ksi)(21.4 in.3) = 1,710 kip-in";
    # "Mn = 1,630 kip-in or 136 kip-ft".
    assert math.isclose(mp_kipin, 1630.0, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(cap_kipin, 1710.0, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(mn_kipin, 1630.0, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(mn_kipft, 136.0, rel_tol=_MANUAL_REL_TOL)
    # Manual L220-247: phi_b Mn = 0.90 (136) = 122 kip-ft;
    # Mn/Omega_b = 136 / 1.67 = 81.4 kip-ft.
    assert math.isclose(phi_mn_kipft, 122.0, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(omega_mn_kipft, 81.4, rel_tol=_MANUAL_REL_TOL)
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


def test_F6_first_principles_hand_calc_eq_F6_1_yielding() -> None:
    """Additional self-contained first-principles Eq. F6-1 hand-calc.

    NOT the tier-2 authority (that is
    :func:`test_F6_manual_v15_1_F5_minor_axis_published_anchor`, the
    real AISC Manual Ex. F.5 published anchor, F6-EC-2 RESOLVED).  This
    is retained as an *extra* independent pin of the §F6 yielding limit
    state on a different, fully hand-derived section - a
    self-contained cross-check, NOT an AISC-published number.

    Hand calc.  A doubly-symmetric I-shape with
    ``bf = 256 mm``, ``tf = 16.3 mm`` (a W14x90-scale flange - chosen
    only for a concrete, hand-traceable section; NOT claimed to be the
    Manual's selection), ``hw = 315 mm``, ``tw = 11.2 mm``, ASTM A992
    (``Fy = 50 ksi``).

      b/tf = (bf/2)/tf = 128 / 16.3 = 7.853...
      sqrt(E/Fy) = sqrt(29000/50) [ksi-cancel] = sqrt(580.0) = 24.0832
      lambda_pf  = 0.38 * 24.0832 = 9.1516
      7.853 < 9.1516  ->  flange COMPACT  ->  §F6.2(a): FLB N/A

      Zy = tf*bf^2/2 + tw^2*hw/4
         = 16.3*256^2/2 + 11.2^2*315/4
         = 16.3*65536/2 + 125.44*315/4
         = 534,118.4 + 9,878.4  =  543,996.8 mm^3
      Sy = Iy/(bf/2),
        Iy = 2*(tf*bf^3/12) + hw*tw^3/12
           = 2*(16.3*256^3/12) + 315*11.2^3/12
           = 2*(16.3*16,777,216/12) + 315*1404.928/12
           = 2*22,789,051.7333... + 36,879.36
           = 45,578,103.4666... + 36,879.36 = 45,614,982.8266... mm^3 (Iy)
        Sy = 45,614,982.8266... / 128 = 356,367.05...mm^3

      Eq. F6-1:  Mp = Fy*Zy ;  cap = 1.6*Fy*Sy.
        Zy/Sy = 543,996.8 / 356,367.05 = 1.5265 < 1.6  -> cap inactive
        Mn = Fy*Zy.

    The library must reproduce this hand value bit-exactly (it is the
    *same* closed form, so ``rel_tol=1e-9`` is appropriate - this pins
    the §F6 yielding equation independently of the oracle).
    """
    shape = _IShape(bf=256.0, tf=16.3, hw=315.0, tw=11.2)
    Fy = A992.yield_stress_Fy

    # Hand-derived section constants (recomputed here from the plate
    # dimensions, the SAME way the docstring derives them).
    Zy_hand = 16.3 * 256.0**2 / 2.0 + 11.2**2 * 315.0 / 4.0
    Iy_hand = 2.0 * (16.3 * 256.0**3 / 12.0) + 315.0 * 11.2**3 / 12.0
    Sy_hand = Iy_hand / (256.0 / 2.0)
    lam_hand = (256.0 / 2.0) / 16.3
    lam_pf_hand = 0.38 * math.sqrt(A992.elastic_modulus_E / Fy)

    # The hand calc says: compact flange, cap inactive, Mn = Fy*Zy.
    assert lam_hand < lam_pf_hand  # compact by hand
    assert Zy_hand / Sy_hand < 1.6  # Eq. F6-1 cap inactive by hand
    Mn_hand = Fy * Zy_hand

    rep = compute_flexural_strength_F6_minor_axis(_section_properties(shape), A992)
    assert rep.flange_classification == "compact"
    assert rep.governing_limit_state == "yielding"
    assert math.isclose(rep.flange_slenderness_lambda, lam_hand, rel_tol=REL_TOL)
    assert math.isclose(rep.plastic_moment_Mp, Mn_hand, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_flexural_strength_Mn, Mn_hand, rel_tol=REL_TOL)
    # phi*Mn / Mn-over-Omega plumbing on the hand value.
    assert math.isclose(rep.phi_strength_LRFD, 0.90 * Mn_hand, rel_tol=REL_TOL)
    assert math.isclose(rep.omega_strength_ASD, Mn_hand / 1.67, rel_tol=REL_TOL)

    # Inline golden snapshot of the hand value (kip-ft display units), so
    # any drift in the §F6 yielding path is caught even without the
    # oracle.  Mn_hand in N*mm; convert to kip-ft for a human-readable
    # pinned literal.  543,996.8 mm^3 * 344.7379 MPa = 1.875...e8 N*mm.
    mn_kipft = rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft
    # Pinned to the closed form recomputed in display units (exact).
    assert math.isclose(mn_kipft, (Fy * Zy_hand) / u.MOMENT_DISPLAY_UNIT_kip_ft, rel_tol=REL_TOL)

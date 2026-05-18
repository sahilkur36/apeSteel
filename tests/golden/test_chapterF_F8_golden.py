"""Phase F-2 anchors for AISC 360-22 §F8 (round HSS / Pipe).

Two-tier anchor per design note 10 §6:

**Tier 1 (primary, bit-exact ``rel_tol=1e-9``):** the library
``compute_flexural_strength_F8_round_hss`` is pinned to the independent
standalone stdlib oracle :mod:`tests.golden._chapterF_F8_oracle` (which
imports **nothing** from :mod:`apeSteel.flexure`), across all three
``D/t`` regimes - compact (Eq. F8-1), noncompact (Eq. F8-2), slender
(Eq. F8-3 / F8-4) - and ``>= 2`` steel grades.  A disagreement means
the library or the oracle transcribed a §F8 equation / constant wrong;
agreement is bit-exact because both implement the same closed forms
from independently written source.  Hard literal snapshots (governing
limit state, wall classification, ``D/t``, the §F8 constants) are
pinned inline as well so any drift is caught even if the oracle moved
in lock-step.

**Tier 2 (external authority - AISC Manual v15.1 Ex. F.9B, Pipe):** the
full published F.9B "Pipe Flexural Member" worked example is now staged
verbatim at
``docs/design_notes/_aisc_src_extract/manual_F9_examples.txt`` (AISC
Manual v15.1 Vol.1, Manual pages F-43/F-44, PDF p.190-191).  The
library §F8 path is driven on the Manual's **published** F.9B section
(Pipe 8 x-Strong, ASTM A53 Gr. B ``Fy = 35 ksi``, AISC Manual
Table 1-14 ``Z = 31.0 in.^3`` and ``D/t = 18.5``) and the result is
checked against the Manual's printed numbers - Table B4.1b Case 20
``lambda_p = 0.07 E/Fy = 58.0``, Eq. F8-1 yielding ``Mn = Fy*Z`` =
"1,090 kip-in." = ``90.4 kip-ft``, and ``phi*Mn = 81.4 kip-ft`` (LRFD)
- to the Manual's 3 printed significant figures.  See the docstring on
:func:`test_F8_manual_v15_1_F9B_*` for the exact provenance boundary
(ENGINEER-CONFIRM **F8-EC-A** is now RESOLVED: the full F.9B body is
staged; no Manual value is invented).

Full AISC-v16-catalog wiring of Pipe / HSS shapes is Phase F-8; §F8
ships here as geometry method + pure calculator + oracle + golden only
(no facade / ``Element`` wiring).
"""

from __future__ import annotations

import math

import pytest

from apeSteel.core import units as u
from apeSteel.core.materials import A36, A992, S355, SteelMaterial
from apeSteel.flexure.F8_round_hss import compute_flexural_strength_F8_round_hss
from apeSteel.sections.flexural_properties import FlexuralSectionProperties
from apeSteel.sections.geometry.round_hss import RoundHSS
from tests.golden._chapterF_F8_oracle import F8OracleProps, mn_F8

REL_TOL = 1e-9

# AISC §F1 strength factors (independent literals, not imported from the
# library, so a typo in apeSteel surfaces here).
_PHI_B = 0.90
_OMEGA_B = 1.67


def _oracle_props(rhss: RoundHSS, mat: SteelMaterial) -> F8OracleProps:
    """Lift the geometry snapshot into the independent oracle's inputs.

    ``Z``/``S`` come from the apeSteel geometry layer (whose round-tube
    closed forms are cross-checked against the compression path's
    ``Ag``/``I`` in the geometry tests); the oracle re-derives only the
    §F8 strength composition, so this is still an independent anchor of
    the Chapter-F math.
    """
    fsp = rhss.compute_section_properties()
    return F8OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        D=fsp.diameter_D,
        t=fsp.wall_thickness_t,
        Z=fsp.plastic_modulus_Zx,
        S=fsp.elastic_modulus_Sx,
    )


# ===========================================================================
# Geometry sanity: the flexure snapshot shares Ag / I / J with the
# (frozen, untouched) compression snapshot bit-for-bit.
# ===========================================================================
def test_F8_geometry_shares_gross_props_with_compression_path() -> None:
    """``compute_section_properties`` must not perturb the §E numbers.

    ``RoundHSS.compute_compression_properties`` is frozen (Phase E).
    The new flexure method re-uses the *identical* ``Ag`` / ``I`` / ``J``
    closed forms; assert they coincide exactly so the additive flexure
    path provably did not disturb the verified compression path, and
    that the axisymmetric equalities (Ix==Iy, Sx==Sy, Zx==Zy, rx==ry)
    hold.
    """
    rhss = RoundHSS(outside_diameter_D=300.0 * u.mm, wall_thickness_t=10.0 * u.mm)
    comp = rhss.compute_compression_properties(A992)
    flex = rhss.compute_section_properties()

    assert flex.gross_area_Ag == comp.gross_area_Ag
    assert flex.moment_of_inertia_Ix == comp.moment_of_inertia_x_Ix
    assert flex.moment_of_inertia_Iy == comp.moment_of_inertia_y_Iy
    assert flex.torsional_constant_J == comp.torsional_constant_J
    assert flex.radius_of_gyration_rx == comp.radius_of_gyration_x_rx
    # Axisymmetry.
    assert flex.moment_of_inertia_Ix == flex.moment_of_inertia_Iy
    assert flex.elastic_modulus_Sx == flex.elastic_modulus_Sy
    assert flex.plastic_modulus_Zx == flex.plastic_modulus_Zy
    assert flex.radius_of_gyration_rx == flex.radius_of_gyration_ry
    assert flex.section_kind == "round_HSS"


def test_F8_geometry_closed_forms_pinned() -> None:
    """Pin the round-tube ``Z``/``S``/``Ag`` closed forms inline.

    Independent re-derivation of the annular section constants for
    ``D=300 mm``, ``t=10 mm`` (``Di=280 mm``):

    * ``Ag  = (pi/4)(D^2 - Di^2)``
    * ``I   = (pi/64)(D^4 - Di^4)``
    * ``S   = 2 I / D``
    * ``Z   = (D^3 - Di^3)/6``
    """
    D, t = 300.0, 10.0
    Di = D - 2.0 * t
    rhss = RoundHSS(outside_diameter_D=D * u.mm, wall_thickness_t=t * u.mm)
    flex = rhss.compute_section_properties()

    expected_Ag = math.pi / 4.0 * (D**2 - Di**2)
    expected_I = math.pi / 64.0 * (D**4 - Di**4)
    expected_S = 2.0 * expected_I / D
    expected_Z = (D**3 - Di**3) / 6.0

    assert math.isclose(flex.gross_area_Ag, expected_Ag, rel_tol=REL_TOL)
    assert math.isclose(flex.moment_of_inertia_Ix, expected_I, rel_tol=REL_TOL)
    assert math.isclose(flex.elastic_modulus_Sx, expected_S, rel_tol=REL_TOL)
    assert math.isclose(flex.plastic_modulus_Zx, expected_Z, rel_tol=REL_TOL)
    # Hard literal snapshot (closed-form, exact rationals where possible).
    assert math.isclose(flex.plastic_modulus_Zx, 841333.3333333334, rel_tol=REL_TOL)


# ===========================================================================
# Tier 1 - library vs independent §F8 oracle, all 3 regimes, >= 2 grades
# ===========================================================================
# Geometries chosen so D/t lands well inside each Table B4.1b Case 20
# band for the given grade (lambda_p = 0.07 E/Fy, lambda_r = 0.31 E/Fy;
# §F8 applicability ceiling 0.45 E/Fy).  For A992 E/Fy = 580.0 exactly
# (29000/50 ksi) -> lambda_p=40.6, lambda_r=179.8, ceiling=261.0.  For
# S355 E/Fy ~= 563.2 -> lambda_p~=39.4, lambda_r~=174.6, ceiling~=253.4.
@pytest.mark.parametrize(
    ("name", "D_mm", "t_mm", "material", "expected_class", "expected_ls"),
    [
        # --- compact (Eq. F8-1, Mn = Mp) ---
        ("A992 compact D/t=30", 300.0, 10.0, A992, "compact", "yielding"),
        ("S355 compact D/t=20", 200.0, 10.0, S355, "compact", "yielding"),
        ("A36 compact D/t=15", 150.0, 10.0, A36, "compact", "yielding"),
        # --- noncompact (Eq. F8-2) ---
        ("A992 NC D/t=100", 600.0, 6.0, A992, "non_compact", "flange_local_buckling"),
        ("S355 NC D/t=80", 480.0, 6.0, S355, "non_compact", "flange_local_buckling"),
        # --- slender (Eq. F8-3 / F8-4) ---
        ("A992 slender D/t=225", 900.0, 4.0, A992, "slender", "flange_local_buckling"),
        ("S355 slender D/t=200", 800.0, 4.0, S355, "slender", "flange_local_buckling"),
    ],
)
def test_F8_matches_independent_oracle_all_regimes(
    name: str,
    D_mm: float,
    t_mm: float,
    material: SteelMaterial,
    expected_class: str,
    expected_ls: str,
) -> None:
    """Library §F8 ``Mn`` == independent oracle, bit-exact, every regime."""
    rhss = RoundHSS(outside_diameter_D=D_mm * u.mm, wall_thickness_t=t_mm * u.mm)
    fsp = rhss.compute_section_properties()

    report = compute_flexural_strength_F8_round_hss(fsp, material)
    oracle = mn_F8(_oracle_props(rhss, material))

    # Primary bit-exact pin.
    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.diameter_to_thickness_ratio_D_t, oracle.D_t, rel_tol=REL_TOL)
    assert math.isclose(report.compact_limit_lambda_p, oracle.lambda_p, rel_tol=REL_TOL)
    assert math.isclose(report.noncompact_limit_lambda_r, oracle.lambda_r, rel_tol=REL_TOL)
    assert math.isclose(report.critical_stress_Fcr, oracle.Fcr, rel_tol=REL_TOL)

    # The regime really is the one intended (so all three branches are
    # genuinely exercised, not just one).
    assert report.wall_classification == expected_class == oracle.classification
    assert report.governing_limit_state == expected_ls == oracle.governing

    # phi / Omega plumbing (independent literals).
    assert report.phi_LRFD == _PHI_B
    assert report.omega_ASD == _OMEGA_B
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_F8_regime_formulae_pinned_inline() -> None:
    """Inline closed-form pins for one representative of each §F8 branch.

    Re-derives Eq. F8-1 / F8-2 / F8-3+F8-4 from scratch (independent of
    both the library and the oracle) and pins the library output to
    them, so a coordinated library+oracle drift is still caught.
    """
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E

    # -- compact: Eq. F8-1  Mn = Mp = Fy*Z --
    rc = RoundHSS(outside_diameter_D=300.0 * u.mm, wall_thickness_t=10.0 * u.mm)
    fc = rc.compute_section_properties()
    mn_c = compute_flexural_strength_F8_round_hss(fc, A992).nominal_flexural_strength_Mn
    assert math.isclose(mn_c, Fy * fc.plastic_modulus_Zx, rel_tol=REL_TOL)

    # -- noncompact: Eq. F8-2  Mn = (0.021 E/(D/t) + Fy) * S --
    rn = RoundHSS(outside_diameter_D=600.0 * u.mm, wall_thickness_t=6.0 * u.mm)
    fn = rn.compute_section_properties()
    D_t_n = fn.diameter_D / fn.wall_thickness_t
    expected_n = (0.021 * E / D_t_n + Fy) * fn.elastic_modulus_Sx
    mn_n = compute_flexural_strength_F8_round_hss(fn, A992).nominal_flexural_strength_Mn
    assert math.isclose(mn_n, expected_n, rel_tol=REL_TOL)

    # -- slender: Eq. F8-3  Mn = Fcr*S, Eq. F8-4  Fcr = 0.33 E/(D/t) --
    rs = RoundHSS(outside_diameter_D=900.0 * u.mm, wall_thickness_t=4.0 * u.mm)
    fs = rs.compute_section_properties()
    D_t_s = fs.diameter_D / fs.wall_thickness_t
    expected_fcr = 0.33 * E / D_t_s
    expected_s = expected_fcr * fs.elastic_modulus_Sx
    rep_s = compute_flexural_strength_F8_round_hss(fs, A992)
    assert math.isclose(rep_s.critical_stress_Fcr, expected_fcr, rel_tol=REL_TOL)
    assert math.isclose(rep_s.nominal_flexural_strength_Mn, expected_s, rel_tol=REL_TOL)


def test_F8_monotonic_in_D_t() -> None:
    """phi*Mn must not increase as the wall gets relatively thinner.

    Sanity guard independent of the oracle: a stockier pipe is never
    weaker than a more slender one of the same diameter & grade.
    """
    D = 600.0 * u.mm
    prev = math.inf
    for t in (16.0, 10.0, 6.0, 4.0, 3.0):
        rhss = RoundHSS(outside_diameter_D=D, wall_thickness_t=t * u.mm)
        phi_mn = compute_flexural_strength_F8_round_hss(
            rhss.compute_section_properties(), A992
        ).phi_strength_LRFD
        assert phi_mn <= prev + 1.0  # +1 N*mm slack for float noise
        prev = phi_mn


# ===========================================================================
# Guard rails
# ===========================================================================
def test_F8_rejects_non_round_hss_kind() -> None:
    """A non-round-HSS snapshot must be refused (no silent wrong number)."""
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
    )
    with pytest.raises(ValueError, match="round HSS"):
        compute_flexural_strength_F8_round_hss(bogus, A992)


def test_F8_rejects_section_outside_applicability_limit() -> None:
    """``D/t >= 0.45 E/Fy`` is outside §F8 - must raise, not return."""
    # A992 ceiling = 0.45 * 580.0 = 261.0; D=2700,t=10 -> D/t=270 > 261.
    rhss = RoundHSS(outside_diameter_D=2700.0 * u.mm, wall_thickness_t=10.0 * u.mm)
    fsp = rhss.compute_section_properties()
    with pytest.raises(ValueError, match="applicability"):
        compute_flexural_strength_F8_round_hss(fsp, A992)
    # And the independent oracle agrees the section is out of scope.
    with pytest.raises(ValueError, match="§F8 applicability"):
        mn_F8(_oracle_props(rhss, A992))


def test_F8_cites_spec_equations_and_case20() -> None:
    """Citations must pin §F8 Eq. F8-1..F8-4 + Table B4.1b Case 20.

    Provenance gate: equation numbers / page verbatim from
    ``spec_chapterF.txt`` (§F8 @ printed 16.1-65), Case 20 CONFIRMED
    (Manual Ex. F.9B) with ``page=None`` per ENGINEER-CONFIRM EC-3.
    """
    rhss = RoundHSS(outside_diameter_D=300.0 * u.mm, wall_thickness_t=10.0 * u.mm)
    rep = compute_flexural_strength_F8_round_hss(rhss.compute_section_properties(), A992)
    pairs = {(c.section, c.equation) for c in rep.cited_clauses}
    assert ("F8.1", "F8-1") in pairs
    assert ("F8.2", "F8-2") in pairs
    assert ("F8.2", "F8-3") in pairs
    assert ("F8.2", "F8-4") in pairs
    assert ("Table B4.1b", "Case 20") in pairs
    f8_pages = {c.page for c in rep.cited_clauses if c.section.startswith("F8")}
    assert f8_pages == {"16.1-65"}
    # Case 20 page is intentionally None (EC-3: B4.1b row page unconfirmed).
    case20 = next(c for c in rep.cited_clauses if c.equation == "Case 20")
    assert case20.page is None


# ===========================================================================
# Tier 2 - AISC Manual v15.1 Example F.9B (Pipe), printed sig-figs
# ===========================================================================
# PROVENANCE BOUNDARY (read before changing these numbers):
#
# The FULL published Example F.9B "Pipe Flexural Member" is staged
# verbatim at
# ``docs/design_notes/_aisc_src_extract/manual_F9_examples.txt``
# (AISC Manual v15.1 Vol.1, Design Examples; Manual pages F-43/F-44,
# PDF p.190-191).  Every number asserted below is quoted from that
# staged extract - nothing is invented or re-derived from a pipe:
#
#   "EXAMPLE F.9B PIPE FLEXURAL MEMBER"                       (p.190)
#   "From AISC Manual Table 2-4 ... ASTM A53 Grade B
#    Fy = 35 ksi   Fu = 60 ksi"                               (p.190)
#   "From AISC Manual Table 1-14, the geometric properties ...
#    Pipe 8 x-Strong   Z = 31.0 in.3   D/t = 18.5"            (p.190)
#   "Determine the limiting diameter-to-thickness ratio for a
#    compact section from AISC Specification Table B4.1b Case 20.
#    0.07 (29,000 ksi)/(35 ksi) = 58.0"                       (p.190)
#   "18.5 < lambda_p ; therefore, the section is compact and the
#    limit state of flange local buckling does not apply"     (p.190)
#   "0.45 (29,000 ksi)/(35 ksi) = 373 > 18.5; therefore, AISC
#    Specification Section F8 applies"                         (p.190)
#   "Based on the limit state of yielding given in AISC
#    Specification Section F8.1:
#    Mn = Mp = Fy Z = 35 ksi (31.0 in.3) = 1,090 kip-in.
#    or 90.4 kip-ft        (Spec. Eq. F8-1)"                  (p.191)
#   "phi_b = 0.90 ... phi_b Mn = 0.90 (90.4 kip-ft)
#    = 81.4 kip-ft"  (LRFD)                                    (p.191)
#   "Omega_b = 1.67 ... Mn/Omega_b = (90.4 kip-ft)/1.67
#    = 54.1 kip-ft"  (ASD)                                     (p.191)
#
# Note the Manual's printed rounding: Fy*Z = 35 * 31.0 = 1085 kip-in
# exactly, which the Manual prints as "1,090 kip-in." (3 sig figs) and
# 1085/12 = 90.4167 kip-ft printed as "90.4 kip-ft"; phi*Mn =
# 0.90 * 90.4167 = 81.375 kip-ft printed as "81.4 kip-ft".  The
# library carries full precision, so the Manual-result comparisons use
# ``math.isclose(..., rel_tol=2e-3)`` - tight enough to catch a wrong
# §F8 equation, loose enough for the Manual's 3-sig-fig rounding.
# ENGINEER-CONFIRM F8-EC-A is RESOLVED by this staged authority.
#
# ASTM A53 Gr. B is not a pre-built apeSteel grade; construct it
# locally from the Manual's stated Fy = 35 ksi (Fu only for trace).
_A53_GrB = SteelMaterial(
    name="ASTM A53 Gr. B",
    yield_stress_Fy=35.0 * u.ksi,
    tensile_stress_Fu=60.0 * u.ksi,
    elastic_modulus_E=A992.elastic_modulus_E,  # AISC E = 29,000 ksi
    shear_modulus_G=A992.shear_modulus_G,
    density_rho=A992.density_rho,
    expected_yield_ratio_Ry=1.6,
    expected_tensile_ratio_Rt=1.2,
)


def _f9b_published_section() -> FlexuralSectionProperties:
    """The Manual F.9B section from its **published** Table 1-14 values.

    AISC Manual v15.1 Ex. F.9B (PDF p.190) quotes, verbatim from AISC
    Manual Table 1-14 for **Pipe 8 x-Strong**:

        ``Z = 31.0 in.^3``        ``D/t = 18.5``

    Those two *published* numbers are exactly what §F8 yielding needs
    (Eq. F8-1 ``Mn = Mp = Fy*Z``; the Case 20 regime split needs only
    ``D/t``).  The section snapshot is therefore built **directly from
    the Manual's published Z and D/t** - it is NOT re-derived from a
    pipe's D and wall (the §F8 calculator reads ``Z``, ``D`` and ``t``
    straight off the snapshot and never recomputes ``Z`` from ``D``,
    ``t``).  ``diameter_D``/``wall_thickness_t`` are set so their ratio
    is *exactly* the published ``D/t = 18.5`` (D = Pipe 8 nominal OD
    8.625 in.; t = D / 18.5); ``S`` is the consistent annular elastic
    modulus carried for trace only (the yielding branch returns
    ``Mn = Fy*Z`` and never reads ``S``).
    """
    Z_pub = 31.0 * u.inches**3  # AISC Manual Table 1-14 (F.9B), published
    D_t_pub = 18.5  # AISC Manual Table 1-14 (F.9B), published
    D = 8.625 * u.inches  # Pipe 8 nominal outside diameter
    t = D / D_t_pub  # set so D/t is EXACTLY the published 18.5
    Di = D - 2.0 * t
    Idiam = math.pi / 64.0 * (D**4 - Di**4)
    S_trace = 2.0 * Idiam / D  # consistent annular S (trace; unused by F8-1)
    return FlexuralSectionProperties(
        section_kind="round_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=D,
        gross_area_Ag=math.pi / 4.0 * (D**2 - Di**2),
        moment_of_inertia_Ix=Idiam,
        elastic_modulus_Sx=S_trace,
        plastic_modulus_Zx=Z_pub,  # the Manual's PUBLISHED Z = 31.0 in^3
        radius_of_gyration_rx=math.sqrt(Idiam / (math.pi / 4.0 * (D**2 - Di**2))),
        moment_of_inertia_Iy=Idiam,
        elastic_modulus_Sy=S_trace,
        plastic_modulus_Zy=Z_pub,
        radius_of_gyration_ry=math.sqrt(Idiam / (math.pi / 4.0 * (D**2 - Di**2))),
        diameter_D=D,
        wall_thickness_t=t,
        plate_elements=(),
    )


def test_F8_manual_v15_1_F9B_case20_lambda_p_matches_printed_58_0() -> None:
    """Manual F.9B prints ``lambda_p = 0.07 E/Fy = 58.0`` (Fy=35 ksi).

    AISC Manual v15.1 Ex. F.9B, Manual p. F-43 (PDF p.190): "Determine
    the limiting diameter-to-thickness ratio for a compact section from
    AISC Specification Table B4.1b Case 20.  0.07 (29,000 ksi)/(35 ksi)
    = 58.0".  The value the F-0 classifier feeds §F8 for the Case 20
    compact limit must equal the Manual's printed **58.0** (the Manual
    prints 3 sig figs; the library carries full precision, so compare
    at the printed precision - an external-authority sig-fig check per
    design note 10 §6).
    """
    rep = compute_flexural_strength_F8_round_hss(_f9b_published_section(), _A53_GrB)
    # 0.07 * 29000 / 35 = 58.0 exactly in ksi (the ksi->MPa factor
    # cancels in E/Fy); pin to the closed form at rel_tol and to the
    # Manual's printed 58.0 at its 3 sig figs.  (math.isclose, not
    # pytest.approx, to hold the Chapter-F pyright/idiom baseline.)
    Fy = _A53_GrB.yield_stress_Fy
    E = _A53_GrB.elastic_modulus_E
    assert math.isclose(rep.compact_limit_lambda_p, 0.07 * E / Fy, rel_tol=REL_TOL)
    assert math.isclose(rep.compact_limit_lambda_p, 58.0, abs_tol=0.05)
    assert round(rep.compact_limit_lambda_p, 1) == 58.0


def test_F8_manual_v15_1_F9B_published_anchor_eq_F8_1_yielding() -> None:
    """AISC Manual v15.1 Ex. F.9B published-result cross-check (Eq. F8-1).

    External-authority anchor (F8-EC-A RESOLVED).  Drive the library
    §F8 path on the Manual's **published** F.9B section (Pipe 8
    x-Strong; AISC Manual Table 1-14 ``Z = 31.0 in.^3``, ``D/t = 18.5``;
    ASTM A53 Gr. B ``Fy = 35 ksi``) and reproduce the Manual's printed
    numbers (AISC Manual v15.1 Vol.1 Ex. F.9B, Manual p. F-43/F-44, PDF
    p.190-191; Spec. Eq. F8-1):

    * Table B4.1b Case 20  ``lambda_p = 0.07 E/Fy = 58.0``;
    * ``D/t = 18.5 < 58.0``  ->  section compact, FLB does not apply;
    * ``0.45 E/Fy = 373 > 18.5``  ->  §F8 applies;
    * Eq. F8-1 yielding  ``Mn = Mp = Fy*Z = 35 ksi (31.0 in.^3)``
      = "1,090 kip-in." = ``90.4 kip-ft`` (Manual printed, 3 sig figs);
    * ``phi*Mn = 0.90 (90.4) = 81.4 kip-ft`` (LRFD);
    * ``Mn/Omega = 90.4/1.67 = 54.1 kip-ft`` (ASD).

    The library carries full precision; ``Fy*Z = 35*31.0 = 1085``
    kip-in is what the Manual rounds and prints as "1,090"/"90.4", so
    the Manual-result comparisons use ``rel_tol=2e-3`` (catches a wrong
    §F8 equation; absorbs the Manual's 3-sig-fig rounding).  The
    closed-form Mn is *also* pinned bit-exactly (``rel_tol=1e-9``)
    against ``Fy*Z`` recomputed here, so the equation itself is locked
    independently of the rounding tolerance.
    """
    fsp = _f9b_published_section()
    rep = compute_flexural_strength_F8_round_hss(fsp, _A53_GrB)

    Fy = _A53_GrB.yield_stress_Fy
    Z_pub = 31.0 * u.inches**3  # AISC Manual Table 1-14 (F.9B), published

    # Published geometry round-trips exactly: D/t == 18.5, Z == 31.0 in^3.
    assert math.isclose(rep.diameter_to_thickness_ratio_D_t, 18.5, rel_tol=REL_TOL)
    assert math.isclose(fsp.plastic_modulus_Zx, Z_pub, rel_tol=REL_TOL)

    # Table B4.1b Case 20 compact limit = Manual's printed 58.0.
    assert math.isclose(rep.compact_limit_lambda_p, 58.0, abs_tol=0.05)
    # 18.5 < 58.0 -> compact -> Eq. F8-1 yielding (the Manual's regime).
    assert rep.diameter_to_thickness_ratio_D_t < rep.compact_limit_lambda_p
    assert rep.wall_classification == "compact"
    assert rep.governing_limit_state == "yielding"

    # Eq. F8-1: Mn = Mp = Fy*Z.  Bit-exact vs the closed form recomputed
    # here (locks the equation), then vs the Manual's printed kip-ft.
    Mp_closed_form = Fy * Z_pub
    assert math.isclose(rep.plastic_moment_Mp, Mp_closed_form, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_flexural_strength_Mn, Mp_closed_form, rel_tol=REL_TOL)

    # Manual printed results, in the Manual's display units (kip-ft).
    # 35*31.0 = 1085 kip-in -> 90.4167 kip-ft; Manual prints "90.4".
    mn_kipft = rep.nominal_flexural_strength_Mn / u.MOMENT_DISPLAY_UNIT_kip_ft
    phi_mn_kipft = rep.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kip_ft
    omega_mn_kipft = rep.omega_strength_ASD / u.MOMENT_DISPLAY_UNIT_kip_ft
    # rel_tol=2e-3 absorbs the Manual's 3-sig-fig rounding
    # (1085->"1,090", 90.4167->"90.4", 81.375->"81.4", 54.14->"54.1").
    assert math.isclose(mn_kipft, 90.4, rel_tol=2e-3)
    assert math.isclose(phi_mn_kipft, 81.4, rel_tol=2e-3)
    assert math.isclose(omega_mn_kipft, 54.1, rel_tol=2e-3)
    # And phi/Omega are exactly the §F1 factors applied to the same Mn.
    assert math.isclose(
        rep.phi_strength_LRFD, _PHI_B * rep.nominal_flexural_strength_Mn, rel_tol=REL_TOL
    )
    assert math.isclose(
        rep.omega_strength_ASD,
        rep.nominal_flexural_strength_Mn / _OMEGA_B,
        rel_tol=REL_TOL,
    )

"""Phase F-6 anchors for AISC 360-22 §F10 (single-angle flexure).

Two-tier anchor per design note 10 §6:

**Tier 1 (primary, bit-exact ``rel_tol=1e-9``):** the library
``compute_flexural_strength_F10_single_angle`` is pinned to the
independent standalone stdlib oracle
:mod:`tests.golden._chapterF_F10_oracle` (which imports **nothing** from
:mod:`apeSteel.flexure`), across: yielding (Eq. F10-1); LTB on the
geometric-axis (Eq. F10-5a compression-toe / F10-5b tension-toe, with
and without §F10.2(b)(ii) restraint) and major-principal-axis
(Eq. F10-4) paths, both ``Mcr``-governing (Eq. F10-3) and
``My``-governing (Eq. F10-2); leg local buckling (compact N/A,
noncompact Eq. F10-6, slender Eq. F10-7/F10-8); equal- *and*
unequal-leg; and ``>= 2`` steel grades.  A disagreement means the
library or the oracle transcribed a §F10 equation / constant wrong;
agreement is bit-exact because both implement the same closed forms
from independently written source.  Inline closed-form pins for one
representative of each branch catch a coordinated library+oracle drift.

**Tier 2 (external authority - AISC Manual v15.1 Ex. F.11A / F.11B /
Ex. F.11C):** the full published single-angle worked examples are
staged verbatim at
``docs/design_notes/_aisc_src_extract/manual_F9_examples.txt`` and
``manual_F11_F12_examples.txt`` (AISC Manual v15.1 Vol.1; Ex. F.11A
Manual p. F-48/F-50, PDF p.195-198; Ex. F.11B Manual p. F-52/F-54, PDF
p.199-201; Ex. F.11C Manual p. F-55/F-59, PDF p.202-207).  The library
§F10 path is driven on the Manual's **published** L4x4x1/4 (ASTM A36,
``Fy = 36 ksi``) section moduli and the printed numbers reproduced to
the Manual's 3 significant figures **and** bit-exactly against the §F10
equation recomputed in-test.

PROVENANCE BOUNDARY (read before changing any number here):

* **CONFIRMED, bit-exact Manual anchors:**
  - Ex. F.11A Eq. F10-1 yielding ``Mn = 1.5*Fy*Sx = 1.5*36*1.03 =
    55.6 kip-in`` (geometric ``Sx`` published in AISC Manual Table 1-7,
    ``manual_F9_examples.txt`` L1127; "(Spec. Eq. F10-1)" L1164).
  - Ex. F.11A Eq. F10-6 leg LB (noncompact leg) ``Mn = Fy*Sc*(2.43 -
    1.72*(b/t)*sqrt(Fy/E)) = 43.3 kip-in`` with ``Sc = 0.80*Sx``,
    ``b/t = 16.0`` (``manual_F11_F12_examples.txt`` L341-461;
    "(Spec. Eq. F10-6)").
  - Ex. F.11C major-principal (W-axis): Eq. F10-1 ``Mnw = 1.5*Fy*SwC =
    95.0 kip-in`` (``manual_F11_F12_examples.txt`` L1488-1510); Eq.
    F10-4 ``Mcr = 195 kip-in`` (equal-leg, ``beta_w = 0``, L1518-1650);
    Eq. F10-2 ``Mnw = (1.92-1.17*sqrt(My/Mcr))*My = 79.4 kip-in``
    (L1654-1736); Eq. F10-6 ``Mnw = 92.5 kip-in`` (L1762-1811).
  - Ex. F.11C minor-principal (Z-axis): Eq. F10-1 ``Mnz = 1.5*Fy*SzB =
    42.0 kip-in``; **no LTB** (§F10 User Note - minor axis); Eq. F10-6
    ``Mnz = 45.0 kip-in`` (``manual_F11_F12_examples.txt`` L1282-1444).

* **ENGINEER-CONFIRM F10-EC-1 RESOLVED - now CONFIRMED, bit-exact
  Manual anchors:** Eq. F10-5a / F10-5b (geometric-axis ``Me``).  The
  authoritative §F10.2(b) form ``Me = 0.58*E*b^4*t*Cb/Lb^2 *
  [sqrt(1+0.88*(Lb*t/b^2)^2) -/+ 1]`` (``- 1`` compression-toe
  Eq. F10-5a, ``+ 1`` tension-toe Eq. F10-5b) is CONFIRMED verbatim
  from ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``
  (printed 16.1-69/70, re-pulled by the orchestrator from
  ``a360-22w.pdf``).  The prior curated ``b*t^2/Lb`` powers were
  correctly REJECTED (wrong dimensions; ~30 not 107).  The verified
  form reproduces, to the printed 3 sig figs:
  - Ex. F.11A (L4x4x1/4, A36, geometric x, max compression at toe, NO
    LT restraint, ``Cb = 1.14``, ``Lb = 6 ft``): ``Mcr = 107 kip-in``
    (Eq. F10-5a); ``My = 0.80*Fy*Sx = 29.7 kip-in``; ``My/Mcr = 0.278
    <= 1`` -> Eq. F10-2 -> ``Mn = 38.7 kip-in``; leg LB ``43.3``;
    governing ``Mn = 38.7 kip-in`` (``manual_F9_examples.txt``
    L1196-1314, "(Spec. Eq. F10-5a)" / "(Spec. Eq. F10-2)").
  - Ex. F.11B (same section, LT restraint at the max-moment point,
    ``Cb = 1.30``, ``Lb = 3 ft``): ``Mcr = 1.25*F10-5a = 176 kip-in``
    (§F10.2(b)(ii)); ``My = Fy*Sx = 37.1 kip-in`` (full, NOT 0.80);
    ``My/Mcr = 0.211`` -> Eq. F10-2 -> ``Mn = 51.3 kip-in``; leg LB
    ``43.3`` governs (``manual_F11_F12_examples.txt`` L637-891).
  Both are wired below as tier-2 published anchors (3-sig-fig printed
  match **and** bit-exact vs the F10-5a/5b equation recomputed
  in-test).  The principal-axis Eq. F10-4 path remains confirmed
  (Ex. F.11C ``Mcr = 195``).

* The published ``b/t = 16.0`` for L4x4x1/4 is the Manual's printed
  value (``manual_F11_F12_examples.txt`` L343-352, "= 4.00 in./(1/4
  in.) = 16.0"); ``Sx``/``SwC``/``SzB``/``SzC`` are the Manual's
  printed Table 1-7 / AISC Shapes Database values - sourced + cited,
  never invented.

Full AISC-v16-catalog wiring of L / 2L shapes to §F10, and any
facade / ``Element`` wiring, are Phase F-8 (design note 10 §5, F-6
line); §F10 ships here as geometry method + pure calculator + oracle +
golden only.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pytest

from apeSteel.core import units as u
from apeSteel.core.materials import A36, A992, S355, SteelMaterial
from apeSteel.flexure.F10_single_angle import (
    SingleAngleBendingMode,
    SingleAngleToeState,
    compute_flexural_strength_F10_single_angle,
)
from apeSteel.sections.flexural_properties import FlexuralSectionProperties
from apeSteel.sections.geometry.single_angle_section import SingleAngleSection
from tests.golden._chapterF_F10_oracle import F10OracleProps, mn_F10

REL_TOL = 1e-9

# AISC §F1 strength factors (independent literals, not imported from the
# library, so a typo in apeSteel surfaces here).
_PHI_B = 0.90
_OMEGA_B = 1.67


# ===========================================================================
# Plate-consistent equal-leg-angle section helper.
#
# An equal-leg L modelled as two rectangles (the geometry class'
# idealization): Ag = t*(2b - t).  Building the FlexuralSectionProperties
# from this *consistent* Ag means the §F10 calculator's t-recovery
# (t = b - sqrt(b^2 - Ag)) returns the input t EXACTLY, so the library,
# the oracle and the in-test recomputation are bit-identical.  Geometric-
# axis Sx/Iz/rz are the equal-leg closed forms (the geometry's own
# forms, re-derived here independently of the apeSteel geometry layer so
# this anchor does not rest on the library's section math).
# ===========================================================================
@dataclass(frozen=True)
class _EqLeg:
    b: float  # leg width (mm)
    t: float  # leg thickness (mm)


def _eq_leg_props(s: _EqLeg) -> dict[str, float]:
    """Equal-leg-angle closed forms (mm units), independent re-derivation.

    Mirrors :meth:`SingleAngleSection.compute_section_properties` (which
    is itself byte-identical to ``compute_compression_properties``); the
    duplication is intentional so a typo in the geometry surfaces as a
    test disagreement.
    """
    b, t = s.b, s.t
    Ag = b * t + (b - t) * t  # = t*(2b - t)
    xbar = (b * t * b / 2.0 + (b - t) * (t / 2.0) * t) / Ag
    ybar = (b * t**2 / 2.0 + (b - t) * t * ((b - t) / 2.0 + t)) / Ag
    Ixg = (
        b * t**3 / 12.0
        + b * t * (ybar - t / 2.0) ** 2
        + t * (b - t) ** 3 / 12.0
        + (b - t) * t * (ybar - ((b - t) / 2.0 + t)) ** 2
    )
    Iyg = (
        t * b**3 / 12.0
        + t * b * (b / 2.0 - xbar) ** 2
        + (b - t) * t**3 / 12.0
        + (b - t) * t * (xbar - t / 2.0) ** 2
    )
    Ixy = b * t * (ybar - t / 2.0) * (b / 2.0 - xbar) + (b - t) * t * (
        ybar - ((b - t) / 2.0 + t)
    ) * (t / 2.0 - xbar)
    avg = (Ixg + Iyg) / 2.0
    I_minor = avg - abs(Ixy)  # Iz
    I_major = avg + abs(Ixy)  # Iw
    rz = math.sqrt(I_minor / Ag)
    c_toe_x = b - ybar
    Sx_geom = Ixg / c_toe_x
    return {
        "b": b,
        "t": t,
        "Ag": Ag,
        "Iz": I_minor,
        "Iw": I_major,
        "rz": rz,
        "Sx_geom": Sx_geom,
        "b_t": b / t,
    }


def _fsp_equal_leg(s: _EqLeg) -> FlexuralSectionProperties:
    """Build the §F10 currency for a plate-consistent equal-leg angle.

    Uses the geometry class directly (its method is the deliverable);
    that method's Ag is exactly ``t*(2b - t)`` so the calculator's
    t-recovery is exact.
    """
    return SingleAngleSection(leg_length=s.b, thickness=s.t).compute_section_properties()


def _oracle(
    s: _EqLeg,
    mat: SteelMaterial,
    *,
    S: float,
    Lb: float,
    Cb: float,
    bending_mode: SingleAngleBendingMode,
    toe_state: SingleAngleToeState = "compression_at_toe",
    lt_restraint: bool = False,
) -> F10OracleProps:
    g = _eq_leg_props(s)
    return F10OracleProps(
        Fy=mat.yield_stress_Fy,
        E=mat.elastic_modulus_E,
        b=g["b"],
        t=g["t"],
        Ag=g["Ag"],
        rz=g["rz"],
        S=S,
        Lb=Lb,
        Cb=Cb,
        bending_mode=bending_mode,
        toe_state=toe_state,
        lt_restraint_at_max_moment=lt_restraint,
    )


# Representative equal-leg angles (mm).  L102x102x6.35 ~= L4x4x1/4.
_L4X4X1_4 = _EqLeg(b=102.0, t=6.35)  # b/t ~= 16.06 -> noncompact (A36)
_L_THICK = _EqLeg(b=80.0, t=12.0)  # b/t ~= 6.67 -> compact (most grades)
_L_SLENDER = _EqLeg(b=200.0, t=6.0)  # b/t ~= 33.3 -> slender (A36/A992)


# ===========================================================================
# Geometry: the §F10 flexure snapshot shares its section math with the
# (frozen, untouched) §E compression snapshot, byte-for-byte.
# ===========================================================================
def test_F10_geometry_shares_section_math_with_compression_path() -> None:
    """``compute_section_properties`` must reuse the §E closed forms.

    ``SingleAngleSection.compute_compression_properties`` is frozen
    (Phase E).  The new flexure method re-uses the *identical* Ag /
    centroid / principal-rotation forms; assert the shared principal
    quantities coincide **exactly** (``==``, not ``isclose``) so the
    additive §F10 path provably did not disturb the verified §E path.
    """
    ang = SingleAngleSection(leg_length=102.0, thickness=6.35)
    comp = ang.compute_compression_properties(A992)
    flex = ang.compute_section_properties()

    # §E stores Ix=I_minor (Iz), Iy=I_major (Iw); §F10 stores them in
    # the principal_* fields.  Byte-identical block -> exact equality.
    assert flex.gross_area_Ag == comp.gross_area_Ag
    assert flex.principal_I_minor_Iz == comp.moment_of_inertia_x_Ix
    assert flex.principal_I_major_Iw == comp.moment_of_inertia_y_Iy
    assert flex.min_principal_radius_rz == comp.min_principal_radius_of_gyration_rz
    assert flex.section_kind == "single_angle"
    assert flex.equal_leg is True
    assert flex.geometric_axis_bending is False


def test_F10_geometry_t_recovery_is_exact() -> None:
    """The calculator's ``t = b - sqrt(b^2 - Ag)`` recovers ``t`` exactly.

    Because the geometry's ``Ag = t*(2b - t)`` is the plate-consistent
    form, the §F10 calculator recovers the leg thickness with no error
    (this is what makes the bit-exact tier-1 / tier-2 pins valid).
    """
    for s in (_L4X4X1_4, _L_THICK, _L_SLENDER):
        fsp = _fsp_equal_leg(s)
        b = fsp.overall_depth_d
        t_recovered = b - math.sqrt(b**2 - fsp.gross_area_Ag)
        assert math.isclose(t_recovered, s.t, rel_tol=REL_TOL)
        assert math.isclose(b, s.b, rel_tol=REL_TOL)


# ===========================================================================
# Tier 1 - library vs independent §F10 oracle (all branches, >=2 grades)
# ===========================================================================
@dataclass(frozen=True)
class _F10Case:
    """One precisely-typed tier-1 §F10 parametrize row.

    A frozen param object (the repo's pervasive style) so every
    argument carries its concrete type into
    :func:`test_F10_matches_independent_oracle` - the
    ``pytest.mark.parametrize`` list is ``list[_F10Case]`` (one type),
    not a heterogeneous tuple inferred as a
    ``str | _EqLeg | SteelMaterial | float | bool`` union.  No ``Any``,
    no ``cast``, no ``# type: ignore``.
    """

    name: str
    shape: _EqLeg
    material: SteelMaterial
    S_mm3: float
    Lb_mm: float
    Cb: float
    mode: SingleAngleBendingMode
    toe: SingleAngleToeState
    lt_restraint: bool
    exp_leg_class: str
    exp_ls: str


@pytest.mark.parametrize(
    "case",
    [
        # --- principal-major LTB, My-governing (Eq. F10-2), compact leg
        #     (no leg LB); long Lb so LTB governs over yielding ---
        _F10Case(
            name="A992 principal-major F10-2 compact",
            shape=_L_THICK,
            material=A992,
            S_mm3=40000.0,
            Lb_mm=6000.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="compact",
            exp_ls="lateral_torsional_buckling",
        ),
        _F10Case(
            name="S355 principal-major F10-2 compact",
            shape=_L_THICK,
            material=S355,
            S_mm3=40000.0,
            Lb_mm=6000.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="compact",
            exp_ls="lateral_torsional_buckling",
        ),
        # --- principal-major LTB, Mcr-governing (Eq. F10-3): very long
        #     Lb makes Me small so My/Me > 1.0 ---
        _F10Case(
            name="A992 principal-major F10-3 (My/Me>1)",
            shape=_L_THICK,
            material=A992,
            S_mm3=40000.0,
            Lb_mm=30000.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="compact",
            exp_ls="lateral_torsional_buckling",
        ),
        # --- short Lb: yielding (Eq. F10-1) governs, compact leg ---
        _F10Case(
            name="A992 yielding governs compact",
            shape=_L_THICK,
            material=A992,
            S_mm3=40000.0,
            Lb_mm=300.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="compact",
            exp_ls="yielding",
        ),
        # --- principal-major LTB, noncompact leg, LTB governs (long
        #     Lb) - exercises LTB + noncompact-leg interaction ---
        _F10Case(
            name="A36 principal-major LTB noncompact-leg",
            shape=_L4X4X1_4,
            material=A36,
            S_mm3=16879.0,
            Lb_mm=9000.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="non_compact",
            exp_ls="lateral_torsional_buckling",
        ),
        # --- S355 principal-major, short Lb, noncompact leg, leg-LB
        #     governs (3rd grade on the leg-LB branch) ---
        _F10Case(
            name="S355 noncompact-leg F10-6 governs",
            shape=_L4X4X1_4,
            material=S355,
            S_mm3=16879.0,
            Lb_mm=300.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="non_compact",
            exp_ls="leg_local_buckling",
        ),
        # --- leg local buckling governs: slender leg, short Lb ---
        _F10Case(
            name="A992 slender-leg leg-LB governs",
            shape=_L_SLENDER,
            material=A992,
            S_mm3=60000.0,
            Lb_mm=300.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="slender",
            exp_ls="leg_local_buckling",
        ),
        _F10Case(
            name="A36 slender-leg leg-LB governs",
            shape=_L_SLENDER,
            material=A36,
            S_mm3=60000.0,
            Lb_mm=300.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="slender",
            exp_ls="leg_local_buckling",
        ),
        # --- noncompact leg, leg-LB (Eq. F10-6) governs vs yielding,
        #     short Lb ---
        _F10Case(
            name="A992 noncompact-leg F10-6 governs",
            shape=_L4X4X1_4,
            material=A992,
            S_mm3=16879.0,
            Lb_mm=300.0,
            Cb=1.0,
            mode="principal_major",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="non_compact",
            exp_ls="leg_local_buckling",
        ),
        # --- minor principal axis: NO LTB (User Note); yielding governs
        #     (compact leg) ---
        _F10Case(
            name="A992 minor-principal yielding (no LTB)",
            shape=_L_THICK,
            material=A992,
            S_mm3=18000.0,
            Lb_mm=6000.0,
            Cb=1.0,
            mode="principal_minor",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="compact",
            exp_ls="yielding",
        ),
        # --- tension at toe: leg LB does NOT apply (toe not in
        #     compression); LTB governs ---
        _F10Case(
            name="A992 principal-major tension-at-toe (no leg LB)",
            shape=_L_SLENDER,
            material=A992,
            S_mm3=60000.0,
            Lb_mm=12000.0,
            Cb=1.0,
            mode="principal_major",
            toe="tension_at_toe",
            lt_restraint=False,
            exp_leg_class="slender",
            exp_ls="lateral_torsional_buckling",
        ),
        # --- geometric-axis LTB, Eq. F10-5a (compression at the toe),
        #     no LT restraint (My = 0.80*Fy*Sx); long Lb so LTB governs
        #     (F10-EC-1 RESOLVED) - compact leg so leg LB is N/A ---
        _F10Case(
            name="A36 geometric F10-5a compr-toe no-restraint LTB",
            shape=_L_THICK,
            material=A36,
            S_mm3=40000.0,
            Lb_mm=9000.0,
            Cb=1.0,
            mode="geometric",
            toe="compression_at_toe",
            lt_restraint=False,
            exp_leg_class="compact",
            exp_ls="lateral_torsional_buckling",
        ),
        # --- geometric-axis LTB, Eq. F10-5b (tension at the toe): leg
        #     LB N/A (toe not in compression); My = 0.80*Fy*Sx ---
        _F10Case(
            name="A992 geometric F10-5b tension-toe LTB",
            shape=_L_THICK,
            material=A992,
            S_mm3=40000.0,
            Lb_mm=9000.0,
            Cb=1.0,
            mode="geometric",
            toe="tension_at_toe",
            lt_restraint=False,
            exp_leg_class="compact",
            exp_ls="lateral_torsional_buckling",
        ),
        # --- geometric-axis, LT restraint at the max-moment point
        #     (§F10.2(b)(ii): Mcr x 1.25, My = full Fy*Sx, NOT 0.80);
        #     Lb chosen so LTB strictly governs - exercises the
        #     restraint My-basis + the 1.25 Mcr factor ---
        _F10Case(
            name="A36 geometric restraint-at-max-moment LTB",
            shape=_L_THICK,
            material=A36,
            S_mm3=40000.0,
            Lb_mm=6000.0,
            Cb=1.30,
            mode="geometric",
            toe="compression_at_toe",
            lt_restraint=True,
            exp_leg_class="compact",
            exp_ls="lateral_torsional_buckling",
        ),
        # --- geometric-axis, restraint at max moment, noncompact leg
        #     (Sc = full Sx, NOT 0.80, since there IS LT restraint); the
        #     §F10.3 Eq. F10-6 leg-LB path is exercised (pinned bit-exact
        #     vs the oracle) while LTB governs the composite Mn - the
        #     geometric-axis F10-5a Me is bounded as Lb->0 so LTB always
        #     undercuts leg LB for this proportion (verified by hand) ---
        _F10Case(
            name="A36 geometric restraint noncompact-leg (F10-6 path, LTB governs)",
            shape=_L4X4X1_4,
            material=A36,
            S_mm3=16879.0,
            Lb_mm=600.0,
            Cb=1.30,
            mode="geometric",
            toe="compression_at_toe",
            lt_restraint=True,
            exp_leg_class="non_compact",
            exp_ls="lateral_torsional_buckling",
        ),
    ],
)
def test_F10_matches_independent_oracle(case: _F10Case) -> None:
    """Library §F10 ``Mn`` == independent oracle, bit-exact, every branch."""
    shape = case.shape
    material = case.material
    fsp = _fsp_equal_leg(shape)
    report = compute_flexural_strength_F10_single_angle(
        fsp,
        material,
        unbraced_length_Lb=case.Lb_mm,
        Cb=case.Cb,
        bending_mode=case.mode,
        toe_state=case.toe,
        section_modulus_S=case.S_mm3,
        lateral_torsional_restraint_at_max_moment=case.lt_restraint,
    )
    oracle = mn_F10(
        _oracle(
            shape,
            material,
            S=case.S_mm3,
            Lb=case.Lb_mm,
            Cb=case.Cb,
            bending_mode=case.mode,
            toe_state=case.toe,
            lt_restraint=case.lt_restraint,
        )
    )

    # Primary bit-exact pins (the regression spine).
    assert math.isclose(report.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    # §F10.1 basis (full Fy*S) and the §F10.2 LTB basis (0.80-reduced
    # only for geometric / no-LT-restraint) are pinned separately.
    assert math.isclose(report.yield_moment_My, oracle.My_yield, rel_tol=REL_TOL)
    assert math.isclose(report.yield_moment_for_LTB_My, oracle.My, rel_tol=REL_TOL)
    assert math.isclose(report.yielding_moment_Mn_F10_1, oracle.Mn_F10_1, rel_tol=REL_TOL)
    assert math.isclose(report.elastic_LTB_moment_Me, oracle.Me, rel_tol=REL_TOL)
    assert math.isclose(report.LTB_moment_Mn_F10_2_3, oracle.Mn_LTB, rel_tol=REL_TOL)
    assert math.isclose(report.leg_slenderness_b_t, oracle.b_t, rel_tol=REL_TOL)
    assert math.isclose(report.leg_compact_limit_lambda_p, oracle.lambda_p, rel_tol=REL_TOL)
    assert math.isclose(report.leg_noncompact_limit_lambda_r, oracle.lambda_r, rel_tol=REL_TOL)
    assert math.isclose(report.section_modulus_to_compression_toe_Sc, oracle.Sc, rel_tol=REL_TOL)
    assert math.isclose(report.leg_LB_critical_stress_Fcr, oracle.Fcr, rel_tol=REL_TOL)
    assert math.isclose(report.leg_LB_moment_Mn_F10_6_7, oracle.Mn_leg_LB, rel_tol=REL_TOL)

    # The regime / leg class really is the one intended (so every branch
    # is genuinely exercised, not just one).
    assert report.leg_classification == case.exp_leg_class == oracle.leg_classification
    assert report.governing_limit_state == case.exp_ls == oracle.governing

    # phi / Omega plumbing (independent literals).
    assert report.phi_LRFD == _PHI_B
    assert report.omega_ASD == _OMEGA_B
    assert math.isclose(report.phi_strength_LRFD, _PHI_B * oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(report.omega_strength_ASD, oracle.Mn / _OMEGA_B, rel_tol=REL_TOL)


def test_F10_regime_formulae_pinned_inline() -> None:
    """Inline closed-form pins for one representative of each §F10 branch.

    Re-derives Eq. F10-1 / F10-2 / F10-4 / F10-6 / F10-8 from scratch
    (independent of both the library and the oracle) and pins the
    library output to them, so a coordinated library+oracle drift is
    still caught.
    """
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E

    # -- yielding: Eq. F10-1  Mn = 1.5*Fy*S (principal) --
    s = _L_THICK
    g = _eq_leg_props(s)
    S = 18000.0
    rep_y = compute_flexural_strength_F10_single_angle(
        _fsp_equal_leg(s),
        A992,
        unbraced_length_Lb=300.0,
        Cb=1.0,
        bending_mode="principal_major",
        section_modulus_S=S,
    )
    assert math.isclose(rep_y.yielding_moment_Mn_F10_1, 1.5 * Fy * S, rel_tol=REL_TOL)

    # -- Eq. F10-4 (equal-leg, beta_w=0): Me = 9*E*A*rz*t*Cb/(8*Lb) --
    Lb, Cb = 6000.0, 1.0
    Me_expected = 9.0 * E * g["Ag"] * g["rz"] * g["t"] * Cb / (8.0 * Lb)
    rep_ltb = compute_flexural_strength_F10_single_angle(
        _fsp_equal_leg(s),
        A992,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="principal_major",
        section_modulus_S=40000.0,
    )
    assert math.isclose(rep_ltb.elastic_LTB_moment_Me, Me_expected, rel_tol=REL_TOL)
    # Eq. F10-2: My/Me <= 1.0 -> Mn = (1.92 - 1.17*sqrt(My/Me))*My,
    # capped at 1.5*My.
    My = Fy * 40000.0
    if My / Me_expected <= 1.0:
        mn_f10_2 = min((1.92 - 1.17 * math.sqrt(My / Me_expected)) * My, 1.5 * My)
        assert math.isclose(rep_ltb.LTB_moment_Mn_F10_2_3, mn_f10_2, rel_tol=REL_TOL)

    # -- Eq. F10-3 (My/Me > 1.0): Mn = (0.92 - 0.17*Me/My)*Me --
    Lb_long = 30000.0
    Me_long = 9.0 * E * g["Ag"] * g["rz"] * g["t"] * 1.0 / (8.0 * Lb_long)
    My3 = Fy * 40000.0
    assert My3 / Me_long > 1.0  # genuinely the Eq. F10-3 branch
    rep3 = compute_flexural_strength_F10_single_angle(
        _fsp_equal_leg(s),
        A992,
        unbraced_length_Lb=Lb_long,
        Cb=1.0,
        bending_mode="principal_major",
        section_modulus_S=40000.0,
    )
    mn_f10_3 = (0.92 - 0.17 * Me_long / My3) * Me_long
    assert math.isclose(rep3.LTB_moment_Mn_F10_2_3, mn_f10_3, rel_tol=REL_TOL)

    # -- Eq. F10-6 (noncompact leg): Mn = Fy*Sc*(2.43 - 1.72*(b/t)*
    #    sqrt(Fy/E)) --
    sN = _L4X4X1_4
    gN = _eq_leg_props(sN)
    ScN = 16879.0
    rep6 = compute_flexural_strength_F10_single_angle(
        _fsp_equal_leg(sN),
        A992,
        unbraced_length_Lb=300.0,
        Cb=1.0,
        bending_mode="principal_major",
        section_modulus_S=ScN,
    )
    assert rep6.leg_classification == "non_compact"
    mn_f10_6 = Fy * ScN * (2.43 - 1.72 * gN["b_t"] * math.sqrt(Fy / E))
    assert math.isclose(rep6.leg_LB_moment_Mn_F10_6_7, mn_f10_6, rel_tol=REL_TOL)

    # -- Eq. F10-7/F10-8 (slender leg): Fcr = 0.71*E/(b/t)^2,
    #    Mn = Fcr*Sc --
    sS = _L_SLENDER
    gS = _eq_leg_props(sS)
    ScS = 60000.0
    rep8 = compute_flexural_strength_F10_single_angle(
        _fsp_equal_leg(sS),
        A992,
        unbraced_length_Lb=300.0,
        Cb=1.0,
        bending_mode="principal_major",
        section_modulus_S=ScS,
    )
    assert rep8.leg_classification == "slender"
    fcr = 0.71 * E / gS["b_t"] ** 2
    assert math.isclose(rep8.leg_LB_critical_stress_Fcr, fcr, rel_tol=REL_TOL)
    assert math.isclose(rep8.leg_LB_moment_Mn_F10_6_7, fcr * ScS, rel_tol=REL_TOL)


def test_F10_minor_principal_axis_has_no_LTB() -> None:
    """§F10 User Note: minor principal axis -> only yielding + leg LB.

    Independent of the oracle: the minor-principal-axis report must
    expose ``Me == 0`` / ``Mn_LTB == 0`` and never select LTB as the
    governing limit state (even with a long unbraced length that would
    make a major-axis member LTB-govern).
    """
    fsp = _fsp_equal_leg(_L_THICK)
    rep = compute_flexural_strength_F10_single_angle(
        fsp,
        A992,
        unbraced_length_Lb=30000.0,  # very long: would govern LTB if it applied
        Cb=1.0,
        bending_mode="principal_minor",
        section_modulus_S=18000.0,
    )
    assert rep.elastic_LTB_moment_Me == 0.0
    assert rep.LTB_moment_Mn_F10_2_3 == 0.0
    assert rep.governing_limit_state in ("yielding", "leg_local_buckling")


def test_F10_leg_LB_only_when_toe_in_compression() -> None:
    """§F10.3 applies only when the toe of the leg is in compression.

    A slender-leg angle with *tension* at the toe must NOT take a leg-LB
    reduction (``Mn_leg_LB == 0``); with compression at the toe (same
    geometry) it must.
    """
    s = _L_SLENDER
    rep_t = compute_flexural_strength_F10_single_angle(
        _fsp_equal_leg(s),
        A992,
        unbraced_length_Lb=600.0,
        Cb=1.0,
        bending_mode="principal_major",
        toe_state="tension_at_toe",
        section_modulus_S=55000.0,
    )
    rep_c = compute_flexural_strength_F10_single_angle(
        _fsp_equal_leg(s),
        A992,
        unbraced_length_Lb=600.0,
        Cb=1.0,
        bending_mode="principal_major",
        toe_state="compression_at_toe",
        section_modulus_S=55000.0,
    )
    assert rep_t.leg_LB_moment_Mn_F10_6_7 == 0.0
    assert rep_t.section_modulus_to_compression_toe_Sc == 0.0
    assert rep_c.leg_LB_moment_Mn_F10_6_7 > 0.0
    assert rep_c.governing_limit_state == "leg_local_buckling"


def test_F10_monotonic_in_Lb_principal_major() -> None:
    """phi*Mn must not increase as the unbraced length grows.

    Sanity guard independent of the oracle: a longer unbraced length is
    never stronger for the LTB-controlled principal-major path.
    """
    s = _L_THICK
    prev = math.inf
    for lb in (300.0, 1500.0, 3000.0, 6000.0, 12000.0, 30000.0):
        rep = compute_flexural_strength_F10_single_angle(
            _fsp_equal_leg(s),
            A992,
            unbraced_length_Lb=lb,
            Cb=1.0,
            bending_mode="principal_major",
            section_modulus_S=40000.0,
        )
        assert rep.phi_strength_LRFD <= prev + 1.0  # +1 N*mm float slack
        prev = rep.phi_strength_LRFD


# ===========================================================================
# Unequal-leg coverage (the geometry class is equal-leg-only; build the
# §F10 currency directly with equal_leg=False to exercise the
# unequal-leg yielding + leg-LB path and the geometric-axis guard rail).
# ===========================================================================
def _fsp_unequal_leg(*, b: float, t: float, Ag: float) -> FlexuralSectionProperties:
    """Minimal unequal-leg ``single_angle`` snapshot.

    Only the §F10 yielding + leg-LB path is exercised for an unequal-leg
    angle here (those limit states do not depend on the principal-axis
    LTB constants); ``Ag = t*(2b - t)`` keeps the calculator's
    t-recovery exact.  Principal-axis LTB of an *unequal*-leg angle
    needs the full Eq. F10-4 with ``beta_w != 0`` (the library
    implements only the equal-leg ``beta_w = 0`` collapse; the general
    ``beta_w`` term is out of the F-6 scope), so it is deliberately not
    asserted.  (Geometric-axis Eq. F10-5a/F10-5b is equal-leg-only and
    fully delivered - F10-EC-1 RESOLVED.)
    """
    return FlexuralSectionProperties(
        section_kind="single_angle",
        symmetry="singly_symmetric",
        overall_depth_d=b,
        gross_area_Ag=Ag,
        moment_of_inertia_Ix=1.0,
        elastic_modulus_Sx=1.0,
        plastic_modulus_Zx=1.0,
        radius_of_gyration_rx=1.0,
        moment_of_inertia_Iy=1.0,
        elastic_modulus_Sy=1.0,
        plastic_modulus_Zy=1.0,
        radius_of_gyration_ry=1.0,
        principal_I_major_Iw=1.0,
        principal_I_minor_Iz=1.0,
        min_principal_radius_rz=1.0,
        equal_leg=False,
        geometric_axis_bending=False,
        plate_elements=(),
    )


def test_F10_unequal_leg_yielding_and_leg_LB_matches_oracle() -> None:
    """Unequal-leg single angle: yielding + leg-LB path == oracle.

    Covers ``equal_leg=False`` for the limit states that do not need the
    equal-leg principal-axis Eq. F10-4 (yielding Eq. F10-1, leg LB
    Eq. F10-6/F10-7/F10-8).  Uses the minor principal axis so LTB does
    not apply (§F10 User Note) - this isolates the unequal-leg yielding
    + leg-LB composition cleanly.
    """
    b, t = 150.0, 8.0  # b/t = 18.75
    Ag = t * (2.0 * b - t)
    fsp = _fsp_unequal_leg(b=b, t=t, Ag=Ag)
    S = 22000.0
    rep = compute_flexural_strength_F10_single_angle(
        fsp,
        A992,
        unbraced_length_Lb=4000.0,
        Cb=1.0,
        bending_mode="principal_minor",  # no LTB -> isolates yield + leg LB
        section_modulus_S=S,
    )
    # Oracle with the same plate-consistent (b, t, Ag); minor axis -> no
    # LTB, so the principal-LTB constants are irrelevant.
    oracle = mn_F10(
        F10OracleProps(
            Fy=A992.yield_stress_Fy,
            E=A992.elastic_modulus_E,
            b=b,
            t=t,
            Ag=Ag,
            rz=1.0,  # unused (minor axis -> no LTB)
            S=S,
            Lb=4000.0,
            Cb=1.0,
            bending_mode="principal_minor",
            toe_state="compression_at_toe",
            lt_restraint_at_max_moment=False,
        )
    )
    assert math.isclose(rep.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(rep.yielding_moment_Mn_F10_1, oracle.Mn_F10_1, rel_tol=REL_TOL)
    assert math.isclose(rep.leg_LB_moment_Mn_F10_6_7, oracle.Mn_leg_LB, rel_tol=REL_TOL)
    assert rep.leg_classification == oracle.leg_classification
    assert rep.elastic_LTB_moment_Me == 0.0  # minor axis: no LTB
    assert rep.governing_limit_state == oracle.governing


def test_F10_geometric_axis_rejected_for_unequal_leg() -> None:
    """§F10 permits geometric-axis design only for equal-leg angles.

    An unequal-leg angle with ``bending_mode="geometric"`` must raise
    (not silently return a number using the equal-leg F10-5a form).
    """
    fsp = _fsp_unequal_leg(b=150.0, t=8.0, Ag=8.0 * (2.0 * 150.0 - 8.0))
    # RUF043: "equal-leg" / "geometric-axis" contain "-" (regex range
    # metachar); escape each literal alternative rather than ship a raw
    # pattern.
    msg_pattern = "|".join(re.escape(s) for s in ("equal-leg", "geometric-axis"))
    with pytest.raises(ValueError, match=msg_pattern):
        compute_flexural_strength_F10_single_angle(
            fsp,
            A992,
            unbraced_length_Lb=3000.0,
            Cb=1.0,
            bending_mode="geometric",
            section_modulus_S=20000.0,
        )


# ===========================================================================
# Guard rails
# ===========================================================================
def test_F10_rejects_non_single_angle_kind() -> None:
    """A non-single-angle snapshot must be refused (no silent number)."""
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
    with pytest.raises(ValueError, match="single angle"):
        compute_flexural_strength_F10_single_angle(
            bogus,
            A992,
            unbraced_length_Lb=3000.0,
            section_modulus_S=1000.0,
        )


def test_F10_rejects_nonpositive_Lb_and_S() -> None:
    """Non-positive ``Lb`` / ``S`` must raise (the LTB eqns divide by Lb)."""
    fsp = _fsp_equal_leg(_L_THICK)
    with pytest.raises(ValueError, match="unbraced_length_Lb"):
        compute_flexural_strength_F10_single_angle(
            fsp, A992, unbraced_length_Lb=0.0, section_modulus_S=1000.0
        )
    with pytest.raises(ValueError, match="section_modulus_S"):
        compute_flexural_strength_F10_single_angle(
            fsp, A992, unbraced_length_Lb=3000.0, section_modulus_S=0.0
        )


def test_F10_cites_spec_equations_and_leg_case() -> None:
    """Citations must pin §F10 Eq. F10-1..F10-8 + the leg B4.1b row.

    Provenance gate (design note §9): F10-6/F10-7/F10-8 CONFIRMED
    verbatim (printed 16.1-70); **F10-5a/F10-5b CONFIRMED verbatim from
    ``spec_F10_geometric.txt``** (printed 16.1-69/F10-5a, 16.1-70/
    F10-5b prose) - **ENGINEER-CONFIRM F10-EC-1 RESOLVED**; F10-1..
    F10-4 are still on the printed 16.1-69 ABSENT from
    ``spec_chapterF.txt`` -> ``page=None`` (EC-9, numerically
    Manual-confirmed); the single-angle-leg B4.1b case label is
    UNVERIFIED -> ``"Case ?"`` / ``page=None`` (EC-4/EC-10).  Nothing
    is invented.
    """
    fsp = _fsp_equal_leg(_L_THICK)
    rep = compute_flexural_strength_F10_single_angle(
        fsp,
        A992,
        unbraced_length_Lb=3000.0,
        Cb=1.0,
        bending_mode="principal_major",
        section_modulus_S=20000.0,
    )
    pairs = {(c.section, c.equation) for c in rep.cited_clauses}
    for eq in ("F10-1", "F10-2", "F10-3", "F10-4", "F10-5a", "F10-5b"):
        assert ("F10.1", eq) in pairs or ("F10.2", eq) in pairs
    assert ("F10.3", "F10-6") in pairs
    assert ("F10.3", "F10-7") in pairs
    assert ("F10.3", "F10-8") in pairs
    assert ("Table B4.1b", "Case ?") in pairs

    by_eq = {c.equation: c for c in rep.cited_clauses}
    # F10-6/F10-7/F10-8 pages CONFIRMED 16.1-70.
    for eq in ("F10-6", "F10-7", "F10-8"):
        assert by_eq[eq].page == "16.1-70"
    # F10-EC-1 RESOLVED: F10-5a CONFIRMED 16.1-69, F10-5b CONFIRMED
    # 16.1-70 (both verbatim from spec_F10_geometric.txt).
    assert by_eq["F10-5a"].page == "16.1-69"
    assert by_eq["F10-5b"].page == "16.1-70"
    # F10-1..F10-4 still on the 16.1-69 ABSENT from spec_chapterF.txt
    # -> page=None (EC-9; numerically Manual-confirmed).
    for eq in ("F10-1", "F10-2", "F10-3", "F10-4"):
        assert by_eq[eq].page is None
    # Single-angle-leg B4.1b case label unverified -> page=None.
    assert by_eq["Case ?"].page is None


# ===========================================================================
# Tier 2 - AISC Manual v15.1 Ex. F.11A / F.11B / Ex. F.11C (single
#          angle), printed sig-figs + bit-exact in-test recomputation.
#          Ex. F.11A/F.11B also anchor the F10-EC-1 RESOLVED
#          geometric-axis Eq. F10-5a/F10-5b path (107 / 176 kip-in).
# ===========================================================================
#: AISC Manual v15.1 single-angle examples print Mn to 3 sig figs (e.g.
#: "55.6 kip-in" from the exact 55.62; "95.0" from 95.04).  5e-3 absorbs
#: the 3-sig-fig display rounding (one example, "195"/"196", rounds a
#: digit coarser when built from the plate-consistent Ag - see the
#: anchor docstrings) while still catching a wrong §F10 coefficient; the
#: bit-exact in-test recomputation provides the tight equation pin.
_MANUAL_REL_TOL = 5e-3

# AISC Manual v15.1 published L4x4x1/4 / A36 values (verbatim; in.->mm).
# Ex. F.11A geometric Sx (AISC Manual Table 1-7, manual_F9_examples.txt
# L1127).  Ex. F.11C principal SwC / SzB / SzC (AISC Shapes Database,
# manual_F11_F12_examples.txt L1278-1280) + the published b/t = 16.0
# (L343-352) and Fy = 36 ksi (A36).
_F11_L4_SX_IN3 = 1.03  # geometric x-axis, Ex. F.11A (Table 1-7)
_F11C_SWC_IN3 = 1.76  # principal major (w) to toe C, Ex. F.11C
_F11C_SZB_IN3 = 0.778  # principal minor (z) to point B, Ex. F.11C (yield)
_F11C_SZC_IN3 = 0.856  # principal minor (z) to toe C, Ex. F.11C (leg LB)

# L4x4x1/4: b = 4.00 in, t = 1/4 in (the Manual's stated dims; Ex. F.11A
# "b/t = 4.00 in./(1/4 in.) = 16.0").  Plate-consistent Ag = t*(2b - t)
# so the §F10 calculator recovers t = 0.25 in EXACTLY.
_F11_B_IN = 4.00
_F11_T_IN = 0.25


def _f11_L4_equal_leg() -> _EqLeg:
    """L4x4x1/4 as the plate-consistent equal-leg shape (mm)."""
    return _EqLeg(b=_F11_B_IN * u.inches, t=_F11_T_IN * u.inches)


def test_F10_manual_v15_1_F11A_yielding_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.11A published cross-check (Eq. F10-1).

    External-authority anchor for the §F10 **yielding** limit state
    (Eq. F10-1).  Ex. F.11A: L4x4x1/4, ASTM A36 (``Fy = 36 ksi``),
    geometric x-axis, no lateral-torsional restraint, toe in
    compression (Manual p. F-48/F-50, PDF p.195-198;
    ``manual_F9_examples.txt`` L1028-1364, ``manual_F11_F12_examples
    .txt`` L1-479).  Manual prints, from AISC Manual Table 1-7,
    ``Sx = 1.03 in.^3``, and "Mn = 1.5 My = 1.5 Fy Sx = 1.5 (36 ksi)
    (1.03 in.3) = 55.6 kip-in.  (Spec. Eq. F10-1)".

    Eq. F10-1 yielding is ``Mn = 1.5*My`` with ``My = Fy*Sx`` (the
    **full** geometric ``Sx``: the §F10.2 0.80 reduction does NOT apply
    to Eq. F10-1 - the Manual prints F10-1 from the full ``Fy*Sx`` and,
    *separately*, "My = 0.80 Fy Sx = 29.7 kip-in." under LTB).  The
    library's ``My_yield`` is **always** ``Fy*S`` and is mode-
    independent, so Eq. F10-1 is anchored here via the **principal-major
    mode** (whose composite ``Mn`` IS computable - Eq. F10-4); a short
    ``Lb`` makes yielding the governing state so the reported
    ``Mn == 1.5*Fy*Sx`` equals the Manual's "55.6 kip-in" exactly.

    Ex. F.11A's *actual* configuration is geometric-axis, whose LTB
    (Eq. F10-5a, Manual ``Mcr = 107`` -> governing ``Mn = 38.7`` via
    F10-2) and leg-LB (Eq. F10-6 with ``Sc = 0.80*Sx``, Manual ``43.3``)
    are anchored in full in
    :func:`test_F10_manual_v15_1_F11A_geometric_axis_published_anchor`
    (the geometric-axis calculator path is **fully delivered** -
    F10-EC-1 RESOLVED, Eq. F10-5a CONFIRMED verbatim from
    ``spec_F10_geometric.txt``).  This test independently anchors the
    mode-independent §F10.1 yielding *value* (55.6) via the
    principal-major mode.
    """
    s = _f11_L4_equal_leg()
    fsp = _fsp_equal_leg(s)
    Fy = A36.yield_stress_Fy
    Sx = _F11_L4_SX_IN3 * u.inches**3

    # Principal-major mode (its composite Mn IS computable, Eq. F10-4);
    # short Lb so LTB caps at the yield plateau, and tension-at-toe so
    # the §F10.3 leg-LB limit state does not apply (it would otherwise
    # slightly undercut yielding for this noncompact-leg L4x4x1/4 with
    # Sc=Sx) - this isolates Eq. F10-1 yielding as the governing /
    # reported Mn.  The asserted quantity, My_yield = Fy*Sx, is
    # mode- *and* toe-independent, so Eq. F10-1 == the Manual's
    # "1.5 Fy Sx = 55.6 kip-in" exactly.
    rep = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=150.0,
        Cb=1.0,
        bending_mode="principal_major",
        toe_state="tension_at_toe",
        section_modulus_S=Sx,
    )

    expected_mn_f10_1 = 1.5 * Fy * Sx
    # Bit-exact vs Eq. F10-1 recomputed in-test from the published Sx
    # (locks the equation independent of the Manual's 3-sig-fig print).
    assert math.isclose(rep.yielding_moment_Mn_F10_1, expected_mn_f10_1, rel_tol=REL_TOL)
    assert math.isclose(rep.yield_moment_My, Fy * Sx, rel_tol=REL_TOL)
    # Short Lb -> Eq. F10-1 yielding is the governing/ reported Mn.
    assert rep.governing_limit_state == "yielding"
    assert math.isclose(rep.nominal_flexural_strength_Mn, expected_mn_f10_1, rel_tol=REL_TOL)
    mn1_kipin = rep.yielding_moment_Mn_F10_1 / (u.kip * u.inches)
    # Manual L1143-1164: "Mn = 1.5 My = 1.5 Fy Sx = 1.5 (36 ksi)
    # (1.03 in.3) = 55.6 kip-in.  (Spec. Eq. F10-1)".
    assert math.isclose(mn1_kipin, 55.6, rel_tol=_MANUAL_REL_TOL)
    # phi/Omega plumbing on the Manual-anchored value.
    assert math.isclose(
        rep.phi_strength_LRFD, _PHI_B * rep.nominal_flexural_strength_Mn, rel_tol=REL_TOL
    )
    assert math.isclose(
        rep.omega_strength_ASD,
        rep.nominal_flexural_strength_Mn / _OMEGA_B,
        rel_tol=REL_TOL,
    )


def test_F10_manual_v15_1_F11C_principal_axis_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.11C published cross-check (F10-1/F10-2/F10-4).

    External-authority anchor for the **major-principal-axis** LTB
    path (Eq. F10-4; the geometric-axis Eq. F10-5a/F10-5b path is
    separately Manual-anchored to Ex. F.11A/F.11B - F10-EC-1
    RESOLVED).  Ex. F.11C: L4x4x1/4, ASTM A36 (``Fy = 36 ksi``),
    equal-leg, no continuous LT restraint (Manual p. F-58/F-59, PDF
    p.205-207; ``manual_F11_F12_examples.txt`` L1484-1815).  W-axis,
    published ``SwC = 1.76 in.^3``:

    * Eq. F10-1 ``Mnw = 1.5*Fy*SwC = 1.5 (36)(1.76) = 95.0 kip-in.``
      (Manual L1488-1510, "(from Spec. Eq. F10-1)").
    * Eq. F10-4 ``Mcr`` (equal-leg, ``beta_w = 0``): ``Mcr =
      9*E*A*rz*t*Cb/(8*Lb)``; the Manual prints "195 kip-in." for
      ``Cb = 1.14``, ``Lb = 6 ft``.  apeSteel reproduces this on the
      plate-consistent ``Ag = t*(2b - t)`` (which differs from the
      Manual's catalog ``A = 1.93 in.^2`` by the k-fillet area, the
      documented ~1 % plate-vs-catalog gap - design note 10 §6); the
      printed "195" is matched to ``_MANUAL_REL_TOL`` and the equation
      is pinned bit-exactly in-test.
    * Eq. F10-2 ``Mnw = (1.92 - 1.17*sqrt(My/Mcr))*My <= 1.5*My`` with
      ``My = Fy*SwC``: Manual prints "79.4 kip-in." (L1654-1736,
      "(Spec. Eq. F10-2)").

    Z-axis (minor principal), published ``SzB = 0.778 in.^3`` (yield),
    ``SzC = 0.856 in.^3`` (leg LB to toe C):

    * Eq. F10-1 ``Mnz = 1.5*Fy*SzB = 1.5 (36)(0.778) = 42.0 kip-in.``;
    * **no LTB** (§F10 User Note - minor axis);
    * Eq. F10-6 ``Mnz = Fy*SzC*(2.43-1.72*(b/t)*sqrt(Fy/E)) = 45.0
      kip-in.`` (Manual L1380-1444).
    """
    s = _f11_L4_equal_leg()
    fsp = _fsp_equal_leg(s)
    Fy = A36.yield_stress_Fy
    E = A36.elastic_modulus_E
    SwC = _F11C_SWC_IN3 * u.inches**3
    SzB = _F11C_SZB_IN3 * u.inches**3
    SzC = _F11C_SZC_IN3 * u.inches**3
    Lb = 6.0 * u.ft
    Cb = 1.14

    # --- W-axis (major principal): F10-1, F10-4, F10-2 ---
    rep_w = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="principal_major",
        toe_state="compression_at_toe",
        section_modulus_S=SwC,
    )

    # Eq. F10-1: Mnw = 1.5*Fy*SwC (Manual: "95.0 kip-in.").
    expected_mnw_f10_1 = 1.5 * Fy * SwC
    assert math.isclose(rep_w.yielding_moment_Mn_F10_1, expected_mnw_f10_1, rel_tol=REL_TOL)
    mnw1_kipin = rep_w.yielding_moment_Mn_F10_1 / (u.kip * u.inches)
    assert math.isclose(mnw1_kipin, 95.0, rel_tol=_MANUAL_REL_TOL)

    # Eq. F10-4: Me = 9*E*A*rz*t*Cb/(8*Lb) (beta_w=0, equal-leg).
    #
    # TWO independent pins (design note 10 §6 two-tier):
    #
    # (1) **Bit-exact equation lock** (rel_tol=1e-9): the library ``Me``
    #     == Eq. F10-4 recomputed on the SAME plate-consistent section
    #     the library used (its own Ag/rz/t).  This locks the F10-4
    #     transcription independent of any catalog/Manual rounding.
    g = _eq_leg_props(s)
    expected_me_plate = 9.0 * E * g["Ag"] * g["rz"] * g["t"] * Cb / (8.0 * Lb)
    assert math.isclose(rep_w.elastic_LTB_moment_Me, expected_me_plate, rel_tol=REL_TOL)

    # (2) **External Manual cross-check** using the Manual's OWN
    #     published catalog inputs (NOT the plate-built section - design
    #     note §6: feed the *catalog* properties so the documented
    #     plate-vs-catalog k-fillet gap does not swamp the comparison).
    #     AISC Manual v15.1 Ex. F.11C / AISC Shapes Database for
    #     L4x4x1/4: A = 1.93 in.^2, rz = 0.783 in., t = 1/4 in.;
    #     Cb = 1.14, Lb = 6 ft.  Manual prints Eq. F10-4 "Mcr = 195
    #     kip-in." (manual_F11_F12_examples.txt L1645).
    A_cat = 1.93 * u.inches**2  # AISC Shapes Database (Ex. F.11C L1265)
    rz_cat = 0.783 * u.inches  # AISC Shapes Database (Ex. F.11C L1270)
    t_cat = 0.25 * u.inches  # L4x4x1/4 nominal leg thickness (Manual)
    me_catalog = 9.0 * E * A_cat * rz_cat * t_cat * Cb / (8.0 * Lb)
    me_catalog_kipin = me_catalog / (u.kip * u.inches)
    # Manual prints "195 kip-in." (3 sig figs); recomputed from its own
    # catalog inputs this is ~195.x, matched at the printed precision.
    assert math.isclose(me_catalog_kipin, 195.0, rel_tol=_MANUAL_REL_TOL)

    # Eq. F10-2: My = Fy*SwC; My/Me <= 1.0 -> Mn = (1.92 -
    # 1.17*sqrt(My/Me))*My <= 1.5*My.
    #
    # (1) Bit-exact equation lock: library F10-2 == the closed form on
    #     the library's OWN Me (locks Eq. F10-2 independent of rounding).
    My_w = Fy * SwC
    assert My_w / rep_w.elastic_LTB_moment_Me <= 1.0  # the Eq. F10-2 branch
    expected_mnw_f10_2 = min(
        (1.92 - 1.17 * math.sqrt(My_w / rep_w.elastic_LTB_moment_Me)) * My_w,
        1.5 * My_w,
    )
    assert math.isclose(rep_w.LTB_moment_Mn_F10_2_3, expected_mnw_f10_2, rel_tol=REL_TOL)
    # (2) External Manual cross-check: Eq. F10-2 evaluated on the
    #     Manual's catalog Me (item (2) above) and published SwC equals
    #     the Manual's printed "79.4 kip-in." (manual_F11_F12_examples
    #     .txt L1699) to its 3 sig figs.
    My_w_cat = Fy * SwC  # SwC is the Manual's published modulus (1.76 in^3)
    mnw2_catalog = min(
        (1.92 - 1.17 * math.sqrt(My_w_cat / me_catalog)) * My_w_cat,
        1.5 * My_w_cat,
    )
    mnw2_catalog_kipin = mnw2_catalog / (u.kip * u.inches)
    assert math.isclose(mnw2_catalog_kipin, 79.4, rel_tol=_MANUAL_REL_TOL)

    # --- Z-axis (minor principal): F10-1, NO LTB, F10-6 ---
    rep_z = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="principal_minor",
        toe_state="compression_at_toe",
        section_modulus_S=SzB,  # SzB governs Z-axis yielding
    )
    # Eq. F10-1: Mnz = 1.5*Fy*SzB (Manual: "42.0 kip-in.").
    expected_mnz_f10_1 = 1.5 * Fy * SzB
    assert math.isclose(rep_z.yielding_moment_Mn_F10_1, expected_mnz_f10_1, rel_tol=REL_TOL)
    mnz1_kipin = rep_z.yielding_moment_Mn_F10_1 / (u.kip * u.inches)
    assert math.isclose(mnz1_kipin, 42.0, rel_tol=_MANUAL_REL_TOL)
    # §F10 User Note: no LTB for the minor principal axis.
    assert rep_z.elastic_LTB_moment_Me == 0.0
    assert rep_z.LTB_moment_Mn_F10_2_3 == 0.0

    # Eq. F10-6 leg LB to the minor-axis toe C: Sc = SzC (Manual:
    # "Mnz = ... = 45.0 kip-in.").  Re-run with SzC as the modulus to
    # the compression toe (the Manual uses SzC for leg LB, SzB for
    # yielding - different fibres).
    rep_z_legLB = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="principal_minor",
        toe_state="compression_at_toe",
        section_modulus_S=SzC,
    )
    assert rep_z_legLB.leg_classification == "non_compact"
    b_t = rep_z_legLB.leg_slenderness_b_t
    expected_mnz_f10_6 = Fy * SzC * (2.43 - 1.72 * b_t * math.sqrt(Fy / E))
    assert math.isclose(rep_z_legLB.leg_LB_moment_Mn_F10_6_7, expected_mnz_f10_6, rel_tol=REL_TOL)
    mnz6_kipin = rep_z_legLB.leg_LB_moment_Mn_F10_6_7 / (u.kip * u.inches)
    assert math.isclose(mnz6_kipin, 45.0, rel_tol=_MANUAL_REL_TOL)


def _f10_5_me(*, E: float, b: float, t: float, Lb: float, Cb: float, plus: bool) -> float:
    """AISC 360-22 Eq. F10-5a / F10-5b ``Me``, recomputed in-test.

    The authoritative §F10.2(b) form, transcribed independently of the
    library / oracle from ``spec_F10_geometric.txt`` (any consistent
    unit system - pass either base mm units or US ksi/in)::

        Me = 0.58*E*b^4*t*Cb/Lb^2 * [sqrt(1+0.88*(Lb*t/b^2)^2) -/+ 1]

    ``plus=False`` -> Eq. F10-5a (``- 1``, max compression at the toe);
    ``plus=True`` -> Eq. F10-5b (``+ 1``, max tension at the toe).
    The ``b^4*t/Lb^2`` powers make this dimensionally a moment.
    """
    arg = Lb * t / b**2
    sign = 1.0 if plus else -1.0
    return 0.58 * E * b**4 * t * Cb / Lb**2 * (math.sqrt(1.0 + 0.88 * arg**2) + sign)


def test_F10_manual_v15_1_F11A_geometric_axis_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.11A geometric-axis cross-check (F10-EC-1 RESOLVED).

    External-authority anchor for the **geometric-axis LTB** limit
    state (Eq. F10-5a, no lateral-torsional restraint).  Ex. F.11A:
    L4x4x1/4, ASTM A36 (``Fy = 36 ksi``), bending about the geometric
    x-axis, vertical leg up, toe in compression, NO LT restraint,
    ``Cb = 1.14`` (AISC Manual Table 3-1), ``Lb = 6 ft``
    (``manual_F9_examples.txt`` L1028-1364).  The Manual prints, from
    "(Spec. Eq. F10-5a)" (L1196-1286), the identical authoritative form
    ``Mcr = 0.58*E*b^4*t*Cb/Lb^2 * [sqrt(1+0.88*(Lb*t/b^2)^2) - 1] =
    107 kip-in``; ``My = 0.80*Fy*Sx = 29.7 kip-in``; ``My/Mcr = 0.278
    <= 1.0`` -> Eq. F10-2 -> ``Mn = 38.7 kip-in``; leg LB Eq. F10-6
    ``43.3``; the LTB limit state controls -> ``Mn = 38.7 kip-in``.

    F10-EC-1 RESOLVED (the authoritative form is CONFIRMED verbatim
    from ``spec_F10_geometric.txt``, printed 16.1-69/70; the prior
    curated ``b*t^2/Lb`` form was correctly rejected - ~30, not 107).
    The geometric-axis path is now a fully-delivered limit state.
    Driven on the Manual's published L4x4x1/4 ``Sx = 1.03 in.^3``
    (Table 1-7); ``Mcr``/``Mn``/``phi*Mn`` matched to the Manual's 3
    sig figs AND bit-exact vs Eq. F10-5a recomputed in-test.
    """
    s = _f11_L4_equal_leg()
    fsp = _fsp_equal_leg(s)
    g = _eq_leg_props(s)
    Fy = A36.yield_stress_Fy
    E = A36.elastic_modulus_E
    Sx = _F11_L4_SX_IN3 * u.inches**3
    Lb = 6.0 * u.ft
    Cb = 1.14

    rep = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="geometric",
        toe_state="compression_at_toe",  # Eq. F10-5a
        section_modulus_S=Sx,
        lateral_torsional_restraint_at_max_moment=False,  # §F10.2(b)(i)
    )

    # --- Eq. F10-5a Mcr (two-pin, mirroring the F.11C F10-4 anchor) ---
    # (1) Bit-exact equation lock (rel_tol=1e-9), BASE units: library
    #     Me == Eq. F10-5a recomputed on the SAME plate-consistent b/t
    #     the library used (the plate-built L4x4x1/4 recovers
    #     b=4.00 in, t=0.25 in EXACTLY -> g["b"], g["t"]).  Locks the
    #     F10-5a transcription independent of any unit rounding.
    expected_me_base = _f10_5_me(E=E, b=g["b"], t=g["t"], Lb=Lb, Cb=Cb, plus=False)
    assert math.isclose(rep.elastic_LTB_moment_Me, expected_me_base, rel_tol=REL_TOL)
    # (2) External Manual cross-check: the Manual prints, from
    #     "(Spec. Eq. F10-5a)", "Mcr = 107 kip-in."
    #     (manual_F9_examples.txt L1231) - matched to 3 sig figs in the
    #     Manual's own US units (E = 29000 ksi, b = 4.00 in,
    #     t = 0.25 in, Lb = 6 ft).
    me_kipin = rep.elastic_LTB_moment_Me / (u.kip * u.inches)
    me_us = _f10_5_me(E=29000.0, b=_F11_B_IN, t=_F11_T_IN, Lb=6.0 * 12.0, Cb=Cb, plus=False)
    assert math.isclose(me_us, 107.0, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(me_kipin, 107.0, rel_tol=_MANUAL_REL_TOL)

    # --- §F10.2(b)(i) My = 0.80*Fy*Sx (no LT restraint) ---
    expected_my_ltb = 0.80 * Fy * Sx
    assert math.isclose(rep.yield_moment_for_LTB_My, expected_my_ltb, rel_tol=REL_TOL)
    my_ltb_kipin = rep.yield_moment_for_LTB_My / (u.kip * u.inches)
    # Manual L1171-1187: "My = 0.80 Fy Sx = 29.7 kip-in.".
    assert math.isclose(my_ltb_kipin, 29.7, rel_tol=_MANUAL_REL_TOL)

    # --- Eq. F10-2 (My/Mcr = 0.278 <= 1.0) -> Mn_LTB = 38.7 kip-in ---
    My = rep.yield_moment_for_LTB_My
    assert My / rep.elastic_LTB_moment_Me <= 1.0  # genuinely Eq. F10-2
    expected_mn_f10_2 = min(
        (1.92 - 1.17 * math.sqrt(My / rep.elastic_LTB_moment_Me)) * My,
        1.5 * My,
    )
    assert math.isclose(rep.LTB_moment_Mn_F10_2_3, expected_mn_f10_2, rel_tol=REL_TOL)
    mn_ltb_kipin = rep.LTB_moment_Mn_F10_2_3 / (u.kip * u.inches)
    # Manual L1303-1316: "Mn = (1.92 - 1.17 sqrt(My/Mcr)) My ... = 38.7
    # kip-in. (Spec. Eq. F10-2)".
    assert math.isclose(mn_ltb_kipin, 38.7, rel_tol=_MANUAL_REL_TOL)

    # --- Governing: the LTB limit state controls, Mn = 38.7 kip-in ---
    # (Manual L463-465: "The lateral-torsional buckling limit state
    # controls.  Mn = 38.7 kip-in.").  The §F10.3 leg-LB candidate is
    # the noncompact-leg Eq. F10-6 with Sc = 0.80*Sx (= the Manual's
    # 43.3 kip-in), which does NOT govern - LTB (38.7) < leg LB (43.3)
    # < yielding (55.6).
    assert rep.governing_limit_state == "lateral_torsional_buckling"
    mn_kipin = rep.nominal_flexural_strength_Mn / (u.kip * u.inches)
    assert math.isclose(mn_kipin, 38.7, rel_tol=_MANUAL_REL_TOL)
    # The confirmed §F10.3 Eq. F10-6 leg-LB candidate (Sc = 0.80*Sx,
    # geometric / no restraint) is the Manual's printed 43.3 kip-in.
    leg_lb_kipin = rep.leg_LB_moment_Mn_F10_6_7 / (u.kip * u.inches)
    assert math.isclose(leg_lb_kipin, 43.3, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(rep.section_modulus_to_compression_toe_Sc, 0.80 * Sx, rel_tol=REL_TOL)

    # phi/Omega plumbing on the Manual-anchored governing Mn.
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

    # Independent oracle mirrors the library bit-exact on the resolved
    # geometric path (the layer-rule oracle re-derives F10-5a from its
    # own spec literals).
    oracle = mn_F10(
        _oracle(
            s,
            A36,
            S=Sx,
            Lb=Lb,
            Cb=Cb,
            bending_mode="geometric",
            toe_state="compression_at_toe",
            lt_restraint=False,
        )
    )
    assert math.isclose(rep.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(rep.elastic_LTB_moment_Me, oracle.Me, rel_tol=REL_TOL)
    assert rep.governing_limit_state == oracle.governing


def test_F10_manual_v15_1_F11B_geometric_axis_restraint_published_anchor() -> None:
    """AISC Manual v15.1 Ex. F.11B geometric-axis cross-check (§F10.2(b)(ii)).

    External-authority anchor for the geometric-axis LTB limit state
    **with lateral-torsional restraint at the point of maximum moment
    only** (§F10.2(b)(ii)).  Ex. F.11B: same L4x4x1/4 / A36 as
    Ex. F.11A but braced at ends *and* midspan, ``Cb = 1.30`` (AISC
    Manual Table 3-1), ``Lb = 3 ft`` (``manual_F11_F12_examples.txt``
    L529-891).  The Manual prints:

    * ``My = Fy*Sx = 37.1 kip-in`` (the **full** geometric yield
      moment - NOT the 0.80 reduction; §F10.2(b)(ii), Manual L668-688).
    * ``Mcr = 1.25 * (Eq. F10-5a) = 176 kip-in`` (§F10.2(b)(ii), Manual
      L690-772, "(from Spec. Eq. F10-5a)").
    * ``My/Mcr = 0.211 <= 1.0`` -> Eq. F10-2 -> ``Mn = 51.3 kip-in``
      (Manual L810-838).
    * Leg LB ``43.3 kip-in`` from Ex. F.11A controls -> ``Mn = 43.3
      kip-in`` (Manual L883-891).

    Driven on the Manual's published ``Sx = 1.03 in.^3``.  This test
    anchors the **§F10.2(b)(ii) pieces** - ``My = Fy*Sx`` (full),
    ``Mcr = 1.25 * Eq. F10-5a``, ``Mn_LTB`` (Eq. F10-2) - to the
    Manual's printed 37.1 / 176 / 51.3 kip-in (3 sig figs) AND
    bit-exact (base units) vs ``1.25 *`` Eq. F10-5a recomputed
    in-test, and pins the composite ``Mn`` against the independent
    oracle bit-exact.

    (The Manual's *governing* Ex. F.11B ``Mn = 43.3 kip-in`` is the
    leg-LB value reused from Ex. F.11A, which the Manual re-derives
    with the **no-restraint** ``Sc = 0.80*Sx`` - leg LB is a
    section-capacity limit independent of the LT-restraint condition.
    The library, given ``lateral_torsional_restraint_at_max_moment=
    True``, correctly forms its §F10.3 ``Sc`` as the *full* ``Sx`` for
    this restrained case, so its leg-LB candidate is not the Manual's
    43.3; the leg-LB *equation* itself (Eq. F10-6) is anchored to the
    Manual elsewhere - Ex. F.11A 43.3, Ex. F.11C 92.5/45.0.  Hence the
    Manual cross-check here is scoped to the §F10.2(b)(ii) LTB pieces,
    with the composite ``Mn`` pinned to the independent oracle.)
    """
    s = _f11_L4_equal_leg()
    fsp = _fsp_equal_leg(s)
    g = _eq_leg_props(s)
    Fy = A36.yield_stress_Fy
    E = A36.elastic_modulus_E
    Sx = _F11_L4_SX_IN3 * u.inches**3
    Lb = 3.0 * u.ft
    Cb = 1.30

    rep = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="geometric",
        toe_state="compression_at_toe",  # Eq. F10-5a base
        section_modulus_S=Sx,
        lateral_torsional_restraint_at_max_moment=True,  # §F10.2(b)(ii)
    )

    # --- §F10.2(b)(ii) My = Fy*Sx (FULL, no 0.80 reduction) ---
    expected_my_ltb = Fy * Sx
    assert math.isclose(rep.yield_moment_for_LTB_My, expected_my_ltb, rel_tol=REL_TOL)
    my_ltb_kipin = rep.yield_moment_for_LTB_My / (u.kip * u.inches)
    # Manual L673-688: "My = Fy Sx = 37.1 kip-in.".
    assert math.isclose(my_ltb_kipin, 37.1, rel_tol=_MANUAL_REL_TOL)

    # --- Mcr = 1.25 * Eq. F10-5a (§F10.2(b)(ii)) ---
    # (1) Bit-exact (rel_tol=1e-9), BASE units: library Me == 1.25 *
    #     Eq. F10-5a recomputed on the SAME plate-consistent b/t.
    expected_me_base = 1.25 * _f10_5_me(E=E, b=g["b"], t=g["t"], Lb=Lb, Cb=Cb, plus=False)
    assert math.isclose(rep.elastic_LTB_moment_Me, expected_me_base, rel_tol=REL_TOL)
    # (2) External Manual cross-check: "Mcr = ... = 176 kip-in."
    #     (manual_F11_F12_examples.txt L772) - 3 sig figs in the
    #     Manual's own US units (E = 29000 ksi, b = 4.00 in,
    #     t = 0.25 in, Lb = 3 ft).
    me_kipin = rep.elastic_LTB_moment_Me / (u.kip * u.inches)
    me_us = 1.25 * _f10_5_me(E=29000.0, b=_F11_B_IN, t=_F11_T_IN, Lb=3.0 * 12.0, Cb=Cb, plus=False)
    assert math.isclose(me_us, 176.0, rel_tol=_MANUAL_REL_TOL)
    assert math.isclose(me_kipin, 176.0, rel_tol=_MANUAL_REL_TOL)

    # --- Eq. F10-2 (My/Mcr = 0.211 <= 1.0) -> Mn_LTB = 51.3 kip-in ---
    My = rep.yield_moment_for_LTB_My
    assert My / rep.elastic_LTB_moment_Me <= 1.0  # genuinely Eq. F10-2
    expected_mn_f10_2 = min(
        (1.92 - 1.17 * math.sqrt(My / rep.elastic_LTB_moment_Me)) * My,
        1.5 * My,
    )
    assert math.isclose(rep.LTB_moment_Mn_F10_2_3, expected_mn_f10_2, rel_tol=REL_TOL)
    mn_ltb_kipin = rep.LTB_moment_Mn_F10_2_3 / (u.kip * u.inches)
    # Manual L825-838: "Mn = (1.92 - 1.17 sqrt(My/Mcr)) My ... = 51.3
    # kip-in. (Spec. Eq. F10-2)".
    assert math.isclose(mn_ltb_kipin, 51.3, rel_tol=_MANUAL_REL_TOL)

    # Independent oracle mirrors the library bit-exact (resolved
    # geometric-restraint path).
    oracle = mn_F10(
        _oracle(
            s,
            A36,
            S=Sx,
            Lb=Lb,
            Cb=Cb,
            bending_mode="geometric",
            toe_state="compression_at_toe",
            lt_restraint=True,
        )
    )
    assert math.isclose(rep.nominal_flexural_strength_Mn, oracle.Mn, rel_tol=REL_TOL)
    assert math.isclose(rep.elastic_LTB_moment_Me, oracle.Me, rel_tol=REL_TOL)
    assert math.isclose(rep.LTB_moment_Mn_F10_2_3, oracle.Mn_LTB, rel_tol=REL_TOL)
    assert rep.governing_limit_state == oracle.governing


def test_F10_geometric_axis_F10_5a_vs_F10_5b_sign() -> None:
    """Eq. F10-5a (``- 1``) vs Eq. F10-5b (``+ 1``) toe-state sign.

    For the same equal-leg angle / ``Lb`` / ``Cb``, tension at the toe
    (Eq. F10-5b, ``+ 1``) gives a strictly **larger** elastic LTB
    moment than compression at the toe (Eq. F10-5a, ``- 1``) - the
    bracket differs by exactly ``2`` (``sqrt(...) + 1`` vs
    ``sqrt(...) - 1``).  Pins the sign wiring against the F10-EC-1
    RESOLVED form recomputed in-test.
    """
    s = _f11_L4_equal_leg()
    fsp = _fsp_equal_leg(s)
    g = _eq_leg_props(s)
    E = A36.elastic_modulus_E
    Sx = _F11_L4_SX_IN3 * u.inches**3
    Lb = 6.0 * u.ft
    Cb = 1.14

    rep_c = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="geometric",
        toe_state="compression_at_toe",
        section_modulus_S=Sx,
    )
    rep_t = compute_flexural_strength_F10_single_angle(
        fsp,
        A36,
        unbraced_length_Lb=Lb,
        Cb=Cb,
        bending_mode="geometric",
        toe_state="tension_at_toe",
        section_modulus_S=Sx,
    )

    me_c = rep_c.elastic_LTB_moment_Me
    me_t = rep_t.elastic_LTB_moment_Me
    assert me_t > me_c  # +1 (F10-5b) > -1 (F10-5a)
    # Bit-exact (base units): each toe state == its F10-5a/5b form
    # recomputed on the same plate-consistent b/t.
    exp_c = _f10_5_me(E=E, b=g["b"], t=g["t"], Lb=Lb, Cb=Cb, plus=False)
    exp_t = _f10_5_me(E=E, b=g["b"], t=g["t"], Lb=Lb, Cb=Cb, plus=True)
    assert math.isclose(me_c, exp_c, rel_tol=REL_TOL)
    assert math.isclose(me_t, exp_t, rel_tol=REL_TOL)
    # The bracket differs by exactly 2 (sqrt+1 vs sqrt-1) ->
    # Me_t - Me_c = 2 * 0.58*E*b^4*t*Cb/Lb^2.
    coeff = 0.58 * E * g["b"] ** 4 * g["t"] * Cb / Lb**2
    assert math.isclose(me_t - me_c, 2.0 * coeff, rel_tol=REL_TOL)

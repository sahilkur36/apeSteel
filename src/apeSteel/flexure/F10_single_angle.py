"""AISC 360-22 §F10 - flexural strength of single angles.

This module is the pure §F10 calculator: it takes a single-angle
:class:`FlexuralSectionProperties` snapshot (as produced natively by
``SingleAngleSection.compute_section_properties`` in
:mod:`apeSteel.sections.geometry.single_angle_section`), a material, an
unbraced length, ``Cb`` and the bending mode, and returns the nominal
flexural strength ``Mn`` with the controlling limit state identified.

§F10 is the most code-intensive section in Chapter F.  ``Mn`` is the
lowest value of three limit states (AISC 360-22 §F10 lead paragraph):

* **Yielding (F10.1)** ``Mn = 1.5*My``                       (Eq. F10-1)
* **Lateral-torsional buckling (F10.2)** via the elastic LTB moment
  ``Me``:

  - ``My/Me <= 1.0`` -> ``Mn = (1.92 - 1.17*sqrt(My/Me))*My <= 1.5*My``
                                                              (Eq. F10-2)
  - ``My/Me > 1.0``  -> ``Mn = (0.92 - 0.17*Me/My)*Me``       (Eq. F10-3)

  with ``Me`` from
  - Eq. F10-4 - equal-leg angle, bending about the **major principal
    axis** (``beta_w = 0`` for an equal-leg angle);
  - Eq. F10-5a / F10-5b - bending about a **geometric axis** (max
    compression / max tension at the toe);
  - the §F10 User Note: for bending about the **minor principal axis**
    only yielding and leg local buckling apply (no LTB).

* **Leg local buckling (F10.3)** - applies when the toe of the leg is
  in compression; ``b/t`` classified via the F-0 generalized classifier
  (``section_kind="single_angle"``):

  - compact -> does not apply;
  - noncompact -> ``Mn = Fy*Sc*(2.43 - 1.72*(b/t)*sqrt(Fy/E))``
                                                              (Eq. F10-6)
  - slender   -> ``Mn = Fcr*Sc`` (Eq. F10-7) with
                 ``Fcr = 0.71*E/(b/t)^2`` (Eq. F10-8).

``My`` is formed from a **section modulus** (never a plastic modulus):

* principal-axis bending: ``My = Fy*S`` (``S`` = the principal-axis
  elastic modulus to the fibre of interest);
* geometric-axis bending of an equal-leg angle **without** lateral-
  torsional restraint: ``My = 0.80*Fy*Sx`` (§F10.2, the F10-5a/F10-5b
  case; ``Sc`` for leg-LB is likewise ``0.80`` of the geometric-axis
  modulus, §F10.3 ``Sc`` definition / Eq. F10-9 prose);
* geometric-axis bending with lateral-torsional restraint at the point
  of maximum moment only: ``My = Fy*Sx`` and ``Mcr`` is ``1.25`` times
  the Eq. F10-5a/F10-5b value (§F10.2(b)(ii)).

``phi_b = 0.90`` / ``Omega_b = 1.67`` (AISC 360-22 §F1), shared with the
rest of Chapter F via :mod:`apeSteel.flexure._common`.

Layering: this module is in the ``flexure`` layer; it imports only from
``sections`` (:class:`FlexuralSectionProperties`), ``classification``
(:func:`classify_flexural_compactness`) and ``core``.  It is **not**
wired into any facade / ``Element`` here - that is Phase F-8.

Provenance (design note 10 §9 / ``_chapterF_citation_reference.md``
§F10):

* Eq. **F10-6 / F10-7 / F10-8** and their page (printed 16.1-70) are
  CONFIRMED verbatim from
  ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` and
  numerically reproduce AISC Manual v15.1 Ex. F.11A (43.3 kip-in) /
  Ex. F.11C (45.0 / 92.5 kip-in).
* Eq. **F10-1 / F10-2 / F10-3 / F10-4 / F10-5a** are on printed
  **16.1-69**, which is **absent from the staged spec extract** (the
  extract jumps 16.1-68 -> 16.1-70); the F10-1..F10-4 forms are taken
  from the curated reference (``skill_reference_chapterF.md`` /
  ``_chapterF_citation_reference.md`` §F10).  Eq. **F10-1** (1.5*My),
  **F10-2** and **F10-4** are numerically CONFIRMED against the Manual:
  Ex. F.11A F10-1 = 55.6 kip-in; Ex. F.11C F10-1 = 95.0 / 42.0 kip-in,
  F10-4 = 195 kip-in, F10-2 = 79.4 kip-in.
* Eq. **F10-5a / F10-5b** - **ENGINEER-CONFIRM F10-EC-1 RESOLVED.**
  The authoritative §F10.2(b) form
  ``Me = 0.58*E*b^4*t*Cb/Lb^2 * [sqrt(1 + 0.88*(Lb*t/b^2)^2) -/+ 1]``
  (``- 1`` Eq. F10-5a / compression at the toe; ``+ 1`` Eq. F10-5b /
  tension at the toe) is CONFIRMED verbatim from
  ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``
  (printed 16.1-69/70, re-pulled by the orchestrator) - the prior
  curated ``b*t^2/Lb`` powers were correctly REJECTED (wrong
  dimensions; ~30 not 107).  The verified form is dimensionally a
  moment (``[F/L^2]*[L^4]*[L]/[L^2] = F*L``) and reproduces the AISC
  Manual v15.1 published Ex. F.11A ``Mcr = 107 kip-in`` (no LT
  restraint, ``My = 0.80*Fy*Sx``; governing ``Mn = 38.7`` via F10-2)
  and Ex. F.11B ``Mcr = 1.25*F10-5a = 176 kip-in`` (LT restraint at
  the max-moment point, ``My = Fy*Sx``; §F10.2(b)(ii)) to the printed
  3 sig figs.  Geometric-axis bending is now a fully-delivered limit
  state and the Eq. F10-5b citation page is CONFIRMED 16.1-70.

References
----------
.. [1] AISC 360-22 §F10 "Single Angles", Eq. F10-1 - F10-8,
       pp. 16.1-69 - 16.1-70.  American Institute of Steel Construction,
       2022.  §F10.3 (Eq. F10-6/7/8) and the §F10 lead/User-Note prose
       transcribed verbatim from
       ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` (printed
       16.1-70) and ``docs/design_notes/_chapterF_citation_reference.md``
       (§F10 row).  Eq. F10-1..F10-4 are from the curated reference
       (printed 16.1-69 absent from ``spec_chapterF.txt`` -
       ENGINEER-CONFIRM EC-9; numerically Manual-confirmed).
       Eq. **F10-5a / F10-5b** are CONFIRMED verbatim from
       ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``
       (printed 16.1-69/70, orchestrator-staged) and reproduce AISC
       Manual v15.1 Ex. F.11A (107 kip-in) / Ex. F.11B (176 kip-in) -
       **ENGINEER-CONFIRM F10-EC-1 RESOLVED**.
.. [2] AISC 360-22 Table B4.1b single-angle-leg flexure (§F10.3 supplies
       the ``b/t`` breakpoints directly): ``lambda_p = 0.54 sqrt(E/Fy)``,
       ``lambda_r = 0.91 sqrt(E/Fy)`` - the case-number label is
       UNVERIFIED (likely Case 12; ENGINEER-CONFIRM EC-4/EC-10), so the
       leg citation carries ``page=None``; the F10-8 slender ``Fcr``
       form IS confirmed (printed 16.1-70).  The numeric limits reach
       §F10 through :func:`classify_flexural_compactness`, not
       re-declared here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from apeSteel.classification.flexural_compactness import classify_flexural_compactness
from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.flexure._common import (
    CITATIONS_AISC_360_CHAPTER_F,
    OMEGA_FLEXURE_ASD,
    PHI_FLEXURE_LRFD,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.flexural_properties import FlexuralSectionProperties

# ---------------------------------------------------------------------------
# §F10 bending-mode discriminator
# ---------------------------------------------------------------------------
#: How the single angle is designed (AISC 360-22 §F10 lead paragraph +
#: User Note):
#:
#: * ``"principal_major"`` - bending about the **major** principal axis
#:   (``w``); LTB via Eq. F10-4 (equal-leg) - the default for a single
#:   angle without continuous lateral-torsional restraint.
#: * ``"principal_minor"`` - bending about the **minor** principal axis
#:   (``z``); per the §F10 User Note **only yielding and leg local
#:   buckling apply** (no LTB).
#: * ``"geometric"`` - bending about a geometric (x or y) axis of an
#:   equal-leg angle; LTB via Eq. F10-5a / F10-5b.  Permitted only for
#:   equal-leg angles (§F10 lead paragraph).
SingleAngleBendingMode = Literal["principal_major", "principal_minor", "geometric"]

#: Which toe is in flexural compression for the geometric-axis Me
#: (Eq. F10-5a vs F10-5b) and whether leg local buckling applies
#: (§F10.3 applies only when the toe of the leg is in compression).
SingleAngleToeState = Literal["compression_at_toe", "tension_at_toe"]


# ---------------------------------------------------------------------------
# Constants - AISC 360-22 §F10 (each magic number named + cited so the
# §F10 provenance is traceable at the call site, mirroring the F8 style).
# ---------------------------------------------------------------------------
#: Eq. F10-1 yielding plateau factor: ``Mn = 1.5*My`` (curated reference,
#: printed 16.1-69 absent from the staged extract - ENGINEER-CONFIRM
#: EC-9; numerically CONFIRMED vs AISC Manual v15.1 Ex. F.11A = 55.6
#: kip-in and Ex. F.11C = 95.0 / 42.0 kip-in).
_EQ_F10_1_YIELD_FACTOR: float = 1.5

#: Eq. F10-2 inelastic-LTB coefficients
#: ``Mn = (1.92 - 1.17*sqrt(My/Me))*My <= 1.5*My`` (curated; CONFIRMED vs
#: Ex. F.11A 38.7 kip-in path and Ex. F.11C 79.4 kip-in).
_EQ_F10_2_A: float = 1.92
_EQ_F10_2_B: float = 1.17

#: Eq. F10-3 elastic-LTB coefficients
#: ``Mn = (0.92 - 0.17*Me/My)*Me`` (curated; printed 16.1-69 absent -
#: ENGINEER-CONFIRM EC-9; no Manual example exercises the
#: ``My/Me > 1.0`` branch, so EC-9 stands for F10-3).
_EQ_F10_3_A: float = 0.92
_EQ_F10_3_B: float = 0.17

#: Eq. F10-2 / F10-3 regime split: F10-2 when ``My/Me <= 1.0`` else
#: F10-3 (AISC Manual v15.1 Ex. F.11A: "My/Mcr = 0.278 < 1.0; therefore
#: ... Equation F10-2 is applicable").
_EQ_F10_2_3_REGIME_LIMIT: float = 1.0

#: Eq. F10-4 equal-leg / major-principal-axis elastic LTB moment
#: ``Me = 9*E*A*rz*t*Cb/(8*Lb)
#:        * [sqrt(1 + 4.4*(beta_w*rz/(Lb*t))^2) + 4.4*beta_w*rz/(Lb*t)]``
#: with ``beta_w = 0`` for an equal-leg angle (§F10.2(b)(1)).  CONFIRMED:
#: reproduces AISC Manual v15.1 Ex. F.11C ``Mcr = 195 kip-in`` exactly.
_EQ_F10_4_NUM_COEFF: float = 9.0
_EQ_F10_4_DEN_COEFF: float = 8.0
_EQ_F10_4_BETA_W_COEFF: float = 4.4

#: Eq. F10-5a / F10-5b geometric-axis elastic LTB moment
#: ``Me = (0.58*E*b^4*t*Cb/Lb^2) * [sqrt(1 + 0.88*(Lb*t/b^2)^2) -/+ 1]``
#: with ``- 1`` for max **compression** at the toe (Eq. F10-5a) and
#: ``+ 1`` for max **tension** at the toe (Eq. F10-5b).  **F10-EC-1
#: RESOLVED**: the authoritative form is CONFIRMED verbatim from
#: ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``
#: (printed 16.1-69/70) - the ``b^4*t/Lb^2`` powers (NOT the previously
#: rejected curated ``b*t^2/Lb``) make it dimensionally a moment
#: (``[F/L^2]*[L^4]*[L]/[L^2] = F*L``) AND it reproduces the AISC
#: Manual v15.1 published Ex. F.11A ``Mcr = 107 kip-in`` and Ex. F.11B
#: ``Mcr = 176 kip-in`` (1.25x F10-5a) to the printed 3 sig figs.  The
#: Manual prints this identical form ("(Spec. Eq. F10-5a)",
#: ``manual_F9_examples.txt`` L1196-1286 / ``manual_F11_F12_examples
#: .txt`` L171-260).
_EQ_F10_5_NUM_COEFF: float = 0.58
_EQ_F10_5_BRACKET_COEFF: float = 0.88

#: §F10.2(b)(ii) restraint factor: with lateral-torsional restraint at
#: the point of maximum moment only, ``Mcr`` is ``1.25`` times the
#: Eq. F10-5a / F10-5b value (CONFIRMED verbatim from
#: ``spec_F10_geometric.txt`` L285-287; AISC Manual v15.1 Ex. F.11B
#: prints "Mcr shall be taken as 1.25 times Mcr computed using ...
#: Equation F10-5a", reproducing 176 kip-in).
_F10_2B_II_RESTRAINT_FACTOR: float = 1.25

#: §F10.2 geometric-axis (no LT restraint) yield-moment reduction:
#: ``My`` = ``0.80`` * the yield moment from the geometric section
#: modulus (§F10.2; also the §F10.3 ``Sc`` factor for geometric-axis
#: leg LB).  CONFIRMED vs AISC Manual v15.1 Ex. F.11A (``My = 0.80*Fy*Sx
#: = 29.7 kip-in``; ``Sc = 0.80*Sx = 0.824 in^3``).
_F10_GEOMETRIC_YIELD_FACTOR: float = 0.80

#: Eq. F10-6 noncompact-leg local-buckling coefficients
#: ``Mn = Fy*Sc*(2.43 - 1.72*(b/t)*sqrt(Fy/E))`` (CONFIRMED verbatim
#: from spec_chapterF.txt printed 16.1-70; reproduces AISC Manual v15.1
#: Ex. F.11A = 43.3 kip-in and Ex. F.11C = 45.0 / 92.5 kip-in).
_EQ_F10_6_A: float = 2.43
_EQ_F10_6_B: float = 1.72

#: Eq. F10-8 slender-leg critical-stress coefficient
#: ``Fcr = 0.71*E/(b/t)^2`` (CONFIRMED verbatim from spec_chapterF.txt
#: printed 16.1-70).
_EQ_F10_8_FCR_COEFF: float = 0.71


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF10Report(Report):
    """AISC 360-22 §F10 flexural-strength result for a single angle.

    All moments are in apeSteel base units (N*mm); ``b``/``t`` in mm;
    stresses in MPa.

    Attributes
    ----------
    bending_mode : SingleAngleBendingMode
        Which axis the angle is designed about
        (``"principal_major"`` / ``"principal_minor"`` / ``"geometric"``).
    toe_state : SingleAngleToeState
        Which toe is in flexural compression - selects Eq. F10-5a
        (compression at the toe) vs Eq. F10-5b (tension at the toe) for
        the geometric-axis ``Me`` *and* determines whether §F10.3 leg
        local buckling applies (only when the toe is in compression).
    yield_moment_My : float
        ``My_yield`` - the §F10.1 yield-moment basis (``Fy*S``, the
        *full* geometric or principal section modulus; the §F10.2 0.80
        reduction does **not** apply to Eq. F10-1).  This is the basis
        of Eq. F10-1 (N*mm).
    yield_moment_for_LTB_My : float
        ``My_ltb`` - the §F10.2 LTB yield-moment basis: ``Fy*S`` for
        principal-axis or geometric-with-LT-restraint bending,
        ``0.80*Fy*Sx`` for geometric-axis bending **without**
        lateral-torsional restraint (§F10.2).  This is the ``My`` used
        in Eq. F10-2 / F10-3 (N*mm); ``0.0``-irrelevant for the minor
        principal axis (no LTB).
    yielding_moment_Mn_F10_1 : float
        Eq. F10-1 ``Mn = 1.5*My_yield`` (N*mm).
    elastic_LTB_moment_Me : float
        Elastic LTB moment ``Me`` (N*mm): Eq. F10-4 for the
        principal-major axis, Eq. F10-5a / F10-5b for the geometric
        axis (the §F10.2(b)(ii) ``1.25`` restraint factor folded in
        when applicable).  ``0.0`` for the minor principal axis (no LTB
        per the §F10 User Note).
    LTB_moment_Mn_F10_2_3 : float
        Eq. F10-2 / F10-3 LTB nominal moment (N*mm).  ``0.0`` for the
        minor principal axis.
    leg_slenderness_b_t : float
        Leg ``b/t`` (dimensionless).
    leg_compact_limit_lambda_p : float
        §F10.3 leg compact limit ``0.54*sqrt(E/Fy)`` (via the F-0
        classifier).
    leg_noncompact_limit_lambda_r : float
        §F10.3 leg noncompact limit ``0.91*sqrt(E/Fy)`` (via the F-0
        classifier).
    leg_classification : str
        ``"compact"`` / ``"non_compact"`` / ``"slender"`` for the leg.
    section_modulus_to_compression_toe_Sc : float
        ``Sc`` used by Eq. F10-6/F10-7 (the elastic modulus to the toe
        in compression; ``0.80`` of the geometric modulus for a
        geometric-axis equal-leg angle with no LT restraint).  ``0.0``
        when leg LB does not apply (compact leg, or tension at the toe).
    leg_LB_critical_stress_Fcr : float
        Eq. F10-8 ``Fcr = 0.71*E/(b/t)^2`` (MPa); computed only on the
        slender-leg branch, ``0.0`` otherwise.
    leg_LB_moment_Mn_F10_6_7 : float
        Eq. F10-6 (noncompact) / Eq. F10-7 (slender) leg-LB nominal
        moment (N*mm).  ``0.0`` when leg LB does not apply.
    nominal_flexural_strength_Mn : float
        Final ``Mn`` = the lowest applicable §F10 limit state (N*mm).
        Mirrors :attr:`Report.nominal_strength`.
    """

    bending_mode: SingleAngleBendingMode = "principal_major"
    toe_state: SingleAngleToeState = "compression_at_toe"
    yield_moment_My: float = 0.0
    yield_moment_for_LTB_My: float = 0.0
    yielding_moment_Mn_F10_1: float = 0.0
    elastic_LTB_moment_Me: float = 0.0
    LTB_moment_Mn_F10_2_3: float = 0.0
    leg_slenderness_b_t: float = 0.0
    leg_compact_limit_lambda_p: float = 0.0
    leg_noncompact_limit_lambda_r: float = 0.0
    leg_classification: str = "compact"
    section_modulus_to_compression_toe_Sc: float = 0.0
    leg_LB_critical_stress_Fcr: float = 0.0
    leg_LB_moment_Mn_F10_6_7: float = 0.0
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Equation-set citations
# ---------------------------------------------------------------------------
_CITATIONS_F10: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    # §F10 lead paragraph + User Note (limit-state set; principal vs
    # geometric vs minor-axis routing).  Printed 16.1-69/70 - the lead
    # prose extracted at 16.1-70; page kept as the confirmed 16.1-70.
    AISCClauseReference("AISC 360-22", "F10", None, "16.1-70"),
    # Eq. F10-1 / F10-2 / F10-3 / F10-4: printed 16.1-69 is ABSENT from
    # spec_chapterF.txt (ENGINEER-CONFIRM EC-9); F10-1/2/4 are
    # numerically Manual-confirmed but the *page label* is unverified
    # -> page=None (never invented).
    AISCClauseReference("AISC 360-22", "F10.1", "F10-1", None),
    AISCClauseReference("AISC 360-22", "F10.2", "F10-2", None),
    AISCClauseReference("AISC 360-22", "F10.2", "F10-3", None),
    AISCClauseReference("AISC 360-22", "F10.2", "F10-4", None),
    # Eq. F10-5a / F10-5b: ENGINEER-CONFIRM F10-EC-1 RESOLVED - both
    # CONFIRMED verbatim from spec_F10_geometric.txt (printed
    # 16.1-69/70, orchestrator-staged) and reproducing AISC Manual
    # v15.1 Ex. F.11A (107 kip-in) / Ex. F.11B (176 kip-in); page
    # CONFIRMED 16.1-69 (F10-5a) / 16.1-70 (F10-5b prose).
    AISCClauseReference("AISC 360-22", "F10.2", "F10-5a", "16.1-69"),
    AISCClauseReference("AISC 360-22", "F10.2", "F10-5b", "16.1-70"),
    # §F10.3 leg local buckling - Eq. F10-6/F10-7/F10-8 CONFIRMED
    # verbatim from spec_chapterF.txt printed 16.1-70.
    AISCClauseReference("AISC 360-22", "F10.3", "F10-6", "16.1-70"),
    AISCClauseReference("AISC 360-22", "F10.3", "F10-7", "16.1-70"),
    AISCClauseReference("AISC 360-22", "F10.3", "F10-8", "16.1-70"),
    # Single-angle-leg flexure B4.1b limits reach §F10 via the F-0
    # classifier; case label UNVERIFIED (likely Case 12,
    # ENGINEER-CONFIRM EC-4/EC-10) -> page=None.
    AISCClauseReference("AISC 360-22", "Table B4.1b", "Case ?", None),
)


# ---------------------------------------------------------------------------
# Internal helpers (one closed form each - keeps the public calculator a
# flat read; decomposed rather than silenced for complexity).
# ---------------------------------------------------------------------------
def _me_principal_major_equal_leg(
    *,
    elastic_modulus_E: float,
    gross_area_Ag: float,
    min_principal_radius_rz: float,
    thickness_t: float,
    Cb: float,
    unbraced_length_Lb: float,
) -> float:
    """Eq. F10-4 elastic LTB moment, equal-leg, major principal axis.

    ``beta_w = 0`` for an equal-leg angle (§F10.2(b)(1)), so the bracket
    collapses to ``1`` and
    ``Me = 9*E*Ag*rz*t*Cb / (8*Lb)``.  Reproduces AISC Manual v15.1
    Ex. F.11C ``Mcr = 195 kip-in`` exactly (CONFIRMED).
    """
    beta_w: float = 0.0  # §F10.2(b)(1): beta_w = 0 for an equal-leg angle
    bracket_arg: float = beta_w * min_principal_radius_rz / (unbraced_length_Lb * thickness_t)
    bracket: float = (
        math.sqrt(1.0 + _EQ_F10_4_BETA_W_COEFF * bracket_arg**2)
        + _EQ_F10_4_BETA_W_COEFF * bracket_arg
    )
    return (
        _EQ_F10_4_NUM_COEFF
        * elastic_modulus_E
        * gross_area_Ag
        * min_principal_radius_rz
        * thickness_t
        * Cb
        / (_EQ_F10_4_DEN_COEFF * unbraced_length_Lb)
        * bracket
    )


def _me_geometric_equal_leg(
    *,
    elastic_modulus_E: float,
    leg_width_b: float,
    thickness_t: float,
    Cb: float,
    unbraced_length_Lb: float,
    toe_in_compression: bool,
    lateral_torsional_restraint_at_max_moment: bool,
) -> float:
    """Eq. F10-5a / F10-5b geometric-axis elastic LTB moment ``Me``.

    **ENGINEER-CONFIRM F10-EC-1 RESOLVED.**  AISC 360-22 §F10.2(b),
    CONFIRMED verbatim from
    ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``
    (printed 16.1-69/70; equal-leg angle, geometric-axis bending, no
    axial compression)::

        Me = (0.58*E*b^4*t*Cb / Lb^2)
             * [ sqrt(1 + 0.88*(Lb*t / b^2)^2)  (-/+)  1 ]

    * ``- 1`` -> **Eq. F10-5a**: maximum **compression** at the toe.
    * ``+ 1`` -> **Eq. F10-5b**: maximum **tension** at the toe.

    with ``b`` the full width of the leg, ``t`` the leg thickness.  The
    ``b^4*t/Lb^2`` powers (NOT the previously rejected curated
    ``b*t^2/Lb``) make this dimensionally a moment -
    ``[F/L^2]*[L^4]*[L]/[L^2] = F*L`` - and reproduce the AISC Manual
    v15.1 published examples to the printed 3 sig figs: Ex. F.11A
    (L4x4x1/4, A36, ``b=4 in``, ``t=0.25 in``, ``Lb=72 in``,
    ``Cb=1.14``, compression at the toe) -> ``Mcr = 107 kip-in``;
    Ex. F.11B (same section, ``Lb=36 in``, ``Cb=1.30``, LT restraint at
    the max-moment point) -> ``Mcr = 1.25 * F10-5a = 176 kip-in``.

    Per §F10.2(b)(ii) (``spec_F10_geometric.txt`` L285-287), **with
    lateral-torsional restraint at the point of maximum moment only**
    ``Mcr`` is ``1.25`` times the Eq. F10-5a / F10-5b value (the
    ``My``-basis switch - ``0.80*Fy*Sx`` with no restraint vs the full
    ``Fy*Sx`` with restraint - is handled by the caller, mirroring the
    Manual's Ex. F.11A vs Ex. F.11B ``My``).
    """
    bracket_arg: float = unbraced_length_Lb * thickness_t / leg_width_b**2
    sign: float = -1.0 if toe_in_compression else 1.0  # F10-5a vs F10-5b
    me: float = (
        _EQ_F10_5_NUM_COEFF
        * elastic_modulus_E
        * leg_width_b**4
        * thickness_t
        * Cb
        / unbraced_length_Lb**2
        * (math.sqrt(1.0 + _EQ_F10_5_BRACKET_COEFF * bracket_arg**2) + sign)
    )
    if lateral_torsional_restraint_at_max_moment:
        me *= _F10_2B_II_RESTRAINT_FACTOR  # §F10.2(b)(ii)
    return me


def mn_ltb_from_me(*, yield_moment_My: float, elastic_LTB_moment_Me: float) -> float:
    """Eq. F10-2 / F10-3 LTB nominal moment from ``My`` and ``Me``.

    ``My/Me <= 1.0`` -> Eq. F10-2 ``Mn = (1.92 - 1.17*sqrt(My/Me))*My
    <= 1.5*My``; otherwise Eq. F10-3 ``Mn = (0.92 - 0.17*Me/My)*Me``.
    """
    ratio_My_Me: float = yield_moment_My / elastic_LTB_moment_Me
    if ratio_My_Me <= _EQ_F10_2_3_REGIME_LIMIT:
        mn_f10_2: float = (_EQ_F10_2_A - _EQ_F10_2_B * math.sqrt(ratio_My_Me)) * yield_moment_My
        cap: float = _EQ_F10_1_YIELD_FACTOR * yield_moment_My  # <= 1.5*My
        return min(mn_f10_2, cap)
    ratio_Me_My: float = elastic_LTB_moment_Me / yield_moment_My
    return (_EQ_F10_3_A - _EQ_F10_3_B * ratio_Me_My) * elastic_LTB_moment_Me


@dataclass(frozen=True, slots=True)
class _LegLocalBuckling:
    """§F10.3 leg-local-buckling sub-result (internal)."""

    leg_slenderness_b_t: float
    compact_limit_lambda_p: float
    noncompact_limit_lambda_r: float
    classification: str
    section_modulus_to_compression_toe_Sc: float
    critical_stress_Fcr: float
    nominal_moment_Mn: float


def _leg_local_buckling(
    *,
    material: SteelMaterial,
    leg_slenderness_b_t: float,
    section_modulus_S: float,
    toe_in_compression: bool,
    geometric_no_restraint: bool,
) -> _LegLocalBuckling:
    """§F10.3 leg local buckling (Eq. F10-6 / F10-7 / F10-8).

    Applies only when the toe of the leg is in compression (§F10.3 lead
    sentence).  ``b/t`` is classified by the F-0 generalized classifier
    (the single source of truth for the §F10.3 breakpoints - the
    ``0.54`` / ``0.91`` coefficients are *not* re-declared here):

    * compact   -> leg LB does not apply (``Mn = 0``);
    * noncompact -> Eq. F10-6 ``Mn = Fy*Sc*(2.43 - 1.72*(b/t)*
      sqrt(Fy/E))``;
    * slender   -> Eq. F10-7 ``Mn = Fcr*Sc`` with Eq. F10-8
      ``Fcr = 0.71*E/(b/t)^2``.

    ``Sc`` is the elastic modulus to the toe in compression; for a
    geometric-axis equal-leg angle with no lateral-torsional restraint
    it is ``0.80`` of the geometric modulus (§F10.3 ``Sc`` definition -
    the same ``0.80`` as §F10.2's ``My``).  When the toe is *not* in
    compression, leg LB does not apply and every field bar the
    classifier outputs is ``0.0``.

    **§F10.3 DRY (Phase F-8, decided):** the *identical* Eq. F10-6/7/8
    arithmetic also lives in
    :func:`apeSteel.flexure.F9_tee_double_angle._f10_3_leg_local_buckling`
    (used by §F9.3(b)/§F9.4(b) for double-angle legs).  The two were
    **deliberately NOT merged** into one shared helper: this function
    additionally calls the F-0 classifier, resolves ``Sc`` with the
    §F10.2 ``0.80`` geometric factor, and returns a rich
    :class:`_LegLocalBuckling` dataclass, whereas the §F9 sibling is a
    flat ``leg_class``+``Sc``-in -> ``Mn``-out function with a
    ``math.inf`` not-applicable sentinel (vs ``0.0`` here).  Per the
    Phase-F-8 contract **bit-exactness > DRY**: an extraction whose
    bit-exactness could not be *proven* by the gate is not taken.  The
    constants here (``_EQ_F10_6_A/_B``, ``_EQ_F10_8_FCR_COEFF``) and
    there (``_EQ_F10_6_A/_B``, ``_EQ_F10_8_COEFF``) are the same
    printed 16.1-70 literals, independently declared, so a typo in
    either surfaces as an oracle / golden disagreement.  See the
    matching cross-citing note on
    :func:`F9_tee_double_angle._f10_3_leg_local_buckling`.
    """
    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E

    classification_report = classify_flexural_compactness(
        material,
        section_kind="single_angle",
        angle_leg_slenderness_b_t=leg_slenderness_b_t,
    )
    leg_elements = classification_report.plate_elements
    if len(leg_elements) != 1:  # pragma: no cover - classifier invariant
        msg = f"single-angle classifier must emit exactly one leg element, got {len(leg_elements)}"
        raise ValueError(msg)
    leg_element = leg_elements[0]
    lambda_p: float = leg_element.compact_limit_lambda_p
    lambda_r: float = leg_element.noncompact_limit_lambda_r
    leg_class = leg_element.classification

    Sc: float = 0.0
    Fcr: float = 0.0
    mn_leg_lb: float = 0.0
    if toe_in_compression and leg_class != "compact":
        Sc = (
            _F10_GEOMETRIC_YIELD_FACTOR * section_modulus_S
            if geometric_no_restraint
            else section_modulus_S
        )
        if leg_class == "non_compact":
            # Eq. F10-6.
            mn_leg_lb = (
                Fy * Sc * (_EQ_F10_6_A - _EQ_F10_6_B * leg_slenderness_b_t * math.sqrt(Fy / E))
            )
        else:  # slender
            Fcr = _EQ_F10_8_FCR_COEFF * E / leg_slenderness_b_t**2  # Eq. F10-8
            mn_leg_lb = Fcr * Sc  # Eq. F10-7

    return _LegLocalBuckling(
        leg_slenderness_b_t=leg_slenderness_b_t,
        compact_limit_lambda_p=lambda_p,
        noncompact_limit_lambda_r=lambda_r,
        classification=leg_class,
        section_modulus_to_compression_toe_Sc=Sc,
        critical_stress_Fcr=Fcr,
        nominal_moment_Mn=mn_leg_lb,
    )


# ---------------------------------------------------------------------------
# Public calculator
# ---------------------------------------------------------------------------
def compute_flexural_strength_F10_single_angle(
    section_properties_or_fsp: FlexuralSectionProperties,
    material: SteelMaterial,
    *,
    unbraced_length_Lb: float,
    Cb: float = 1.0,
    bending_mode: SingleAngleBendingMode = "principal_major",
    toe_state: SingleAngleToeState = "compression_at_toe",
    section_modulus_S: float,
    lateral_torsional_restraint_at_max_moment: bool = False,
) -> FlexureF10Report:
    """Return ``Mn`` per AISC 360-22 §F10 for a single angle.

    ``Mn`` is the lowest of the applicable §F10 limit states (§F10 lead
    paragraph): yielding (Eq. F10-1), lateral-torsional buckling
    (Eq. F10-2/F10-3 via ``Me`` Eq. F10-4 / F10-5a / F10-5b), and leg
    local buckling (Eq. F10-6/F10-7/F10-8).  For the **minor principal
    axis** only yielding and leg local buckling apply (§F10 User Note).

    Parameters
    ----------
    section_properties_or_fsp : FlexuralSectionProperties
        A ``section_kind == "single_angle"`` snapshot, as produced by
        :meth:`SingleAngleSection.compute_section_properties`.  Reads
        ``gross_area_Ag``, ``min_principal_radius_rz``,
        ``overall_depth_d`` (= leg width ``b``), ``equal_leg`` and the
        leg ``b/t`` (re-derived from ``b`` and ``t``); ``S`` (the
        modulus that forms ``My``/``Sc``) is passed explicitly because
        which fibre governs depends on the load case (the Manual's
        ``SwC`` / ``SzB`` / ``SzC`` / geometric ``Sx``), and the §F10
        ``0.80`` geometric-axis reduction is applied here.
    material : SteelMaterial
        Reads ``Fy`` and ``E`` only.
    unbraced_length_Lb : float
        Laterally-unbraced length ``Lb`` (mm).  Must be positive (the
        LTB equations divide by it).
    Cb : float, optional
        Lateral-torsional-buckling modification factor (AISC §F1).
        Default ``1.0``.
    bending_mode : SingleAngleBendingMode, optional
        ``"principal_major"`` (default; Eq. F10-4 LTB - verified),
        ``"principal_minor"`` (no LTB - §F10 User Note), or
        ``"geometric"`` (equal-leg only; §F10.2(b) LTB via
        Eq. F10-5a/F10-5b - F10-EC-1 RESOLVED, CONFIRMED verbatim from
        ``spec_F10_geometric.txt`` and reproducing AISC Manual v15.1
        Ex. F.11A/F.11B).
    toe_state : SingleAngleToeState, optional
        ``"compression_at_toe"`` (default; Eq. F10-5a, and §F10.3 leg
        LB applies) or ``"tension_at_toe"`` (Eq. F10-5b; §F10.3 leg LB
        does **not** apply - the toe is not in compression).
    section_modulus_S : float
        The elastic section modulus (mm^3) to the fibre of interest for
        this load case (principal ``S``, or the *unreduced* geometric
        ``Sx``).  ``My`` and ``Sc`` are formed from this; the §F10.2 /
        §F10.3 ``0.80`` reduction for a geometric-axis equal-leg angle
        **without** lateral-torsional restraint is applied internally,
        so pass the unreduced geometric modulus.
    lateral_torsional_restraint_at_max_moment : bool, optional
        Geometric-axis only: ``True`` if there is lateral-torsional
        restraint at the point of maximum moment (§F10.2(b)(ii)) -
        ``Mcr`` is then ``1.25`` x the Eq. F10-5a/5b value and ``My =
        Fy*Sx`` (no ``0.80`` reduction).  Default ``False``.

    Returns
    -------
    FlexureF10Report
        Frozen dataclass exposing every §F10 intermediate.

    Raises
    ------
    ValueError
        If the snapshot is not ``single_angle``; if ``Lb`` or ``S`` is
        non-positive; or if geometric-axis bending is requested for an
        unequal-leg angle (§F10 permits geometric-axis design only for
        equal-leg angles).

    Notes
    -----
    **ENGINEER-CONFIRM F10-EC-1 RESOLVED.**  Earlier revisions raised
    :class:`NotImplementedError` for ``bending_mode == "geometric"``
    because the only available (curated) Eq. F10-5a form was
    dimensionally wrong and failed the AISC Manual cross-check.  The
    orchestrator re-pulled the authoritative §F10.2(b) form into
    ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``
    (printed 16.1-69/70); it is CONFIRMED verbatim, reproduces the
    Manual's published Ex. F.11A (107 kip-in) / Ex. F.11B (176 kip-in)
    ``Mcr``, and is now a fully-delivered limit state - geometric-axis
    bending no longer raises.
    """
    fsp: FlexuralSectionProperties = section_properties_or_fsp
    if fsp.section_kind != "single_angle":
        msg = f"§F10 applies only to single angles; got section_kind={fsp.section_kind!r}"
        raise ValueError(msg)
    if unbraced_length_Lb <= 0.0:
        raise ValueError(f"unbraced_length_Lb must be positive, got {unbraced_length_Lb!r}")
    if section_modulus_S <= 0.0:
        raise ValueError(f"section_modulus_S must be positive, got {section_modulus_S!r}")
    if bending_mode == "geometric" and not fsp.equal_leg:
        msg = (
            "AISC 360-22 §F10 permits geometric-axis design only for "
            "equal-leg single angles; this angle is unequal-leg."
        )
        raise ValueError(msg)

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E

    # Leg geometry: b = leg width (carried as overall_depth_d), t from
    # b and Ag for an equal-leg L (Ag = t*(2b - t) -> t solved); this
    # avoids adding a thickness field to the frozen model.  Equivalent
    # to the geometry's own ``leg``/``t`` (asserted in the golden).
    b: float = fsp.overall_depth_d
    if b <= 0.0:
        raise ValueError(f"single-angle leg width (overall_depth_d) must be positive, got {b!r}")
    # Ag = b*t + (b - t)*t = t*(2b - t)  ->  t^2 - 2b*t + Ag = 0
    #   t = b - sqrt(b^2 - Ag)   (the physical, thin-leg root).  For any
    #   real equal-leg L (t < b) Ag = t*(2b - t) < b^2, so the radicand
    #   is positive; guard a malformed snapshot rather than emit a math
    #   domain error.
    radicand: float = b**2 - fsp.gross_area_Ag
    if radicand <= 0.0:
        msg = (
            f"single-angle snapshot is not L-consistent: b^2 - Ag = {radicand!r} "
            f"(b={b!r}, Ag={fsp.gross_area_Ag!r}); Ag must satisfy Ag = t*(2b - t) "
            f"< b^2 for a real equal-leg angle."
        )
        raise ValueError(msg)
    t: float = b - math.sqrt(radicand)
    b_t: float = b / t

    # §F10 yield-moment bases (always from the section modulus, never a
    # plastic modulus).  AISC 360-22 §F10 uses TWO distinct ``My``:
    #
    #   * §F10.1 *yielding* (Eq. F10-1) always uses the full yield
    #     moment ``My_yield = Fy*S`` (geometric or principal modulus) -
    #     the §F10.2 0.80 reduction does NOT apply to Eq. F10-1
    #     (AISC Manual v15.1 Ex. F.11A prints "Mn = 1.5 My = 1.5 Fy Sx"
    #     for F10-1, and *separately* "My = 0.80 Fy Sx" under LTB).
    #
    #   * §F10.2 *LTB* (Eq. F10-2/F10-3) uses:
    #       - principal axis             -> My_ltb = Fy*S
    #       - geometric, no LT restraint -> My_ltb = 0.80*Fy*Sx (§F10.2)
    #       - geometric, LT restraint    -> My_ltb = Fy*Sx
    #                                       (§F10.2(b)(ii); Mcr x 1.25)
    geometric_no_restraint: bool = (
        bending_mode == "geometric" and not lateral_torsional_restraint_at_max_moment
    )
    My_yield: float = Fy * section_modulus_S  # Eq. F10-1 basis (always full)
    My_ltb: float = (
        _F10_GEOMETRIC_YIELD_FACTOR * Fy * section_modulus_S
        if geometric_no_restraint
        else Fy * section_modulus_S
    )

    # --- Limit state 1: yielding (Eq. F10-1) ---
    mn_yield: float = _EQ_F10_1_YIELD_FACTOR * My_yield

    # --- Limit state 2: lateral-torsional buckling (Eq. F10-2/F10-3) ---
    # The §F10 User Note: for the minor principal axis only yielding and
    # leg local buckling apply (no LTB).
    me: float = 0.0
    mn_ltb: float = 0.0
    if bending_mode == "principal_major":
        me = _me_principal_major_equal_leg(
            elastic_modulus_E=E,
            gross_area_Ag=fsp.gross_area_Ag,
            min_principal_radius_rz=fsp.min_principal_radius_rz,
            thickness_t=t,
            Cb=Cb,
            unbraced_length_Lb=unbraced_length_Lb,
        )
        mn_ltb = mn_ltb_from_me(yield_moment_My=My_ltb, elastic_LTB_moment_Me=me)
    elif bending_mode == "geometric":
        # §F10.2(b) geometric-axis LTB (equal-leg; F10-EC-1 RESOLVED -
        # Eq. F10-5a/F10-5b CONFIRMED verbatim from spec_F10_geometric
        # .txt and reproducing AISC Manual v15.1 Ex. F.11A Mcr = 107 /
        # Ex. F.11B Mcr = 176).  Eq. F10-5a (compression at the toe) vs
        # Eq. F10-5b (tension at the toe) is selected by ``toe_state``;
        # the §F10.2(b)(ii) 1.25 restraint factor is applied inside the
        # helper.  ``My_ltb`` already carries the matching basis -
        # 0.80*Fy*Sx with no restraint (§F10.2(b)(i)), the full Fy*Sx
        # with restraint at the max-moment point (§F10.2(b)(ii)).
        me = _me_geometric_equal_leg(
            elastic_modulus_E=E,
            leg_width_b=b,
            thickness_t=t,
            Cb=Cb,
            unbraced_length_Lb=unbraced_length_Lb,
            toe_in_compression=(toe_state == "compression_at_toe"),
            lateral_torsional_restraint_at_max_moment=lateral_torsional_restraint_at_max_moment,
        )
        mn_ltb = mn_ltb_from_me(yield_moment_My=My_ltb, elastic_LTB_moment_Me=me)
    # else principal_minor: no LTB limit state (§F10 User Note).

    # --- Limit state 3: leg local buckling (§F10.3, Eq. F10-6/7/8) ---
    # Decomposed into a helper (keeps this orchestration flat and the
    # §F10.3 classifier-coupling in one place); applies only when the
    # toe of the leg is in compression.
    llb = _leg_local_buckling(
        material=material,
        leg_slenderness_b_t=b_t,
        section_modulus_S=section_modulus_S,
        toe_in_compression=(toe_state == "compression_at_toe"),
        geometric_no_restraint=geometric_no_restraint,
    )

    # --- Governing: lowest applicable limit state ---
    candidates: list[tuple[str, float]] = [("yielding", mn_yield)]
    if bending_mode != "principal_minor":
        candidates.append(("lateral_torsional_buckling", mn_ltb))
    if llb.nominal_moment_Mn > 0.0:
        candidates.append(("leg_local_buckling", llb.nominal_moment_Mn))
    governing_limit_state, Mn = min(candidates, key=lambda kv: kv[1])

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF10Report(
        cited_clauses=_CITATIONS_F10,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        bending_mode=bending_mode,
        toe_state=toe_state,
        yield_moment_My=My_yield,
        yield_moment_for_LTB_My=My_ltb,
        yielding_moment_Mn_F10_1=mn_yield,
        elastic_LTB_moment_Me=me,
        LTB_moment_Mn_F10_2_3=mn_ltb,
        leg_slenderness_b_t=llb.leg_slenderness_b_t,
        leg_compact_limit_lambda_p=llb.compact_limit_lambda_p,
        leg_noncompact_limit_lambda_r=llb.noncompact_limit_lambda_r,
        leg_classification=llb.classification,
        section_modulus_to_compression_toe_Sc=llb.section_modulus_to_compression_toe_Sc,
        leg_LB_critical_stress_Fcr=llb.critical_stress_Fcr,
        leg_LB_moment_Mn_F10_6_7=llb.nominal_moment_Mn,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF10Report",
    "SingleAngleBendingMode",
    "SingleAngleToeState",
    "compute_flexural_strength_F10_single_angle",
    "mn_ltb_from_me",
]

"""AISC 360-22 §F9 - flexure of tees & double angles in the plane of symmetry.

This module is the pure §F9 calculator: it takes a tee / double-angle
:class:`FlexuralSectionProperties` snapshot (as produced natively by
``TeeSection.compute_section_properties`` /
``DoubleAngleSection.compute_section_properties``),
a material, the unbraced length ``Lb`` and the lateral-torsional-
buckling modification factor ``Cb``, plus the loading orientation
(whether the tee stem / double-angle web leg is in tension or
compression), and returns the nominal flexural strength ``Mn`` with the
controlling limit state identified.

§F9 (spec_chapterF.txt, printed 16.1-65 .. 16.1-68) takes ``Mn`` as the
lowest of four limit states:

* **Yielding (§F9.1):** ``Mn = Mp``                               (F9-1)

  * (a) tee stems / web legs in **tension**:
    ``Mp = Fy*Zx <= 1.6*My``                                      (F9-2)
    with ``My = Fy*Sx``                                           (F9-3)
  * (b) tee stems in **compression**: ``Mp = My``                 (F9-4)
  * (c) double angles with web legs in **compression**:
    ``Mp = 1.5*My``                                               (F9-5)

  Stem / web-leg **in compression is a low-ductility configuration**
  (the §F9 commentary; AISC Manual reference): the report sets
  :attr:`FlexureF9Report.stem_in_compression_low_ductility`.

* **Lateral-torsional buckling (§F9.2):**

  * (a) stems / web legs in **tension**: ``Lb <= Lp`` -> N/A;
    ``Lp < Lb <= Lr`` -> Eq. F9-6 inelastic interpolation;
    ``Lb > Lr`` -> ``Mn = Mcr``                                   (F9-7)
    with ``Lp`` (F9-8), ``Lr`` (F9-9), ``Mcr`` (F9-10) and the LTB
    constant ``B = +2.3 (d/Lb) sqrt(Iy/J)``                        (F9-11)
  * (b) stems / web legs in **compression** anywhere along ``Lb``:
    ``Mcr`` per F9-10 with the **sign of B reversed**
    ``B = -2.3 (d/Lb) sqrt(Iy/J)``                                 (F9-12);
    for tee stems ``Mn = Mcr <= My``                               (F9-13).
    For double-angle web legs **§F9.2(b)(2)** (F9-EC-1 **RESOLVED**):
    ``Mn`` is determined using **Eq. F10-2 / F10-3** with ``Mcr``
    from Eq. F9-10 and ``My`` from Eq. F9-3 (``Fy*Sx``).  §F10
    (Phase F-6) shipped before this phase (F-8); the §F10.2
    inelastic/elastic-LTB reduction (``F10_single_angle._mn_ltb_
    from_me``, the single source of truth for Eq. F10-2/F10-3) is
    reused via the permitted intra-``flexure``-layer import - **not**
    re-derived here, so §F9 and §F10 cannot disagree on that
    reduction.  (The earlier conservative §F9.2(b)(1)-form bound
    ``Mn = Mcr <= My`` is superseded; F9-EC-1 is closed - see the
    ENGINEER-CONFIRM ledger in ``_chapterF_citation_reference.md``.)

* **Flange local buckling (§F9.3):**

  * (a) tee flanges: compact -> N/A; noncompact ->
    ``Mn = Mp - (Mp - 0.7 Fy Sxc)(l-lpf)/(lrf-lpf) <= 1.6*My``     (F9-14);
    slender -> ``Mn = 0.7 E Sxc / (bf/2tf)^2``                     (F9-15)
  * (b) double-angle flange legs in compression -> §F10.3 with
    ``Sc = Sxc`` (Eq. F10-6 noncompact / F10-7 + F10-8 slender,
    re-derived inline below - §F10 is a later phase and must not be
    imported; the §F10.3 leg classification is supplied by the F-0
    classifier).

* **Local buckling of tee stems / double-angle web legs in flexural
  compression (§F9.4):**

  * (a) tee stems: ``Mn = Fcr*Sx``                                 (F9-16)
    with ``Fcr = Fy`` (F9-17), ``Fcr = (1.43 - 0.515 (d/tw)
    sqrt(Fy/E)) Fy`` (F9-18), ``Fcr = 1.52 E / (d/tw)^2`` (F9-19)
  * (b) double-angle web legs -> §F10.3 with ``Sc = Sx`` (same
    inline §F10.3 form as §F9.3(b)).

``phi_b = 0.90`` / ``Omega_b = 1.67`` (AISC 360-22 §F1), shared with the
rest of Chapter F via :mod:`apeSteel.flexure._common`.

The Table B4.1b Case 10 tee-flange ``lambda_pf`` / ``lambda_rf`` and the
§F9.4 stem (and §F10.3 double-angle leg) breakpoints are obtained from
the F-0 generalized classifier
:func:`apeSteel.classification.classify_flexural_compactness`
(``section_kind="tee"`` / ``"double_angle"``), not re-derived here, so
§F9 and the classifier cannot disagree on the regime boundaries.

Layering: this module is in the ``flexure`` layer; it imports only from
``sections`` (:class:`FlexuralSectionProperties`), ``classification``
(:func:`classify_flexural_compactness`), and ``core``.  It is **not**
wired into any facade / ``Element`` here - that is Phase F-8.

References
----------
.. [1] AISC 360-22 §F9 "Tees and Double Angles Loaded in the Plane of
       Symmetry", Eq. F9-1 - F9-19, pp. 16.1-65 - 16.1-68. American
       Institute of Steel Construction, 2022. Equation forms and page
       transcribed verbatim from
       ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt``.
.. [2] AISC 360-22 §F10.3 "Leg Local Buckling", Eq. F10-6 / F10-7 /
       F10-8, p. 16.1-70 (referenced by §F9.3(b) / §F9.4(b) for the
       double-angle leg checks; re-derived inline because §F10 is a
       later phase).
.. [3] AISC Manual v15.1 Vol.1, Example F.10 "WT-Shape Flexural
       Member", Manual p. F-45..F-47 (PDF p.192-194) - the §F9 tee
       external anchor (see ``tests/golden/test_chapterF_F9_golden.py``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification.flexural_compactness import classify_flexural_compactness
from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.flexure._common import (
    CITATIONS_AISC_360_CHAPTER_F,
    OMEGA_FLEXURE_ASD,
    PHI_FLEXURE_LRFD,
)
from apeSteel.flexure.F10_single_angle import mn_ltb_from_me

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.flexural_properties import (
        FlexuralPlateElement,
        FlexuralSectionProperties,
    )

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 §F9 (spec_chapterF.txt, printed 16.1-65..68)
#
# Each magic number is named + cited so the §F9 provenance is traceable
# at the call site, mirroring the F2 / F4 / F8 constant style.  The
# Table B4.1b Case 10 tee-flange lambda_pf / lambda_rf and the §F9.4
# stem / §F10.3 double-angle-leg breakpoint coefficients are NOT
# redeclared here: they live in the F-0 classifier and reach §F9
# through classify_flexural_compactness, so the two cannot drift.
# ---------------------------------------------------------------------------

#: AISC 360-22 Eq. F9-2 yielding cap multiplier: for tee stems / web
#: legs in tension ``Mp = Fy*Zx <= 1.6*My`` (spec_chapterF.txt printed
#: 16.1-66).  Also the §F9.3 Eq. F9-14 upper bound.
_EQ_F9_2_MY_CAP: float = 1.6

#: AISC 360-22 Eq. F9-5 double-angle (web legs in compression) yielding
#: multiplier: ``Mp = 1.5*My`` (spec_chapterF.txt printed 16.1-66).
_EQ_F9_5_MY_FACTOR: float = 1.5

#: AISC 360-22 Eq. F9-8 ``Lp = 1.76 * ry * sqrt(E/Fy)``
#: (spec_chapterF.txt printed 16.1-66).
_EQ_F9_8_LP_COEFF: float = 1.76

#: AISC 360-22 Eq. F9-9 leading coefficient
#: ``Lr = 1.95 (E/Fy) sqrt(Iy J)/Sx * sqrt(2.36 (Fy/E)(d Sx/J) + 1)``
#: (spec_chapterF.txt printed 16.1-66).
_EQ_F9_9_LR_COEFF: float = 1.95

#: AISC 360-22 Eq. F9-9 inner coefficient (the ``2.36`` under the
#: radical) (spec_chapterF.txt printed 16.1-66).
_EQ_F9_9_INNER_COEFF: float = 2.36

#: AISC 360-22 Eq. F9-10 leading coefficient
#: ``Mcr = (1.95 E / Lb) sqrt(Iy J)(B + sqrt(1 + B^2))``
#: (spec_chapterF.txt printed 16.1-66).
_EQ_F9_10_MCR_COEFF: float = 1.95

#: AISC 360-22 Eq. F9-11 / F9-12 LTB-constant coefficient
#: ``B = +/- 2.3 (d/Lb) sqrt(Iy/J)`` - the SIGN is ``+`` for stems /
#: web legs in tension (F9-11) and ``-`` when the stem / web leg is in
#: compression anywhere along ``Lb`` (F9-12) (spec_chapterF.txt printed
#: 16.1-66).
_EQ_F9_11_B_COEFF: float = 2.3

#: AISC 360-22 Eq. F9-15 slender-flange critical-stress numerator
#: ``Mn = 0.7 E Sxc / (bf/2tf)^2`` (spec_chapterF.txt printed 16.1-67).
#: Also the Eq. F9-14 residual-stress factor ``0.7 Fy Sxc``.
_EQ_F9_14_15_07: float = 0.7

#: AISC 360-22 Eq. F9-18 noncompact tee-stem critical-stress
#: coefficients ``Fcr = (1.43 - 0.515 (d/tw) sqrt(Fy/E)) Fy``
#: (spec_chapterF.txt printed 16.1-68).
_EQ_F9_18_A: float = 1.43
_EQ_F9_18_B: float = 0.515

#: AISC 360-22 Eq. F9-19 slender tee-stem critical-stress numerator
#: ``Fcr = 1.52 E / (d/tw)^2`` (spec_chapterF.txt printed 16.1-68).
_EQ_F9_19_COEFF: float = 1.52

#: AISC 360-22 Eq. F10-6 noncompact leg-local-buckling coefficients
#: ``Mn = Fy Sc (2.43 - 1.72 (b/t) sqrt(Fy/E))`` - used by §F9.3(b) /
#: §F9.4(b) for double-angle legs (spec_chapterF.txt printed 16.1-70).
_EQ_F10_6_A: float = 2.43
_EQ_F10_6_B: float = 1.72

#: AISC 360-22 Eq. F10-8 slender leg critical-stress numerator
#: ``Fcr = 0.71 E / (b/t)^2`` - used by §F9.3(b) / §F9.4(b) for
#: double-angle legs (spec_chapterF.txt printed 16.1-70).
_EQ_F10_8_COEFF: float = 0.71


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF9Report(Report):
    """AISC 360-22 §F9 flexural-strength result for a tee / double angle.

    All moments are in apeSteel base units (N*mm); lengths in mm;
    stresses in MPa.

    Attributes
    ----------
    section_kind : str
        ``"tee"`` or ``"double_angle"`` (echo of the input snapshot).
    stem_in_tension : bool
        ``True`` if the tee stem / double-angle web leg is in tension
        (the §F9.1(a) / §F9.2(a) branch); ``False`` if in compression
        (§F9.1(b)/(c), §F9.2(b)).
    stem_in_compression_low_ductility : bool
        ``True`` when the stem / web leg is in flexural compression -
        §F9 flags this as a low-ductility configuration.
    plastic_moment_Mp : float
        ``Mp`` per §F9.1 (Eq. F9-2 capped at ``1.6*My`` for stems in
        tension; ``My`` Eq. F9-4 for tee stems in compression;
        ``1.5*My`` Eq. F9-5 for 2L web legs in compression) (N*mm).
    yield_moment_My : float
        ``My = Fy*Sx`` (Eq. F9-3) (N*mm).
    yielding_moment_Mn_F9_1 : float
        The §F9.1 yielding ``Mn = Mp`` (N*mm).
    limiting_length_Lp : float
        Eq. F9-8 ``Lp`` (mm); ``0.0`` when LTB is not evaluated.
    limiting_length_Lr : float
        Eq. F9-9 ``Lr`` (mm); ``0.0`` when LTB is not evaluated.
    ltb_constant_B : float
        Eq. F9-11 (``+``) / F9-12 (``-``) ``B``; ``0.0`` when LTB not
        evaluated.
    critical_moment_Mcr : float
        Eq. F9-10 ``Mcr`` (N*mm); ``0.0`` when LTB not evaluated.
    lateral_torsional_buckling_moment_Mn_F9_2 : float
        The §F9.2 LTB ``Mn`` (N*mm); ``math.inf`` when LTB does not
        apply (so it never governs the ``min``).
    flange_slenderness_lambda : float
        Tee-flange ``bf/2tf`` (or double-angle flange-leg ``b/t``).
    compact_limit_lambda_pf : float
        Table B4.1b Case 10 (tee flange) / §F10.3 (2L leg)
        ``lambda_pf``.
    noncompact_limit_lambda_rf : float
        Table B4.1b Case 10 (tee flange) / §F10.3 (2L leg)
        ``lambda_rf``.
    flange_classification : str
        ``"compact"`` / ``"non_compact"`` / ``"slender"`` flange.
    flange_local_buckling_moment_Mn_F9_3 : float
        The §F9.3 FLB ``Mn`` (N*mm); ``math.inf`` when FLB does not
        apply.
    stem_slenderness_lambda : float
        Tee-stem ``d/tw`` (or double-angle web-leg ``b/t``).
    stem_compact_limit_lambda_p : float
        §F9.4 (tee stem) / §F10.3 (2L web leg) ``lambda_p``.
    stem_noncompact_limit_lambda_r : float
        §F9.4 (tee stem) / §F10.3 (2L web leg) ``lambda_r``.
    stem_classification : str
        ``"compact"`` / ``"non_compact"`` / ``"slender"`` stem / web
        leg.
    critical_stress_Fcr : float
        Eq. F9-17/18/19 (tee stem) or Eq. F10-8 (2L web leg) ``Fcr``
        (MPa); ``0.0`` when stem LB does not apply / not slender.
    stem_local_buckling_moment_Mn_F9_4 : float
        The §F9.4 stem / web-leg LB ``Mn`` (N*mm); ``math.inf`` when it
        does not apply (stem in tension, or compact stem).
    nominal_flexural_strength_Mn : float
        Final ``Mn = min`` of the applicable limit states (N*mm).
        Mirrors :attr:`Report.nominal_strength`.
    """

    section_kind: str = "tee"
    stem_in_tension: bool = True
    stem_in_compression_low_ductility: bool = False
    plastic_moment_Mp: float = 0.0
    yield_moment_My: float = 0.0
    yielding_moment_Mn_F9_1: float = 0.0
    limiting_length_Lp: float = 0.0
    limiting_length_Lr: float = 0.0
    ltb_constant_B: float = 0.0
    critical_moment_Mcr: float = 0.0
    lateral_torsional_buckling_moment_Mn_F9_2: float = 0.0
    flange_slenderness_lambda: float = 0.0
    compact_limit_lambda_pf: float = 0.0
    noncompact_limit_lambda_rf: float = 0.0
    flange_classification: str = "compact"
    flange_local_buckling_moment_Mn_F9_3: float = 0.0
    stem_slenderness_lambda: float = 0.0
    stem_compact_limit_lambda_p: float = 0.0
    stem_noncompact_limit_lambda_r: float = 0.0
    stem_classification: str = "compact"
    critical_stress_Fcr: float = 0.0
    stem_local_buckling_moment_Mn_F9_4: float = 0.0
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Equation-set citations
# ---------------------------------------------------------------------------
_CITATIONS_F9: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    # §F9 body - equation numbers + page verbatim from
    # spec_chapterF.txt (§F9 @ printed 16.1-65 .. 16.1-68).
    AISCClauseReference("AISC 360-22", "F9", None, "16.1-65"),
    AISCClauseReference("AISC 360-22", "F9.1", "F9-1", "16.1-65"),
    AISCClauseReference("AISC 360-22", "F9.1", "F9-2", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.1", "F9-3", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.1", "F9-4", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.1", "F9-5", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-6", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-7", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-8", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-9", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-10", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-11", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-12", "16.1-66"),
    AISCClauseReference("AISC 360-22", "F9.2", "F9-13", "16.1-67"),
    AISCClauseReference("AISC 360-22", "F9.3", "F9-14", "16.1-67"),
    AISCClauseReference("AISC 360-22", "F9.3", "F9-15", "16.1-67"),
    AISCClauseReference("AISC 360-22", "F9.4", "F9-16", "16.1-67"),
    AISCClauseReference("AISC 360-22", "F9.4", "F9-17", "16.1-68"),
    AISCClauseReference("AISC 360-22", "F9.4", "F9-18", "16.1-68"),
    AISCClauseReference("AISC 360-22", "F9.4", "F9-19", "16.1-68"),
    # §F10.3 (referenced by §F9.3(b) / §F9.4(b) for double-angle legs).
    AISCClauseReference("AISC 360-22", "F10.3", "F10-6", "16.1-70"),
    AISCClauseReference("AISC 360-22", "F10.3", "F10-7", "16.1-70"),
    AISCClauseReference("AISC 360-22", "F10.3", "F10-8", "16.1-70"),
    # Table B4.1b Case 10 (tee flange uses the rolled I-flange rule per
    # §F9.3); the §F9.4 stem and §F10.3 2L-leg breakpoints are defined
    # in the section text, not a B4.1b row (classifier ENGINEER-CONFIRM
    # EC-4/EC-5/EC-10), so they carry page=None.
    AISCClauseReference("AISC 360-22", "Table B4.1b", "Case 10", None),
)


# ---------------------------------------------------------------------------
# Limit-state helpers (decomposed so the public entry point stays flat -
# no PLR0912/PLR0915 silencing).
# ---------------------------------------------------------------------------
def _pick_flange_and_stem(
    fsp: FlexuralSectionProperties,
    material: SteelMaterial,
    *,
    flange_slenderness: float,
    stem_slenderness: float,
) -> tuple[FlexuralPlateElement, FlexuralPlateElement]:
    """Classify via the F-0 generalized classifier; return (flange, stem).

    For a tee the classifier emits ``flange`` (Table B4.1b Case 10) and
    ``stem`` (§F9.4 breakpoints).  For a double angle it emits a single
    ``leg`` element (§F10.3 breakpoints) which §F9.3(b)/§F9.4(b) use for
    *both* the flange-leg and web-leg checks - so the same element is
    returned for flange and stem.  The §F9 calculator never re-derives
    these limits (single source of truth with the classifier).
    """
    if fsp.section_kind == "tee":
        report = classify_flexural_compactness(
            material,
            section_kind="tee",
            flange_slenderness_bf_2tf=flange_slenderness,
            tee_stem_slenderness_d_tw=stem_slenderness,
        )
        elements = report.plate_elements
        if len(elements) != 2:  # pragma: no cover - classifier invariant
            msg = f"tee classifier must emit 2 elements, got {len(elements)}"
            raise ValueError(msg)
        flange_element = next(e for e in elements if e.role == "compression_flange")
        stem_element = next(e for e in elements if e.role == "stem")
        return flange_element, stem_element

    # double_angle: one §F10.3 leg element used for both leg checks.
    report = classify_flexural_compactness(
        material,
        section_kind="double_angle",
        angle_leg_slenderness_b_t=flange_slenderness,
    )
    elements = report.plate_elements
    if len(elements) != 1:  # pragma: no cover - classifier invariant
        msg = f"double_angle classifier must emit 1 leg element, got {len(elements)}"
        raise ValueError(msg)
    leg_element = elements[0]
    return leg_element, leg_element


def _yielding_Mp(
    fsp: FlexuralSectionProperties,
    *,
    Fy: float,
    My: float,
    stem_in_tension: bool,
) -> float:
    """§F9.1 ``Mp`` (Eq. F9-2 / F9-4 / F9-5)."""
    if stem_in_tension:
        # Eq. F9-2: tee stems / web legs in tension, Mp = Fy*Zx <= 1.6*My.
        return min(Fy * fsp.plastic_modulus_Zx, _EQ_F9_2_MY_CAP * My)
    if fsp.section_kind == "tee":
        # Eq. F9-4: tee stems in compression, Mp = My.
        return My
    # Eq. F9-5: double angles with web legs in compression, Mp = 1.5*My.
    return _EQ_F9_5_MY_FACTOR * My


def _ltb(
    fsp: FlexuralSectionProperties,
    *,
    Fy: float,
    E: float,
    My: float,
    Mp: float,
    Lb: float,
    Cb: float,
    stem_in_tension: bool,
) -> tuple[float, float, float, float, float]:
    """§F9.2 LTB ``(Mn, Lp, Lr, B, Mcr)``.

    Returns ``Mn = math.inf`` when LTB does not apply (stem in tension
    with ``Lb <= Lp``), so it never governs the final ``min``.
    """
    d: float = fsp.overall_depth_d
    Iy: float = fsp.moment_of_inertia_Iy
    J: float = fsp.torsional_constant_J
    Sx: float = fsp.elastic_modulus_Sx
    ry: float = fsp.radius_of_gyration_ry

    # B (Eq. F9-11 stems/web legs in tension; Eq. F9-12 in compression -
    # same magnitude, opposite sign).
    b_magnitude: float = _EQ_F9_11_B_COEFF * (d / Lb) * math.sqrt(Iy / J)
    B: float = b_magnitude if stem_in_tension else -b_magnitude

    # Mcr (Eq. F9-10) - common to both branches; Cb applied per §F1.
    Mcr: float = (
        Cb * (_EQ_F9_10_MCR_COEFF * E / Lb) * math.sqrt(Iy * J) * (B + math.sqrt(1.0 + B**2))
    )

    if not stem_in_tension:
        # §F9.2(b): stem / web leg in compression anywhere along Lb.
        # Lp / Lr (F9-8/F9-9) do not gate the compression branch (LTB
        # is always evaluated there); reported for trace.
        Lp_c: float = _EQ_F9_8_LP_COEFF * ry * math.sqrt(E / Fy)
        Lr_c: float = _lr_F9_9(Fy=Fy, E=E, Iy=Iy, J=J, Sx=Sx, d=d)
        if fsp.section_kind == "double_angle":
            # §F9.2(b)(2) (F9-EC-1 RESOLVED): "For double-angle web legs,
            # Mn shall be determined using Equations F10-2 and F10-3
            # with Mcr determined using Equation F9-10 and My determined
            # using Equation F9-3."  (spec_chapterF.txt printed 16.1-67,
            # §F9.2(b)(2) verbatim - the §F10.2 inelastic/elastic LTB
            # reduction applied to the §F9-10 Mcr with My = Fy*Sx.)
            # §F10 is an *earlier* phase here (F-6 shipped before F-8);
            # the intra-``flexure``-layer import of §F10's
            # ``mn_ltb_from_me`` (Eq. F10-2 / F10-3, the single source
            # of truth for that reduction) is permitted by the
            # architecture layer rule (``flexure`` may import
            # ``flexure``).  ``My`` here is Eq. F9-3 (Fy*Sx, the
            # ``My`` argument); the F9-10 ``Mcr`` plays the role of
            # §F10's ``Me``.
            mn_2l_ltb: float = mn_ltb_from_me(yield_moment_My=My, elastic_LTB_moment_Me=Mcr)
            return mn_2l_ltb, Lp_c, Lr_c, B, Mcr
        # Tee stems (§F9.2(b)(1), Eq. F9-13): Mn = Mcr <= My.
        return min(Mcr, My), Lp_c, Lr_c, B, Mcr

    # §F9.2(a): stems / web legs in tension.
    Lp: float = _EQ_F9_8_LP_COEFF * ry * math.sqrt(E / Fy)  # Eq. F9-8
    Lr: float = _lr_F9_9(Fy=Fy, E=E, Iy=Iy, J=J, Sx=Sx, d=d)  # Eq. F9-9
    if Lb <= Lp:
        # §F9.2(a)(1): LTB does not apply.
        return math.inf, Lp, Lr, B, Mcr
    if Lb <= Lr:
        # §F9.2(a)(2) Eq. F9-6: inelastic interpolation, capped at Mp.
        mn_interp: float = Mp - (Mp - My) * (Lb - Lp) / (Lr - Lp)
        return min(mn_interp, Mp), Lp, Lr, B, Mcr
    # §F9.2(a)(3) Eq. F9-7: Mn = Mcr.
    return Mcr, Lp, Lr, B, Mcr


def _lr_F9_9(*, Fy: float, E: float, Iy: float, J: float, Sx: float, d: float) -> float:
    """AISC 360-22 Eq. F9-9 ``Lr`` (spec_chapterF.txt printed 16.1-66).

    ``Lr = 1.95 (E/Fy) sqrt(Iy J)/Sx
            * sqrt( 2.36 (Fy/E)(d Sx/J) + 1 )``.
    """
    return (
        _EQ_F9_9_LR_COEFF
        * (E / Fy)
        * (math.sqrt(Iy * J) / Sx)
        * math.sqrt(_EQ_F9_9_INNER_COEFF * (Fy / E) * (d * Sx / J) + 1.0)
    )


def _flange_local_buckling(
    fsp: FlexuralSectionProperties,
    flange_element: FlexuralPlateElement,
    *,
    Fy: float,
    E: float,
    My: float,
    Mp: float,
) -> float:
    """§F9.3 flange local buckling ``Mn`` (Eq. F9-14 / F9-15, or §F10.3
    for double-angle flange legs).

    Returns ``math.inf`` when FLB does not apply (compact flange), so it
    never governs the final ``min``.
    """
    flange_class = flange_element.classification
    if flange_class == "compact":
        # §F9.3(a)(1) / §F10.3(a): FLB does not apply.
        return math.inf

    lambda_f: float = flange_element.slenderness_ratio_lambda
    lambda_pf: float = flange_element.compact_limit_lambda_p
    lambda_rf: float = flange_element.noncompact_limit_lambda_r
    Sxc: float = fsp.elastic_modulus_compression_flange_Sxc

    if fsp.section_kind == "double_angle":
        # §F9.3(b): double-angle flange legs -> §F10.3 with Sc = Sxc.
        return _f10_3_leg_local_buckling(
            flange_class,
            Fy=Fy,
            E=E,
            Sc=Sxc,
            b_t=lambda_f,
        )

    # §F9.3(a) tee flanges.
    residual: float = _EQ_F9_14_15_07 * Fy * Sxc
    cap: float = _EQ_F9_2_MY_CAP * My  # Eq. F9-14 upper bound 1.6*My
    if flange_class == "non_compact":
        # Eq. F9-14: Mn = Mp - (Mp - 0.7 Fy Sxc)(l-lpf)/(lrf-lpf) <= 1.6 My.
        mn: float = Mp - (Mp - residual) * (lambda_f - lambda_pf) / (lambda_rf - lambda_pf)
        return min(mn, cap)
    # Eq. F9-15: slender flange, Mn = 0.7 E Sxc / (bf/2tf)^2.
    return _EQ_F9_14_15_07 * E * Sxc / lambda_f**2


def _stem_local_buckling(
    fsp: FlexuralSectionProperties,
    stem_element: FlexuralPlateElement,
    *,
    Fy: float,
    E: float,
    stem_in_tension: bool,
) -> tuple[float, float]:
    """§F9.4 stem / web-leg local buckling ``(Mn, Fcr)``.

    §F9.4 applies only when the stem / web leg is in **flexural
    compression**; returns ``(math.inf, 0.0)`` when the stem is in
    tension (limit state does not apply) so it never governs the final
    ``min``.
    """
    if stem_in_tension:
        # §F9.4 applies only to stems / web legs in compression.
        return math.inf, 0.0

    Sx: float = fsp.elastic_modulus_Sx
    lambda_s: float = stem_element.slenderness_ratio_lambda

    if fsp.section_kind == "double_angle":
        # §F9.4(b): double-angle web legs -> §F10.3 with Sc = Sx.
        mn_2l: float = _f10_3_leg_local_buckling(
            stem_element.classification,
            Fy=Fy,
            E=E,
            Sc=Sx,
            b_t=lambda_s,
        )
        return mn_2l, 0.0

    # §F9.4(a) tee stems: Mn = Fcr*Sx (Eq. F9-16).  The compact /
    # noncompact stem boundaries d/tw = 0.84 sqrt(E/Fy) (Eq. F9-17) and
    # 1.52 sqrt(E/Fy) (Eq. F9-19) come from the F-0 classifier
    # (F9_4_TEE_STEM_COMPACT_COEFF / _NONCOMPACT_COEFF reach §F9 through
    # stem_element) - single source of truth, NOT re-declared here.
    boundary_p: float = stem_element.compact_limit_lambda_p  # 0.84 sqrt(E/Fy)
    boundary_r: float = stem_element.noncompact_limit_lambda_r  # 1.52 sqrt(E/Fy)
    if lambda_s <= boundary_p:
        # Eq. F9-17: Fcr = Fy.
        Fcr: float = Fy
    elif lambda_s <= boundary_r:
        # Eq. F9-18: Fcr = (1.43 - 0.515 (d/tw) sqrt(Fy/E)) Fy.
        Fcr = (_EQ_F9_18_A - _EQ_F9_18_B * lambda_s * math.sqrt(Fy / E)) * Fy
    else:
        # Eq. F9-19: Fcr = 1.52 E / (d/tw)^2.
        Fcr = _EQ_F9_19_COEFF * E / lambda_s**2
    return Fcr * Sx, Fcr


def _f10_3_leg_local_buckling(
    leg_class: str,
    *,
    Fy: float,
    E: float,
    Sc: float,
    b_t: float,
) -> float:
    """AISC 360-22 §F10.3 leg local buckling ``Mn`` (Eq. F10-6/7/8).

    Referenced by §F9.3(b) / §F9.4(b) for double-angle legs.  The
    §F10.3 leg ``lambda_p``/``lambda_r`` classification is supplied by
    the F-0 classifier (``leg_class``); the Eq. F10-6/7/8 *forms* are
    re-derived here verbatim from spec_chapterF.txt (printed 16.1-70).

    * compact -> §F10.3(a): does not apply (``math.inf``);
    * noncompact -> Eq. F10-6 ``Mn = Fy Sc (2.43 - 1.72 (b/t)
      sqrt(Fy/E))``;
    * slender -> Eq. F10-7 ``Mn = Fcr Sc``, Eq. F10-8
      ``Fcr = 0.71 E / (b/t)^2``.

    **§F10.3 DRY (Phase F-8, decided):** the *identical* Eq. F10-6/7/8
    arithmetic also lives in
    :func:`apeSteel.flexure.F10_single_angle._leg_local_buckling`.
    The two were **deliberately NOT merged** into one shared helper:
    that sibling does considerably more (it also calls the F-0
    classifier, resolves ``Sc`` with the §F10.2 ``0.80`` geometric
    factor, and returns a rich ``_LegLocalBuckling`` dataclass with
    ``lambda_p``/``lambda_r``/``Fcr``/``classification``), and uses a
    different not-applicable sentinel (``0.0`` vs this function's
    ``math.inf``, which lets §F9's ``min(...)`` ignore it).  Folding
    them would have to reconcile those flows; per the Phase-F-8
    contract **bit-exactness > DRY** and an extraction whose
    bit-exactness could not be *proven* by the gate is not taken.  The
    constants here (``_EQ_F10_6_A/_B``, ``_EQ_F10_8_COEFF``) and there
    (``_EQ_F10_6_A/_B``, ``_EQ_F10_8_FCR_COEFF``) are the same printed
    16.1-70 literals, independently declared, so a typo in either
    surfaces as an oracle / golden disagreement.  See the matching
    cross-citing note on
    :func:`F10_single_angle._leg_local_buckling`.
    """
    if leg_class == "compact":
        return math.inf
    if leg_class == "non_compact":
        # Eq. F10-6.
        return Fy * Sc * (_EQ_F10_6_A - _EQ_F10_6_B * b_t * math.sqrt(Fy / E))
    # Eq. F10-7 + F10-8.
    Fcr: float = _EQ_F10_8_COEFF * E / b_t**2
    return Fcr * Sc


# ---------------------------------------------------------------------------
# Public calculator
# ---------------------------------------------------------------------------
def compute_flexural_strength_F9_tee_double_angle(
    section_properties_or_fsp: FlexuralSectionProperties,
    material: SteelMaterial,
    *,
    unbraced_length_Lb: float,
    flange_slenderness_bf_2tf: float,
    stem_slenderness_d_tw: float,
    lateral_torsional_buckling_factor_Cb: float = 1.0,
    stem_in_tension: bool = True,
) -> FlexureF9Report:
    """Return ``Mn`` per AISC 360-22 §F9 for a tee / double angle.

    ``Mn`` is the lowest of the four §F9 limit states - yielding
    (§F9.1, Eq. F9-1..F9-5), lateral-torsional buckling (§F9.2,
    Eq. F9-6..F9-13), flange local buckling (§F9.3, Eq. F9-14/F9-15,
    or §F10.3 for double-angle flange legs) and local buckling of tee
    stems / double-angle web legs in flexural compression (§F9.4,
    Eq. F9-16..F9-19, or §F10.3 for double-angle web legs).

    The Table B4.1b Case 10 tee-flange limits and the §F9.4 stem /
    §F10.3 double-angle-leg breakpoints come from the F-0 generalized
    classifier
    :func:`~apeSteel.classification.classify_flexural_compactness`
    (so §F9 and the classifier share one source of truth for the regime
    boundaries); only the section moduli / geometry are read from
    ``section_properties_or_fsp``.

    Parameters
    ----------
    section_properties_or_fsp : FlexuralSectionProperties
        A ``section_kind in {"tee", "double_angle"}`` snapshot, as
        produced by
        :meth:`TeeSection.compute_section_properties` /
        :meth:`DoubleAngleSection.compute_section_properties`.  Tees and
        double angles have no legacy I-shape :class:`SectionProperties`
        representation, so this is always the generalized currency (the
        parameter name mirrors the other §F calculators' dual-input
        contract).  Reads ``plastic_modulus_Zx``, ``elastic_modulus_Sx``,
        ``elastic_modulus_compression_flange_Sxc``, ``overall_depth_d``,
        ``moment_of_inertia_Iy``, ``torsional_constant_J`` and
        ``radius_of_gyration_ry``.
    material : SteelMaterial
        Reads ``Fy`` and ``E`` only.
    unbraced_length_Lb : float
        Laterally-unbraced length ``Lb`` (mm), > 0.  A continuously
        braced member (the AISC Manual Ex. F.10 case) has no LTB limit
        state; pass a tiny ``Lb`` (so ``Lb <= Lp`` and §F9.2(a)(1)
        applies) or simply note LTB is N/A - the report exposes the
        regime so the caller can confirm.
    flange_slenderness_bf_2tf : float
        Tee flange ``bf/2tf`` (Table B4.1b Case 10 via §F9.3) - or the
        double-angle flange-leg ``b/t`` (§F10.3 via §F9.3(b)).
    stem_slenderness_d_tw : float
        Tee stem ``d/tw`` (§F9.4) - or the double-angle web-leg ``b/t``
        (§F10.3 via §F9.4(b)).  For a double angle this is ignored (the
        classifier emits a single §F10.3 leg element used for both leg
        checks); pass the leg ``b/t`` for trace.
    lateral_torsional_buckling_factor_Cb : float, optional
        AISC §F1 ``Cb`` (default ``1.0``).  Applied to Eq. F9-10
        ``Mcr``.
    stem_in_tension : bool, optional
        ``True`` (default) -> the tee stem / double-angle web leg is in
        tension (§F9.1(a)/§F9.2(a); the usual WT-with-stem-in-tension
        orientation, Manual Ex. F.10).  ``False`` -> the stem / web leg
        is in compression (§F9.1(b)/(c), §F9.2(b), §F9.4) - flagged as
        a low-ductility configuration in the report.

    Returns
    -------
    FlexureF9Report
        Frozen dataclass with every §F9 intermediate exposed.

    Raises
    ------
    ValueError
        If ``section_properties_or_fsp.section_kind`` is not ``"tee"``
        or ``"double_angle"``; or if ``unbraced_length_Lb`` is
        non-positive.
    """
    fsp: FlexuralSectionProperties = section_properties_or_fsp
    if fsp.section_kind not in ("tee", "double_angle"):
        msg = f"§F9 applies only to tees and double angles; got section_kind={fsp.section_kind!r}"
        raise ValueError(msg)
    if unbraced_length_Lb <= 0.0:
        msg = f"unbraced_length_Lb must be positive, got {unbraced_length_Lb!r}"
        raise ValueError(msg)

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E

    flange_element, stem_element = _pick_flange_and_stem(
        fsp,
        material,
        flange_slenderness=flange_slenderness_bf_2tf,
        stem_slenderness=stem_slenderness_d_tw,
    )

    # §F9.1 yielding.  My = Fy*Sx (Eq. F9-3); Mp per F9-2/F9-4/F9-5.
    My: float = Fy * fsp.elastic_modulus_Sx
    Mp: float = _yielding_Mp(fsp, Fy=Fy, My=My, stem_in_tension=stem_in_tension)
    mn_yield: float = Mp  # Eq. F9-1

    # §F9.2 LTB.
    mn_ltb, Lp, Lr, B, Mcr = _ltb(
        fsp,
        Fy=Fy,
        E=E,
        My=My,
        Mp=Mp,
        Lb=unbraced_length_Lb,
        Cb=lateral_torsional_buckling_factor_Cb,
        stem_in_tension=stem_in_tension,
    )

    # §F9.3 flange local buckling.
    mn_flb: float = _flange_local_buckling(fsp, flange_element, Fy=Fy, E=E, My=My, Mp=Mp)

    # §F9.4 stem / web-leg local buckling.
    mn_slb, Fcr = _stem_local_buckling(
        fsp, stem_element, Fy=Fy, E=E, stem_in_tension=stem_in_tension
    )

    # Mn = lowest applicable limit state (non-applicable states are
    # math.inf so they never win).
    candidates: dict[str, float] = {
        "yielding": mn_yield,
        "lateral_torsional_buckling": mn_ltb,
        "flange_local_buckling": mn_flb,
        "stem_local_buckling": mn_slb,
    }
    governing_limit_state: str = min(candidates, key=lambda k: candidates[k])
    Mn: float = candidates[governing_limit_state]

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF9Report(
        cited_clauses=_CITATIONS_F9,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        section_kind=fsp.section_kind,
        stem_in_tension=stem_in_tension,
        stem_in_compression_low_ductility=not stem_in_tension,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
        yielding_moment_Mn_F9_1=mn_yield,
        limiting_length_Lp=Lp,
        limiting_length_Lr=Lr,
        ltb_constant_B=B,
        critical_moment_Mcr=Mcr,
        lateral_torsional_buckling_moment_Mn_F9_2=mn_ltb,
        flange_slenderness_lambda=flange_element.slenderness_ratio_lambda,
        compact_limit_lambda_pf=flange_element.compact_limit_lambda_p,
        noncompact_limit_lambda_rf=flange_element.noncompact_limit_lambda_r,
        flange_classification=flange_element.classification,
        flange_local_buckling_moment_Mn_F9_3=mn_flb,
        stem_slenderness_lambda=stem_element.slenderness_ratio_lambda,
        stem_compact_limit_lambda_p=stem_element.compact_limit_lambda_p,
        stem_noncompact_limit_lambda_r=stem_element.noncompact_limit_lambda_r,
        stem_classification=stem_element.classification,
        critical_stress_Fcr=Fcr,
        stem_local_buckling_moment_Mn_F9_4=mn_slb,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF9Report",
    "compute_flexural_strength_F9_tee_double_angle",
]

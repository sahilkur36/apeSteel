"""AISC 360-22 §F7 - flexural strength of square / rectangular HSS & box.

This module is the pure §F7 calculator: it takes a rectangular-HSS
:class:`FlexuralSectionProperties` snapshot (as produced natively by
:meth:`apeSteel.sections.geometry.rectangular_hss.RectangularHSS.compute_section_properties`),
a material, and a bending axis, and returns the nominal flexural
strength ``Mn`` with the controlling §F7 limit state identified.

§F7 applies to square and rectangular HSS and box sections bent about
**either axis**.  ``Mn`` is the lowest value of four limit states
(AISC 360-22 §F7 lead paragraph, spec_chapterF.txt printed 16.1-63):

* **Yielding** (Eq. F7-1) ``Mn = Mp = Fy*Z``;
* **Flange local buckling** (§F7.2) - compact flange: N/A;
  noncompact (Eq. F7-2)
  ``Mn = Mp - (Mp - Fy*S)(lambda - lambda_pf)/(lambda_rf - lambda_pf)
  <= Mp``; slender (Eq. F7-3) ``Mn = Fy*Se`` with the effective
  compression-flange width ``be`` from Eq. F7-4 (HSS) / Eq. F7-5 (box);
* **Web local buckling** (§F7.3) - compact web: N/A; noncompact
  (Eq. F7-6); slender web (Eq. F7-7) ``Mn = Rpg*Fy*S`` - the §F7.3
  User Note states *there are no HSS with slender webs*, so the
  slender-web branch is only ever reachable by a box section;
* **Lateral-torsional buckling** (§F7.4) - ``Lb <= Lp``: N/A;
  ``Lp < Lb <= Lr`` (Eq. F7-10); ``Lb > Lr`` (Eq. F7-11), with
  ``Lp`` (Eq. F7-12) and ``Lr`` (Eq. F7-13).  Per the §F7.4 User Note
  *lateral-torsional buckling will not occur in square sections or
  sections bending about their minor axis* - that gate is implemented
  explicitly (LTB is skipped for ``B == H`` and for
  ``bending_axis == "minor"``).

``Mn = min(applicable limit states)``.  The Table B4.1b flange / web
``lambda_p`` / ``lambda_r`` are obtained from the F-0 generalized
classifier
:func:`apeSteel.classification.classify_flexural_compactness`
(``section_kind="rectangular_HSS"``), not re-derived here, so §F7 and
the classifier cannot disagree on the regime boundaries.

``phi_b = 0.90`` / ``Omega_b = 1.67`` (AISC 360-22 §F1), shared with
the rest of Chapter F via :mod:`apeSteel.flexure._common`.

Layering: this module is in the ``flexure`` layer; it imports only from
``sections`` (:class:`FlexuralSectionProperties`), ``classification``
(:func:`classify_flexural_compactness`), and ``core``.  It is **not**
wired into any facade / ``Element`` here - that is Phase F-8.

§F13.1 (tension-flange-hole rupture) is **not** invoked here: §F7
itself does not call §F13.1, and a standalone net-flexural-rupture
calculator is a separate per-phase add (design note 10 §1).  The report
flags this so a caller designing a holed HSS knows to apply §F13.1
separately.

References
----------
.. [1] AISC 360-22 §F7 "Square and Rectangular HSS and Box Sections",
       Eq. F7-1 - F7-13, pp. 16.1-63 - 16.1-65. American Institute of
       Steel Construction, 2022. Equation forms and page transcribed
       verbatim from
       ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` and
       ``docs/design_notes/_chapterF_citation_reference.md`` (§F7 row).
.. [2] AISC 360-22 Table B4.1b square / rectangular HSS flexure rows
       (flange ``lambda_p = 1.12 sqrt(E/Fy)``,
       ``lambda_r = 1.40 sqrt(E/Fy)``; web
       ``lambda_p = 2.42 sqrt(E/Fy)``, ``lambda_r = 5.70 sqrt(E/Fy)``).
       The exact B4.1b *case numbers* (conventionally Case 17 flange /
       Case 19 web - the value the AISC Manual v15.1 Ex. F.7B / F.8B
       prints) are ENGINEER-CONFIRM EC-1 / EC-2, so those rows carry
       ``page=None`` and ``equation="Case ?"``; the numeric limits do
       not depend on the label and the independent oracle re-derives
       them numerically.
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

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.flexural_properties import (
        BendingAxis,
        FlexuralPlateElement,
        FlexuralSectionProperties,
    )

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 §F7 (spec_chapterF.txt, printed 16.1-63 .. 16.1-65)
#
# Each magic number is named + cited so the §F7 provenance is traceable
# at the call site, mirroring the F2 / F4 / F8 constant style.  The
# Table B4.1b flange / web lambda_p / lambda_r coefficients
# (1.12 / 1.40 flange, 2.42 / 5.70 web, of sqrt(E/Fy)) are NOT
# redeclared here: they live in the F-0 classifier
# (B4_1B_HSS_FLANGE_* / B4_1B_HSS_WEB_*) and reach §F7 through
# classify_flexural_compactness, so the two cannot drift.
# ---------------------------------------------------------------------------

#: AISC 360-22 Eq. F7-4 effective-width coefficient for **HSS**:
#: ``be = 1.92 t sqrt(E/Fy) (1 - 0.38/(b/t) sqrt(E/Fy)) <= b``
#: (spec_chapterF.txt printed 16.1-63).
_EQ_F7_4_5_LEAD_COEFF: float = 1.92

#: AISC 360-22 Eq. F7-4 inner ``0.38`` coefficient (HSS effective width).
_EQ_F7_4_HSS_INNER_COEFF: float = 0.38

#: AISC 360-22 Eq. F7-5 inner ``0.34`` coefficient (box effective width).
_EQ_F7_5_BOX_INNER_COEFF: float = 0.34

#: AISC 360-22 §F7.4 lateral-torsional-buckling stress fraction
#: ``0.7 Fy`` in Eq. F7-10 / Eq. F7-13 (spec_chapterF.txt 16.1-64/65).
_EQ_F7_LTB_STRESS_FRACTION_OF_FY: float = 0.7

#: AISC 360-22 Eq. F7-12 ``Lp = 0.13 E ry sqrt(J Ag) / Mp``
#: (spec_chapterF.txt printed 16.1-64).
_EQ_F7_12_LP_COEFF: float = 0.13

#: AISC 360-22 Eq. F7-13 / Eq. F7-11 leading ``2`` in
#: ``Lr = 2 E ry sqrt(J Ag) / (0.7 Fy Sx)`` and
#: ``Mn = 2 E Cb sqrt(J Ag) / (Lb/ry)`` (spec_chapterF.txt 16.1-64/65).
_EQ_F7_11_13_LEAD_COEFF: float = 2.0

#: AISC 360-22 Eq. F5-6 web-slenderness term ``5.7 sqrt(E/Fy)`` (the
#: §F7.3 slender-web branch reuses Eq. F5-6 for ``Rpg``;
#: spec_chapterF.txt printed 16.1-61).
_EQ_F5_6_RPG_WEB_COEFF: float = 5.7

#: AISC 360-22 Eq. F5-6 ``Rpg`` denominator constants ``1200`` and
#: ``300`` in ``Rpg = 1 - aw/(1200 + 300 aw) (hc/tw - 5.7 sqrt(E/Fy))``.
_EQ_F5_6_RPG_DENOM_A: float = 1200.0
_EQ_F5_6_RPG_DENOM_B: float = 300.0

#: AISC 360-22 §F7.3 ``aw`` for the slender-web branch:
#: ``aw = 2 h tw / (b tf)`` (spec_chapterF.txt printed 16.1-64), and
#: per Eq. F5-6 / Eq. F4-12 ``aw`` shall not exceed 10.
_F7_3_AW_LEAD_COEFF: float = 2.0
_F7_3_AW_MAX: float = 10.0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF7Report(Report):
    """AISC 360-22 §F7 flexural-strength result for a rect / square HSS.

    All moments are in apeSteel base units (N*mm); lengths in mm;
    stresses in MPa.

    Attributes
    ----------
    bending_axis : str
        ``"major"`` or ``"minor"`` - the axis this result is for.
    flange_slenderness_b_t : float
        Compression-flange flat-width ``b/t`` for the requested axis.
    flange_compact_limit_lambda_p, flange_noncompact_limit_lambda_r : float
        Table B4.1b flange ``lambda_p = 1.12 sqrt(E/Fy)`` /
        ``lambda_r = 1.40 sqrt(E/Fy)``.
    flange_classification : str
        ``"compact"`` / ``"non_compact"`` / ``"slender"`` (flange).
    web_slenderness_h_t : float
        Web flat-depth ``h/t`` for the requested axis.
    web_compact_limit_lambda_p, web_noncompact_limit_lambda_r : float
        Table B4.1b web ``lambda_p = 2.42 sqrt(E/Fy)`` /
        ``lambda_r = 5.70 sqrt(E/Fy)``.
    web_classification : str
        ``"compact"`` / ``"non_compact"`` / ``"slender"`` (web).
    plastic_moment_Mp : float
        ``Mp = Fy*Z``, the Eq. F7-1 plateau (N*mm).
    yield_moment_My : float
        ``My = Fy*S`` about the bending axis (N*mm), reported for trace.
    effective_section_modulus_Se : float
        Eq. F7-3 effective section modulus for a slender flange (mm^3);
        ``0.0`` unless the flange is slender.
    Mn_yielding : float
        Eq. F7-1 ``Mp`` (N*mm).
    Mn_flange_local_buckling : float
        §F7.2 flange-local-buckling ``Mn`` (N*mm); equals ``Mp`` when
        the flange is compact (limit state does not apply).
    Mn_web_local_buckling : float
        §F7.3 web-local-buckling ``Mn`` (N*mm); equals ``Mp`` when the
        web is compact (limit state does not apply).
    Mn_lateral_torsional_buckling : float
        §F7.4 LTB ``Mn`` (N*mm); equals ``Mp`` (LTB does not apply) for
        a square section, for minor-axis bending, or when
        ``Lb <= Lp`` / no unbraced length is supplied.
    limiting_length_Lp, limiting_length_Lr : float
        Eq. F7-12 / Eq. F7-13 LTB lengths (mm); ``0.0`` when LTB is N/A.
    lateral_torsional_buckling_applies : bool
        ``False`` when the §F7.4 User Note exclusion fires (square HSS
        or minor-axis bending) or no ``Lb`` is supplied.
    unbraced_length_Lb : float
        The ``Lb`` used (mm); ``0.0`` if none supplied.
    Cb : float
        The lateral-torsional-buckling modification factor used (§F1).
    nominal_flexural_strength_Mn : float
        Final ``Mn = min(applicable)`` (N*mm).  Mirrors
        :attr:`Report.nominal_strength`.
    tension_flange_hole_rupture_check_required : bool
        Always ``True`` - §F7 itself does not cover §F13.1; a caller
        with bolt holes in the tension flange must apply §F13.1
        separately (design note 10 §1).  No numeric reduction is
        applied here.
    """

    bending_axis: str = "major"
    flange_slenderness_b_t: float = 0.0
    flange_compact_limit_lambda_p: float = 0.0
    flange_noncompact_limit_lambda_r: float = 0.0
    flange_classification: str = "compact"
    web_slenderness_h_t: float = 0.0
    web_compact_limit_lambda_p: float = 0.0
    web_noncompact_limit_lambda_r: float = 0.0
    web_classification: str = "compact"
    plastic_moment_Mp: float = 0.0
    yield_moment_My: float = 0.0
    effective_section_modulus_Se: float = 0.0
    Mn_yielding: float = 0.0
    Mn_flange_local_buckling: float = 0.0
    Mn_web_local_buckling: float = 0.0
    Mn_lateral_torsional_buckling: float = 0.0
    limiting_length_Lp: float = 0.0
    limiting_length_Lr: float = 0.0
    lateral_torsional_buckling_applies: bool = False
    unbraced_length_Lb: float = 0.0
    Cb: float = 1.0
    nominal_flexural_strength_Mn: float = 0.0
    tension_flange_hole_rupture_check_required: bool = True


# ---------------------------------------------------------------------------
# Equation-set citations
# ---------------------------------------------------------------------------
_CITATIONS_F7: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    # §F7 body - equation numbers + page verbatim from
    # spec_chapterF.txt / _chapterF_citation_reference.md (§F7 row,
    # printed 16.1-63 .. 16.1-65).
    AISCClauseReference("AISC 360-22", "F7", None, "16.1-63"),
    AISCClauseReference("AISC 360-22", "F7.1", "F7-1", "16.1-63"),
    AISCClauseReference("AISC 360-22", "F7.2", "F7-2", "16.1-63"),
    AISCClauseReference("AISC 360-22", "F7.2", "F7-3", "16.1-63"),
    AISCClauseReference("AISC 360-22", "F7.2", "F7-4", "16.1-63"),
    AISCClauseReference("AISC 360-22", "F7.2", "F7-5", "16.1-63"),
    AISCClauseReference("AISC 360-22", "F7.3", "F7-6", "16.1-63"),
    AISCClauseReference("AISC 360-22", "F7.3", "F7-7", "16.1-64"),
    AISCClauseReference("AISC 360-22", "F7.4", "F7-10", "16.1-64"),
    AISCClauseReference("AISC 360-22", "F7.4", "F7-11", "16.1-64"),
    AISCClauseReference("AISC 360-22", "F7.4", "F7-12", "16.1-64"),
    AISCClauseReference("AISC 360-22", "F7.4", "F7-13", "16.1-64"),
    # §F7.3 slender-web branch reuses Eq. F5-6 for Rpg.
    AISCClauseReference("AISC 360-22", "F5.2", "F5-6", "16.1-61"),
    # Table B4.1b HSS flange / web flexure rows - case numbers are
    # ENGINEER-CONFIRM EC-1 (flange, ~Case 17) / EC-2 (web, ~Case 19);
    # page=None - never invented.
    AISCClauseReference("AISC 360-22", "Table B4.1b", "Case ?", None),
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _interp_local_buckling(
    Mp: float,
    Fy_S: float,
    lam: float,
    lam_p: float,
    lam_r: float,
) -> float:
    """Eq. F7-2 / Eq. F7-6 noncompact linear interpolation, capped at ``Mp``.

    ``Mn = Mp - (Mp - Fy*S) (lambda - lambda_p)/(lambda_r - lambda_p)
    <= Mp`` - the identical functional form is used by §F7.2 (flange,
    Eq. F7-2) and §F7.3 (web, Eq. F7-6); only the slenderness and the
    Table B4.1b limits differ.
    """
    Mn = Mp - (Mp - Fy_S) * (lam - lam_p) / (lam_r - lam_p)
    return min(Mn, Mp)


def _effective_width_be(
    *,
    b: float,
    t: float,
    E: float,
    Fy: float,
    inner_coeff: float,
) -> float:
    """Eq. F7-4 (HSS, ``inner_coeff=0.38``) / Eq. F7-5 (box, ``0.34``).

    ``be = 1.92 t sqrt(E/Fy) (1 - inner_coeff/(b/t) sqrt(E/Fy)) <= b``.
    """
    sqrt_E_Fy = math.sqrt(E / Fy)
    b_t = b / t
    be = _EQ_F7_4_5_LEAD_COEFF * t * sqrt_E_Fy * (1.0 - inner_coeff / b_t * sqrt_E_Fy)
    return min(be, b)


def _effective_section_modulus_Se(
    *,
    I_axis: float,
    section_depth_d: float,
    b_flange_flat: float,
    be: float,
    tf: float,
) -> float:
    """Eq. F7-3 effective section modulus for a slender HSS flange.

    Uses the conservative symmetric-removal construction documented in
    AISC Manual v15.1 Ex. F.8B (Manual p. F-40/F-41): the ineffective
    flange width ``(b - be)`` is removed from **both** the top and
    bottom flanges, so the elastic neutral axis does not shift::

        I_eff = I - 2 [ (b - be) tf^3 / 12
                        + (b - be) tf ((d - tf)/2)^2 ]
        Se    = I_eff / (d / 2)

    where ``d`` is the overall section depth in the bending direction
    (``H`` for major-axis, ``B`` for minor-axis) and the removed plate's
    centroid is at ``(d - tf)/2`` from the section centroid.  This is
    the AISC-documented "simpler but slightly conservative" alternative
    to an exact effective-section analysis (spec Eq. F7-3 defines
    ``Se`` only as "the effective section modulus determined with the
    effective width ``be``"; the Manual fixes the construction).
    """
    ineffective = b_flange_flat - be
    if ineffective <= 0.0:
        # Flange fully effective (be == b): Se is just the gross modulus.
        return I_axis / (section_depth_d / 2.0)
    arm = (section_depth_d - tf) / 2.0
    I_removed = 2.0 * (ineffective * tf**3 / 12.0 + ineffective * tf * arm**2)
    I_eff = I_axis - I_removed
    return I_eff / (section_depth_d / 2.0)


def _rpg_slender_web(
    *,
    aw: float,
    h_tw: float,
    E: float,
    Fy: float,
) -> float:
    """Eq. F5-6 bending-strength reduction factor ``Rpg`` (<= 1.0).

    Reused by §F7.3(c) for a slender-web box section with
    ``aw = 2 h tw / (b tf)`` (spec_chapterF.txt 16.1-64); ``aw`` is
    capped at 10 per Eq. F4-12 / Eq. F5-6.
    """
    aw_eff = min(aw, _F7_3_AW_MAX)
    rpg = 1.0 - (aw_eff / (_EQ_F5_6_RPG_DENOM_A + _EQ_F5_6_RPG_DENOM_B * aw_eff)) * (
        h_tw - _EQ_F5_6_RPG_WEB_COEFF * math.sqrt(E / Fy)
    )
    return min(rpg, 1.0)


def _flange_local_buckling(
    *,
    flange_class: str,
    Mp: float,
    Fy_S: float,
    Fy: float,
    flange_lambda: float,
    flange_lambda_p: float,
    flange_lambda_r: float,
    flange_flat: float,
    t: float,
    E: float,
    I_axis: float,
    section_depth: float,
) -> tuple[float, float]:
    """§F7.2 flange-local-buckling ``(Mn, Se)`` (Eq. F7-2 / F7-3..F7-5).

    Returns ``Mp`` (limit state does not apply) for a compact flange,
    Eq. F7-2 for a noncompact flange, and Eq. F7-3 ``Mn = Fy*Se`` (with
    ``be`` from Eq. F7-4, the HSS effective width - apeSteel's
    ``RectangularHSS`` geometry models a *welded HSS*, so the HSS inner
    coefficient ``0.38`` is the correct branch, not the box ``0.34``)
    for a slender flange.  ``Se`` is ``0.0`` unless the flange is
    slender.
    """
    if flange_class == "compact":
        return Mp, 0.0  # §F7.2(a) - limit state does not apply
    if flange_class == "non_compact":
        # Eq. F7-2.
        mn_f7_2 = _interp_local_buckling(Mp, Fy_S, flange_lambda, flange_lambda_p, flange_lambda_r)
        return mn_f7_2, 0.0
    # Eq. F7-3 (slender flange): Mn = Fy*Se, be per Eq. F7-4 (HSS).
    be = _effective_width_be(b=flange_flat, t=t, E=E, Fy=Fy, inner_coeff=_EQ_F7_4_HSS_INNER_COEFF)
    Se = _effective_section_modulus_Se(
        I_axis=I_axis,
        section_depth_d=section_depth,
        b_flange_flat=flange_flat,
        be=be,
        tf=t,
    )
    return Fy * Se, Se


def _web_local_buckling(
    *,
    web_class: str,
    Mp: float,
    Fy_S: float,
    Fy: float,
    S: float,
    web_lambda: float,
    web_lambda_p: float,
    web_lambda_r: float,
    web_flat: float,
    flange_flat: float,
    t: float,
    E: float,
) -> float:
    """§F7.3 web-local-buckling ``Mn`` (Eq. F7-6 / Eq. F7-7).

    Returns ``Mp`` (limit state does not apply) for a compact web,
    Eq. F7-6 for a noncompact web, and Eq. F7-7 ``Mn = Rpg*Fy*S`` (Rpg
    per Eq. F5-6 with ``aw = 2 h tw/(b tf)``) for a slender web.  Per
    the §F7.3 User Note there are no HSS with slender webs - only a box
    section reaches the Eq. F7-7 branch.
    """
    if web_class == "compact":
        return Mp  # §F7.3(a) - limit state does not apply
    if web_class == "non_compact":
        # Eq. F7-6.
        return _interp_local_buckling(Mp, Fy_S, web_lambda, web_lambda_p, web_lambda_r)
    # Eq. F7-7 (slender web): Mn = Rpg*Fy*S, aw = 2 h tw/(b tf).
    aw = _F7_3_AW_LEAD_COEFF * web_flat * t / (flange_flat * t)
    rpg = _rpg_slender_web(aw=aw, h_tw=web_lambda, E=E, Fy=Fy)
    return rpg * Fy * S


def _lateral_torsional_buckling(
    *,
    Mp: float,
    Fy: float,
    S: float,
    E: float,
    Cb: float,
    ry_minor: float,
    J: float,
    Ag: float,
    Lb: float,
) -> tuple[float, float, float, bool]:
    """§F7.4 LTB ``(Mn, Lp, Lr, ltb_applies)`` (Eq. F7-10..F7-13).

    Caller has already applied the §F7.4 User Note exclusion (square
    section / minor-axis bending) and the no-``Lb`` short-circuit; this
    helper assumes LTB is in scope and a positive ``Lb`` is supplied.
    ``ry`` is the minor-axis radius of gyration (spec writes ``ry``).
    """
    sqrt_JAg = math.sqrt(J * Ag)
    E_ry_sqrtJAg = E * ry_minor * sqrt_JAg
    Lp = _EQ_F7_12_LP_COEFF * E_ry_sqrtJAg / Mp  # Eq. F7-12
    Lr_denom = _EQ_F7_LTB_STRESS_FRACTION_OF_FY * Fy * S  # 0.7 Fy Sx
    Lr = _EQ_F7_11_13_LEAD_COEFF * E_ry_sqrtJAg / Lr_denom  # Eq. F7-13
    if Lb <= Lp:
        return Mp, Lp, Lr, False  # §F7.4(a) - LTB does not apply
    if Lb <= Lr:
        # Eq. F7-10 (inelastic LTB).
        m07 = _EQ_F7_LTB_STRESS_FRACTION_OF_FY * Fy * S  # 0.7 Fy Sx
        bracket = Mp - (Mp - m07) * (Lb - Lp) / (Lr - Lp)
        mn = min(Cb * bracket, Mp)
        return mn, Lp, Lr, True
    # Eq. F7-11 (elastic LTB): Mn = 2 E Cb sqrt(J Ag)/(Lb/ry).
    mn = min(_EQ_F7_11_13_LEAD_COEFF * E * Cb * sqrt_JAg / (Lb / ry_minor), Mp)
    return mn, Lp, Lr, True


@dataclass(frozen=True, slots=True)
class _AxisResolvedQuantities:
    """Per-``bending_axis`` §F7 quantities resolved from the snapshot.

    Internal grouping of the axis-dependent section quantities so the
    public calculator stays a thin orchestrator (no behaviour: every
    field is copied verbatim from the snapshot in
    :func:`_resolve_axis_quantities`).
    """

    z_bending: float  # plastic modulus about the bending axis (mm^3)
    s_bending: float  # elastic modulus about the bending axis (mm^3)
    I_axis: float  # second moment about the bending axis (mm^4)
    section_depth: float  # H for major-axis, B for minor-axis (mm)
    flange_lambda: float  # compression-flange b/t for this axis
    flange_flat: float  # compression-flange flat width for this axis (mm)
    web_lambda: float  # web h/t for this axis
    ry_minor: float  # MINOR-axis radius of gyration (Eq. F7-11/12/13) (mm)


def _validate_and_extract_walls(
    fsp: FlexuralSectionProperties,
    unbraced_length_Lb: float | None,
) -> tuple[float, FlexuralPlateElement, FlexuralPlateElement]:
    """Validate the §F7 snapshot and return ``(t, wall_B, wall_H)``.

    Raises the same :class:`ValueError` cases the public calculator
    documents (wrong ``section_kind``; non-positive ``wall_thickness_t``;
    non-positive supplied ``unbraced_length_Lb``; a snapshot not carrying
    exactly the two expected flat walls).  Behaviour is identical to the
    inline checks it replaces - pure code-motion.
    """
    if fsp.section_kind != "rectangular_HSS":
        raise ValueError(
            f"§F7 applies only to rectangular/square HSS & box; got "
            f"section_kind={fsp.section_kind!r}"
        )

    t: float = fsp.wall_thickness_t
    if t <= 0.0:
        raise ValueError(f"rectangular-HSS wall_thickness_t must be positive, got {t!r}")
    if unbraced_length_Lb is not None and unbraced_length_Lb <= 0.0:
        raise ValueError(
            f"unbraced_length_Lb must be positive when supplied, got {unbraced_length_Lb!r}"
        )

    # The geometry snapshot carries exactly two flat walls:
    #   wall_B  -> flat width (B - 2t)  (flange in major-axis bending)
    #   wall_H  -> flat width (H - 2t)  (web    in major-axis bending)
    walls = {e.name: e for e in fsp.plate_elements}
    if set(walls) != {"wall_B", "wall_H"}:
        msg = (
            "rectangular-HSS snapshot must carry exactly the flat walls "
            f"{{'wall_B', 'wall_H'}}, got {sorted(walls)!r}"
        )
        raise ValueError(msg)
    return t, walls["wall_B"], walls["wall_H"]


def _resolve_axis_quantities(
    fsp: FlexuralSectionProperties,
    *,
    bending_axis: BendingAxis,
    wall_B: FlexuralPlateElement,
    wall_H: FlexuralPlateElement,
    t: float,
    H_depth: float,
    B_width: float,
) -> _AxisResolvedQuantities:
    """Pick the axis-correct ``Z``/``S``/``I``, depth and flange/web roles.

    For major-axis the ``B``-walls are the flanges and the ``H``-walls
    the webs; for minor-axis the roles swap.  ``ry`` (Eq. F7-11/12/13)
    is always the snapshot's MINOR-axis radius of gyration (the spec
    writes ``ry``; §F7.4 LTB applies only to major-axis bending).  Pure
    code-motion of the inline axis-resolution block.
    """
    if bending_axis == "major":
        # Bending about x: flange = B-walls, web = H-walls. Section
        # depth in the bending direction = H.
        z_bending = fsp.plastic_modulus_Zx
        s_bending = fsp.elastic_modulus_Sx
        I_axis = fsp.moment_of_inertia_Ix
        section_depth = H_depth
        flange_lambda = wall_B.slenderness_ratio_lambda
        flange_flat = wall_B.slenderness_ratio_lambda * t
        web_lambda = wall_H.slenderness_ratio_lambda
    else:
        # Bending about y: flange = H-walls, web = B-walls. Section
        # depth in the bending direction = B.
        z_bending = fsp.plastic_modulus_Zy
        s_bending = fsp.elastic_modulus_Sy
        I_axis = fsp.moment_of_inertia_Iy
        section_depth = B_width
        flange_lambda = wall_H.slenderness_ratio_lambda
        flange_flat = wall_H.slenderness_ratio_lambda * t
        web_lambda = wall_B.slenderness_ratio_lambda

    # §F7.4 Eq. F7-11/F7-12/F7-13 use ry = the MINOR-axis radius of
    # gyration (spec writes ``ry``; AISC Manual v15.1 Ex. F.7B uses the
    # weak-axis radius for a strong-axis-bent HSS).  §F7.4 LTB applies
    # only to major-axis bending, so this is always the snapshot's
    # minor-axis ``radius_of_gyration_ry``.
    return _AxisResolvedQuantities(
        z_bending=z_bending,
        s_bending=s_bending,
        I_axis=I_axis,
        section_depth=section_depth,
        flange_lambda=flange_lambda,
        flange_flat=flange_flat,
        web_lambda=web_lambda,
        ry_minor=fsp.radius_of_gyration_ry,
    )


def _classify_flange_web(
    material: SteelMaterial,
    *,
    flange_lambda: float,
    web_lambda: float,
) -> tuple[str, float, float, str, float, float]:
    """Run the F-0 classifier; return flange + web class & B4.1b limits.

    Returns ``(flange_class, flange_lambda_p, flange_lambda_r,
    web_class, web_lambda_p, web_lambda_r)`` from
    :func:`classify_flexural_compactness` (the single source of truth for
    the Table B4.1b ``lambda_p`` / ``lambda_r``; the 1.12/1.40 & 2.42/
    5.70 coefficients are NOT re-declared here).  Pure code-motion.
    """
    classification_report = classify_flexural_compactness(
        material,
        section_kind="rectangular_HSS",
        hss_flange_slenderness_b_t=flange_lambda,
        hss_web_slenderness_h_t=web_lambda,
    )
    cls_elems = {e.name: e for e in classification_report.plate_elements}
    flange_el = cls_elems["flange"]
    web_el = cls_elems["web"]
    return (
        flange_el.classification,
        flange_el.compact_limit_lambda_p,
        flange_el.noncompact_limit_lambda_r,
        web_el.classification,
        web_el.compact_limit_lambda_p,
        web_el.noncompact_limit_lambda_r,
    )


def _resolve_governing_limit_state(
    *,
    Mn: float,
    Mn_yield: float,
    Mn_flb: float,
    Mn_wlb: float,
    Mn_ltb: float,
    ltb_applies: bool,
) -> str:
    """Identify the governing §F7 limit state for the final ``Mn``.

    A local-buckling / LTB branch that did not reduce ``Mn`` below
    ``Mp`` ("limit state does not apply") must not be reported as
    governing; ties at ``Mp`` resolve to yielding.  Ordering of the
    strict-reduction checks is the conventional §F7 reporting order
    (FLB, then WLB, then LTB).  Pure code-motion - same predicates.
    """
    if Mn_flb < Mn_yield and Mn == Mn_flb:
        return "flange_local_buckling"
    if Mn_wlb < Mn_yield and Mn == Mn_wlb:
        return "web_local_buckling"
    if ltb_applies and Mn_ltb < Mn_yield and Mn == Mn_ltb:
        return "lateral_torsional_buckling"
    return "yielding"


# ---------------------------------------------------------------------------
# Public calculator
# ---------------------------------------------------------------------------
def compute_flexural_strength_F7_rect_hss(
    section_properties_or_fsp: FlexuralSectionProperties,
    material: SteelMaterial,
    *,
    bending_axis: BendingAxis = "major",
    unbraced_length_Lb: float | None = None,
    Cb: float = 1.0,
) -> FlexureF7Report:
    """Return ``Mn`` per AISC 360-22 §F7 for a square / rectangular HSS.

    ``Mn`` is the lowest of the four §F7 limit states (yielding,
    flange local buckling, web local buckling, lateral-torsional
    buckling), evaluated for the requested ``bending_axis``:

    * Eq. F7-1 yielding ``Mn = Mp = Fy*Z``;
    * §F7.2 flange local buckling - compact: N/A; noncompact Eq. F7-2;
      slender Eq. F7-3 ``Mn = Fy*Se`` with ``be`` from Eq. F7-4 (HSS);
    * §F7.3 web local buckling - compact: N/A; noncompact Eq. F7-6;
      slender Eq. F7-7 ``Mn = Rpg*Fy*S``;
    * §F7.4 lateral-torsional buckling - skipped entirely for a square
      section (``B == H``) or minor-axis bending (the §F7.4 User Note
      exclusion); otherwise Eq. F7-10 (``Lp < Lb <= Lr``) / Eq. F7-11
      (``Lb > Lr``) with ``Lp`` (Eq. F7-12) and ``Lr`` (Eq. F7-13).
      Note Eq. F7-11 / F7-12 / F7-13 use ``ry`` = the **minor-axis**
      radius of gyration (the spec writes ``ry`` literally; AISC Manual
      v15.1 Ex. F.7B confirms it - LTB of a strong-axis-bent HSS is
      governed by the weak-axis / torsional stiffness), not the
      bending-axis radius.  §F7.4 LTB only applies to major-axis bending
      anyway, so ``ry`` is unambiguously
      :attr:`FlexuralSectionProperties.radius_of_gyration_ry`.

    The Table B4.1b flange / web ``lambda_p`` / ``lambda_r`` come from
    the F-0 generalized classifier
    :func:`~apeSteel.classification.classify_flexural_compactness`
    (``section_kind="rectangular_HSS"``) so §F7 and the classifier
    share one source of truth for the regime boundaries.

    Parameters
    ----------
    section_properties_or_fsp : FlexuralSectionProperties
        A ``section_kind == "rectangular_HSS"`` snapshot, as produced by
        :meth:`RectangularHSS.compute_section_properties`.  Reads the
        both-axis ``Z`` / ``S`` / ``I`` / ``r``, ``Ag``, ``J``,
        ``overall_depth_d`` (``H``), ``wall_thickness_t`` (``t``), and
        the two flat-wall ``plate_elements`` (``wall_B`` of flat width
        ``B - 2t``, ``wall_H`` of flat width ``H - 2t``).
    material : SteelMaterial
        Reads ``Fy`` and ``E`` only.
    bending_axis : {"major", "minor"}, optional
        Axis of bending.  Default ``"major"``.  For major-axis the
        ``B``-walls are the flanges and the ``H``-walls the webs; for
        minor-axis the roles swap.  Per the §F7.4 User Note, LTB does
        not apply to minor-axis bending.
    unbraced_length_Lb : float or None, optional
        Laterally unbraced length ``Lb`` (mm).  Required to evaluate
        §F7.4 LTB on a *rectangular* (non-square) section in *major*-axis
        bending; if ``None`` there, LTB is reported as not evaluated
        (``Mn`` then reflects only yielding + local buckling, and the
        caller is responsible for the unbraced-length check).  Ignored
        (LTB N/A) for a square section or minor-axis bending.
    Cb : float, optional
        Lateral-torsional-buckling modification factor (§F1, Eq. F1-1).
        Default ``1.0`` (conservative, uniform moment).

    Returns
    -------
    FlexureF7Report
        Frozen dataclass with every §F7 intermediate exposed.

    Raises
    ------
    ValueError
        If ``section_kind`` is not ``"rectangular_HSS"``; if the
        snapshot does not carry exactly the two expected flat-wall
        plate elements; if ``wall_thickness_t`` is non-positive; or if
        ``unbraced_length_Lb`` is supplied non-positive.
    """
    fsp: FlexuralSectionProperties = section_properties_or_fsp

    # --- Validate the snapshot + extract the two flat walls ---
    t, wall_B, wall_H = _validate_and_extract_walls(fsp, unbraced_length_Lb)

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E

    # The overall depth ``H`` is carried verbatim on the snapshot
    # (``overall_depth_d``); the overall width ``B`` is reconstructed
    # from the B-wall flat slenderness (flat = B - 2t, so
    # B = lambda*t + 2t) - exact for the plate-built geometry (same
    # closed form), and for an externally-published catalog section it
    # is the consistent B that pairs with the published b/t.  The
    # bending-direction section depth is ``H`` for major-axis and ``B``
    # for minor-axis (used only by the slender-flange Se, Eq. F7-3).
    H_depth: float = fsp.overall_depth_d
    B_width: float = wall_B.slenderness_ratio_lambda * t + 2.0 * t

    # --- Axis-specific section quantities + flange/web roles ---
    axis = _resolve_axis_quantities(
        fsp,
        bending_axis=bending_axis,
        wall_B=wall_B,
        wall_H=wall_H,
        t=t,
        H_depth=H_depth,
        B_width=B_width,
    )
    flange_lambda = axis.flange_lambda
    web_lambda = axis.web_lambda

    # --- Table B4.1b classification via the F-0 generalized classifier
    # (single source of truth for the flange/web lambda_p / lambda_r;
    # the 1.12/1.40 & 2.42/5.70 coefficients are NOT re-declared here).
    (
        flange_class,
        flange_lambda_p,
        flange_lambda_r,
        web_class,
        web_lambda_p,
        web_lambda_r,
    ) = _classify_flange_web(
        material,
        flange_lambda=flange_lambda,
        web_lambda=web_lambda,
    )

    Mp: float = Fy * axis.z_bending  # Eq. F7-1
    My: float = Fy * axis.s_bending  # elastic yield moment about bending axis
    Fy_S: float = Fy * axis.s_bending

    # --- Limit state 1: Yielding (Eq. F7-1) ---
    Mn_yield: float = Mp

    # --- Limit state 2: Flange local buckling (§F7.2) ---
    Mn_flb, Se = _flange_local_buckling(
        flange_class=flange_class,
        Mp=Mp,
        Fy_S=Fy_S,
        Fy=Fy,
        flange_lambda=flange_lambda,
        flange_lambda_p=flange_lambda_p,
        flange_lambda_r=flange_lambda_r,
        flange_flat=axis.flange_flat,
        t=t,
        E=E,
        I_axis=axis.I_axis,
        section_depth=axis.section_depth,
    )

    # --- Limit state 3: Web local buckling (§F7.3) ---
    Mn_wlb = _web_local_buckling(
        web_class=web_class,
        Mp=Mp,
        Fy_S=Fy_S,
        Fy=Fy,
        S=axis.s_bending,
        web_lambda=web_lambda,
        web_lambda_p=web_lambda_p,
        web_lambda_r=web_lambda_r,
        web_flat=web_lambda * t,
        flange_flat=axis.flange_flat,
        t=t,
        E=E,
    )

    # --- Limit state 4: Lateral-torsional buckling (§F7.4) ---
    # §F7.4 User Note: LTB will not occur in square sections or sections
    # bending about their minor axis -> the limit state simply does not
    # apply there (treat as Mn = Mp, do not penalise).  A section is
    # "square" iff its two flat walls are identical (same t, equal
    # flat width <=> equal b/t); this invariant is robust to the
    # welded-box vs catalog-corner width convention (an HSS8x8 prints
    # b/t == h/t in either model), unlike comparing reconstructed outer
    # dimensions.
    is_square = math.isclose(
        wall_B.slenderness_ratio_lambda,
        wall_H.slenderness_ratio_lambda,
        rel_tol=1e-12,
        abs_tol=0.0,
    )
    ltb_excluded_by_user_note = is_square or bending_axis == "minor"

    Lp: float = 0.0
    Lr: float = 0.0
    Mn_ltb: float = Mp
    ltb_applies = False
    Lb_used: float = 0.0
    if not ltb_excluded_by_user_note and unbraced_length_Lb is not None:
        Lb_used = unbraced_length_Lb
        Mn_ltb, Lp, Lr, ltb_applies = _lateral_torsional_buckling(
            Mp=Mp,
            Fy=Fy,
            S=axis.s_bending,
            E=E,
            Cb=Cb,
            ry_minor=axis.ry_minor,
            J=fsp.torsional_constant_J,
            Ag=fsp.gross_area_Ag,
            Lb=Lb_used,
        )

    # --- Mn = min(applicable limit states) ---
    Mn: float = min(Mn_yield, Mn_flb, Mn_wlb, Mn_ltb)

    # Identify the governing limit state (FLB -> WLB -> LTB; a branch
    # that did not reduce Mn below Mp does not govern; ties at Mp ->
    # yielding).
    governing = _resolve_governing_limit_state(
        Mn=Mn,
        Mn_yield=Mn_yield,
        Mn_flb=Mn_flb,
        Mn_wlb=Mn_wlb,
        Mn_ltb=Mn_ltb,
        ltb_applies=ltb_applies,
    )

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF7Report(
        cited_clauses=_CITATIONS_F7,
        governing_limit_state=governing,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        bending_axis=bending_axis,
        flange_slenderness_b_t=flange_lambda,
        flange_compact_limit_lambda_p=flange_lambda_p,
        flange_noncompact_limit_lambda_r=flange_lambda_r,
        flange_classification=flange_class,
        web_slenderness_h_t=web_lambda,
        web_compact_limit_lambda_p=web_lambda_p,
        web_noncompact_limit_lambda_r=web_lambda_r,
        web_classification=web_class,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
        effective_section_modulus_Se=Se,
        Mn_yielding=Mn_yield,
        Mn_flange_local_buckling=Mn_flb,
        Mn_web_local_buckling=Mn_wlb,
        Mn_lateral_torsional_buckling=Mn_ltb,
        limiting_length_Lp=Lp,
        limiting_length_Lr=Lr,
        lateral_torsional_buckling_applies=ltb_applies,
        unbraced_length_Lb=Lb_used,
        Cb=Cb,
        nominal_flexural_strength_Mn=Mn,
        tension_flange_hole_rupture_check_required=True,
    )


__all__ = [
    "FlexureF7Report",
    "compute_flexural_strength_F7_rect_hss",
]

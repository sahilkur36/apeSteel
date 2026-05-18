"""AISC 360-22 §F8 - flexural strength of round HSS / Pipe.

This module is the pure §F8 calculator: it takes a round-HSS
:class:`FlexuralSectionProperties` snapshot (as produced natively by
:meth:`apeSteel.sections.geometry.round_hss.RoundHSS.compute_section_properties`)
and a material, and returns the nominal flexural strength ``Mn`` with
the controlling limit state identified.

§F8 is the cheapest section in Chapter F: a round HSS is axisymmetric,
so there is **no lateral-torsional-buckling limit state** and no
unbraced length / ``Cb`` input.  ``Mn`` is governed solely by the
diameter-to-thickness ratio ``D/t`` through the Table B4.1b Case 20
classification:

* **Compact** ``D/t <= lambda_p = 0.07 E/Fy`` -> yielding
  ``Mn = Mp = Fy*Z``                                       (Eq. F8-1)
* **Noncompact** ``lambda_p < D/t <= lambda_r = 0.31 E/Fy`` -> local
  buckling ``Mn = (0.021 E / (D/t) + Fy) * S``             (Eq. F8-2)
* **Slender** ``D/t > lambda_r`` -> ``Mn = Fcr * S``       (Eq. F8-3)
  with ``Fcr = 0.33 E / (D/t)``                            (Eq. F8-4)

§F8 itself applies only to round HSS with ``D/t < 0.45 E/Fy`` (the
section-applicability limit stated in the §F8 lead paragraph); a ratio
at or above that bound is outside the scope of §F8 and raises
:class:`ValueError` rather than returning a non-compliant number.

The Table B4.1b Case 20 ``lambda_p`` / ``lambda_r`` are obtained from
the F-0 generalized classifier
:func:`apeSteel.classification.classify_flexural_compactness`
(``section_kind="round_HSS"``), not re-derived here, so §F8 and the
classifier cannot disagree on the regime boundaries.

``phi_b = 0.90`` / ``Omega_b = 1.67`` (AISC 360-22 §F1), shared with
the rest of Chapter F via :mod:`apeSteel.flexure._common`.

Layering: this module is in the ``flexure`` layer; it imports only from
``sections`` (:class:`FlexuralSectionProperties`), ``classification``
(:func:`classify_flexural_compactness`), and ``core``.  It is **not**
wired into any facade / ``Element`` here - that is Phase F-8.

References
----------
.. [1] AISC 360-22 §F8 "Round HSS", Eq. F8-1 - F8-4, p. 16.1-65.
       American Institute of Steel Construction, 2022. Equation forms
       and page transcribed verbatim from
       ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` and
       ``docs/design_notes/_chapterF_citation_reference.md`` (§F8 row).
.. [2] AISC 360-22 Table B4.1b Case 20 (round HSS, flexure):
       ``lambda_p = 0.07 E/Fy``, ``lambda_r = 0.31 E/Fy`` - CONFIRMED
       as Case 20 from AISC Manual v15.1 Ex. F.9B; the ``16.1-NN`` page
       label for that B4.1b row is unconfirmed (ENGINEER-CONFIRM EC-3),
       so the Case-20 citation carries ``page=None``.
"""

from __future__ import annotations

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
    from apeSteel.sections.flexural_properties import FlexuralSectionProperties

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 §F8 (spec_chapterF.txt, printed 16.1-65)
#
# Each magic number is named + cited so the §F8 provenance is traceable
# at the call site, mirroring the F2 / F4 constant style.  The Table
# B4.1b Case 20 lambda_p / lambda_r coefficients (0.07 / 0.31, of E/Fy)
# are NOT redeclared here: they live in the F-0 classifier
# (B4_1B_ROUND_HSS_COMPACT_COEFF / _NONCOMPACT_COEFF) and reach §F8
# through classify_flexural_compactness, so the two cannot drift.
# ---------------------------------------------------------------------------

#: §F8 section-applicability bound: §F8 applies to round HSS having
#: ``D/t < 0.45 * E/Fy`` (AISC 360-22 §F8 lead paragraph,
#: spec_chapterF.txt printed 16.1-65).  At or above this ratio the
#: section is outside §F8 and this calculator refuses it.
_F8_APPLICABILITY_D_T_COEFF: float = 0.45

#: AISC 360-22 Eq. F8-2 noncompact local-buckling coefficient:
#: ``Mn = (0.021 * E / (D/t) + Fy) * S`` (spec_chapterF.txt printed
#: 16.1-65).
_EQ_F8_2_NONCOMPACT_COEFF: float = 0.021

#: AISC 360-22 Eq. F8-4 slender-wall critical-stress coefficient:
#: ``Fcr = 0.33 * E / (D/t)`` (spec_chapterF.txt printed 16.1-65).
_EQ_F8_4_FCR_COEFF: float = 0.33


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF8Report(Report):
    """AISC 360-22 §F8 flexural-strength result for a round HSS / Pipe.

    All moments are in apeSteel base units (N*mm); ``D``/``t`` in mm;
    stresses in MPa.

    Attributes
    ----------
    diameter_to_thickness_ratio_D_t : float
        The governing slenderness ``D/t`` (dimensionless).
    compact_limit_lambda_p : float
        Table B4.1b Case 20 ``lambda_p = 0.07 E/Fy`` (the compact /
        noncompact boundary; a *ratio* of ``E/Fy``, not its square
        root).
    noncompact_limit_lambda_r : float
        Table B4.1b Case 20 ``lambda_r = 0.31 E/Fy`` (the noncompact /
        slender boundary).
    wall_classification : str
        ``"compact"`` / ``"non_compact"`` / ``"slender"`` for the round
        wall (Case 20).
    plastic_moment_Mp : float
        ``Mp = Fy*Z``, the Eq. F8-1 plateau (N*mm).
    yield_moment_My : float
        ``My = Fy*S``, the elastic yield moment (N*mm); reported for
        trace (it bounds the noncompact / slender branches from below).
    critical_stress_Fcr : float
        Eq. F8-4 ``Fcr = 0.33 E/(D/t)`` (MPa).  Computed only on the
        slender branch; ``0.0`` otherwise (the formula does not apply).
    nominal_flexural_strength_Mn : float
        Final ``Mn`` per the governing §F8 limit state (N*mm).  Mirrors
        :attr:`Report.nominal_strength`.
    """

    diameter_to_thickness_ratio_D_t: float = 0.0
    compact_limit_lambda_p: float = 0.0
    noncompact_limit_lambda_r: float = 0.0
    wall_classification: str = "compact"
    plastic_moment_Mp: float = 0.0
    yield_moment_My: float = 0.0
    critical_stress_Fcr: float = 0.0
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Equation-set citations
# ---------------------------------------------------------------------------
_CITATIONS_F8: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    # §F8 body - equation numbers + page verbatim from
    # spec_chapterF.txt / _chapterF_citation_reference.md (§F8 row,
    # printed 16.1-65).
    AISCClauseReference("AISC 360-22", "F8", None, "16.1-65"),
    AISCClauseReference("AISC 360-22", "F8.1", "F8-1", "16.1-65"),
    AISCClauseReference("AISC 360-22", "F8.2", "F8-2", "16.1-65"),
    AISCClauseReference("AISC 360-22", "F8.2", "F8-3", "16.1-65"),
    AISCClauseReference("AISC 360-22", "F8.2", "F8-4", "16.1-65"),
    # Table B4.1b Case 20 - CONFIRMED case number (AISC Manual v15.1
    # Ex. F.9B text); page label unconfirmed (ENGINEER-CONFIRM EC-3),
    # so page=None - never invented.
    AISCClauseReference("AISC 360-22", "Table B4.1b", "Case 20", None),
)


# ---------------------------------------------------------------------------
# Public calculator
# ---------------------------------------------------------------------------
def compute_flexural_strength_F8_round_hss(
    section_properties_or_fsp: FlexuralSectionProperties,
    material: SteelMaterial,
) -> FlexureF8Report:
    """Return ``Mn`` per AISC 360-22 §F8 for a round HSS / Pipe.

    Round HSS are axisymmetric: §F8 has **no** lateral-torsional-
    buckling limit state, hence no unbraced-length / ``Cb`` argument
    (contrast §F2-§F5).  ``Mn`` follows entirely from the wall
    ``D/t`` classification (Table B4.1b Case 20):

    * compact -> Eq. F8-1 ``Mn = Mp = Fy*Z``;
    * noncompact -> Eq. F8-2 ``Mn = (0.021 E/(D/t) + Fy) * S``;
    * slender -> Eq. F8-3 ``Mn = Fcr*S`` with Eq. F8-4
      ``Fcr = 0.33 E/(D/t)``.

    The Case 20 ``lambda_p`` / ``lambda_r`` come from the F-0
    generalized classifier
    :func:`~apeSteel.classification.classify_flexural_compactness`
    (so §F8 and the classifier share one source of truth for the
    regime boundaries); only ``Z``, ``S``, ``D`` and ``t`` are read
    from ``section_properties_or_fsp``.

    Parameters
    ----------
    section_properties_or_fsp : FlexuralSectionProperties
        A ``section_kind == "round_HSS"`` snapshot, as produced by
        :meth:`RoundHSS.compute_section_properties`.  Round HSS have no
        legacy I-shape :class:`SectionProperties` representation, so
        this is always the generalized currency (the parameter name
        mirrors the other §F calculators' dual-input contract).  Reads
        ``plastic_modulus_Zx`` (= ``Zx`` = ``Zy`` by symmetry),
        ``elastic_modulus_Sx``, ``diameter_D`` and ``wall_thickness_t``.
    material : SteelMaterial
        Reads ``Fy`` and ``E`` only.

    Returns
    -------
    FlexureF8Report
        Frozen dataclass with every §F8 intermediate exposed.

    Raises
    ------
    ValueError
        If ``section_properties_or_fsp.section_kind`` is not
        ``"round_HSS"``; if ``D`` or ``t`` is non-positive; or if
        ``D/t >= 0.45 E/Fy`` (outside the §F8 section-applicability
        limit stated in the §F8 lead paragraph - returning a number
        there would not be an AISC-compliant strength).
    """
    fsp: FlexuralSectionProperties = section_properties_or_fsp
    if fsp.section_kind != "round_HSS":
        raise ValueError(f"§F8 applies only to round HSS; got section_kind={fsp.section_kind!r}")

    D: float = fsp.diameter_D
    t: float = fsp.wall_thickness_t
    if D <= 0.0:
        raise ValueError(f"round-HSS diameter_D must be positive, got {D!r}")
    if t <= 0.0:
        raise ValueError(f"round-HSS wall_thickness_t must be positive, got {t!r}")

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    D_t: float = D / t

    # §F8 section-applicability limit (lead paragraph): D/t < 0.45 E/Fy.
    applicability_limit_D_t: float = _F8_APPLICABILITY_D_T_COEFF * (E / Fy)
    if D_t >= applicability_limit_D_t:
        msg = (
            f"D/t = {D_t!r} is outside the AISC 360-22 §F8 applicability "
            f"limit 0.45*E/Fy = {applicability_limit_D_t!r}; §F8 does not "
            f"apply to this round HSS."
        )
        raise ValueError(msg)

    # Table B4.1b Case 20 lambda_p / lambda_r via the F-0 generalized
    # classifier (single source of truth for the regime boundaries -
    # the 0.07 / 0.31 coefficients are NOT re-declared in this module).
    classification_report = classify_flexural_compactness(
        material,
        section_kind="round_HSS",
        round_hss_slenderness_D_t=D_t,
    )
    # The round-HSS classifier emits exactly one wall element
    # (Table B4.1b Case 20); guard the invariant explicitly rather
    # than tuple-unpacking (pyright-strict-clean on the variadic tuple).
    wall_elements = classification_report.plate_elements
    if len(wall_elements) != 1:  # pragma: no cover - classifier invariant
        msg = f"round-HSS classifier must emit exactly one wall element, got {len(wall_elements)}"
        raise ValueError(msg)
    wall_element = wall_elements[0]
    lambda_p: float = wall_element.compact_limit_lambda_p
    lambda_r: float = wall_element.noncompact_limit_lambda_r
    wall_class = wall_element.classification

    Z: float = fsp.plastic_modulus_Zx  # = Zy (axisymmetric)
    S: float = fsp.elastic_modulus_Sx  # = Sy (axisymmetric)
    Mp: float = Fy * Z  # Eq. F8-1
    My: float = Fy * S  # elastic yield moment (trace)

    Fcr: float = 0.0
    if wall_class == "compact":
        # Eq. F8-1 - yielding (plastic moment).
        governing_limit_state = "yielding"
        Mn: float = Mp
    elif wall_class == "non_compact":
        # Eq. F8-2 - local buckling, noncompact wall.
        governing_limit_state = "flange_local_buckling"
        Mn = (_EQ_F8_2_NONCOMPACT_COEFF * E / D_t + Fy) * S
    else:
        # Eq. F8-3 / F8-4 - local buckling, slender wall.
        governing_limit_state = "flange_local_buckling"
        Fcr = _EQ_F8_4_FCR_COEFF * E / D_t  # Eq. F8-4
        Mn = Fcr * S  # Eq. F8-3

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF8Report(
        cited_clauses=_CITATIONS_F8,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        diameter_to_thickness_ratio_D_t=D_t,
        compact_limit_lambda_p=lambda_p,
        noncompact_limit_lambda_r=lambda_r,
        wall_classification=wall_class,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
        critical_stress_Fcr=Fcr,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF8Report",
    "compute_flexural_strength_F8_round_hss",
]

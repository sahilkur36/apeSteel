"""AISC 360-22 §F6 - minor-axis flexure of I-shaped members.

This module is the pure §F6 calculator: it takes a doubly- or
singly-symmetric I-shape (the shipped I-only
:class:`apeSteel.sections.properties.SectionProperties`, lifted into the
generalized :class:`FlexuralSectionProperties` via
:meth:`FlexuralSectionProperties.from_legacy` exactly as the shipped
``flexure/F2..F5`` do) bent about its **minor (y) axis**, plus a
material, and returns the nominal flexural strength ``Mn`` with the
controlling limit state identified.

§F6 ("I-shaped members and channels bent about their minor axis") is the
second-cheapest section in Chapter F.  A minor-axis-bent I-shape has
**no lateral-torsional-buckling limit state** (the minor axis is the
weak axis - there is nothing to buckle laterally *into*), so there is no
unbraced-length / ``Cb`` input (contrast §F2-§F5).  ``Mn`` is the lower
of the limit states of *yielding* (plastic moment) and *flange local
buckling* (FLB), the FLB branch selected by the compression-flange
slenderness ``lambda = b/tf`` through the Table B4.1b Case 10/11
classification (the **same** ``lambda_pf`` / ``lambda_rf`` the major-axis
§F3/§F4 flange uses - §F6 says "lambda_pf = lambda_p ... as defined in
Table B4.1b", "lambda_rf = lambda_r ... as defined in Table B4.1b"):

* **Yielding** ``Mn = Mp = Fy*Zy <= 1.6*Fy*Sy``            (Eq. F6-1)
* **Compact flange** -> FLB does not apply -> ``Mn`` is the Eq. F6-1
  value (§F6.2(a))
* **Noncompact flange**
  ``Mn = Mp - (Mp - 0.70*Fy*Sy)*(lambda - lambda_pf)
         / (lambda_rf - lambda_pf)``                        (Eq. F6-2)
* **Slender flange** ``Mn = Fcr*Sy``                        (Eq. F6-3)
  with ``Fcr = 0.70*E / (b/tf)^2``                          (Eq. F6-4)

For an I-shape the §F6 flange-slenderness measure is ``lambda = b/tf``
with ``b`` = *half* the full flange width ``bf`` (§F6.2 definition of
``b``), i.e. ``lambda = bf/(2 tf)`` - precisely the shipped
``SectionProperties.flange_width_to_thickness_ratio_bf_2tf`` and exactly
the ratio the F-0 classifier consumes as ``flange_slenderness_bf_2tf``.
Channels (where ``b`` is the *full* flange width) are **out of F-4
scope** - deferred to F-8 (design note 10 §5, F-4 line).

The Table B4.1b Case 10/11 ``lambda_pf`` / ``lambda_rf`` are obtained
from the F-0 generalized classifier
:func:`apeSteel.classification.classify_flexural_compactness`
(``section_kind="doubly_symmetric_I"`` / ``"singly_symmetric_I"``), not
re-derived here, so §F6 and the classifier cannot disagree on the FLB
regime boundaries.

``phi_b = 0.90`` / ``Omega_b = 1.67`` (AISC 360-22 §F1), shared with the
rest of Chapter F via :mod:`apeSteel.flexure._common`.

Layering: this module is in the ``flexure`` layer; it imports only from
``sections`` (:class:`FlexuralSectionProperties`,
:class:`SectionProperties`), ``classification``
(:func:`classify_flexural_compactness`), and ``core``.  It is **not**
wired into any facade / ``Element`` here - that, and channel minor-axis
§F6, are Phase F-8 (design note 10 §5, F-4 line: F-4 ships a pure,
parallel-safe §F6 engine + oracle + golden only; no
``Element.combined_strength_H1`` / ``element.py`` ``Mcy`` wiring).

References
----------
.. [1] AISC 360-22 §F6 "I-Shaped Members and Channels Bent About Their
       Minor Axis", Eq. F6-1 - F6-4, p. 16.1-62. American Institute of
       Steel Construction, 2022.  Equation forms and page transcribed
       verbatim from
       ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` (§F6
       body, printed 16.1-62) and the Chapter-F citation source-of-truth
       ``docs/design_notes/_chapterF_citation_reference.md`` (§F6 row).
.. [2] AISC 360-22 Table B4.1b Case 10 (rolled) / Case 11 (welded) -
       I-shape flange in flexure: ``lambda_pf = 0.38 sqrt(E/Fy)``;
       ``lambda_rf = 1.0 sqrt(E/Fy)`` (rolled) or
       ``0.95 sqrt(kc E / FL)`` (welded).  Reached through the F-0
       classifier; not re-declared here.
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
    FlexuralLimitState,
)
from apeSteel.sections.flexural_properties import FlexuralSectionProperties

if TYPE_CHECKING:
    from apeSteel.classification._common import SectionConstruction
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.compression_properties import SectionSymmetry
    from apeSteel.sections.flexural_properties import FlexuralSectionKind
    from apeSteel.sections.properties import SectionProperties

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 §F6 (spec_chapterF.txt / _chapterF_citation_
# reference.md, §F6 row, printed 16.1-62)
#
# Each magic number is named + cited so the §F6 provenance is traceable
# at the call site, mirroring the F2 / F8 constant style.  The Table
# B4.1b Case 10/11 lambda_pf / lambda_rf coefficients are NOT redeclared
# here: they live in the F-0 classifier and reach §F6 through
# classify_flexural_compactness, so the two cannot drift.
# ---------------------------------------------------------------------------

#: AISC 360-22 Eq. F6-1 plastic-moment cap multiplier: the §F6 yielding
#: moment is ``Mn = Mp = Fy*Zy`` but **not more than** ``1.6*Fy*Sy``
#: (an upper bound on the shape factor for minor-axis bending, where
#: ``Zy/Sy`` can be large).  ``_chapterF_citation_reference.md`` §F6 row,
#: spec_chapterF.txt printed 16.1-62.
_EQ_F6_1_SHAPE_FACTOR_CAP: float = 1.6

#: AISC 360-22 Eq. F6-2 / Eq. F6-4 elastic-residual-stress coefficient
#: ``0.70``: the noncompact-flange interpolation anchors the slender end
#: at ``0.70*Fy*Sy`` (Eq. F6-2) and the slender-flange critical stress is
#: ``Fcr = 0.70*E/(b/tf)^2`` (Eq. F6-4).
#:
#: ENGINEER-CONFIRM **F6-EC-1 - RESOLVED**: AISC 360-22 §F6 Eq. F6-4
#: ``Fcr=0.70E/lambda^2`` and §F6.2 plateau ``0.70*Fy*Sy``, verbatim
#: a360-22w.pdf (orchestrator-verified, spec_chapterF.txt L1293/L1312);
#: 360-16 used 0.69 - documented edition delta per design-note §9.  The
#: "0 70" in the staged extract is PyMuPDF stripping the decimal point
#: of "0.70" (text extraction does not transpose digits), so the
#: coefficient is unambiguously 0.70.  ``0.70`` is used here AND in the
#: independent oracle, so the bit-exact tier-1 anchor does not mask the
#: choice.
_EQ_F6_2_F6_4_RESIDUAL_STRESS_COEFF: float = 0.70

#: AISC 360-22 Eq. F6-4 critical-stress numerator coefficient ``0.70``:
#: ``Fcr = 0.70*E/(b/tf)^2`` (slender flange).  Identical literal to the
#: Eq. F6-2 residual coefficient (both are the §F6 ``0.70`` elastic
#: factor) but named separately so each equation's provenance is
#: independently citable at its call site.  Same source / F6-EC-1
#: (RESOLVED) provenance as
#: :data:`_EQ_F6_2_F6_4_RESIDUAL_STRESS_COEFF` (a360-22w.pdf,
#: spec_chapterF.txt L1312; 360-16 used 0.69 - documented edition delta
#: per design-note §9).
_EQ_F6_4_FCR_COEFF: float = 0.70


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF6Report(Report):
    """AISC 360-22 §F6 minor-axis flexural-strength result for an I-shape.

    All moments are in apeSteel base units (N*mm); stresses in MPa;
    section moduli in mm^3.

    Attributes
    ----------
    flange_slenderness_lambda : float
        The §F6 compression-flange slenderness ``lambda = b/tf`` with
        ``b = bf/2`` for an I-shape (i.e. ``bf/2tf``), dimensionless.
    compact_limit_lambda_pf : float
        Table B4.1b Case 10/11 ``lambda_pf`` (the compact / noncompact
        flange boundary) - obtained from the F-0 classifier.
    noncompact_limit_lambda_rf : float
        Table B4.1b Case 10/11 ``lambda_rf`` (the noncompact / slender
        flange boundary) - obtained from the F-0 classifier.
    flange_classification : str
        ``"compact"`` / ``"non_compact"`` / ``"slender"`` for the
        compression flange (Case 10/11).
    plastic_moment_Mp : float
        ``Mp = Fy*Zy``, the unbounded Eq. F6-1 plastic moment (N*mm);
        reported for trace (the §F6-1 strength is this capped by
        ``1.6*Fy*Sy``).
    yield_moment_My : float
        ``My = Fy*Sy``, the minor-axis elastic yield moment (N*mm).
        ``1.6*My`` is the Eq. F6-1 cap; ``0.70*My`` anchors the Eq. F6-2
        noncompact interpolation and Eq. F6-3 slender branch.
    plastic_moment_cap_1_6_Fy_Sy : float
        The Eq. F6-1 upper bound ``1.6*Fy*Sy`` (N*mm).
    yielding_moment_Mn_F6_1 : float
        The Eq. F6-1 yielding strength ``min(Fy*Zy, 1.6*Fy*Sy)`` (N*mm)
        - i.e. ``Mp`` after the ``1.6*Fy*Sy`` cap.  This is the FLB
        plateau the Eq. F6-2 interpolation departs from.
    critical_stress_Fcr : float
        Eq. F6-4 ``Fcr = 0.70 E/(b/tf)^2`` (MPa).  Computed only on the
        slender-flange branch; ``0.0`` otherwise (the formula does not
        apply).
    nominal_flexural_strength_Mn : float
        Final ``Mn`` per the governing §F6 limit state (N*mm).  Mirrors
        :attr:`Report.nominal_strength`.
    """

    flange_slenderness_lambda: float = 0.0
    compact_limit_lambda_pf: float = 0.0
    noncompact_limit_lambda_rf: float = 0.0
    flange_classification: str = "compact"
    plastic_moment_Mp: float = 0.0
    yield_moment_My: float = 0.0
    plastic_moment_cap_1_6_Fy_Sy: float = 0.0
    yielding_moment_Mn_F6_1: float = 0.0
    critical_stress_Fcr: float = 0.0
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Equation-set citations
# ---------------------------------------------------------------------------
_CITATIONS_F6: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    # §F6 body - equation numbers + page verbatim from
    # spec_chapterF.txt / _chapterF_citation_reference.md (§F6 row,
    # printed 16.1-62).
    AISCClauseReference("AISC 360-22", "F6", None, "16.1-62"),
    AISCClauseReference("AISC 360-22", "F6.1", "F6-1", "16.1-62"),
    AISCClauseReference("AISC 360-22", "F6.2", "F6-2", "16.1-62"),
    AISCClauseReference("AISC 360-22", "F6.2", "F6-3", "16.1-62"),
    AISCClauseReference("AISC 360-22", "F6.2", "F6-4", "16.1-62"),
    # Table B4.1b Case 10 (rolled) / Case 11 (welded) - I-shape flange in
    # flexure; reached through the F-0 classifier (single source of truth
    # for the FLB regime boundaries).  Page label intentionally None: the
    # B4.1b case-row pages are not in the staged extract
    # (_chapterF_citation_reference.md ENGINEER-CONFIRM); the numeric
    # limits do not depend on the label and the oracle re-derives them.
    AISCClauseReference("AISC 360-22", "Table B4.1b", "Case 10", None),
    AISCClauseReference("AISC 360-22", "Table B4.1b", "Case 11", None),
)


# ---------------------------------------------------------------------------
# Public calculator
# ---------------------------------------------------------------------------
def compute_flexural_strength_F6_minor_axis(
    section_properties: SectionProperties,
    material: SteelMaterial,
    *,
    section_kind: FlexuralSectionKind = "doubly_symmetric_I",
    construction: SectionConstruction = "rolled",
) -> FlexureF6Report:
    """Return ``Mn`` per AISC 360-22 §F6 for a minor-axis-bent I-shape.

    A minor-axis-bent I-shape has **no** lateral-torsional-buckling
    limit state, hence no unbraced-length / ``Cb`` argument (contrast
    §F2-§F5).  ``Mn`` is the lower of yielding and flange local
    buckling:

    * yielding -> Eq. F6-1 ``Mn = Mp = Fy*Zy <= 1.6*Fy*Sy``;
    * compact flange -> FLB does not apply (the Eq. F6-1 value stands);
    * noncompact flange -> Eq. F6-2 interpolation between the Eq. F6-1
      plateau and ``0.70*Fy*Sy``;
    * slender flange -> Eq. F6-3 ``Mn = Fcr*Sy`` with Eq. F6-4
      ``Fcr = 0.70 E/(b/tf)^2``.

    The shipped I-only :class:`SectionProperties` is lifted into the
    generalized :class:`FlexuralSectionProperties` via
    :meth:`FlexuralSectionProperties.from_legacy` (zero numerical change
    - the same ``Sy``/``Zy`` floats flow through), exactly as the
    shipped §F2-§F5 path does.  ``Zy``/``Sy`` come from the lifted
    snapshot; the Case 10/11 ``lambda_pf`` / ``lambda_rf`` come from the
    F-0 generalized classifier
    :func:`~apeSteel.classification.classify_flexural_compactness`
    (so §F6 and the classifier share one source of truth for the FLB
    regime boundaries).  The §F6 flange slenderness for an I-shape is
    ``lambda = b/tf`` with ``b = bf/2`` (§F6.2), i.e.
    ``flange_width_to_thickness_ratio_bf_2tf`` - read straight off the
    legacy ``SectionProperties``.

    Parameters
    ----------
    section_properties : SectionProperties
        The shipped I-only currency (from
        ``DoublySymmetricISection`` / ``SinglySymmetricISection``
        ``.compute_section_properties()`` or a catalog adapter).  Reads
        ``plastic_section_modulus_weak_axis_Zy``,
        ``elastic_section_modulus_weak_axis_Sy``,
        ``flange_width_to_thickness_ratio_bf_2tf`` (the §F6 ``b/tf``
        with ``b = bf/2``) and
        ``web_height_to_thickness_ratio_h_tw`` (only for the welded
        Case 11 ``kc`` factor; ignored for rolled Case 10).
    material : SteelMaterial
        Reads ``Fy`` and ``E`` only.
    section_kind : FlexuralSectionKind, keyword-only, optional
        ``"doubly_symmetric_I"`` (default) or ``"singly_symmetric_I"``.
        Both are I-shapes for §F6 minor-axis flange-FLB purposes (the
        flange Case 10/11 limits are identical; §F6 has no web limit
        state).  ``"channel"`` is **out of F-4 scope** (deferred to
        F-8) and rejected.
    construction : SectionConstruction, keyword-only, optional
        ``"rolled"`` (default) or ``"welded"``.  Selects Table B4.1b
        Case 10 (rolled, ``lambda_rf = 1.0 sqrt(E/Fy)``) vs Case 11
        (welded built-up, ``lambda_rf = 0.95 sqrt(kc E / FL)``) for the
        flange - passed straight through to the F-0 classifier.

    Returns
    -------
    FlexureF6Report
        Frozen dataclass with every §F6 intermediate exposed.

    Raises
    ------
    ValueError
        If ``section_kind`` is not an I-shape kind
        (``"doubly_symmetric_I"`` / ``"singly_symmetric_I"``) - channel
        minor-axis §F6 is deferred to F-8; or if ``Zy`` or ``Sy`` is
        non-positive (degenerate section).
    """
    if section_kind not in ("doubly_symmetric_I", "singly_symmetric_I"):
        msg = (
            f"§F6 (F-4) applies only to doubly-/singly-symmetric I-shapes; "
            f"got section_kind={section_kind!r}.  Channel minor-axis §F6 is "
            f"deferred to Phase F-8 (design note 10 §5, F-4 line)."
        )
        raise ValueError(msg)

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E

    # Lift the shipped I-only currency into the generalized Chapter-F
    # model (mirrors the §F2 idiom).  ``from_legacy`` copies Sy/Zy
    # verbatim - zero numerical change.  ``symmetry`` does not influence
    # any quantity §F6 reads from ``fsp`` (§F6 minor-axis flange-FLB uses
    # only Zy, Sy and the flange Case 10/11 limits, which are symmetry-
    # independent); it is passed for call-site parity with the
    # classifier.
    fsp_symmetry: SectionSymmetry = (
        "doubly_symmetric" if section_kind == "doubly_symmetric_I" else "singly_symmetric"
    )
    fsp: FlexuralSectionProperties = FlexuralSectionProperties.from_legacy(
        section_properties,
        kind=section_kind,
        symmetry=fsp_symmetry,
        construction=construction,
    )

    Zy: float = fsp.plastic_modulus_Zy
    Sy: float = fsp.elastic_modulus_Sy
    if Zy <= 0.0:
        raise ValueError(f"minor-axis plastic modulus Zy must be positive, got {Zy!r}")
    if Sy <= 0.0:
        raise ValueError(f"minor-axis elastic modulus Sy must be positive, got {Sy!r}")

    # §F6 flange slenderness for an I-shape: lambda = b/tf with b = bf/2
    # (§F6.2 definition of b), i.e. exactly bf/2tf - read straight off
    # the legacy currency (the generalized FlexuralSectionProperties does
    # not carry the raw flange ratio; the legacy SectionProperties does).
    lambda_flange: float = section_properties.flange_width_to_thickness_ratio_bf_2tf
    web_h_tw: float = section_properties.web_height_to_thickness_ratio_h_tw

    # Table B4.1b Case 10/11 lambda_pf / lambda_rf via the F-0 generalized
    # classifier (single source of truth for the FLB regime boundaries -
    # the 0.38 / 1.0 / 0.95 coefficients are NOT re-declared in this
    # module).  §F6 has no web limit state, but the classifier needs the
    # web ratio to form the welded-flange kc factor (Case 11); for the
    # rolled default it is unused.
    classification_report = classify_flexural_compactness(
        material,
        section_kind=section_kind,
        construction=construction,
        flange_slenderness_bf_2tf=lambda_flange,
        web_slenderness_h_tw=web_h_tw,
    )
    # The I-shape classifier emits [flange, web]; §F6 only uses the
    # flange element (no minor-axis web limit state).  Guard the
    # invariant explicitly rather than positional-unpacking.
    flange_elements = [
        e for e in classification_report.plate_elements if e.role == "compression_flange"
    ]
    if len(flange_elements) != 1:  # pragma: no cover - classifier invariant
        msg = (
            f"I-shape classifier must emit exactly one compression-flange "
            f"element, got {len(flange_elements)}"
        )
        raise ValueError(msg)
    flange = flange_elements[0]
    lambda_pf: float = flange.compact_limit_lambda_p
    lambda_rf: float = flange.noncompact_limit_lambda_r
    flange_class = flange.classification

    # --- Eq. F6-1 yielding: Mn = Mp = Fy*Zy <= 1.6*Fy*Sy ---
    Mp: float = Fy * Zy
    My: float = Fy * Sy
    cap_1_6_Fy_Sy: float = _EQ_F6_1_SHAPE_FACTOR_CAP * Fy * Sy
    Mn_F6_1: float = min(Mp, cap_1_6_Fy_Sy)  # Eq. F6-1 (capped plateau)

    Fcr: float = 0.0
    governing_limit_state: FlexuralLimitState
    if flange_class == "compact":
        # §F6.2(a): for compact flanges FLB does not apply -> Eq. F6-1.
        governing_limit_state = "yielding"
        Mn: float = Mn_F6_1
    elif flange_class == "non_compact":
        # Eq. F6-2: linear interpolation between the Eq. F6-1 plateau
        # (Mn_F6_1, the capped Mp) at lambda_pf and 0.70*Fy*Sy at
        # lambda_rf.  AISC writes the plateau term as ``Mp``; the §F6-1
        # cap ``1.6*Fy*Sy`` bounds that plateau, so the interpolation
        # starts from the *capped* value (Mn_F6_1) - identical to ``Mp``
        # for ordinary W-shapes where Fy*Zy < 1.6*Fy*Sy.
        governing_limit_state = "flange_local_buckling"
        residual = _EQ_F6_2_F6_4_RESIDUAL_STRESS_COEFF * Fy * Sy
        Mn = Mn_F6_1 - (Mn_F6_1 - residual) * (lambda_flange - lambda_pf) / (lambda_rf - lambda_pf)
    else:
        # Eq. F6-3 / F6-4: slender flange.  Fcr = 0.70 E/(b/tf)^2 with
        # b/tf = lambda_flange (b = bf/2 for an I-shape, §F6.2).
        governing_limit_state = "flange_local_buckling"
        Fcr = _EQ_F6_4_FCR_COEFF * E / lambda_flange**2  # Eq. F6-4
        Mn = Fcr * Sy  # Eq. F6-3

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF6Report(
        cited_clauses=_CITATIONS_F6,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        flange_slenderness_lambda=lambda_flange,
        compact_limit_lambda_pf=lambda_pf,
        noncompact_limit_lambda_rf=lambda_rf,
        flange_classification=flange_class,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
        plastic_moment_cap_1_6_Fy_Sy=cap_1_6_Fy_Sy,
        yielding_moment_Mn_F6_1=Mn_F6_1,
        critical_stress_Fcr=Fcr,
        nominal_flexural_strength_Mn=Mn,
    )


def compute_flexural_strength_F6_minor_axis_channel(
    section_properties: FlexuralSectionProperties,
    material: SteelMaterial,
    *,
    channel_flange_slenderness_b_t: float,
    construction: SectionConstruction = "rolled",
) -> FlexureF6Report:
    """Return ``Mn`` per AISC 360-22 §F6 for a **channel**, minor axis.

    AISC 360-22 §F6 ("I-shaped members **and channels** bent about
    their minor axis") applies to channels exactly as to I-shapes -
    same Eq. F6-1..F6-4, same Table B4.1b Case 10/11 flange
    ``lambda_pf`` / ``lambda_rf`` - with **one** difference, the §F6.2
    definition of the flange-slenderness measure ``b``:

    * I-shape flange: ``b = bf/2`` (so ``lambda = bf/2tf``);
    * **channel flange: ``b`` = the *full* nominal flange width**
      (so ``lambda = bf/tf``).

    (AISC 360-22 §F6.2 spec note, verbatim from
    ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` /
    ``_chapterF_citation_reference.md`` §F6 row: "``b`` = bf/2 for
    I-shape flanges, full flange width for channels".)

    This is a thin channel-specific entry point so the verified
    I-shape :func:`compute_flexural_strength_F6_minor_axis` (a
    *legacy*-``SectionProperties`` calculator, regression-pinned by
    ``test_chapterF_F6_golden``) is **byte-unchanged**.  It reads
    ``Sy``/``Zy`` natively from the channel's
    :class:`FlexuralSectionProperties` (produced by
    :meth:`ChannelSection.compute_section_properties`); the §F6 logic
    (Eq. F6-1 cap, Eq. F6-2 interpolation, Eq. F6-3/F6-4 slender) is
    identical to the I-shape path and the Case 10/11 ``lambda_pf`` /
    ``lambda_rf`` come from the same F-0 generalized classifier
    (``section_kind="channel"``), so §F6 and the classifier share one
    source of truth for the FLB regime boundaries.

    Parameters
    ----------
    section_properties : FlexuralSectionProperties
        A ``section_kind == "channel"`` snapshot, as produced by
        :meth:`ChannelSection.compute_section_properties`.  Reads
        ``plastic_modulus_Zy`` and ``elastic_modulus_Sy`` only.
    material : SteelMaterial
        Reads ``Fy`` and ``E`` only.
    channel_flange_slenderness_b_t : float, keyword-only
        The §F6 channel flange slenderness ``b/tf`` with ``b`` = the
        **full** nominal flange width (``bf/tf``), > 0.  Passed
        explicitly (the geometry computes it) because the generalized
        :class:`FlexuralSectionProperties` does not carry the raw
        flange ratio - exactly as §F9 takes ``flange_slenderness_bf_2tf``
        explicitly for a tee / double angle.
    construction : SectionConstruction, keyword-only, optional
        ``"rolled"`` (default) or ``"welded"``.  Selects Table B4.1b
        Case 10 vs Case 11 for the flange (passed straight through to
        the F-0 classifier; channels are rolled in practice but the
        parameter mirrors the I-shape §F6 contract).

    Returns
    -------
    FlexureF6Report
        Frozen dataclass with every §F6 intermediate exposed.

    Raises
    ------
    ValueError
        If ``section_kind`` is not ``"channel"``; if ``Zy``/``Sy`` is
        non-positive; or if ``channel_flange_slenderness_b_t`` is
        non-positive.
    """
    if section_properties.section_kind != "channel":
        msg = (
            f"compute_flexural_strength_F6_minor_axis_channel applies only to "
            f"channels; got section_kind={section_properties.section_kind!r}.  "
            f"For an I-shape use compute_flexural_strength_F6_minor_axis."
        )
        raise ValueError(msg)
    if channel_flange_slenderness_b_t <= 0.0:
        msg = (
            f"channel_flange_slenderness_b_t must be positive, "
            f"got {channel_flange_slenderness_b_t!r}"
        )
        raise ValueError(msg)

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E

    Zy: float = section_properties.plastic_modulus_Zy
    Sy: float = section_properties.elastic_modulus_Sy
    if Zy <= 0.0:
        raise ValueError(f"minor-axis plastic modulus Zy must be positive, got {Zy!r}")
    if Sy <= 0.0:
        raise ValueError(f"minor-axis elastic modulus Sy must be positive, got {Sy!r}")

    # §F6 channel flange slenderness: lambda = b/tf with b = the FULL
    # flange width (§F6.2 spec note) - passed in as
    # channel_flange_slenderness_b_t.
    lambda_flange: float = channel_flange_slenderness_b_t

    # Table B4.1b Case 10/11 lambda_pf / lambda_rf via the F-0
    # generalized classifier (single source of truth - the 0.38 / 1.0
    # / 0.95 coefficients are NOT re-declared here).  The channel
    # classifier needs the web ratio only to form the welded-flange kc
    # factor (Case 11); §F6 has no channel web limit state, and for the
    # rolled default the web ratio is unused, so a neutral 0.0 is
    # passed (Case 10 lambda_rf = 1.0 sqrt(E/Fy) is web-independent).
    classification_report = classify_flexural_compactness(
        material,
        section_kind="channel",
        construction=construction,
        flange_slenderness_bf_2tf=lambda_flange,
        web_slenderness_h_tw=0.0,
    )
    flange_elements = [
        e for e in classification_report.plate_elements if e.role == "compression_flange"
    ]
    if len(flange_elements) != 1:  # pragma: no cover - classifier invariant
        msg = (
            f"channel classifier must emit exactly one compression-flange "
            f"element, got {len(flange_elements)}"
        )
        raise ValueError(msg)
    flange = flange_elements[0]
    lambda_pf: float = flange.compact_limit_lambda_p
    lambda_rf: float = flange.noncompact_limit_lambda_r
    flange_class = flange.classification

    # --- Eq. F6-1 yielding: Mn = Mp = Fy*Zy <= 1.6*Fy*Sy ---
    Mp: float = Fy * Zy
    My: float = Fy * Sy
    cap_1_6_Fy_Sy: float = _EQ_F6_1_SHAPE_FACTOR_CAP * Fy * Sy
    Mn_F6_1: float = min(Mp, cap_1_6_Fy_Sy)  # Eq. F6-1 (capped plateau)

    Fcr: float = 0.0
    governing_limit_state: FlexuralLimitState
    if flange_class == "compact":
        # §F6.2(a): for compact flanges FLB does not apply -> Eq. F6-1.
        governing_limit_state = "yielding"
        Mn: float = Mn_F6_1
    elif flange_class == "non_compact":
        # Eq. F6-2: interpolation between the Eq. F6-1 plateau and
        # 0.70*Fy*Sy (identical form to the I-shape §F6 path).
        governing_limit_state = "flange_local_buckling"
        residual = _EQ_F6_2_F6_4_RESIDUAL_STRESS_COEFF * Fy * Sy
        Mn = Mn_F6_1 - (Mn_F6_1 - residual) * (lambda_flange - lambda_pf) / (lambda_rf - lambda_pf)
    else:
        # Eq. F6-3 / F6-4: slender flange.  Fcr = 0.70 E/(b/tf)^2 with
        # b/tf = lambda_flange (b = the full flange width for a channel).
        governing_limit_state = "flange_local_buckling"
        Fcr = _EQ_F6_4_FCR_COEFF * E / lambda_flange**2  # Eq. F6-4
        Mn = Fcr * Sy  # Eq. F6-3

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF6Report(
        cited_clauses=_CITATIONS_F6,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        flange_slenderness_lambda=lambda_flange,
        compact_limit_lambda_pf=lambda_pf,
        noncompact_limit_lambda_rf=lambda_rf,
        flange_classification=flange_class,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
        plastic_moment_cap_1_6_Fy_Sy=cap_1_6_Fy_Sy,
        yielding_moment_Mn_F6_1=Mn_F6_1,
        critical_stress_Fcr=Fcr,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF6Report",
    "compute_flexural_strength_F6_minor_axis",
    "compute_flexural_strength_F6_minor_axis_channel",
]

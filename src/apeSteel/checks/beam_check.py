"""BeamCheck - the high-level facade that runs a full AISC beam check.

`run_full_beam_check(element)` (also available as `Element.run_full_check()`)
orchestrates the full member-level check sequence:

    1. Classify per AISC 360 Table B4.1b (flexural compactness).
    2. Route to:
         * F4  if the section is singly-symmetric with a compact or
                  non-compact web (Phase 9b)
         * F5  if the section is singly-symmetric with a slender web
                  (AISC §F5 covers DS *and* SS - Phase F-1)
         * F2  if doubly-symmetric, web compact + flange compact
         * F3  if doubly-symmetric, web compact + flange non-compact / slender
         * F4  if doubly-symmetric, web non-compact (Phase 9a)
         * F5  if doubly-symmetric, web slender (plate girder)
    3. Run both flanges through the routed F engine and identify the
       governing flange (lowest phi*Mn).
    4. Run G2 shear (Vn) - DS only at present.
    5. Return a single `BeamCheckReport` aggregating everything.

The facade does NOT run seismic-compactness or axial-compression checks
by default - those require additional inputs (ductility level, axial
demand) that the caller must explicitly supply.  Element exposes them
as separate methods.

See docs/design_notes/04_flexure_F2_F3_F4_F5.md and
docs/design_notes/05_shear_G2.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.classification import FlexuralCompactnessReport
    from apeSteel.element import (
        BothFlangesFlexureF2Report,
        BothFlangesFlexureF3Report,
        BothFlangesFlexureF4Report,
        BothFlangesFlexureF5Report,
        Element,
        GoverningFlange,
    )
    from apeSteel.shear import ShearG2Report


RoutedFlexureChapter = Literal[
    "F2",
    "F3",
    "F4",
    "F5",
]


@dataclass(frozen=True, slots=True)
class BeamCheckReport(Report):
    """Aggregate report from `run_full_beam_check`.

    Attributes
    ----------
    flexural_classification : FlexuralCompactnessReport
        The B4.1b classifier output that drove routing.
    routed_flexure_chapter : str
        "F2", "F3", "F4", or "F5".
    flexure_both_flanges : BothFlangesFlexureF2Report | BothFlangesFlexureF3Report \
        | BothFlangesFlexureF4Report | BothFlangesFlexureF5Report | None
        The both-flanges flexural result.
    governing_flexural_flange : "top" | "bot" | None
        Which flange's phi*Mn governed.  None when not routed.
    governing_flexural_phi_Mn : float
        The min(top phi*Mn, bot phi*Mn).  0.0 when not routed.
    shear : ShearG2Report | None
        AISC G2 web shear result.  None for singly-symmetric sections
        (G2 SS not yet shipped); always populated for doubly-symmetric.
    """

    flexural_classification: FlexuralCompactnessReport = None  # type: ignore[assignment]
    routed_flexure_chapter: RoutedFlexureChapter = "F2"
    flexure_both_flanges: (
        BothFlangesFlexureF2Report
        | BothFlangesFlexureF3Report
        | BothFlangesFlexureF4Report
        | BothFlangesFlexureF5Report
        | None
    ) = None
    governing_flexural_flange: GoverningFlange | None = None
    governing_flexural_phi_Mn: float = 0.0
    shear: ShearG2Report | None = None


_CITATIONS_BEAM_CHECK: tuple[AISCClauseReference, ...] = (
    AISCClauseReference("AISC 360-22", "B4.1b", None, "16.1-11"),
    AISCClauseReference("AISC 360-22", "F2", None, "16.1-49"),
    AISCClauseReference("AISC 360-22", "F3", None, "16.1-50"),
    AISCClauseReference("AISC 360-22", "F4", None, "16.1-56"),
    AISCClauseReference("AISC 360-22", "F5", None, "16.1-60"),
    AISCClauseReference("AISC 360-22", "G2.1", None, "16.1-65"),
)


def run_full_beam_check(
    element: Element,
    transverse_stiffener_spacing_a: float | None = None,
) -> BeamCheckReport:
    """Run classification + F-routing + G2 shear on the given Element.

    Parameters
    ----------
    element : Element
        Must have `bracing` set so the flexural-LTB methods can run.
    transverse_stiffener_spacing_a : float or None, optional
        Passed through to the shear check.  None (default) = unstiffened.
        Ignored for singly-symmetric sections (no G2 SS yet).

    Returns
    -------
    BeamCheckReport

    Notes
    -----
    Singly-symmetric I-sections route to F4 (compact / non-compact web)
    or F5 (slender web - AISC §F5 covers DS *and* SS).  G2 shear is
    still doubly-symmetric-only, so ``shear`` is ``None`` for SS.
    """
    # Local import to avoid circular import at module load
    from apeSteel.sections.geometry import SinglySymmetricISection  # noqa: PLC0415

    is_singly_symmetric = isinstance(element.section, SinglySymmetricISection)

    # --- 1. Classification (always available, no bracing required) ---
    classification = element.classify_flexural()

    # --- 2. Routing based on geometry type and web classification ---
    web_class = classification.web.classification
    flange_class = classification.flange.classification

    routed: RoutedFlexureChapter
    flexure_both: (
        BothFlangesFlexureF2Report
        | BothFlangesFlexureF3Report
        | BothFlangesFlexureF4Report
        | BothFlangesFlexureF5Report
    )
    if is_singly_symmetric:
        # Singly-symmetric: F4 covers compact AND non-compact web;
        # slender web -> F5 (AISC §F5 covers DS *and* SS - Phase F-1).
        if web_class == "slender":
            routed = "F5"
            flexure_both = element.flexural_strength_F5_both_flanges()
        else:
            routed = "F4"
            flexure_both = element.flexural_strength_F4_both_flanges()
    elif web_class == "slender":
        # Doubly-symmetric, slender web -> F5 (plate girder).
        routed = "F5"
        flexure_both = element.flexural_strength_F5_both_flanges()
    elif web_class == "non_compact":
        # Doubly-symmetric, non-compact web -> F4 (Phase 9a).
        routed = "F4"
        flexure_both = element.flexural_strength_F4_both_flanges()
    elif flange_class == "compact":
        # Doubly-symmetric, web compact + flange compact -> F2.
        routed = "F2"
        flexure_both = element.flexural_strength_F2_both_flanges()
    else:
        # Doubly-symmetric, web compact + flange nc / slender -> F3.
        routed = "F3"
        flexure_both = element.flexural_strength_F3_both_flanges()

    # --- 3. Shear (G2 is DS-only at present) ---
    shear_report: ShearG2Report | None
    if is_singly_symmetric:
        shear_report = None
    else:
        shear_report = element.shear_strength_G2(
            transverse_stiffener_spacing_a=transverse_stiffener_spacing_a,
        )

    return BeamCheckReport(
        cited_clauses=_CITATIONS_BEAM_CHECK,
        governing_limit_state=flexure_both.governing_report.governing_limit_state,
        phi_LRFD=flexure_both.governing_report.phi_LRFD,
        omega_ASD=flexure_both.governing_report.omega_ASD,
        nominal_strength=flexure_both.governing_report.nominal_strength,
        phi_strength_LRFD=flexure_both.governing_report.phi_strength_LRFD,
        omega_strength_ASD=flexure_both.governing_report.omega_strength_ASD,
        flexural_classification=classification,
        routed_flexure_chapter=routed,
        flexure_both_flanges=flexure_both,
        governing_flexural_flange=flexure_both.governing_flange,
        governing_flexural_phi_Mn=flexure_both.governing_report.phi_strength_LRFD,
        shear=shear_report,
    )


__all__ = [
    "BeamCheckReport",
    "RoutedFlexureChapter",
    "run_full_beam_check",
]

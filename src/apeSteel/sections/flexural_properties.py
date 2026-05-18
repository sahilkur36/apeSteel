"""Canonical :class:`FlexuralSectionProperties` frozen dataclass.

This is the universal currency between geometry and the AISC 360-22
Chapter-F (flexure) calculators, exactly analogous to
:class:`apeSteel.sections.compression_properties.CompressionSectionProperties`
for compression.

A separate contract (rather than overloading the shipped I-only
:class:`apeSteel.sections.properties.SectionProperties`) is used because
flexure of the *full* chapter needs quantities the I-only currency does
not:

* both-axis ``Z``/``S``/``r``/``I`` (flexure is axis-specific — §F6 is
  minor-axis I, §F7 is either-axis HSS);
* per-plate-element flexural classification (compact / non-compact /
  slender, with the Table B4.1b ``lambda_p`` *and* ``lambda_r``) so the
  §F3/§F4/§F5/§F7/§F9 local-buckling branches can be selected;
* singly-symmetric / tee extras (``Sxc, Sxt, Iyc, hc, hp``) carried over
  from the Phase 9b ``SectionProperties`` optionals;
* round-HSS ``D``/``t`` used directly by §F8;
* single-angle principal-axis constants (``Iw, Iz, rz``) for §F10;
* §F2-8a/8b ``section_constant_c`` (1 for doubly-symmetric I, the
  channel form otherwise);
* §F12 extreme-fibre elastic moduli for the elastic ``Fn·S`` catch-all.

Keeping it separate leaves the verified I-shape flexure path
(``flexure/F2..F5``) untouched at the data model; those calculators
adopt this currency in Phase F-1 via :meth:`from_legacy.from_legacy`,
which lifts the shipped :class:`SectionProperties` (including the
Phase 9b SS optionals and their ``resolved_*`` fallbacks) with zero
numerical change. New (non-I) sections populate this dataclass
natively.

All values are in apeSteel's canonical ``N-mm-tonne-s`` base units
(length in mm, area in mm^2, second moment in mm^4, warping constant in
mm^6, moment in N*mm). See ``docs/UNITS_AND_CONVENTIONS.md`` and
``docs/design_notes/10_flexure_full_F.md`` §3.

References
----------
.. [1] AISC 360-22 Chapter F, pp. 16.1-53 - 16.1-74. American Institute
       of Steel Construction, 2022.
.. [2] docs/design_notes/_chapterF_citation_reference.md - the
       Chapter-F citation source-of-truth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from apeSteel.sections.compression_properties import SectionSymmetry
    from apeSteel.sections.properties import SectionProperties

#: AISC 360-22 Eq. F2-8b channel section-constant numerator coefficient:
#: ``c = (ho / 2) * sqrt(Iy / Cw)`` (spec_chapterF.txt printed 16.1-54).
#: Named (rather than the bare literal ``2.0``) so the F2-8a/8b provenance
#: is traceable at the call site, mirroring the ``F4.py`` constant style.
_EQ_F2_8B_HO_DIVISOR: float = 2.0

#: How the section was fabricated. Re-declared here (rather than imported
#: from :mod:`apeSteel.classification`) so this module obeys the
#: architecture layer rule: ``sections`` may not import from
#: ``classification`` (it sits *below* it). Value-identical to
#: ``apeSteel.classification._common.SectionConstruction``.
SectionConstruction = Literal["rolled", "welded"]

#: The Chapter-F section family (drives facade routing / per-section §F).
#:
#: Mirrors :data:`~apeSteel.sections.compression_properties.CompressionSectionKind`
#: but adds the flexure-only ``rectangular_bar`` / ``round_bar`` (§F11)
#: and ``unsymmetric`` (§F12) families.
FlexuralSectionKind = Literal[
    "doubly_symmetric_I",
    "singly_symmetric_I",
    "channel",
    "rectangular_HSS",
    "round_HSS",
    "tee",
    "double_angle",
    "single_angle",
    "rectangular_bar",
    "round_bar",
    "unsymmetric",
]

#: Axis of bending. Flexure is axis-specific: §F2-§F5 are major-axis I,
#: §F6 is minor-axis I/channel, §F7 is either axis for HSS.
BendingAxis = Literal["major", "minor"]

#: Outcome of AISC 360 Table B4.1b flexural classification for one plate
#: element. Re-declared here (rather than imported from
#: :mod:`apeSteel.classification`) so this module obeys the architecture
#: layer rule: ``sections`` may not import from ``classification``.
FlexuralPlateClass = Literal["compact", "non_compact", "slender"]

#: Role of a plate element in the flexural cross-section. Drives which
#: §F local-buckling branch consumes it.
FlexuralPlateRole = Literal[
    "compression_flange",
    "tension_flange",
    "web",
    "stem",
    "leg",
    "hss_flange",
    "hss_web",
]


@dataclass(frozen=True, slots=True)
class FlexuralPlateElement:
    """One plate element of the cross-section, for the Table B4.1b check.

    Attributes
    ----------
    name : str
        Free label, e.g. ``"flange"``, ``"web"``, ``"wall"``,
        ``"stem"``, ``"leg"``.
    role : FlexuralPlateRole
        Which §F local-buckling branch this element feeds
        (``"compression_flange"``, ``"tension_flange"``, ``"web"``,
        ``"stem"``, ``"leg"``, ``"hss_flange"``, ``"hss_web"``).
    aisc_b4_1b_case : str
        AISC 360 Table B4.1b case label, e.g. ``"B4.1b Case 10"``.
        Written ``"B4.1b Case ?"`` for cases that could not be verified
        from the staged spec extract (see
        ``docs/design_notes/_chapterF_citation_reference.md``
        ENGINEER-CONFIRM). The numeric limits are independent of the
        label.
    slenderness_ratio_lambda : float
        The actual element slenderness ratio (``bf/2tf``, ``h/tw``,
        ``D/t``, ``d/tw``, ``b/t`` ...), dimensionless.
    compact_limit_lambda_p : float
        Table B4.1b ``lambda_p`` — the compact / non-compact boundary.
    noncompact_limit_lambda_r : float
        Table B4.1b ``lambda_r`` — the non-compact / slender boundary.
    """

    name: str
    role: FlexuralPlateRole
    aisc_b4_1b_case: str
    slenderness_ratio_lambda: float
    compact_limit_lambda_p: float
    noncompact_limit_lambda_r: float

    @property
    def classification(self) -> FlexuralPlateClass:
        """Compact / non-compact / slender per the standard B4.1b rule.

        ``compact`` iff ``lambda <= lambda_p``; ``non_compact`` iff
        ``lambda_p < lambda <= lambda_r``; ``slender`` otherwise.
        """
        if self.slenderness_ratio_lambda <= self.compact_limit_lambda_p:
            return "compact"
        if self.slenderness_ratio_lambda <= self.noncompact_limit_lambda_r:
            return "non_compact"
        return "slender"


@dataclass(frozen=True, slots=True)
class FlexuralSectionProperties:
    """Frozen Chapter-F inputs for one section, in base units.

    The gross/both-axis block (``d, Ag, Ix, Sx, Zx, rx, Iy, Sy, Zy,
    ry``) is always populated. Family-specific blocks (LTB constants,
    SS/tee optionals, round-HSS ``D``/``t``, single-angle principal
    axes, §F12 extreme-fibre moduli) default to a neutral sentinel and
    are filled only by the geometries / phases that need them, exactly
    as :class:`CompressionSectionProperties` does for Chapter E.

    See ``docs/design_notes/10_flexure_full_F.md`` §3 for the field
    contract and per-clause consumption.
    """

    # --- Identity / routing ---
    section_kind: FlexuralSectionKind
    symmetry: SectionSymmetry

    # --- Gross / both axes (always required; flexure is axis-specific) ---
    overall_depth_d: float
    gross_area_Ag: float
    moment_of_inertia_Ix: float
    elastic_modulus_Sx: float
    plastic_modulus_Zx: float
    radius_of_gyration_rx: float
    moment_of_inertia_Iy: float
    elastic_modulus_Sy: float
    plastic_modulus_Zy: float
    radius_of_gyration_ry: float

    # --- LTB constants (I / channel; default doubly-symmetric I) ---
    torsional_constant_J: float = 0.0
    warping_constant_Cw: float = 0.0
    #: ``ho`` - distance between flange centroids (mm). I / channel.
    distance_between_flange_centroids_ho: float = 0.0
    #: ``rts`` - effective radius of gyration for LTB, Eq. F2-7 (mm).
    effective_radius_of_gyration_for_LTB_rts: float = 0.0
    #: ``c`` - section constant, Eq. F2-8a (``=1`` doubly-symmetric I)
    #: or Eq. F2-8b (channel). Defaults to 1.0.
    section_constant_c: float = 1.0

    # --- Singly-symmetric / tee (carried over from SectionProperties) ---
    #: ``Sxc`` - elastic modulus referred to the compression flange.
    elastic_modulus_compression_flange_Sxc: float = 0.0
    #: ``Sxt`` - elastic modulus referred to the tension flange.
    elastic_modulus_tension_flange_Sxt: float = 0.0
    #: ``Iyc`` - moment of inertia of the compression flange about y.
    moment_of_inertia_compression_flange_Iyc: float = 0.0
    #: ``hc`` - 2 x (elastic NA -> inside face of compression flange).
    web_compression_depth_hc: float = 0.0
    #: ``hp`` - 2 x (plastic NA -> inside face of compression flange).
    web_plastic_depth_hp: float = 0.0

    # --- Round HSS / Pipe (§F8 uses D/t directly) ---
    #: ``D`` - outside diameter of round HSS (mm).
    diameter_D: float = 0.0
    #: ``t`` - design wall thickness of round HSS (mm).
    wall_thickness_t: float = 0.0

    # --- Single angle (§F10 principal-axis) ---
    #: ``Iw`` - major principal moment of inertia (mm^4).
    principal_I_major_Iw: float = 0.0
    #: ``Iz`` - minor principal moment of inertia (mm^4).
    principal_I_minor_Iz: float = 0.0
    #: ``rz`` - minimum (minor principal) radius of gyration (mm).
    min_principal_radius_rz: float = 0.0
    #: True for an equal-leg angle.
    equal_leg: bool = True
    #: True if the single angle is designed on geometric (x, y) axes
    #: rather than principal axes (§F10 geometric-axis option).
    geometric_axis_bending: bool = False

    # --- §F12 elastic Fn*S - extreme-fibre elastic moduli ---
    #: Elastic section moduli to each extreme fibre / corner relative to
    #: the axis of bending (mm^3). ``min(...)`` is ``Smin`` in Eq. F12-1.
    extreme_fibre_moduli: tuple[float, ...] = ()

    # --- Per-element flexural classification (Table B4.1b) ---
    #: One :class:`FlexuralPlateElement` per plate element. Populated by
    #: :func:`apeSteel.classification.classify_flexural_compactness`
    #: (the ``classification`` layer, which sits above ``sections``;
    #: this module never imports it). Left empty by
    #: :meth:`from_legacy` - F-1 wires classify -> from_legacy at the
    #: ``flexure`` layer.
    plate_elements: tuple[FlexuralPlateElement, ...] = field(default_factory=tuple)

    @property
    def section_classification(self) -> FlexuralPlateClass:
        """Worst (least-favourable) of all plate-element classes.

        Ordering: ``compact`` (best) < ``non_compact`` < ``slender``
        (worst). Returns ``"compact"`` when there are no plate elements
        (e.g. a bar, or a :meth:`from_legacy` instance before the
        classifier has populated :attr:`plate_elements`).
        """
        rank: dict[FlexuralPlateClass, int] = {
            "compact": 0,
            "non_compact": 1,
            "slender": 2,
        }
        worst: FlexuralPlateClass = "compact"
        for element in self.plate_elements:
            if rank[element.classification] > rank[worst]:
                worst = element.classification
        return worst

    @classmethod
    def from_legacy(
        cls,
        sp: SectionProperties,
        *,
        kind: FlexuralSectionKind,
        symmetry: SectionSymmetry,
        construction: SectionConstruction,
    ) -> FlexuralSectionProperties:
        """Lift a shipped I-shape :class:`SectionProperties` losslessly.

        This is the bit-exactness lever for Phase F-1: it copies the
        verified I-shape currency into the generalized model with **zero
        numerical change**, reading the Phase 9b singly-symmetric
        optionals through the same ``resolved_*`` accessors the shipped
        ``flexure/F4.py`` uses, so a doubly-symmetric section never has
        to populate the SS fields explicitly and a singly-symmetric one
        reproduces F4's exact inputs.

        ``plate_elements`` is intentionally left empty: producing the
        Table B4.1b classification requires the ``classification``
        layer, which sits *above* ``sections`` (architecture layer
        rule). Phase F-1 calls
        :func:`~apeSteel.classification.classify_flexural_compactness`
        at the ``flexure`` layer and attaches the result; the legacy
        F2-F5 calculators classify independently exactly as today, so
        no value moves.

        Parameters
        ----------
        sp : SectionProperties
            The shipped I-only currency (from
            ``DoublySymmetricISection`` / ``SinglySymmetricISection``
            ``.compute_section_properties()`` or a catalog adapter).
        kind : FlexuralSectionKind
            ``"doubly_symmetric_I"``, ``"singly_symmetric_I"`` or
            ``"channel"`` (the only kinds expressible as the legacy
            I-currency).
        symmetry : SectionSymmetry
            ``"doubly_symmetric"`` or ``"singly_symmetric"``.
        construction : SectionConstruction
            ``"rolled"`` / ``"welded"``. Accepted for call-site parity
            with the classifier; it does not change any lifted number
            (it selects the Table B4.1b flange *case*, which is the
            classifier's concern, not the model's).

        Returns
        -------
        FlexuralSectionProperties
            The same section, in the generalized currency, numerically
            identical to ``sp`` field-for-field (SS optionals via
            ``resolved_*``).
        """
        # ``construction`` is part of the documented signature (call-site
        # parity with the classifier and forward-compat for F-1) but does
        # not influence any lifted numeric field; reference it so the
        # parameter is unambiguously intentional.
        _ = construction

        # AISC 360-22 §F2.2 section constant ``c``:
        #   Eq. F2-8a  c = 1                       (doubly-symmetric I)
        #   Eq. F2-8b  c = (ho/2) * sqrt(Iy/Cw)    (channels)
        # (spec_chapterF.txt printed 16.1-54, verified verbatim.)
        #
        # A singly-symmetric *I* keeps c = 1 (it is an I-shape, not a
        # channel - §F4 uses its own LTB constants regardless). Only
        # ``kind == "channel"`` takes Eq. F2-8b, and it is derived from
        # the *same* lifted ``ho``/``Iy``/``Cw`` so it folds into the
        # exact spec form. Because no shipped DS/SS-I test passes
        # ``kind="channel"``, ``c`` is exactly ``1.0`` on every
        # externally-anchored path -> the F2/F3/F4/F5 goldens are
        # bit-unchanged.
        section_constant_c: float = 1.0
        if kind == "channel":
            section_constant_c = (
                sp.distance_between_flange_centroids_ho / _EQ_F2_8B_HO_DIVISOR
            ) * math.sqrt(sp.moment_of_inertia_weak_axis_Iy / sp.warping_constant_Cw)

        return cls(
            section_kind=kind,
            symmetry=symmetry,
            overall_depth_d=sp.overall_depth_d,
            gross_area_Ag=sp.gross_area_Ag,
            moment_of_inertia_Ix=sp.moment_of_inertia_strong_axis_Ix,
            elastic_modulus_Sx=sp.elastic_section_modulus_strong_axis_Sx,
            plastic_modulus_Zx=sp.plastic_section_modulus_strong_axis_Zx,
            radius_of_gyration_rx=sp.radius_of_gyration_strong_axis_rx,
            moment_of_inertia_Iy=sp.moment_of_inertia_weak_axis_Iy,
            elastic_modulus_Sy=sp.elastic_section_modulus_weak_axis_Sy,
            plastic_modulus_Zy=sp.plastic_section_modulus_weak_axis_Zy,
            radius_of_gyration_ry=sp.radius_of_gyration_weak_axis_ry,
            torsional_constant_J=sp.torsional_constant_J,
            warping_constant_Cw=sp.warping_constant_Cw,
            distance_between_flange_centroids_ho=sp.distance_between_flange_centroids_ho,
            effective_radius_of_gyration_for_LTB_rts=sp.effective_radius_of_gyration_for_LTB_rts,
            section_constant_c=section_constant_c,
            # SS / tee optionals via the resolved_* fallbacks so a DS
            # section yields Sxc=Sxt=Sx, Iyc=Iy/2, hc=hp=hw exactly as
            # the shipped flexure/F4.py reads them (bit-for-bit).
            elastic_modulus_compression_flange_Sxc=sp.resolved_Sxc(),
            elastic_modulus_tension_flange_Sxt=sp.resolved_Sxt(),
            moment_of_inertia_compression_flange_Iyc=sp.resolved_Iyc(),
            web_compression_depth_hc=sp.resolved_hc(),
            # hp keeps the raw SS sentinel semantics: F4.py branches on
            # ``sp.plastic_neutral_axis_depth_hp > 0`` to detect SS, then
            # uses resolved_hp(). Carry the raw field so that exact
            # branch is reproducible; resolved_hp() == resolved_hc() for
            # DS anyway.
            web_plastic_depth_hp=sp.plastic_neutral_axis_depth_hp,
            plate_elements=(),
        )


__all__ = [
    "BendingAxis",
    "FlexuralPlateClass",
    "FlexuralPlateElement",
    "FlexuralPlateRole",
    "FlexuralSectionKind",
    "FlexuralSectionProperties",
    "SectionConstruction",
]

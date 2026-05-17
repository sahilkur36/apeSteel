"""Canonical :class:`CompressionSectionProperties` frozen dataclass.

This is the universal currency between geometry and the AISC 360-22
Chapter-E (compression) calculators, exactly analogous to
:class:`apeSteel.sections.properties.SectionProperties` for flexure.

A separate contract (rather than overloading ``SectionProperties``) is
used because compression needs quantities flexure does not:

* the shear-centre offset ``xo, yo`` and the polar/flexural constants
  ``ro_bar``, ``H`` for the §E4 torsional / flexural-torsional buckling
  equations (Eq. E4-2 / E4-3 / E4-4, E4-8, E4-9);
* a per-plate-element list (each tagged stiffened vs unstiffened with
  its Table B4.1a ``lambda_r``) so the §E7 effective-width calculator
  can reduce ``Ag`` to ``Ae``;
* §E5 single-angle and §E6 built-up extras.

Keeping it separate leaves the verified flexure path untouched
(consistent with the library's "a calculator takes the smallest slice
of data it needs" philosophy).  All values are in apeSteel's canonical
``N-mm-tonne-s`` base units.

References
----------
.. [1] AISC 360-22 Chapter E, pp. 16.1-37 - 16.1-43.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: How the section's symmetry constrains the §E4 buckling equation.
#:
#: * ``"doubly_symmetric"`` - Eq. E4-2 (torsional about the long. axis;
#:   ``xo = yo = 0``, ``H = 1``).
#: * ``"singly_symmetric"`` - Eq. E4-3 (flexural-torsional; one shear-
#:   centre offset non-zero).
#: * ``"unsymmetric"`` - Eq. E4-4 (cubic in Fe).
SectionSymmetry = Literal["doubly_symmetric", "singly_symmetric", "unsymmetric"]

#: The Chapter-E section family (drives facade routing / §E5 / §E6).
CompressionSectionKind = Literal[
    "doubly_symmetric_I",
    "singly_symmetric_I",
    "channel",
    "tee",
    "rectangular_HSS",
    "round_HSS",
    "single_angle",
    "double_angle",
]


@dataclass(frozen=True, slots=True)
class CompressionPlateElement:
    """One plate element of the cross-section, for the §E7 check.

    Attributes
    ----------
    name : str
        Free label, e.g. ``"flange"``, ``"web"``, ``"wall"``, ``"leg"``,
        ``"stem"``.
    kind : {"stiffened", "unstiffened", "hss_wall"}
        AISC element classification.  Drives the Table E7.1 ``c1, c2``
        pair: ``"unstiffened"`` (one edge supported), ``"stiffened"``
        (both edges supported, not an HSS wall), or ``"hss_wall"``
        (wall of a square / rectangular HSS - a stiffened element with
        its own Table E7.1 row).
    width_b : float
        The element width ``b`` used in the ``b/t`` ratio and in the
        effective-width reduction (mm).
    thickness_t : float
        Element thickness ``t`` (mm).
    slenderness_ratio_lambda : float
        ``b / t`` (dimensionless).
    nonslender_limit_lambda_r : float
        Table B4.1a ``lambda_r`` for this element and material.  The
        element is slender (and triggers §E7) when
        ``slenderness_ratio_lambda > nonslender_limit_lambda_r``.
    """

    name: str
    kind: Literal["stiffened", "unstiffened", "hss_wall"]
    width_b: float
    thickness_t: float
    slenderness_ratio_lambda: float
    nonslender_limit_lambda_r: float

    @property
    def is_slender(self) -> bool:
        """True iff ``b/t`` exceeds the Table B4.1a non-slender limit."""
        return self.slenderness_ratio_lambda > self.nonslender_limit_lambda_r


@dataclass(frozen=True, slots=True)
class CompressionSectionProperties:
    """Frozen Chapter-E inputs for one section, in base units.

    The minimal set every section provides covers §E3 (flexural
    buckling) and §E7 (slender elements).  Sections that can buckle
    torsionally / flexural-torsionally additionally populate the §E4
    block (``J, Cw, xo, yo, ro_bar, H``).  §E5 / §E6 extras are filled
    only by single- and double-angle geometries.
    """

    # --- Identity / routing ---
    section_kind: CompressionSectionKind
    symmetry: SectionSymmetry

    # --- §E3 flexural buckling (always required) ---
    gross_area_Ag: float
    radius_of_gyration_x_rx: float
    radius_of_gyration_y_ry: float
    moment_of_inertia_x_Ix: float
    moment_of_inertia_y_Iy: float

    # --- §E4 torsional / flexural-torsional (default = doubly-sym) ---
    torsional_constant_J: float = 0.0
    warping_constant_Cw: float = 0.0
    #: Shear-centre coordinates relative to the centroid (mm).  Zero for
    #: doubly-symmetric sections.
    shear_centre_x_xo: float = 0.0
    shear_centre_y_yo: float = 0.0
    #: Polar radius of gyration about the shear centre, Eq. E4-9 (mm).
    #: ``ro_bar^2 = xo^2 + yo^2 + (Ix + Iy)/Ag``.  Left 0.0 by sections
    #: for which §E4 does not apply; the calculator derives it when 0.
    polar_radius_about_shear_centre_ro_bar: float = 0.0
    #: Flexural constant H, Eq. E4-8: ``H = 1 - (xo^2 + yo^2)/ro_bar^2``.
    #: Defaults to 1.0 (doubly-symmetric).
    flexural_constant_H: float = 1.0

    # --- §E7 slender elements ---
    plate_elements: tuple[CompressionPlateElement, ...] = field(default_factory=tuple)
    #: Round-HSS only: outside diameter D and wall thickness t (mm).
    #: §E7.2(c) uses D/t directly (Eq. E7-6 / E7-7), not a plate element.
    diameter_D: float = 0.0
    wall_thickness_t: float = 0.0

    # --- §E5 single angle / §E6 built-up extras ---
    #: Minor (z) principal radius of gyration (mm), used by single
    #: angles and as the component minimum for double angles.
    min_principal_radius_of_gyration_rz: float = 0.0
    #: Radius of gyration of one component about its own minor axis
    #: (mm), used by the §E6 built-up modified-slenderness equations.
    component_min_radius_of_gyration_ri: float = 0.0

    @property
    def any_element_slender(self) -> bool:
        """True iff §E7 applies (any plate element slender, or round
        HSS D/t over its Table B4.1a limit -- the latter is decided by
        the §E7 calculator from :attr:`diameter_D` / :attr:`wall_thickness_t`)."""
        return any(pe.is_slender for pe in self.plate_elements)


__all__ = [
    "CompressionPlateElement",
    "CompressionSectionKind",
    "CompressionSectionProperties",
    "SectionSymmetry",
]

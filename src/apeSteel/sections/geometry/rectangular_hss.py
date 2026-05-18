"""Plate-built rectangular / square HSS (box) geometry for AISC §E / §F7.

A rectangular HSS is doubly-symmetric.  Because it is a closed section
with very high torsional stiffness, §E4 torsional / flexural-torsional
buckling is not a governing limit state - AISC routes HSS through §E3
(flexural buckling) only - so the compression facade skips §E4 for
``section_kind == "rectangular_HSS"``.  Slender walls are handled by the
§E7.2 effective-width method using the *HSS-wall* Table E7.1 constants
(``c1 = 0.20``, ``c2 = 1.38``); the non-slender limit is Table B4.1a
``lambda_r = 1.40 sqrt(E/Fy)``.

Area / inertia are transcribed from the validated workbook ``HSS``
sheet (``B43 .. B47``).  The flat wall width used for §E7 is the
AISC-correct welded-box clear width ``B - 2t`` (the workbook's display
``(B - t)/t`` slenderness cell is not on the strength path).

For flexure (AISC 360-22 §F7, square / rectangular HSS & box) the
*identical* ``Ag`` / ``Ix`` / ``Iy`` / ``J`` closed forms are reused
unchanged - :meth:`compute_section_properties` shares them byte-for-byte
with :meth:`compute_compression_properties` and only *adds* the plastic
and elastic section moduli (``Zx, Sx, Zy, Sy``) that §F7 needs.  §F7 is
bent about *either* axis, so both-axis moduli are populated.  The two
distinct flat walls (the ``B``-walls of flat width ``B - 2t`` and the
``H``-walls of flat width ``H - 2t``) are carried as the snapshot's
``plate_elements`` so the §F7 calculator can pick the flange vs web for
the requested bending axis and classify them via the generalized
Table B4.1b classifier (the geometry layer never imports
``classification``, so the ``lambda_p`` / ``lambda_r`` are left at the
neutral ``0.0`` sentinel here exactly as the round-HSS §F8 path does).

References
----------
.. [1] AISC 360-22 §E3, §E7.2, Table B4.1a Case 6 (HSS walls,
       1.40 sqrt(E/Fy)), Table E7.1 (HSS-wall c1/c2), pp. 16.1-37 -
       16.1-43.
.. [2] AISC 360-22 §F7 "Square and Rectangular HSS and Box Sections",
       Eq. F7-1 - F7-13, pp. 16.1-63 - 16.1-65.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.compression._common import B4_1A_STIFFENED_HSS_WALL_COEFF
from apeSteel.sections.compression_properties import (
    CompressionPlateElement,
    CompressionSectionProperties,
)
from apeSteel.sections.flexural_properties import (
    FlexuralPlateElement,
    FlexuralSectionProperties,
)

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial


@dataclass(frozen=True, slots=True)
class RectangularHSS:
    """Plate-built rectangular/square HSS, all dims in mm.

    Parameters
    ----------
    depth_H : float
        Overall depth (the dimension whose walls are the ``H`` webs).
    width_B : float
        Overall width.
    wall_thickness_t : float
        Uniform wall thickness.
    """

    depth_H: float
    width_B: float
    wall_thickness_t: float

    def compute_compression_properties(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
    ) -> CompressionSectionProperties:
        """Return the AISC 360-22 Chapter-E input snapshot for a rect HSS."""
        H: float = self.depth_H
        B: float = self.width_B
        t: float = self.wall_thickness_t

        # Workbook HSS!B43: Ag = 2*B*t + 2*(H-2t)*t  (the two B walls
        # full width, the two H walls reduced by the B-wall thicknesses).
        Ag: float = 2.0 * B * t + 2.0 * (H - 2.0 * t) * t
        # Hollow-rectangle second moments (workbook B44 / B46).
        Ix: float = (B * H**3 - (B - 2.0 * t) * (H - 2.0 * t) ** 3) / 12.0
        Iy: float = (H * B**3 - (H - 2.0 * t) * (B - 2.0 * t) ** 3) / 12.0
        rx: float = math.sqrt(Ix / Ag)
        ry: float = math.sqrt(Iy / Ag)

        # Closed-section St-Venant torsion constant (mid-line Bredt);
        # not on the §E3 strength path (HSS skips §E4) - provided for
        # completeness / future Chapter H.
        bm: float = B - t
        hm: float = H - t
        J: float = 2.0 * t * bm**2 * hm**2 / (bm + hm)

        sqrt_E_over_Fy: float = math.sqrt(material.elastic_modulus_E / material.yield_stress_Fy)
        lam_r: float = B4_1A_STIFFENED_HSS_WALL_COEFF * sqrt_E_over_Fy
        # Two distinct flat walls (welded box clear width = dim - 2t).
        wall_h = CompressionPlateElement(
            name="wall_H",
            kind="hss_wall",
            width_b=H - 2.0 * t,
            thickness_t=t,
            slenderness_ratio_lambda=(H - 2.0 * t) / t,
            nonslender_limit_lambda_r=lam_r,
        )
        wall_b = CompressionPlateElement(
            name="wall_B",
            kind="hss_wall",
            width_b=B - 2.0 * t,
            thickness_t=t,
            slenderness_ratio_lambda=(B - 2.0 * t) / t,
            nonslender_limit_lambda_r=lam_r,
        )

        return CompressionSectionProperties(
            section_kind="rectangular_HSS",
            symmetry="doubly_symmetric",
            gross_area_Ag=Ag,
            radius_of_gyration_x_rx=rx,
            radius_of_gyration_y_ry=ry,
            moment_of_inertia_x_Ix=Ix,
            moment_of_inertia_y_Iy=Iy,
            torsional_constant_J=J,
            warping_constant_Cw=0.0,  # closed section: ~0
            polar_radius_about_shear_centre_ro_bar=math.sqrt((Ix + Iy) / Ag),
            flexural_constant_H=1.0,
            plate_elements=(wall_h, wall_b),
        )

    def compute_section_properties(self) -> FlexuralSectionProperties:
        """Return the AISC 360-22 §F7 flexural input snapshot for a rect HSS.

        The gross-section closed forms are **identical** to those in
        :meth:`compute_compression_properties` (same ``Ag`` / ``Ix`` /
        ``Iy`` / ``J``), written byte-for-byte so the two snapshots
        cannot disagree on the shared quantities; this method only
        *adds* the plastic / elastic section moduli that §F7 needs
        (compression never required them).

        For a rectangular box of overall depth ``H``, overall width
        ``B`` and uniform wall thickness ``t`` (inner clear depth
        ``Hi = H - 2t``, inner clear width ``Bi = B - 2t``):

        * gross area ``Ag = 2 B t + 2 (H - 2 t) t``
          (= workbook ``HSS!B43``, same as compression);
        * second moments (workbook ``HSS!B44`` / ``B46``)
          ``Ix = (B H^3 - Bi Hi^3) / 12``,
          ``Iy = (H B^3 - Hi Bi^3) / 12``;
        * elastic moduli ``Sx = 2 Ix / H``, ``Sy = 2 Iy / B``;
        * plastic moduli of the hollow rectangle (solid outer block less
          the rectangular void)
          ``Zx = (B H^2 - Bi Hi^2) / 4``,
          ``Zy = (H B^2 - Hi Bi^2) / 4``.

        §F7 is bent about *either* axis, so both-axis moduli are filled.
        The two distinct flat walls are carried as ``plate_elements``
        (the AISC welded-box clear width ``dim - 2t``, exactly the
        compression convention): ``wall_B`` (flat width ``B - 2t``,
        i.e. the *flange* in major-axis bending / the *web* in
        minor-axis bending) and ``wall_H`` (flat width ``H - 2t``, i.e.
        the *web* in major-axis bending / the *flange* in minor-axis
        bending).  Their Table B4.1b ``lambda_p`` / ``lambda_r`` are
        left at the neutral ``0.0`` sentinel - the ``classification``
        layer sits *above* ``sections`` and the geometry never imports
        it, so the §F7 calculator runs
        :func:`~apeSteel.classification.classify_flexural_compactness`
        itself (identical contract to the round-HSS §F8 path).
        ``overall_depth_d`` carries ``H`` and ``wall_thickness_t``
        carries ``t`` so the calculator can rebuild the per-axis
        flat-flange width for the slender-flange ``Se`` (Eq. F7-3 ..
        F7-5).

        Returns
        -------
        FlexuralSectionProperties
            ``section_kind="rectangular_HSS"``, doubly-symmetric, in
            base units, with both-axis ``Z`` / ``S`` populated.
        """
        H: float = self.depth_H
        B: float = self.width_B
        t: float = self.wall_thickness_t

        # Shared with compute_compression_properties (HSS!B43/B44/B46) -
        # written identically so the two snapshots cannot diverge.
        Ag: float = 2.0 * B * t + 2.0 * (H - 2.0 * t) * t
        Ix: float = (B * H**3 - (B - 2.0 * t) * (H - 2.0 * t) ** 3) / 12.0
        Iy: float = (H * B**3 - (H - 2.0 * t) * (B - 2.0 * t) ** 3) / 12.0
        rx: float = math.sqrt(Ix / Ag)
        ry: float = math.sqrt(Iy / Ag)
        bm: float = B - t
        hm: float = H - t
        J: float = 2.0 * t * bm**2 * hm**2 / (bm + hm)

        # Flexure-only additions.
        # Elastic moduli (extreme fibre at +/- H/2 about x, +/- B/2 about y).
        Sx: float = Ix / (H / 2.0)
        Sy: float = Iy / (B / 2.0)
        # Hollow-rectangle plastic moduli: solid outer block plastic
        # modulus (b d^2 / 4) less the rectangular void's.
        Zx: float = (B * H**2 - (B - 2.0 * t) * (H - 2.0 * t) ** 2) / 4.0
        Zy: float = (H * B**2 - (H - 2.0 * t) * (B - 2.0 * t) ** 2) / 4.0

        # The two distinct flat walls (AISC welded-box clear width
        # dim - 2t, identical to the compression convention).  lambda_p
        # / lambda_r stay 0.0 - the §F7 calculator classifies via the
        # generalized Table B4.1b classifier (geometry never imports the
        # classification layer; mirrors the round-HSS §F8 path).
        wall_b = FlexuralPlateElement(
            name="wall_B",
            role="hss_flange",  # flange in major-axis bending
            aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-1/EC-2
            slenderness_ratio_lambda=(B - 2.0 * t) / t,
            compact_limit_lambda_p=0.0,
            noncompact_limit_lambda_r=0.0,
        )
        wall_h = FlexuralPlateElement(
            name="wall_H",
            role="hss_web",  # web in major-axis bending
            aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-1/EC-2
            slenderness_ratio_lambda=(H - 2.0 * t) / t,
            compact_limit_lambda_p=0.0,
            noncompact_limit_lambda_r=0.0,
        )

        return FlexuralSectionProperties(
            section_kind="rectangular_HSS",
            symmetry="doubly_symmetric",
            overall_depth_d=H,
            gross_area_Ag=Ag,
            moment_of_inertia_Ix=Ix,
            elastic_modulus_Sx=Sx,
            plastic_modulus_Zx=Zx,
            radius_of_gyration_rx=rx,
            moment_of_inertia_Iy=Iy,
            elastic_modulus_Sy=Sy,
            plastic_modulus_Zy=Zy,
            radius_of_gyration_ry=ry,
            torsional_constant_J=J,
            # Closed section: warping ~ 0; §F7 LTB uses J & Ag, not Cw.
            warping_constant_Cw=0.0,
            # Carried so the §F7 calculator can rebuild the per-axis
            # flat-flange width for the slender-flange Se (Eq. F7-3..5).
            wall_thickness_t=t,
            plate_elements=(wall_b, wall_h),
        )


__all__ = ["RectangularHSS"]

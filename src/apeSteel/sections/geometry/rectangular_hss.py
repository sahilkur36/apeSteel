"""Plate-built rectangular / square HSS (box) geometry for AISC §E.

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

References
----------
.. [1] AISC 360-22 §E3, §E7.2, Table B4.1a Case 6 (HSS walls,
       1.40 sqrt(E/Fy)), Table E7.1 (HSS-wall c1/c2), pp. 16.1-37 -
       16.1-43.
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


__all__ = ["RectangularHSS"]

"""Round HSS / pipe geometry for AISC §E.

A round HSS is axisymmetric: only §E3 flexural buckling applies (no
§E4), and §E7.2(c) (Eq. E7-6 / E7-7) reduces the area directly from
``D/t`` - a provision **retained unchanged from 360-16**, so it
coincides with the workbook's ``Qa_3``.  The non-slender ``D/t`` limit
is Table B4.1a Case 9, ``0.11 E/Fy``.

Area / inertia are transcribed from the validated workbook ``HSS T``
sheet (``B38 .. B40``).

References
----------
.. [1] AISC 360-22 §E3, §E7.2(c) Eq. E7-6 / E7-7, Table B4.1a Case 9
       (round HSS, 0.11 E/Fy), pp. 16.1-37 - 16.1-43.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.sections.compression_properties import CompressionSectionProperties

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial


@dataclass(frozen=True, slots=True)
class RoundHSS:
    """Round HSS / pipe, all dims in mm.

    Parameters
    ----------
    outside_diameter_D : float
        Outside diameter.
    wall_thickness_t : float
        Wall thickness.
    """

    outside_diameter_D: float
    wall_thickness_t: float

    def compute_compression_properties(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
    ) -> CompressionSectionProperties:
        """Return the AISC 360-22 Chapter-E input snapshot for a round HSS."""
        D: float = self.outside_diameter_D
        t: float = self.wall_thickness_t
        Di: float = D - 2.0 * t

        # Workbook HSS T!B38 / B39.
        Ag: float = math.pi / 4.0 * (D**2 - Di**2)
        Idiam: float = math.pi / 64.0 * (D**4 - Di**4)  # I about any diameter
        r: float = math.sqrt(Idiam / Ag)
        # Closed circular torsion constant (= polar moment) for
        # completeness; round HSS skips §E4.
        J: float = math.pi / 32.0 * (D**4 - Di**4)

        return CompressionSectionProperties(
            section_kind="round_HSS",
            symmetry="doubly_symmetric",
            gross_area_Ag=Ag,
            radius_of_gyration_x_rx=r,
            radius_of_gyration_y_ry=r,
            moment_of_inertia_x_Ix=Idiam,
            moment_of_inertia_y_Iy=Idiam,
            torsional_constant_J=J,
            warping_constant_Cw=0.0,
            polar_radius_about_shear_centre_ro_bar=math.sqrt(2.0 * Idiam / Ag),
            flexural_constant_H=1.0,
            plate_elements=(),  # §E7.2(c) uses D/t directly
            diameter_D=D,
            wall_thickness_t=t,
        )


__all__ = ["RoundHSS"]

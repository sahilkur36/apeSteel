"""Plate-built single equal-leg angle geometry for AISC §E4 / §E5.

Restricted to **equal-leg** angles (the workbook's ``Angulo`` sheet
enforces ``B5 = B4``).  An equal-leg angle is singly-symmetric about
its major principal axis; the shear centre is at the heel.  Principal-
axis inertias are obtained from the geometric-axis inertias and the
product of inertia via the 45-degree Mohr's-circle rotation, exactly as
the workbook does (``E24 / E25 / E26``).

§E5 (single-angle modified ``Lc/r``) is the practical AISC method and
is edition-independent (no Q for the non-slender leg); pass an §E5 case
to the facade to use it.  Without a §E5 case the facade evaluates §E3
about the minor principal axis plus §E4 flexural-torsional.

Properties are transcribed verbatim from the validated workbook
``Angulo`` sheet (``E23 .. E41``), base-mm.

References
----------
.. [1] AISC 360-22 §E4 / §E5, pp. 16.1-39 - 16.1-41; Table B4.1a
       Case 3 (angle leg, 0.45 sqrt(E/Fy)).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.compression._common import B4_1A_UNSTIFFENED_ANGLE_LEG_COEFF
from apeSteel.sections.compression_properties import (
    CompressionPlateElement,
    CompressionSectionProperties,
)

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial


@dataclass(frozen=True, slots=True)
class SingleAngleSection:
    """Plate-built single **equal-leg** angle, dims in mm.

    Parameters
    ----------
    leg_length : float
        Length of each (equal) leg.
    thickness : float
        Leg thickness.
    """

    leg_length: float
    thickness: float

    def compute_compression_properties(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
    ) -> CompressionSectionProperties:
        """Return the AISC 360-22 Chapter-E input snapshot for the angle."""
        leg: float = self.leg_length
        t: float = self.thickness

        # Workbook Angulo!E23 (Ag), E27/E28 (centroid from the heel).
        Ag: float = leg * t + (leg - t) * t
        xbar: float = (leg * t * leg / 2.0 + (leg - t) * (t / 2.0) * t) / Ag
        ybar: float = (leg * t**2 / 2.0 + (leg - t) * t * ((leg - t) / 2.0 + t)) / Ag

        # Geometric-axis inertias about the centroid (workbook G23/G24).
        Ixg: float = (
            leg * t**3 / 12.0
            + leg * t * (ybar - t / 2.0) ** 2
            + t * (leg - t) ** 3 / 12.0
            + (leg - t) * t * (ybar - ((leg - t) / 2.0 + t)) ** 2
        )
        Iyg: float = (
            t * leg**3 / 12.0
            + t * leg * (leg / 2.0 - xbar) ** 2
            + (leg - t) * t**3 / 12.0
            + (leg - t) * t * (xbar - t / 2.0) ** 2
        )
        # Product of inertia about the centroid (workbook E26).
        Ixy: float = leg * t * (ybar - t / 2.0) * (leg / 2.0 - xbar) + (leg - t) * t * (
            ybar - ((leg - t) / 2.0 + t)
        ) * (t / 2.0 - xbar)

        # 45-degree principal rotation (equal-leg) - workbook E24/E25.
        avg: float = (Ixg + Iyg) / 2.0
        I_minor: float = avg - abs(Ixy)  # z principal (governs flexure)
        I_major: float = avg + abs(Ixy)  # w principal (axis of symmetry)

        rx: float = math.sqrt(I_minor / Ag)  # minor principal r (governs)
        ry: float = math.sqrt(I_major / Ag)

        # Shear centre at the heel; offset from centroid (workbook E33/E34).
        xo: float = xbar - t / 2.0
        yo: float = ybar - t / 2.0
        ro_bar2: float = xo**2 + yo**2 + (I_minor + I_major) / Ag
        ro_bar: float = math.sqrt(ro_bar2)
        flexural_constant_H: float = 1.0 - (xo**2 + yo**2) / ro_bar2

        # Open thin-walled torsion / warping (workbook E38/E41).
        J: float = 2.0 * (leg - t / 2.0) * t**3 / 3.0
        Cw: float = t**3 / 36.0 * (2.0 * (leg - t / 2.0) ** 3)

        sqrt_E_over_Fy: float = math.sqrt(material.elastic_modulus_E / material.yield_stress_Fy)
        leg_element = CompressionPlateElement(
            name="leg",
            kind="unstiffened",
            width_b=leg,
            thickness_t=t,
            slenderness_ratio_lambda=leg / t,
            nonslender_limit_lambda_r=B4_1A_UNSTIFFENED_ANGLE_LEG_COEFF * sqrt_E_over_Fy,
        )

        return CompressionSectionProperties(
            section_kind="single_angle",
            symmetry="singly_symmetric",
            gross_area_Ag=Ag,
            radius_of_gyration_x_rx=rx,
            radius_of_gyration_y_ry=ry,
            moment_of_inertia_x_Ix=I_minor,
            moment_of_inertia_y_Iy=I_major,
            torsional_constant_J=J,
            warping_constant_Cw=Cw,
            shear_centre_x_xo=xo,
            shear_centre_y_yo=yo,
            polar_radius_about_shear_centre_ro_bar=ro_bar,
            flexural_constant_H=flexural_constant_H,
            plate_elements=(leg_element,),
            min_principal_radius_of_gyration_rz=rx,
        )


__all__ = ["SingleAngleSection"]

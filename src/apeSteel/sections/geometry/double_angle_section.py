"""Plate-built double equal-leg angle geometry for AISC §E4 / §E6.

Two equal-leg angles, either back-to-back (legs touching, separated by
the gusset thickness) or with their backs apart by a fixed separation.
The built-up section is singly-symmetric about the axis through the gap
(here the *y*-axis), so ``xo = 0`` and ``yo != 0``; §E4 flexural-
torsional buckling applies, with the §E6 *modified* slenderness about
the built-up (y) axis when intermediate connectors can deform.

Doubled section properties are transcribed from the validated workbook
``Doble Angulo Espalda`` / ``Doble Angulo Cara`` sheets (the ``F``
column), base-mm.

References
----------
.. [1] AISC 360-22 §E4 / §E6, pp. 16.1-39 - 16.1-42; Table B4.1a
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
class DoubleAngleSection:
    """Two equal-leg angles, dims in mm.

    Parameters
    ----------
    leg_length : float
        Length of each (equal) leg of one component angle.
    thickness : float
        Leg thickness of one component angle.
    back_separation : float
        Distance between the two angle backs (gusset thickness for the
        back-to-back arrangement; the workbook ``B4``).
    """

    leg_length: float
    thickness: float
    back_separation: float

    def compute_compression_properties(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
    ) -> CompressionSectionProperties:
        """Return the AISC 360-22 Chapter-E input snapshot."""
        leg: float = self.leg_length
        t: float = self.thickness
        s: float = self.back_separation

        # One component angle (workbook E-column).
        Ag1: float = leg * t + (leg - t) * t
        xbar: float = (leg * t * leg / 2.0 + (leg - t) * (t / 2.0) * t) / Ag1
        ybar: float = (leg * t**2 / 2.0 + (leg - t) * t * ((leg - t) / 2.0 + t)) / Ag1
        Ixg: float = (
            leg * t**3 / 12.0
            + leg * t * (ybar - t / 2.0) ** 2
            + t * (leg - t) ** 3 / 12.0
            + (leg - t) * t * (ybar - ((leg - t) / 2.0 + t)) ** 2
        )
        Iyg1: float = (
            t * leg**3 / 12.0
            + t * leg * (leg / 2.0 - xbar) ** 2
            + (leg - t) * t**3 / 12.0
            + (leg - t) * t * (xbar - t / 2.0) ** 2
        )
        Ixy: float = leg * t * (ybar - t / 2.0) * (leg / 2.0 - xbar) + (leg - t) * t * (
            ybar - ((leg - t) / 2.0 + t)
        ) * (t / 2.0 - xbar)
        # Component minor principal I (for §E6 ri) - workbook E33.
        ri_I: float = (Ixg + Iyg1) / 2.0 - math.sqrt(((Ixg - Iyg1) / 2.0) ** 2 + Ixy**2)

        # Built-up (doubled) properties - workbook F-column.
        Ag: float = 2.0 * Ag1
        # Strong axis x (each angle bends about its own x; workbook F24).
        Ix: float = 2.0 * Ixg
        rx: float = math.sqrt(Ix / Ag)
        # Built-up weak axis y (back-to-back) - transcribed verbatim from
        # the validated workbook ``Doble Angulo Espalda`` F25: each angle
        # is split into its two legs and the parallel-axis terms use the
        # back-to-back layout distances (long leg at leg/2 + t, the
        # connected-leg remnant at t/2 + s/2 from the gap centreline).
        Iy: float = 2.0 * (
            t * leg**3 / 12.0
            + t * leg * (leg / 2.0 + t) ** 2
            + (leg - t) * t**3 / 12.0
            + (leg - t) * t * (t / 2.0 + s / 2.0) ** 2
        )
        ry: float = math.sqrt(Iy / Ag)

        # Shear centre on the y-axis (symmetry axis); offset in y only.
        xo: float = 0.0
        yo: float = ybar - t / 2.0
        ro_bar2: float = xo**2 + yo**2 + (Ix + Iy) / Ag
        ro_bar: float = math.sqrt(ro_bar2)
        flexural_constant_H: float = 1.0 - (xo**2 + yo**2) / ro_bar2

        J: float = 2.0 * (2.0 * (leg - t / 2.0) * t**3 / 3.0)  # 2 angles
        Cw: float = 2.0 * (t**3 / 36.0 * (2.0 * (leg - t / 2.0) ** 3))

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
            section_kind="double_angle",
            symmetry="singly_symmetric",
            gross_area_Ag=Ag,
            radius_of_gyration_x_rx=rx,
            radius_of_gyration_y_ry=ry,
            moment_of_inertia_x_Ix=Ix,
            moment_of_inertia_y_Iy=Iy,
            torsional_constant_J=J,
            warping_constant_Cw=Cw,
            shear_centre_x_xo=xo,
            shear_centre_y_yo=yo,
            polar_radius_about_shear_centre_ro_bar=ro_bar,
            flexural_constant_H=flexural_constant_H,
            plate_elements=(leg_element,),
            min_principal_radius_of_gyration_rz=rx,
            component_min_radius_of_gyration_ri=math.sqrt(ri_I / Ag1),
        )


__all__ = ["DoubleAngleSection"]

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
from apeSteel.sections.flexural_properties import FlexuralSectionProperties

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

    def compute_section_properties(self) -> FlexuralSectionProperties:
        """Return the AISC 360-22 Chapter-F (§F10) input snapshot.

        Produces a ``section_kind="single_angle"``
        :class:`FlexuralSectionProperties` carrying the principal-axis
        constants (``Iw`` major / ``Iz`` minor / ``rz`` min radius), the
        ``equal_leg`` flag, the **geometric**-axis ``Sx``/``Zx`` (the
        ``x`` axis parallel to a leg, used by the §F10 geometric-axis
        option per the §F10 User Note), and the single leg ``b/t`` for
        the §F10.3 leg-local-buckling classification.

        The geometry primitives reused here - ``leg``, ``t``, ``Ag``,
        ``xbar``/``ybar``, ``Ixg``/``Iyg``/``Ixy`` and the 45-degree
        principal rotation (``I_minor`` = ``Iz``, ``I_major`` = ``Iw``)
        - are written **byte-identically** to
        :meth:`compute_compression_properties` (workbook ``Angulo``
        sheet ``E23 .. E41``), so the §F10 flexure path and the §E4/§E5
        compression path provably share the same section math.  A test
        asserts the shared quantities are ``==`` (not just close).
        :meth:`compute_compression_properties` is **not** modified.

        Returns
        -------
        FlexuralSectionProperties
            ``single_angle`` snapshot in base mm units. ``equal_leg`` is
            always ``True`` (this class is restricted to equal-leg
            angles); ``geometric_axis_bending`` is left ``False`` (the
            default) - whether the angle is *designed* on geometric or
            principal axes is the §F10 calculator's input, not the
            geometry's.

        Notes
        -----
        §F10-1 yielding is ``Mn = 1.5*My`` with ``My`` formed from the
        **section modulus** (geometric ``Sx`` or a principal ``S``), not
        from a plastic modulus, so ``Zx``/``Zy`` are carried only for
        the :class:`FlexuralSectionProperties` contract; the §F10
        calculator never reads them.
        """
        # --- byte-identical block with compute_compression_properties --
        # (workbook Angulo!E23/E26/E27/E28, G23/G24).  Kept character-
        # for-character the same so the §E and §F section math cannot
        # silently diverge (asserted == in the golden suite).
        leg: float = self.leg_length
        t: float = self.thickness

        Ag: float = leg * t + (leg - t) * t
        xbar: float = (leg * t * leg / 2.0 + (leg - t) * (t / 2.0) * t) / Ag
        ybar: float = (leg * t**2 / 2.0 + (leg - t) * t * ((leg - t) / 2.0 + t)) / Ag

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
        Ixy: float = leg * t * (ybar - t / 2.0) * (leg / 2.0 - xbar) + (leg - t) * t * (
            ybar - ((leg - t) / 2.0 + t)
        ) * (t / 2.0 - xbar)

        avg: float = (Ixg + Iyg) / 2.0
        I_minor: float = avg - abs(Ixy)  # z principal (Iz; governs LTB)
        I_major: float = avg + abs(Ixy)  # w principal (axis of symmetry)
        # --- end byte-identical block ---------------------------------

        rz: float = math.sqrt(I_minor / Ag)  # minimum (minor principal) r

        # Geometric (x, y) axis section moduli.  An equal-leg angle is
        # geometrically symmetric in (Ixg == Iyg, xbar == ybar); the
        # extreme fibre about the geometric x-axis is the *toe* at a
        # distance (leg - ybar) from the centroid (the toe is farther
        # than the heel, ybar, for an equal-leg L).  Sx/Sy are the
        # elastic moduli to that extreme fibre.
        c_toe_x: float = leg - ybar
        c_toe_y: float = leg - xbar
        Sx_geom: float = Ixg / c_toe_x
        Sy_geom: float = Iyg / c_toe_y

        # Geometric-axis plastic modulus (carried for the
        # FlexuralSectionProperties contract only; §F10 yielding is
        # 1.5*My, S-based, and never reads Zx/Zy).  Equal-leg L modelled
        # as two rectangles - the heel block (width = leg over the height
        # band y in [0, t]) and the upstanding leg (width = t over
        # y in [t, leg]); the same idealization compute_compression_
        # properties uses for Ag.  The plastic NA about the geometric
        # x-axis bisects Ag; for an equal-leg L it lies in the heel band
        # (y_p <= t) at y_p = t*(2*leg - t)/(2*leg).  Zx is the sum of
        # the first moments of the equal half-areas about that NA.
        y_p: float = t * (2.0 * leg - t) / (2.0 * leg)
        area_heel_above: float = leg * (t - y_p)  # y in (y_p, t], width leg
        area_upstand: float = t * (leg - t)  # y in (t, leg], width t
        area_heel_below: float = leg * y_p  # y in [0, y_p], width leg
        Zx_geom: float = (
            area_heel_above * ((y_p + t) / 2.0 - y_p)
            + area_upstand * ((t + leg) / 2.0 - y_p)
            + area_heel_below * (y_p / 2.0)
        )
        Zy_geom: float = Zx_geom  # equal-leg symmetry

        rx_geom: float = math.sqrt(Ixg / Ag)
        ry_geom: float = math.sqrt(Iyg / Ag)

        return FlexuralSectionProperties(
            section_kind="single_angle",
            symmetry="singly_symmetric",
            overall_depth_d=leg,
            gross_area_Ag=Ag,
            moment_of_inertia_Ix=Ixg,
            elastic_modulus_Sx=Sx_geom,
            plastic_modulus_Zx=Zx_geom,
            radius_of_gyration_rx=rx_geom,
            moment_of_inertia_Iy=Iyg,
            elastic_modulus_Sy=Sy_geom,
            plastic_modulus_Zy=Zy_geom,
            radius_of_gyration_ry=ry_geom,
            principal_I_major_Iw=I_major,
            principal_I_minor_Iz=I_minor,
            min_principal_radius_rz=rz,
            equal_leg=True,
            geometric_axis_bending=False,
            plate_elements=(),
        )


__all__ = ["SingleAngleSection"]

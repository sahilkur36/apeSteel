"""Plate-built channel (C-shape) geometry for AISC §E4.

A channel is singly-symmetric about the horizontal axis through
mid-height (here the *x*-axis: equal top and bottom flanges).  The
shear centre lies on that axis, offset horizontally from the centroid
(outside the web), so ``yo = 0`` and ``xo != 0``; §E4 flexural-
torsional buckling (Eq. E4-3) couples flexure about the symmetry axis
``x`` with torsion (Eq. E4-7 ``Fez``).

Section properties (area, ``Ix``, ``Iy``, shear-centre offset ``xo``,
the channel-specific warping constant ``Cw`` and torsion constant
``J``) are transcribed verbatim from the validated
``...Compresion - V2.0.xlsm`` ``Canal`` sheet (``B49 .. B64``), in
apeSteel ``N-mm-tonne-s`` base (the workbook ``/10^n`` cm conversions
dropped).

References
----------
.. [1] AISC 360-22 §E4, Eq. E4-3 / E4-7 / E4-8 / E4-9, pp. 16.1-39 -
       16.1-40; Table B4.1a Cases 1 (channel flange) and 5 (channel
       web), pp. 16.1-13 - 16.1-14.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.compression._common import (
    B4_1A_STIFFENED_WEB_COEFF,
    B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF,
)
from apeSteel.sections.compression_properties import (
    CompressionPlateElement,
    CompressionSectionProperties,
)

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial


@dataclass(frozen=True, slots=True)
class ChannelSection:
    """Plate-built channel (two equal flanges + one web), dims in mm.

    Parameters
    ----------
    flange_width_bf : float
        Flange width (the projecting leg measured from the web face).
    flange_thickness_tf : float
        Flange thickness.
    overall_depth_d : float
        Overall depth (web height + 2 * flange thickness).
    web_thickness_tw : float
        Web thickness.
    """

    flange_width_bf: float
    flange_thickness_tf: float
    overall_depth_d: float
    web_thickness_tw: float

    def compute_compression_properties(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
    ) -> CompressionSectionProperties:
        """Return the AISC 360-22 Chapter-E input snapshot for a channel."""
        bf: float = self.flange_width_bf
        tf: float = self.flange_thickness_tf
        d: float = self.overall_depth_d
        tw: float = self.web_thickness_tw
        clear_web: float = d - 2.0 * tf

        Ag: float = bf * tf * 2.0 + clear_web * tw

        # Strong / symmetry axis x (horizontal) - workbook Canal!B50.
        Ix: float = (bf * tf**3 / 12.0 + bf * tf * ((d / 2.0) - (tf / 2.0)) ** 2) * 2.0 + (
            tw * clear_web**3 / 12.0
        )
        rx: float = math.sqrt(Ix / Ag)

        # Centroid x from the back of the web - workbook B52.
        xbar: float = (bf * tf * (bf / 2.0) * 2.0 + clear_web * tw * (tw / 2.0)) / Ag

        # Channel torsion helper terms - workbook B60/B61/B62.
        b60: float = d - tf
        b61: float = bf - tw / 2.0
        b62: float = 1.0 / (2.0 + (d - tf) * tw / (3.0 * (bf - tw / 2.0) * tf))

        # Shear-centre x-offset from the centroid - workbook B53.
        xo: float = xbar + b61 * b62 - tw / 2.0
        yo: float = 0.0

        # Weak axis y (vertical) - workbook B57.
        Iy: float = (
            (tf * bf**3 / 12.0 + bf * tf * (bf / 2.0 - xbar) ** 2) * 2.0
            + clear_web * tw**3 / 12.0
            + clear_web * tw * (xbar - tw / 2.0) ** 2
        )
        ry: float = math.sqrt(Iy / Ag)

        # Channel warping & torsion constants - workbook B63 / B64.
        Cw: float = (
            b60**2
            * b61**3
            * tf
            * ((1.0 - 3.0 * b62) / 6.0 + b62**2 / 2.0 * (1.0 + b60 * tw / (6.0 * b61 * tf)))
        )
        J: float = (2.0 * (bf - tw / 2.0) * tf**3 + (d - tf) * tw**3) / 3.0

        ro_bar2: float = xo**2 + yo**2 + (Ix + Iy) / Ag
        ro_bar: float = math.sqrt(ro_bar2)
        flexural_constant_H: float = 1.0 - (xo**2 + yo**2) / ro_bar2

        sqrt_E_over_Fy: float = math.sqrt(material.elastic_modulus_E / material.yield_stress_Fy)
        flange = CompressionPlateElement(
            name="flange",
            kind="unstiffened",
            width_b=bf,
            thickness_t=tf,
            slenderness_ratio_lambda=bf / tf,
            nonslender_limit_lambda_r=B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF * sqrt_E_over_Fy,
        )
        web = CompressionPlateElement(
            name="web",
            kind="stiffened",
            width_b=clear_web,
            thickness_t=tw,
            slenderness_ratio_lambda=clear_web / tw,
            nonslender_limit_lambda_r=B4_1A_STIFFENED_WEB_COEFF * sqrt_E_over_Fy,
        )

        return CompressionSectionProperties(
            section_kind="channel",
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
            plate_elements=(flange, web),
        )


__all__ = ["ChannelSection"]

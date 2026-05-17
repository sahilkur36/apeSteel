"""Plate-built structural-tee (split-tee) geometry for AISC §E4.

A tee is singly-symmetric about the vertical axis through the stem
(here labelled the *y*-axis).  The shear centre lies on that axis at
the mid-thickness of the flange, so ``xo = 0`` and ``yo != 0``; §E4
flexural-torsional buckling (Eq. E4-3) couples flexure about the
symmetry axis ``y`` with torsion (Eq. E4-7 ``Fez``).

The closed-form section properties are transcribed verbatim from the
engineer's validated ``...Compresion - V2.0.xlsm`` ``T`` sheet (the
``B45 .. B58`` block), expressed in apeSteel's ``N-mm-tonne-s`` base
(the workbook's ``/10^n`` cm conversions are dropped).

References
----------
.. [1] AISC 360-22 §E4, Eq. E4-3 / E4-7 / E4-8 / E4-9, pp. 16.1-39 -
       16.1-40; Table B4.1a Cases 1 (tee flange) and 4 (tee stem),
       p. 16.1-13.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.compression._common import (
    B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF,
    B4_1A_UNSTIFFENED_TEE_STEM_COEFF,
)
from apeSteel.sections.compression_properties import (
    CompressionPlateElement,
    CompressionSectionProperties,
)

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial


@dataclass(frozen=True, slots=True)
class TeeSection:
    """Plate-built structural tee (flange + stem), all dims in mm.

    Parameters
    ----------
    flange_width_bf : float
        Flange width.
    flange_thickness_tf : float
        Flange thickness.
    overall_depth_d : float
        Overall depth (flange thickness + stem height).
    stem_thickness_tw : float
        Stem (web) thickness.
    """

    flange_width_bf: float
    flange_thickness_tf: float
    overall_depth_d: float
    stem_thickness_tw: float

    def compute_compression_properties(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
    ) -> CompressionSectionProperties:
        """Return the AISC 360-22 Chapter-E input snapshot for a tee."""
        bf: float = self.flange_width_bf
        tf: float = self.flange_thickness_tf
        d: float = self.overall_depth_d
        tw: float = self.stem_thickness_tw
        stem: float = d - tf

        Ag: float = bf * tf + stem * tw
        # Centroid from the top (outer flange) fibre (workbook T!B46).
        ybar: float = tf / 2.0 + stem * d * tw / (2.0 * Ag)

        # Strong axis x (horizontal, through the flange) - workbook B48.
        Ix: float = (
            bf * tf**3 / 12.0
            + bf * tf * (ybar - tf / 2.0) ** 2
            + tw * stem**3 / 12.0
            + tw * stem * (stem / 2.0 + tf - ybar) ** 2
        )
        rx: float = math.sqrt(Ix / Ag)

        # Weak / symmetry axis y (vertical) - workbook B50.
        Iy: float = (tf * bf**3 + d * tw**3) / 12.0
        ry: float = math.sqrt(Iy / Ag)

        # Warping and torsion constants - workbook B53 / B54.
        Cw: float = (tf**3 * bf**3 / 4.0 + tw**3 * (stem + tf / 2.0) ** 3) / 36.0
        J: float = (bf * tf**3 + (stem + tf / 2.0) * tw**3) / 3.0

        # Shear centre on the y-axis at flange mid-thickness (B55/B56).
        xo: float = 0.0
        yo: float = ybar - tf / 2.0
        ro_bar2: float = xo**2 + yo**2 + (Ix + Iy) / Ag
        ro_bar: float = math.sqrt(ro_bar2)
        flexural_constant_H: float = 1.0 - (xo**2 + yo**2) / ro_bar2

        sqrt_E_over_Fy: float = math.sqrt(material.elastic_modulus_E / material.yield_stress_Fy)
        flange = CompressionPlateElement(
            name="flange",
            kind="unstiffened",
            width_b=bf / 2.0,
            thickness_t=tf,
            slenderness_ratio_lambda=(bf / 2.0) / tf,
            nonslender_limit_lambda_r=B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF * sqrt_E_over_Fy,
        )
        stem_element = CompressionPlateElement(
            name="stem",
            kind="unstiffened",
            width_b=d,
            thickness_t=tw,
            slenderness_ratio_lambda=d / tw,
            nonslender_limit_lambda_r=B4_1A_UNSTIFFENED_TEE_STEM_COEFF * sqrt_E_over_Fy,
        )

        return CompressionSectionProperties(
            section_kind="tee",
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
            plate_elements=(flange, stem_element),
        )


__all__ = ["TeeSection"]

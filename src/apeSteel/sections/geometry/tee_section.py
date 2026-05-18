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
from apeSteel.sections.flexural_properties import FlexuralSectionProperties

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

    def compute_section_properties(self) -> FlexuralSectionProperties:
        """Return the AISC 360-22 §F9 flexural input snapshot for a tee.

        The gross-section closed forms (``Ag``, ``Ix``, ``Iy``, ``J``,
        and the centroid ``ybar``) are written **byte-identically** to
        :meth:`compute_compression_properties` (the same workbook ``T``
        sheet expressions), so the flexure path provably cannot perturb
        the verified §E numbers; this method only *adds* the section
        moduli §F9 needs (compression never required ``Sx`` / ``Zx`` /
        the extreme-fibre moduli):

        * elastic modulus to the **flange (outer) fibre**
          ``Sxc = Ix / ybar`` - the §F9 ``Sxc`` (the flange is the
          compression element for the usual WT loaded with the stem in
          tension; §F9.3 Eq. F9-14/F9-15 read ``Sxc``);
        * elastic modulus to the **stem-tip fibre**
          ``Sxt = Ix / (d - ybar)``;
        * the governing strong-axis elastic modulus
          ``Sx = min(Sxc, Sxt) = Ix / max(ybar, d - ybar)`` (Eq. F9-3
          ``My = Fy*Sx`` uses the modulus to the extreme fibre - the
          stem tip for a tee, so ``Sx`` is the smaller of the two);
        * the plastic section modulus about ``x``,
          ``Zx``.  The plastic neutral axis (PNA) splits the gross area
          in half.  For a tee the half-area ``Ag/2`` is reached either
          inside the flange (``Ag/2 <= bf*tf``) or inside the stem; the
          PNA depth ``yp`` from the outer flange fibre and the first
          moment of each half about the PNA give
          ``Zx = sum |A_i| * |d_i|`` (Boresi/Young plastic-modulus
          construction; the standard composite-rectangle plastic
          modulus).

        ``Iy`` and ``J`` (§F9 LTB Eq. F9-9/F9-10/F9-11 ``B`` factor) and
        ``d`` are carried straight from the shared forms.  ``ho``
        (distance between the flange centroid and the stem-tip; used for
        trace) is ``d - tf/2``.  The Table B4.1b flange (Case 10) and
        §F9.4 stem elements are attached later by the
        ``classification`` layer (the geometry layer never imports it),
        so ``plate_elements`` is empty here.

        Returns
        -------
        FlexuralSectionProperties
            ``section_kind="tee"``, singly-symmetric, in base units.
        """
        bf: float = self.flange_width_bf
        tf: float = self.flange_thickness_tf
        d: float = self.overall_depth_d
        tw: float = self.stem_thickness_tw
        stem: float = d - tf

        # --- Byte-identical with compute_compression_properties ---
        # (workbook T!B45.., transcribed verbatim - the geometry tests
        # assert these coincide exactly with the frozen §E snapshot).
        Ag: float = bf * tf + stem * tw
        ybar: float = tf / 2.0 + stem * d * tw / (2.0 * Ag)
        Ix: float = (
            bf * tf**3 / 12.0
            + bf * tf * (ybar - tf / 2.0) ** 2
            + tw * stem**3 / 12.0
            + tw * stem * (stem / 2.0 + tf - ybar) ** 2
        )
        rx: float = math.sqrt(Ix / Ag)
        Iy: float = (tf * bf**3 + d * tw**3) / 12.0
        ry: float = math.sqrt(Iy / Ag)
        J: float = (bf * tf**3 + (stem + tf / 2.0) * tw**3) / 3.0

        # --- Flexure-only additions (not needed by compression) ---
        # Extreme-fibre elastic moduli (§F9.3 needs Sxc; Eq. F9-3 My
        # uses the modulus to the extreme fibre = the smaller of the
        # two).  ``ybar`` is measured from the outer flange fibre.
        depth_to_flange_fibre: float = ybar
        depth_to_stem_tip: float = d - ybar
        Sxc: float = Ix / depth_to_flange_fibre  # to flange (compression)
        Sxt: float = Ix / depth_to_stem_tip  # to stem tip (tension)
        Sx: float = Ix / max(depth_to_flange_fibre, depth_to_stem_tip)

        # Plastic modulus about x.  PNA splits Ag in half; locate it,
        # then Zx = sum over the (two) halves of |A_half| * |centroid
        # of half -> PNA|.  ``yp`` is the PNA depth from the outer
        # flange fibre.
        half_area: float = Ag / 2.0
        flange_area: float = bf * tf
        if half_area <= flange_area:
            # PNA inside the flange.
            yp: float = half_area / bf
            # Compression block: flange strip [0, yp].
            a_top: float = bf * yp
            y_top_centroid: float = yp / 2.0
            # Tension block: flange remainder [yp, tf] + full stem.
            a_flange_rem: float = bf * (tf - yp)
            a_stem: float = stem * tw
            # First moment of the tension block about the PNA.
            q_bot: float = a_flange_rem * ((tf - yp) / 2.0) + a_stem * ((tf - yp) + stem / 2.0)
            q_top: float = a_top * y_top_centroid
            Zx: float = q_top + q_bot
        else:
            # PNA inside the stem (depth yp from the outer flange fibre).
            yp = tf + (half_area - flange_area) / tw
            # Compression block: full flange + stem strip [tf, yp].
            a_flange: float = bf * tf
            a_stem_top: float = tw * (yp - tf)
            q_top = a_flange * (yp - tf / 2.0) + a_stem_top * ((yp - tf) / 2.0)
            # Tension block: stem strip [yp, d].
            a_stem_bot: float = tw * (d - yp)
            q_bot = a_stem_bot * ((d - yp) / 2.0)
            Zx = q_top + q_bot

        # ho - distance flange-centroid -> stem tip (trace only).
        ho: float = d - tf / 2.0

        return FlexuralSectionProperties(
            section_kind="tee",
            symmetry="singly_symmetric",
            overall_depth_d=d,
            gross_area_Ag=Ag,
            moment_of_inertia_Ix=Ix,
            elastic_modulus_Sx=Sx,
            plastic_modulus_Zx=Zx,
            radius_of_gyration_rx=rx,
            moment_of_inertia_Iy=Iy,
            # A tee has no minor-axis flexural design path in §F9 (it is
            # loaded in the plane of symmetry); carry consistent
            # weak-axis values for trace.
            elastic_modulus_Sy=Iy / (bf / 2.0),
            plastic_modulus_Zy=tf * bf**2 / 4.0 + stem * tw**2 / 4.0,
            radius_of_gyration_ry=ry,
            torsional_constant_J=J,
            distance_between_flange_centroids_ho=ho,
            elastic_modulus_compression_flange_Sxc=Sxc,
            elastic_modulus_tension_flange_Sxt=Sxt,
            plate_elements=(),
        )


__all__ = ["TeeSection"]

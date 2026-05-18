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
from apeSteel.sections.flexural_properties import FlexuralSectionProperties

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial

#: AISC 360-22 Eq. F2-8b channel section-constant ``ho`` divisor:
#: ``c = (ho / 2) * sqrt(Iy / Cw)`` (spec_chapterF.txt printed 16.1-54).
#: Named (rather than the bare literal ``2.0``) so the Eq. F2-8b
#: provenance is traceable at the call site, mirroring the
#: ``flexural_properties._EQ_F2_8B_HO_DIVISOR`` style.
_EQ_F2_8B_HO_DIVISOR: float = 2.0


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

    def compute_section_properties(self) -> FlexuralSectionProperties:
        """Return the AISC 360-22 Chapter-F flexural input snapshot.

        A channel bent about its **major** (geometric ``x``) axis is the
        §F2 case (Eq. F2-8b ``c``); bent about its **minor** (``y``)
        axis it is the §F6 case with ``b`` = the **full** nominal flange
        width (AISC 360-22 §F6.2 spec note: ``b`` = ``bf/2`` for an
        I-shape flange but the **full flange width** for a channel).

        The gross-section closed forms (``Ag``, ``Ix``, ``Iy``, ``J``,
        ``Cw``, the back-of-web centroid ``xbar``) are written
        **byte-identically** to :meth:`compute_compression_properties`
        (the same workbook ``Canal``-sheet expressions) so the flexure
        path provably cannot perturb the verified §E numbers; this
        method only *adds* the section moduli §F2 / §F6 need (compression
        never required ``Sx`` / ``Zx`` / ``Sy`` / ``Zy`` / ``rts`` /
        ``ho`` / the Eq. F2-8b ``c``):

        * strong-axis elastic modulus ``Sx = Ix / (d/2)`` (the channel
          is symmetric about ``x``; the extreme fibre is at ``d/2``);
        * strong-axis plastic modulus ``Zx`` - PNA at mid-depth by
          symmetry: ``Zx = 2*bf*tf*((d - tf)/2) + tw*hw^2/4``;
        * minor-axis elastic modulus ``Sy = Iy / xbar`` - the extreme
          fibre about the minor axis is the **back of the web** at
          distance ``xbar`` from the centroid (the farther of the two
          minor-axis extreme fibres: web back ``xbar`` vs flange tip
          ``bf - xbar``; for a channel ``xbar < bf/2`` so the web back
          governs, mirroring the AISC v16 published ``Sy``);
        * minor-axis plastic modulus ``Zy`` (composite-rectangle
          construction; the §F6 channel limit state is FLB on the full
          flange width, so ``Zy`` only feeds the Eq. F6-1 ``Fy*Zy``
          plateau and its ``1.6*Fy*Sy`` cap);
        * ``ho = d - tf`` - the distance between flange centroids
          (Eq. F2-6 / the Eq. F2-8b ``ho``);
        * ``rts`` per Eq. F2-7 ``rts^2 = sqrt(Iy*Cw)/Sx``;
        * the Eq. **F2-8b** section constant
          ``c = (ho/2)*sqrt(Iy/Cw)`` (channels; ``!= 1`` - contrast
          Eq. F2-8a ``c = 1`` for a doubly-symmetric I).  Carrying ``c``
          natively lets the §F2 channel-major path read it straight off
          the snapshot, exactly as
          :meth:`FlexuralSectionProperties.from_legacy` derives it for
          the legacy-currency channel path (the F-1 anchor
          ``test_chapterF_F1_additions`` pins both to the same closed
          form).

        The §F2 / §F6 flange-FLB Table B4.1b classification is attached
        later by the ``classification`` layer (``classify_flexural_
        compactness(section_kind="channel", ...)``), which sits *above*
        ``sections`` (the geometry layer never imports it), so
        ``plate_elements`` is empty here.

        Returns
        -------
        FlexuralSectionProperties
            ``section_kind="channel"``, singly-symmetric, base units.
        """
        bf: float = self.flange_width_bf
        tf: float = self.flange_thickness_tf
        d: float = self.overall_depth_d
        tw: float = self.web_thickness_tw
        clear_web: float = d - 2.0 * tf

        # --- Byte-identical with compute_compression_properties --------
        # (workbook Canal!B49.., transcribed verbatim; the geometry
        # tests assert these coincide exactly with the frozen §E
        # snapshot - the §F flexure path cannot perturb a §E number).
        Ag: float = bf * tf * 2.0 + clear_web * tw
        Ix: float = (bf * tf**3 / 12.0 + bf * tf * ((d / 2.0) - (tf / 2.0)) ** 2) * 2.0 + (
            tw * clear_web**3 / 12.0
        )
        rx: float = math.sqrt(Ix / Ag)
        xbar: float = (bf * tf * (bf / 2.0) * 2.0 + clear_web * tw * (tw / 2.0)) / Ag
        Iy: float = (
            (tf * bf**3 / 12.0 + bf * tf * (bf / 2.0 - xbar) ** 2) * 2.0
            + clear_web * tw**3 / 12.0
            + clear_web * tw * (xbar - tw / 2.0) ** 2
        )
        ry: float = math.sqrt(Iy / Ag)
        b60: float = d - tf  # distance between flange centroids = ho
        b61: float = bf - tw / 2.0
        b62: float = 1.0 / (2.0 + (d - tf) * tw / (3.0 * (bf - tw / 2.0) * tf))
        Cw: float = (
            b60**2
            * b61**3
            * tf
            * ((1.0 - 3.0 * b62) / 6.0 + b62**2 / 2.0 * (1.0 + b60 * tw / (6.0 * b61 * tf)))
        )
        J: float = (2.0 * (bf - tw / 2.0) * tf**3 + (d - tf) * tw**3) / 3.0

        # --- Flexure-only additions (not needed by compression) -------
        # §F2 major-axis: Sx / Zx about the (symmetry) x-axis.
        Sx: float = Ix / (d / 2.0)
        Zx: float = 2.0 * (bf * tf * ((d - tf) / 2.0)) + tw * clear_web**2 / 4.0
        # §F6 minor-axis: Sy = Iy / (distance to the extreme fibre).
        # ``xbar`` is the centroid distance from the web back face; the
        # two minor-axis extreme fibres are the web back (distance
        # ``xbar``) and the flange toe (distance ``bf - xbar``).  The
        # governing (smallest, conservative) elastic modulus uses the
        # *larger* fibre distance - the AISC channel ``Sy`` convention
        # (the flange toe governs for ordinary channel proportions).
        Sy: float = Iy / max(xbar, bf - xbar)
        ho: float = b60
        rts: float = math.sqrt(math.sqrt(Iy * Cw) / Sx)
        # Eq. F2-8b channel section constant.
        section_constant_c: float = (ho / _EQ_F2_8B_HO_DIVISOR) * math.sqrt(Iy / Cw)

        # Minor-axis plastic modulus Zy (composite-rectangle).  Measure
        # x from the back of the web (x = 0 at the web outer face).  The
        # area-per-unit-x profile of a channel is:
        #   * x in [0, tw]:  web (height = clear_web) + the two flange
        #     roots (combined height 2*tf)  ->  density c1 = clear_web
        #     + 2*tf;
        #   * x in [tw, bf]: only the two flanges  ->  density
        #     c2 = 2*tf.
        # The minor-axis plastic NA is the vertical line x = xp that
        # bisects Ag; Zy = sum over the two halves of |A_i| * |xbar_i
        # - xp|.  (The §F6 channel limit states are yielding -
        # Fy*Zy <= 1.6*Fy*Sy - and flange FLB on the full flange width,
        # so Zy feeds only the Eq. F6-1 plateau; the C/MC *catalog*
        # path uses the AISC-published Zy directly.)
        half_area: float = Ag / 2.0
        density_web_band_c1: float = clear_web + 2.0 * tf  # x in [0, tw]
        density_flange_band_c2: float = 2.0 * tf  # x in [tw, bf]
        area_web_band: float = density_web_band_c1 * tw
        if half_area <= area_web_band:
            # PNA inside the web band [0, tw].
            xp: float = half_area / density_web_band_c1
            # Left half: [0, xp].
            q_left: float = (density_web_band_c1 * xp) * (xp / 2.0)
            # Right half: web-band remainder [xp, tw] + flange band
            # [tw, bf].
            a_web_rem: float = density_web_band_c1 * (tw - xp)
            a_flange_band: float = density_flange_band_c2 * (bf - tw)
            q_right: float = a_web_rem * abs((xp + tw) / 2.0 - xp) + a_flange_band * abs(
                (tw + bf) / 2.0 - xp
            )
            Zy: float = q_left + q_right
        else:
            # PNA inside the flange band [tw, bf].
            xp = tw + (half_area - area_web_band) / density_flange_band_c2
            # Left half: full web band [0, tw] + flange-band [tw, xp].
            a_full_web_band: float = density_web_band_c1 * tw
            a_flange_left: float = density_flange_band_c2 * (xp - tw)
            q_left = a_full_web_band * abs(tw / 2.0 - xp) + a_flange_left * abs(
                (tw + xp) / 2.0 - xp
            )
            # Right half: flange-band [xp, bf].
            a_flange_right: float = density_flange_band_c2 * (bf - xp)
            q_right = a_flange_right * abs((xp + bf) / 2.0 - xp)
            Zy = q_left + q_right

        return FlexuralSectionProperties(
            section_kind="channel",
            symmetry="singly_symmetric",
            overall_depth_d=d,
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
            warping_constant_Cw=Cw,
            distance_between_flange_centroids_ho=ho,
            effective_radius_of_gyration_for_LTB_rts=rts,
            section_constant_c=section_constant_c,
            plate_elements=(),
        )


__all__ = ["ChannelSection"]

"""Plate-built doubly-symmetric I-section geometry.

A :class:`DoublySymmetricISection` is the immutable plate-dimension
description of a welded built-up I (two identical flanges + one
centred web). It knows nothing about material properties or unbraced
lengths -- those live elsewhere in the composition spine.

The single public method :meth:`compute_section_properties` returns a
:class:`~apeSteel.sections.properties.SectionProperties` frozen
dataclass containing all the integrated quantities that the rest of
apeSteel needs (``Ag``, ``Ix``, ``Sx``, ``Zx``, ``Iy``, ``Sy``, ``Zy``,
``rx``, ``ry``, ``J``, ``Cw``, ``ho``, ``rts``, the plate slenderness
ratios, and the connection-relevant ``bf``, ``tf``, ``kdes``, ``kdet``,
``k1``).

The closed-form formulas reproduce cells ``B39`` - ``B56`` of the
original ``Vigas - Seccion I - Diseno LTB.xlsx`` spreadsheet exactly,
ported into a single canonical unit system (``N-mm-tonne-s``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification._common import compute_kc_for_built_up_flange
from apeSteel.compression._common import (
    B4_1A_STIFFENED_WEB_COEFF,
    B4_1A_UNSTIFFENED_BUILTUP_FLANGE_COEFF,
    B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF,
)
from apeSteel.core.materials import CARBON_STEEL_DENSITY_rho
from apeSteel.core.units import g as gravitational_acceleration_g
from apeSteel.sections.compression_properties import (
    CompressionPlateElement,
    CompressionSectionProperties,
)
from apeSteel.sections.properties import SectionProperties

if TYPE_CHECKING:
    from apeSteel.bracing import Bracing
    from apeSteel.classification import SectionConstruction, SeismicCodeEdition
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.element import Element


@dataclass(frozen=True, slots=True)
class DoublySymmetricISection:
    """Plate-built doubly-symmetric I-section.

    The four plate dimensions describe a welded I made of three plates:
    two identical flanges and one centred web. All values are in
    ``N-mm-tonne-s`` base units (mm).
    """

    flange_width_bf: float
    flange_thickness_tf: float
    web_clear_height_hw: float
    web_thickness_tw: float

    def compute_section_properties(self) -> SectionProperties:
        """Return the integrated section properties."""
        bf: float = self.flange_width_bf
        tf: float = self.flange_thickness_tf
        hw: float = self.web_clear_height_hw
        tw: float = self.web_thickness_tw

        d: float = hw + 2.0 * tf
        ho: float = hw + tf

        flange_pair_area: float = 2.0 * bf * tf
        web_area: float = hw * tw
        Ag: float = flange_pair_area + web_area

        nominal_weight_per_unit_length_w: float = (
            CARBON_STEEL_DENSITY_rho * gravitational_acceleration_g * Ag
        )

        flange_self_inertia_Ix: float = bf * tf**3 / 12.0
        flange_offset: float = ho / 2.0
        Ix: float = 2.0 * (flange_self_inertia_Ix + bf * tf * flange_offset**2) + tw * hw**3 / 12.0
        Sx: float = Ix / (d / 2.0)
        Zx: float = bf * tf * ho + tw * hw**2 / 4.0
        rx: float = math.sqrt(Ix / Ag)

        Iy: float = 2.0 * (tf * bf**3 / 12.0) + hw * tw**3 / 12.0
        Sy: float = Iy / (bf / 2.0)
        Zy: float = tf * bf**2 / 2.0 + hw * tw**2 / 4.0
        ry: float = math.sqrt(Iy / Ag)

        # AISC Design Guide 9 closed forms for welded I.
        J: float = (2.0 * bf * tf**3 + ho * tw**3) / 3.0
        Cw: float = ho**2 * bf**3 * tf / 24.0
        rts: float = math.sqrt(math.sqrt(Iy * Cw) / Sx)

        flange_width_to_thickness_ratio_bf_2tf: float = bf / (2.0 * tf)
        web_height_to_thickness_ratio_h_tw: float = hw / tw

        return SectionProperties(
            overall_depth_d=d,
            gross_area_Ag=Ag,
            nominal_weight_per_unit_length_w=nominal_weight_per_unit_length_w,
            moment_of_inertia_strong_axis_Ix=Ix,
            elastic_section_modulus_strong_axis_Sx=Sx,
            plastic_section_modulus_strong_axis_Zx=Zx,
            radius_of_gyration_strong_axis_rx=rx,
            moment_of_inertia_weak_axis_Iy=Iy,
            elastic_section_modulus_weak_axis_Sy=Sy,
            plastic_section_modulus_weak_axis_Zy=Zy,
            radius_of_gyration_weak_axis_ry=ry,
            torsional_constant_J=J,
            warping_constant_Cw=Cw,
            distance_between_flange_centroids_ho=ho,
            effective_radius_of_gyration_for_LTB_rts=rts,
            flange_width_to_thickness_ratio_bf_2tf=flange_width_to_thickness_ratio_bf_2tf,
            web_height_to_thickness_ratio_h_tw=web_height_to_thickness_ratio_h_tw,
            web_thickness_tw=tw,
            flange_width_bf=bf,
            flange_thickness_tf=tf,
            # Plate-built sections have no fillet at the flange-web
            # junction: kdes = kdet = tf (depth from outer flange face
            # to the flat web), and k1 = tw/2 (half the web thickness,
            # no fillet shoulder).
            k_design_kdes=tf,
            k_detailing_kdet=tf,
            k_one_k1=tw / 2.0,
        )

    def compute_compression_properties(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
    ) -> CompressionSectionProperties:
        """Return the AISC 360-22 Chapter-E input snapshot.

        Material-aware (unlike :meth:`compute_section_properties`):
        the §E7 / Table B4.1a slender-element limits depend on ``Fy``,
        so this resolves them here - exactly as
        :func:`classify_axial_compression_B4_1a` pairs section + material.

        For a doubly-symmetric I the shear centre coincides with the
        centroid (``xo = yo = 0``, ``H = 1``); §E4 reduces to torsional
        buckling about the longitudinal axis (Eq. E4-2).
        """
        bf: float = self.flange_width_bf
        tf: float = self.flange_thickness_tf
        hw: float = self.web_clear_height_hw
        tw: float = self.web_thickness_tw

        sp = self.compute_section_properties()
        Ag: float = sp.gross_area_Ag
        Ix: float = sp.moment_of_inertia_strong_axis_Ix
        Iy: float = sp.moment_of_inertia_weak_axis_Iy

        sqrt_E_over_Fy: float = math.sqrt(material.elastic_modulus_E / material.yield_stress_Fy)

        # Flange: unstiffened projecting element, b = bf/2, t = tf.
        if construction == "rolled":
            flange_lambda_r: float = B4_1A_UNSTIFFENED_ROLLED_FLANGE_COEFF * sqrt_E_over_Fy
        else:
            kc: float = compute_kc_for_built_up_flange(hw / tw)
            flange_lambda_r = B4_1A_UNSTIFFENED_BUILTUP_FLANGE_COEFF * math.sqrt(
                kc * material.elastic_modulus_E / material.yield_stress_Fy
            )
        flange = CompressionPlateElement(
            name="flange",
            kind="unstiffened",
            width_b=bf / 2.0,
            thickness_t=tf,
            slenderness_ratio_lambda=bf / (2.0 * tf),
            nonslender_limit_lambda_r=flange_lambda_r,
        )
        # Web: stiffened element, b = hw (clear height), t = tw.
        web = CompressionPlateElement(
            name="web",
            kind="stiffened",
            width_b=hw,
            thickness_t=tw,
            slenderness_ratio_lambda=hw / tw,
            nonslender_limit_lambda_r=B4_1A_STIFFENED_WEB_COEFF * sqrt_E_over_Fy,
        )

        return CompressionSectionProperties(
            section_kind="doubly_symmetric_I",
            symmetry="doubly_symmetric",
            gross_area_Ag=Ag,
            radius_of_gyration_x_rx=sp.radius_of_gyration_strong_axis_rx,
            radius_of_gyration_y_ry=sp.radius_of_gyration_weak_axis_ry,
            moment_of_inertia_x_Ix=Ix,
            moment_of_inertia_y_Iy=Iy,
            torsional_constant_J=sp.torsional_constant_J,
            warping_constant_Cw=sp.warping_constant_Cw,
            shear_centre_x_xo=0.0,
            shear_centre_y_yo=0.0,
            polar_radius_about_shear_centre_ro_bar=math.sqrt((Ix + Iy) / Ag),
            flexural_constant_H=1.0,
            plate_elements=(flange, web),
        )

    def element(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
        bracing: Bracing | None = None,
        code_edition_for_seismic: SeismicCodeEdition = "AISC 341-22",
    ) -> Element:
        """Return an Element binding this section to material + bracing."""
        # Local import to break the cycle:
        # apeSteel.element imports DoublySymmetricISection.
        from apeSteel.element import Element  # noqa: PLC0415

        return Element.from_section(
            section=self,
            material=material,
            construction=construction,
            bracing=bracing,
            code_edition_for_seismic=code_edition_for_seismic,
        )


__all__ = ["DoublySymmetricISection"]

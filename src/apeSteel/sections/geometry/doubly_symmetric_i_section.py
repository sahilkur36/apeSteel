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

from apeSteel.core.materials import CARBON_STEEL_DENSITY_rho
from apeSteel.core.units import g as gravitational_acceleration_g
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

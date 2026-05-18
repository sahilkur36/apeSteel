"""Round HSS / pipe geometry for AISC §E (compression) and §F8 (flexure).

A round HSS is axisymmetric: only §E3 flexural buckling applies (no
§E4), and §E7.2(c) (Eq. E7-6 / E7-7) reduces the area directly from
``D/t`` - a provision **retained unchanged from 360-16**, so it
coincides with the workbook's ``Qa_3``.  The non-slender ``D/t`` limit
is Table B4.1a Case 9, ``0.11 E/Fy``.

Area / inertia are transcribed from the validated workbook ``HSS T``
sheet (``B38 .. B40``).

For flexure (AISC 360-22 §F8, round HSS / Pipe) the same axisymmetric
closed forms are reused unchanged - :meth:`compute_section_properties`
shares ``Ag`` / ``I`` / ``J`` with :meth:`compute_compression_properties`
and adds the plastic and elastic section moduli that §F8 needs.  Because
the section is doubly symmetric and axisymmetric, the strong- and
weak-axis moduli are identical (``Zx == Zy``, ``Sx == Sy``,
``Ix == Iy``) and §F8 has no lateral-torsional-buckling limit state.

References
----------
.. [1] AISC 360-22 §E3, §E7.2(c) Eq. E7-6 / E7-7, Table B4.1a Case 9
       (round HSS, 0.11 E/Fy), pp. 16.1-37 - 16.1-43.
.. [2] AISC 360-22 §F8 "Round HSS", Eq. F8-1 - F8-4, p. 16.1-65.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.sections.compression_properties import CompressionSectionProperties
from apeSteel.sections.flexural_properties import FlexuralSectionProperties

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

    def compute_section_properties(self) -> FlexuralSectionProperties:
        """Return the AISC 360-22 §F8 flexural input snapshot for a round HSS.

        The gross-section closed forms are **identical** to those in
        :meth:`compute_compression_properties` (same ``Ag`` / ``Idiam``
        / ``J``), so the two paths cannot disagree on shared quantities;
        this method only *adds* the plastic / elastic section moduli
        that §F8 needs (compression never required them).

        For an annular (round-tube) section with outside diameter ``D``
        and inside diameter ``Di = D - 2t``:

        * gross area ``Ag = (pi/4)(D^2 - Di^2)``
          (= workbook ``HSS T!B38``, same as compression);
        * second moment about any diameter
          ``I = (pi/64)(D^4 - Di^4)``
          (= workbook ``HSS T!B39``, same as compression);
        * elastic section modulus ``S = I / (D/2) = 2 I / D``;
        * plastic section modulus of a circular tube
          ``Z = (D^3 - Di^3) / 6`` (the standard solid-round
          ``Z = d^3/6`` less the bore ``Di^3/6``; Boresi/Young,
          *Roark's Formulas for Stress and Strain*, circular-tube
          plastic modulus).

        Because the cross-section is axisymmetric, the strong- and
        weak-axis values are equal (``Ix == Iy``, ``Sx == Sy``,
        ``Zx == Zy``, ``rx == ry``); §F8 has no LTB limit state, so the
        I/channel LTB constants (``rts``, ``ho``, ``Cw``, ``c``) keep
        their neutral defaults.  ``diameter_D`` / ``wall_thickness_t``
        are carried so §F8 (and the Table B4.1b Case 20 classifier) can
        use ``D/t`` directly.

        Returns
        -------
        FlexuralSectionProperties
            ``section_kind="round_HSS"``, axisymmetric, in base units.
        """
        D: float = self.outside_diameter_D
        t: float = self.wall_thickness_t
        Di: float = D - 2.0 * t

        # Shared with compute_compression_properties (HSS T!B38/B39) -
        # written identically so the two snapshots cannot diverge.
        Ag: float = math.pi / 4.0 * (D**2 - Di**2)
        Idiam: float = math.pi / 64.0 * (D**4 - Di**4)  # about any diameter
        r: float = math.sqrt(Idiam / Ag)
        J: float = math.pi / 32.0 * (D**4 - Di**4)  # closed circular torsion

        # Flexure-only additions.
        S: float = Idiam / (D / 2.0)  # elastic modulus, S = 2 I / D
        Z: float = (D**3 - Di**3) / 6.0  # circular-tube plastic modulus

        return FlexuralSectionProperties(
            section_kind="round_HSS",
            symmetry="doubly_symmetric",
            overall_depth_d=D,
            gross_area_Ag=Ag,
            moment_of_inertia_Ix=Idiam,
            elastic_modulus_Sx=S,
            plastic_modulus_Zx=Z,
            radius_of_gyration_rx=r,
            # Axisymmetric: weak-axis == strong-axis.
            moment_of_inertia_Iy=Idiam,
            elastic_modulus_Sy=S,
            plastic_modulus_Zy=Z,
            radius_of_gyration_ry=r,
            torsional_constant_J=J,
            # §F8 has no LTB; warping / ho / rts / c stay neutral.
            warping_constant_Cw=0.0,
            # §F8 reads D/t directly (Table B4.1b Case 20).
            diameter_D=D,
            wall_thickness_t=t,
            # Classifier (classification layer) attaches the Case 20
            # wall element; the geometry layer never imports it.
            plate_elements=(),
        )


__all__ = ["RoundHSS"]

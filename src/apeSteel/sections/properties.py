"""Canonical :class:`SectionProperties` frozen dataclass.

`SectionProperties` is the universal currency between geometry and
calculators in apeSteel.  Every downstream calculator (classification,
flexure, shear, serviceability, seismic) consumes this dataclass
without caring whether it came from plate dimensions or from a
published catalog table.

All values are in apeSteel's canonical ``N-mm-tonne-s`` base units.

Doubly-symmetric vs singly-symmetric I-sections
-----------------------------------------------
The base fields describe a doubly-symmetric I (equal top / bot flanges,
centroid at mid-depth).  Singly-symmetric I-sections (unequal flanges)
populate the additional ``*_optional`` fields below; for doubly-symmetric
sections those fields can be left at their sentinel ``0.0`` and the
downstream code falls back to the DS-derived value.

The convention for "compression flange" is *the flange in compression
for the bending direction being checked*.  For doubly-symmetric I that
is symmetric (same answer either direction).  For singly-symmetric I the
geometry class produces two `SectionProperties` instances - one for
each bending direction - and the F4 facade picks the right one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SectionProperties:
    """Frozen geometric properties of a structural-steel section.

    All values are stored in apeSteel's canonical ``N-mm-tonne-s`` base
    units (length in mm, area in mm^2, second moment in mm^4, warping
    constant in mm^6). See ``docs/UNITS_AND_CONVENTIONS.md``.
    """

    # Geometry (overall)
    overall_depth_d: float
    gross_area_Ag: float
    nominal_weight_per_unit_length_w: float

    # Strong axis (about the geometric x-axis)
    moment_of_inertia_strong_axis_Ix: float
    elastic_section_modulus_strong_axis_Sx: float
    plastic_section_modulus_strong_axis_Zx: float
    radius_of_gyration_strong_axis_rx: float

    # Weak axis (about the geometric y-axis)
    moment_of_inertia_weak_axis_Iy: float
    elastic_section_modulus_weak_axis_Sy: float
    plastic_section_modulus_weak_axis_Zy: float
    radius_of_gyration_weak_axis_ry: float

    # LTB-relevant section constants
    torsional_constant_J: float
    warping_constant_Cw: float
    distance_between_flange_centroids_ho: float
    effective_radius_of_gyration_for_LTB_rts: float

    # Plate-element slenderness ratios (dimensionless)
    flange_width_to_thickness_ratio_bf_2tf: float
    web_height_to_thickness_ratio_h_tw: float

    # Bare plate dimensions needed by §G2 shear (Aw = d * tw).  Stored
    # so downstream calculators don't have to recover them from ratios.
    web_thickness_tw: float = 0.0

    # Flange plate dimensions needed by the panel-zone column-flange
    # tension check (AISC 341 §E3.6e) and other connection-level
    # calculators.  Stored explicitly so the catalog adapters can hand
    # back the AISC-published values without forcing downstream code
    # to reconstruct them from ``bf / 2tf`` and ``d``.
    flange_width_bf: float = 0.0
    flange_thickness_tf: float = 0.0

    # Detailing offsets - distance from the outer face of the flange to
    # the toe / heel of the web fillet at the flange-to-web junction.
    # Drive: continuity-plate width clip (AISC 358 §2.4.4 / 360 §J10.8).
    #
    # * ``k_design_kdes``  - distance to the *design* toe of the
    #   fillet (smaller, conservative). AISC v16 column ``kdes``.
    # * ``k_detailing_kdet`` - distance to the *detailing* toe (rounded
    #   up for shop drawings). AISC v16 column ``kdet``.
    # * ``k_one_k1`` - distance from the centre of the web to the toe of
    #   the fillet (one side).  Half-width of the column k-detail
    #   region. AISC v16 column ``k1``.
    #
    # All three default to 0.0 so an older :class:`SectionProperties`
    # that pre-dates this field still constructs; downstream code that
    # uses these falls back to a conservative heuristic when zero.
    k_design_kdes: float = 0.0
    k_detailing_kdet: float = 0.0
    k_one_k1: float = 0.0

    # --- Singly-symmetric optional fields (Phase 9b) ------------------
    # These are populated by SinglySymmetricISection.compute_section_properties()
    # and left at their sentinel ``0.0`` by DoublySymmetricISection-derived
    # properties.  Downstream code that handles SS (currently only AISC §F4)
    # reads them and falls back to the DS-equivalent value when zero.
    #
    # ``compression_flange_width_bfc`` - width of the flange in compression
    #     for the bending direction being checked. Defaults to flange_width_bf.
    # ``compression_flange_thickness_tfc`` - thickness of same. Defaults to
    #     flange_thickness_tf.
    # ``elastic_section_modulus_compression_flange_Sxc`` - Ix / c_c, where
    #     c_c is the distance from the elastic NA to the extreme compression
    #     fiber. For DS this equals Sx.
    # ``elastic_section_modulus_tension_flange_Sxt`` - same, tension side.
    #     For DS equals Sx.
    # ``moment_of_inertia_compression_flange_about_y_Iyc`` - moment of
    #     inertia of the compression flange about the y-axis. Drives the
    #     F4-9/F4-10 Rpc switch (Iyc/Iy > or <= 0.23).  For DS = Iy / 2.
    # ``compression_zone_depth_hc`` - twice the distance from the elastic NA
    #     to the inside face of the compression flange (per AISC F4-9
    #     definition, with the fillet-radius subtraction for rolled shapes).
    #     For DS equals the web clear height hw.  Used as the web
    #     slenderness numerator (hc/tw) in B4.1b Case 16 and F4-9.
    # ``plastic_neutral_axis_depth_hp`` - twice the distance from the
    #     elastic NA to the plastic NA.  For DS equals hw.  Drives the
    #     B4.1b Case 16 lambda_pw expression for SS (not used in this
    #     module's classifier yet; reserved for future Case 16 support).
    compression_flange_width_bfc: float = 0.0
    compression_flange_thickness_tfc: float = 0.0
    elastic_section_modulus_compression_flange_Sxc: float = 0.0
    elastic_section_modulus_tension_flange_Sxt: float = 0.0
    moment_of_inertia_compression_flange_about_y_Iyc: float = 0.0
    compression_zone_depth_hc: float = 0.0
    plastic_neutral_axis_depth_hp: float = 0.0

    # --- Convenience resolvers --------------------------------------
    # These methods return the SS field if populated, else the DS-derived
    # equivalent.  Calculators should call these instead of reading the
    # SS fields directly, so DS sections never need to populate the SS
    # fields explicitly.
    def resolved_compression_flange_width_bfc(self) -> float:
        return self.compression_flange_width_bfc or self.flange_width_bf

    def resolved_compression_flange_thickness_tfc(self) -> float:
        return self.compression_flange_thickness_tfc or self.flange_thickness_tf

    def resolved_Sxc(self) -> float:
        return self.elastic_section_modulus_compression_flange_Sxc or self.elastic_section_modulus_strong_axis_Sx

    def resolved_Sxt(self) -> float:
        return self.elastic_section_modulus_tension_flange_Sxt or self.elastic_section_modulus_strong_axis_Sx

    def resolved_Iyc(self) -> float:
        return self.moment_of_inertia_compression_flange_about_y_Iyc or (self.moment_of_inertia_weak_axis_Iy / 2.0)

    def resolved_iyc_over_iy(self) -> float:
        return self.resolved_Iyc() / self.moment_of_inertia_weak_axis_Iy

    def resolved_hc(self) -> float:
        if self.compression_zone_depth_hc:
            return self.compression_zone_depth_hc
        # DS fallback: hc equals the web clear height = h_tw * tw.
        return self.web_height_to_thickness_ratio_h_tw * self.web_thickness_tw

    def resolved_hp(self) -> float:
        if self.plastic_neutral_axis_depth_hp:
            return self.plastic_neutral_axis_depth_hp
        return self.resolved_hc()


__all__ = ["SectionProperties"]

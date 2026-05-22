"""AISC 341-22 seismic checks example.

Demonstrates:

1. ``Element.classify_seismic`` — AISC 341 §D1.1 highly-ductile
   compactness for a fuse beam (flange + web + length checks).
2. ``BeamColumnConnection.check_panel_zone_column_flange_tension`` —
   AISC 341 §E3.6e capacity-amplified column-flange tension check.
3. ``BeamColumnConnection.check_panel_zone_shear`` — AISC 360 §J10.6
   capacity-design panel-zone shear (Eq. J10-9 .. J10-12).
"""

from __future__ import annotations

from apeSteel import A992, Bracing, DoublySymmetricISection
from apeSteel.core import units as u


def main() -> None:
    beam_section = DoublySymmetricISection(
        flange_width_bf=200 * u.mm,
        flange_thickness_tf=16 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=10 * u.mm,
    )
    column_section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=25 * u.mm,
        web_clear_height_hw=350 * u.mm,
        web_thickness_tw=14 * u.mm,
    )
    bracing = Bracing(
        unbraced_length_top_flange_Lb_top=2.0 * u.m,
        unbraced_length_bot_flange_Lb_bot=2.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    beam = beam_section.element(material=A992, construction="rolled", bracing=bracing)
    column = column_section.element(material=A992, construction="rolled")

    seismic = beam.classify_seismic("highly_ductile", axial_demand_ratio_Ca=0.0)
    print(f"Highly-ductile flange OK?   : {seismic.flange.classification}")
    print(f"Highly-ductile web    OK?   : {seismic.web.classification}")
    print(f"Section seismically compact?: {seismic.is_seismically_compact_section}")

    joint = beam.connected_to(column)

    cf = joint.check_panel_zone_column_flange_tension()
    print(f"Column-flange tension DCR   : {cf.demand_to_capacity_ratio:5.3f}")
    print(f"Column-flange thickness OK? : {cf.is_thickness_acceptable}")

    pz = joint.check_panel_zone_shear(
        column_axial_demand_Pr=300.0 * u.kN,
        number_of_beam_sides=1,
    )
    print(f"Panel-zone governing eqn    : {pz.governing_equation}")
    print(f"Panel-zone DCR              : {pz.demand_to_capacity_ratio:5.3f}")


if __name__ == "__main__":
    main()

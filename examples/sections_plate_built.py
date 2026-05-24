"""Plate-built section geometries and their integrated section properties.

Each geometry dataclass in :mod:`apeSteel.sections.geometry` is the
immutable plate-dimension description of a single section family. The
``compute_section_properties`` (or ``compute_compression_properties``)
methods integrate those plate dimensions into the
:class:`SectionProperties` / :class:`CompressionSectionProperties`
frozen dataclasses every AISC calculator consumes.
"""

from __future__ import annotations

from apeSteel import (
    A992,
    ChannelSection,
    DoublySymmetricISection,
    RectangularHSS,
    RoundHSS,
)
from apeSteel.core import units as u


def main() -> None:
    # Welded doubly-symmetric I — the workhorse for §F2/F3/F4/F5 LTB.
    i_section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=12 * u.mm,
    )
    i_props = i_section.compute_section_properties()
    print(
        f"I-section : Ag = {i_props.gross_area_Ag / (u.mm**2):8.0f} mm^2"
        f"   Zx = {i_props.plastic_section_modulus_strong_axis_Zx / (u.mm**3):10.0f} mm^3"
    )

    # Plate-built channel — §F2 major / §F6 minor axis.
    channel = ChannelSection(
        flange_width_bf=80 * u.mm,
        flange_thickness_tf=12 * u.mm,
        overall_depth_d=250 * u.mm,
        web_thickness_tw=8 * u.mm,
    )
    channel_compression = channel.compute_compression_properties(material=A992)
    print(
        f"Channel   : Ag = {channel_compression.gross_area_Ag / (u.mm**2):8.0f} mm^2"
        f"   rx = {channel_compression.radius_of_gyration_x_rx / u.mm:6.2f} mm"
    )

    # Rectangular HSS — §F7 flexure, §E Chapter-E compression.
    rect_hss = RectangularHSS(
        depth_H=200 * u.mm,
        width_B=100 * u.mm,
        wall_thickness_t=8 * u.mm,
    )
    hss_compression = rect_hss.compute_compression_properties(material=A992)
    print(
        f"Rect HSS  : Ag = {hss_compression.gross_area_Ag / (u.mm**2):8.0f} mm^2"
        f"   ry = {hss_compression.radius_of_gyration_y_ry / u.mm:6.2f} mm"
    )

    # Round HSS / pipe — §F8 flexure.
    round_hss = RoundHSS(
        outside_diameter_D=168.3 * u.mm,
        wall_thickness_t=7.1 * u.mm,
    )
    round_compression = round_hss.compute_compression_properties(material=A992)
    print(
        f"Round HSS : Ag = {round_compression.gross_area_Ag / (u.mm**2):8.0f} mm^2"
        f"   rx = {round_compression.radius_of_gyration_x_rx / u.mm:6.2f} mm"
    )


if __name__ == "__main__":
    main()

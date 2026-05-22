"""AISC 360-22 Chapter F flexure example.

Demonstrates two paths into the Chapter-F engines:

1. ``Element.run_full_check`` — the high-level beam-check facade that
   classifies per Table B4.1b, routes flexure to F2 / F3 / F4 / F5,
   evaluates both flanges, and runs G2 shear.
2. ``Element.flexural_strength_F2_both_flanges`` — direct invocation
   of a specific F engine for the compact-flange / compact-web case.
"""

from __future__ import annotations

from apeSteel import A992, Bracing, DoublySymmetricISection
from apeSteel.core import units as u


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=16 * u.mm,
    )
    bracing = Bracing(
        unbraced_length_top_flange_Lb_top=0.001 * u.m,
        unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    element = section.element(material=A992, construction="welded", bracing=bracing)

    beam = element.run_full_check()
    print(f"Routed to             : {beam.routed_flexure_chapter}")
    print(f"Governing flange      : {beam.governing_flexural_flange}")
    print(f"phi*Mn (governing)    : {beam.governing_flexural_phi_Mn / (u.kN * u.m):7.1f} kN.m")

    f2 = element.flexural_strength_F2_both_flanges()
    rep = f2.governing_report
    print(f"F2 governing limit    : {rep.governing_limit_state}")
    print(f"F2 phi*Mn             : {rep.phi_strength_LRFD / (u.kN * u.m):7.1f} kN.m")


if __name__ == "__main__":
    main()

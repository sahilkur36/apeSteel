"""Quickstart example — referenced from docs/index.md.

This file is executable: a CI job runs it to guarantee the snippet
stays in sync with the public API.
"""

from apeSteel import A992, DoublySymmetricISection
from apeSteel.bracing import Bracing
from apeSteel.core import units as u


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=16 * u.mm,
    )
    element = section.element(
        material=A992,
        construction="welded",
        bracing=Bracing(
            unbraced_length_top_flange_Lb_top=0.001 * u.m,
            unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        ),
    )

    flexure = element.flexural_strength_F2_both_flanges()
    phi_Mn = flexure.governing_report.phi_strength_LRFD
    print(f"φMn = {phi_Mn / (u.kN * u.m):.1f} kN·m  (governing: {flexure.governing_flange})")


if __name__ == "__main__":
    main()

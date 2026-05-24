"""AISC 360-22 §H1.1 beam-column interaction example.

Demonstrates ``Element.combined_strength_H1`` for a doubly-symmetric
I-section under combined axial compression and major-axis bending.
``Pc`` is resolved internally from Chapter E (``phi_c*Pn``) and
``Mcx`` from the governing Chapter-F result (``phi_b*Mnx``).
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
        unbraced_length_top_flange_Lb_top=4.0 * u.m,
        unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    element = section.element(material=A992, construction="welded", bracing=bracing)

    h1 = element.combined_strength_H1(
        required_axial_Pr=600.0 * u.kN,
        required_moment_x_Mrx=120.0 * u.kN * u.m,
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
    )

    print(f"Equation governing    : {h1.governing_equation}")
    print(f"Pr / Pc               : {h1.axial_ratio_Pr_Pc:5.3f}")
    print(f"Available Pc          : {h1.available_axial_Pc / u.kN:7.1f} kN")
    print(f"Available Mcx         : {h1.available_moment_x_Mcx / (u.kN * u.m):7.1f} kN.m")
    print(f"Unity check (DCR)     : {h1.demand_capacity_ratio:5.3f}")
    print(f"Passes?               : {h1.unity_check_passes}")


if __name__ == "__main__":
    main()

"""Bracing scenarios — Lb_top vs Lb_bot and the role of Cb.

A :class:`Bracing` describes the lateral-bracing state of a member.
The two unbraced lengths are independent: ``Lb_top`` governs §F2 LTB
when the top flange is in compression (positive bending), ``Lb_bot``
when the bottom flange is in compression (negative bending, e.g. over
a cantilever support). ``Cb`` is the AISC F1-1 moment-diagram
modification factor; default ``1.0`` is conservative.
"""

from __future__ import annotations

from apeSteel import A992, Bracing, DoublySymmetricISection
from apeSteel.core import units as u


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=12 * u.mm,
    )

    # Scenario 1 — composite slab: top flange fully restrained by the
    # slab, bottom flange unbraced for 4 m. Use a small positive value
    # (NOT zero) for the fully-braced flange — the F2-5 regime check
    # expects a positive Lb.
    composite = Bracing(
        unbraced_length_top_flange_Lb_top=0.001 * u.m,
        unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )

    # Scenario 2 — both flanges unbraced for the same length, but the
    # moment diagram justifies Cb = 1.67 (e.g. a uniformly loaded simply
    # supported beam with both ends free to rotate laterally).
    bare_beam = Bracing(
        unbraced_length_top_flange_Lb_top=4.0 * u.m,
        unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.67,
    )

    for name, bracing in (("Composite slab", composite), ("Bare beam, Cb=1.67", bare_beam)):
        element = section.element(material=A992, construction="welded", bracing=bracing)
        flexure = element.flexural_strength_F2_both_flanges()
        print(
            f"{name:22s}"
            f"  top phi*Mn = {flexure.top.phi_strength_LRFD / (u.kN * u.m):7.1f} kN.m"
            f"  bot phi*Mn = {flexure.bot.phi_strength_LRFD / (u.kN * u.m):7.1f} kN.m"
            f"  governing  = {flexure.governing_flange}"
        )

    # Bracing is frozen: rebinding requires constructing a new one (or
    # using ``element.with_bracing(...)`` to replace it on the Element).
    element_a = section.element(material=A992, construction="welded", bracing=composite)
    element_b = element_a.with_bracing(bare_beam)
    assert element_a.bracing is composite
    assert element_b.bracing is bare_beam


if __name__ == "__main__":
    main()

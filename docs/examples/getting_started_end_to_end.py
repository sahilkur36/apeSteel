"""End-to-end Getting Started walkthrough.

Builds a welded doubly-symmetric I-section in A992, binds a Bracing
scenario, and runs the AISC 360-22 §B4 classification, §F2 lateral-
torsional buckling, §G2 web shear, and §E Chapter-E compression checks
through the ``Element`` facade.

Every numeric value passed in is multiplied by an ``apeSteel.core.units``
constant so the canonical N-mm-tonne-s base is preserved at the
boundary.
"""

from __future__ import annotations

from apeSteel import A992, Bracing, DoublySymmetricISection
from apeSteel.core import units as u


def main() -> None:
    # 1. Geometry — plate-built welded I, dimensions multiplied by u.mm
    #    so storage is in the N-mm-tonne-s base.
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=12 * u.mm,
    )

    # 2. Bracing — Lb_top is a near-zero positive (slab-braced top flange);
    #    Lb_bot is the actual unbraced length of the bottom flange.
    bracing = Bracing(
        unbraced_length_top_flange_Lb_top=0.001 * u.m,
        unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )

    # 3. Element — section + material + construction + bracing.
    element = section.element(
        material=A992,
        construction="welded",
        bracing=bracing,
    )

    # 4. AISC 360-22 §B4.1b plate-element classification.
    flexural_classification = element.classify_flexural()
    print(f"Flange class : {flexural_classification.flange.classification}")
    print(f"Web class    : {flexural_classification.web.classification}")

    # 5. AISC 360-22 §F2 LTB — both flange unbraced lengths checked,
    #    governing returned alongside the per-flange reports.
    flexure = element.flexural_strength_F2_both_flanges()
    phi_Mn = flexure.governing_report.phi_strength_LRFD
    print(
        f"phi*Mn (F2)  : {phi_Mn / (u.kN * u.m):7.1f} kN.m"
        f"   governing flange: {flexure.governing_flange}"
    )

    # 6. AISC 360-22 §G2 web shear (unstiffened web).
    shear = element.shear_strength_G2()
    print(f"phi*Vn (G2)  : {shear.phi_strength_LRFD / u.kN:7.1f} kN")

    # 7. AISC 360-22 Chapter E compression (KL = 4 m about every axis).
    compression = element.compression_strength(
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
    )
    print(f"phi*Pn (Ch E): {compression.phi_strength_LRFD / u.kN:7.1f} kN")


if __name__ == "__main__":
    main()

"""The ``Element`` composite — section + material + construction + bracing.

This example shows the four ways to construct an :class:`Element`
(``section.element(...)``, :meth:`Element.from_section`, the ``with_*``
builders) and then drives the high-level method surface: classification
(§B4), Chapter-F flexure (§F2), Chapter-G shear (§G2), Chapter-E
compression, the full beam-check facade, and the §H1.1 beam-column
interaction.
"""

from __future__ import annotations

from apeSteel import A992, S355, Bracing, DoublySymmetricISection, Element
from apeSteel.core import units as u


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=12 * u.mm,
    )
    bracing = Bracing(
        unbraced_length_top_flange_Lb_top=0.001 * u.m,
        unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )

    # (1) Section shortcut — the most common path.
    el_a = section.element(material=A992, construction="welded", bracing=bracing)

    # (2) Explicit constructor.
    el_b = Element(
        section=section,
        material=A992,
        construction="welded",
        bracing=bracing,
    )

    # (3) Classmethod factory.
    el_c = Element.from_section(
        section=section,
        material=A992,
        construction="welded",
        bracing=bracing,
    )

    assert el_a == el_b == el_c

    # (4) ``with_*`` builders return a new Element with one field replaced;
    #     the original is frozen and unchanged.
    el_s355 = el_a.with_material(S355)
    assert el_a.material is A992
    assert el_s355.material is S355

    # High-level methods — classification first.
    classification = el_a.classify_flexural()
    print(f"Flange class : {classification.flange.classification}")
    print(f"Web class    : {classification.web.classification}")

    # F2 LTB — both flange unbraced lengths checked, governing returned.
    flexure = el_a.flexural_strength_F2_both_flanges()
    print(f"phi*Mn (F2)  : {flexure.governing_report.phi_strength_LRFD / (u.kN * u.m):7.1f} kN.m")

    # G2 web shear — Element wraps compute_shear_strength_G2_doubly_symmetric.
    shear = el_a.shear_strength_G2()
    print(f"phi*Vn (G2)  : {shear.phi_strength_LRFD / u.kN:7.1f} kN")

    # Chapter-E compression for KLx = KLy = KLz = 4 m.
    compression = el_a.compression_strength(
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
    )
    print(f"phi*Pn (Ch E): {compression.phi_strength_LRFD / u.kN:7.1f} kN")

    # ``run_full_check`` — classify + route Chapter-F (F2/F3/F4/F5) + G2 shear.
    beam_check = el_a.run_full_check()
    print(
        f"Beam-check governing phi*Mn = "
        f"{beam_check.governing_flexural_phi_Mn / (u.kN * u.m):7.1f} kN.m"
    )

    # §H1.1 uniaxial interaction — Pc / Mcx are resolved internally from
    # Element.compression_strength / Element.run_full_check.
    h1 = el_a.combined_strength_H1(
        required_axial_Pr=500 * u.kN,
        required_moment_x_Mrx=150 * u.kN * u.m,
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
    )
    print(
        f"H1.1 DCR     : {h1.demand_capacity_ratio:5.3f}   (governing Eq. {h1.governing_equation})"
    )


if __name__ == "__main__":
    main()

"""Pulling rolled shapes from AISCv16Catalog and EuropeanIPECatalog.

Both catalogs adapt their underlying CSV-published values into the
canonical :class:`SectionProperties` currency used throughout apeSteel.
A doubly-symmetric I row also exposes a plate-built
:class:`DoublySymmetricISection` geometry through
``get_doubly_symmetric_i_geometry``, which is what hands off cleanly to
the ``Element`` composite.
"""

from __future__ import annotations

from apeSteel import A992, AISCv16Catalog, Bracing, EuropeanIPECatalog, S355
from apeSteel.core import units as u


def main() -> None:
    # AISC v16 — case-insensitive label lookup with RapidFuzz fallback.
    aisc = AISCv16Catalog()
    w_geometry = aisc.get_doubly_symmetric_i_geometry("W14X90")
    print(
        "W14X90 plates:"
        f"  bf = {w_geometry.flange_width_bf / u.mm:6.2f} mm"
        f"   tf = {w_geometry.flange_thickness_tf / u.mm:5.2f} mm"
        f"   hw = {w_geometry.web_clear_height_hw / u.mm:6.2f} mm"
        f"   tw = {w_geometry.web_thickness_tw / u.mm:5.2f} mm"
    )

    w_element = w_geometry.element(
        material=A992,
        construction="rolled",
        bracing=Bracing(
            unbraced_length_top_flange_Lb_top=0.001 * u.m,
            unbraced_length_bot_flange_Lb_bot=3.0 * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        ),
    )
    flexure = w_element.flexural_strength_F2_both_flanges()
    print(
        f"W14X90 phi*Mn (F2) = {flexure.governing_report.phi_strength_LRFD / (u.kN * u.m):7.1f} kN.m"
    )

    # EN 10365 IPE subset — same SectionProperties currency.
    ipe = EuropeanIPECatalog()
    ipe_geometry = ipe.get_doubly_symmetric_i_geometry("IPE 400")
    ipe_element = ipe_geometry.element(
        material=S355,
        construction="rolled",
        bracing=Bracing(
            unbraced_length_top_flange_Lb_top=0.001 * u.m,
            unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        ),
    )
    ipe_flexure = ipe_element.flexural_strength_F2_both_flanges()
    print(
        f"IPE 400 phi*Mn (F2) = "
        f"{ipe_flexure.governing_report.phi_strength_LRFD / (u.kN * u.m):7.1f} kN.m"
    )


if __name__ == "__main__":
    main()

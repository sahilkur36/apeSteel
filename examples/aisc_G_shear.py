"""AISC 360-22 §G2 web-shear example.

Demonstrates ``Element.shear_strength_G2`` for a welded doubly-symmetric
I-section. The unstiffened path (``transverse_stiffener_spacing_a=None``)
uses ``kv = 5.34`` per the 360-22 update; pass an ``a`` value to switch
to the stiffened-web ``kv`` family.
"""

from __future__ import annotations

from apeSteel import A992, DoublySymmetricISection
from apeSteel.core import units as u


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=16 * u.mm,
    )
    element = section.element(material=A992, construction="welded")

    shear = element.shear_strength_G2()
    print(f"Regime                : {shear.governing_limit_state}")
    print(f"h/tw                  : {shear.web_slenderness_ratio_lambda_w:6.2f}")
    print(f"kv                    : {shear.web_plate_buckling_coefficient_kv:5.3f}")
    print(f"Cv1                   : {shear.web_shear_strength_coefficient_Cv1:5.3f}")
    print(f"Vn                    : {shear.nominal_strength / u.kN:7.1f} kN")
    print(f"phi*Vn (LRFD)         : {shear.phi_strength_LRFD / u.kN:7.1f} kN")


if __name__ == "__main__":
    main()

"""AISC 360-22 §B4 classification example.

Demonstrates ``Element.classify_flexural`` (Table B4.1b) and
``Element.classify_axial_compression`` (Table B4.1a) for a welded
doubly-symmetric I-section in A992 steel.
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

    flexural = element.classify_flexural()
    axial = element.classify_axial_compression()

    print(f"Flexural section class : {flexural.section_classification}")
    print(
        f"  flange  lambda={flexural.flange.slenderness_ratio_lambda:6.2f}  "
        f"lambda_p={flexural.flange.compact_limit_lambda_p:6.2f}  "
        f"lambda_r={flexural.flange.noncompact_limit_lambda_r:6.2f}  "
        f"-> {flexural.flange.classification}"
    )
    print(
        f"  web     lambda={flexural.web.slenderness_ratio_lambda:6.2f}  "
        f"lambda_p={flexural.web.compact_limit_lambda_p:6.2f}  "
        f"lambda_r={flexural.web.noncompact_limit_lambda_r:6.2f}  "
        f"-> {flexural.web.classification}"
    )
    print(
        f"Axial: any slender element? {axial.section_has_slender_element}  "
        f"(flange {axial.flange.classification}, web {axial.web.classification})"
    )


if __name__ == "__main__":
    main()

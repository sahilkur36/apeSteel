"""Recipe: end-to-end beam check via ``Element.run_full_check``.

Builds a W-shape, attaches material and bracing, runs the AISC 360-22
beam-check facade, and prints the routed flexure chapter, the
governing limit state, φMn, and φVn.
"""

from __future__ import annotations

from apeSteel import A992, DoublySymmetricISection
from apeSteel.bracing import Bracing
from apeSteel.core import units as u


def main() -> None:
    # 1. Pick a section.
    section = DoublySymmetricISection(
        flange_width_bf=200 * u.mm,
        flange_thickness_tf=12 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=8 * u.mm,
    )

    # 2. Attach material + construction + bracing.
    element = section.element(
        material=A992,
        construction="welded",
        bracing=Bracing(
            unbraced_length_top_flange_Lb_top=0.001 * u.m,
            unbraced_length_bot_flange_Lb_bot=3.0 * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.14,
        ),
    )

    # 3. Run the facade.
    report = element.run_full_check()

    # 4. Interpret the BeamCheckReport.
    flange_class = report.flexural_classification.flange.classification
    web_class = report.flexural_classification.web.classification
    flex = report.flexure_both_flanges
    shear = report.shear
    assert flex is not None
    assert shear is not None

    print(f"Classification : flange = {flange_class}, web = {web_class}")
    print(f"Routed chapter : §{report.routed_flexure_chapter}")
    print(f"Governing flange  : {report.governing_flexural_flange}")
    print(f"Governing limit state: {flex.governing_report.governing_limit_state}")
    phi_Mn = report.governing_flexural_phi_Mn / (u.kN * u.m)
    phi_Vn = shear.phi_strength_LRFD / u.kN
    print(f"φMn = {phi_Mn:.1f} kN·m")
    print(f"φVn = {phi_Vn:.1f} kN")

    # 5. The cited AISC clauses ride along.
    sections_cited = sorted({c.section for c in report.cited_clauses})
    print(f"Cited clauses: {sections_cited}")


if __name__ == "__main__":
    main()

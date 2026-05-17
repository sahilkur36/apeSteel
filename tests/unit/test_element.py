"""Unit tests for Element - the composite that aggregates Section + Material + Bracing.

Three layers of validation:

1. Construction paths (section.element(...) and Element.from_section(...)) agree.
2. Methods on Element produce identical results to the corresponding pure
   functions (no behaviour duplication; Element methods are thin wrappers).
3. Builder methods (with_material, with_bracing, ...) produce new
   Elements with one field replaced; the original is unchanged (immutability).
4. LTB methods raise when bracing is None.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A992,
    S355,
    BothFlangesFlexureF2Report,
    Bracing,
    DoublySymmetricISection,
    Element,
    classify_axial_compression_B4_1a,
    classify_flexural_compactness_B4_1b,
    classify_seismic_compactness_341_D1,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)
from apeSteel.core import units as u

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SECTION = DoublySymmetricISection(
    100.0 * u.mm,
    6.0 * u.mm,
    300.0 * u.mm,
    4.0 * u.mm,
)
BRACING = Bracing(
    unbraced_length_top_flange_Lb_top=0.001 * u.m,
    unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
    lateral_torsional_buckling_modification_factor_Cb=1.0,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
def test_section_element_factory_matches_from_section() -> None:
    a = SECTION.element(material=A992, construction="welded", bracing=BRACING)
    b = Element.from_section(SECTION, A992, "welded", BRACING)
    assert a == b


def test_default_construction_is_welded() -> None:
    el = SECTION.element(material=A992)
    assert el.construction == "welded"


def test_default_bracing_is_None() -> None:
    el = SECTION.element(material=A992)
    assert el.bracing is None


def test_default_seismic_edition_is_341_22() -> None:
    el = SECTION.element(material=A992)
    assert el.code_edition_for_seismic == "AISC 341-22"


# ---------------------------------------------------------------------------
# Derived characteristic (cached_property)
# ---------------------------------------------------------------------------
def test_section_properties_is_cached() -> None:
    el = SECTION.element(material=A992)
    first = el.section_properties
    second = el.section_properties
    assert first is second  # same object, not just equal


def test_section_properties_matches_section_compute() -> None:
    el = SECTION.element(material=A992)
    direct = SECTION.compute_section_properties()
    assert el.section_properties == direct


# ---------------------------------------------------------------------------
# Builders return new Elements (immutability via dataclasses.replace)
# ---------------------------------------------------------------------------
def test_with_material_returns_new_element_with_replaced_material() -> None:
    el = SECTION.element(material=A992, bracing=BRACING)
    el2 = el.with_material(S355)
    assert el2.material is S355
    assert el.material is A992  # original unchanged


def test_with_construction_returns_new_element() -> None:
    el = SECTION.element(material=A992, construction="welded")
    el2 = el.with_construction("rolled")
    assert el2.construction == "rolled"
    assert el.construction == "welded"


def test_with_bracing_replaces_bracing() -> None:
    el = SECTION.element(material=A992)
    assert el.bracing is None
    new_bracing = Bracing(0.001 * u.m, 2.0 * u.m, 1.2)
    el2 = el.with_bracing(new_bracing)
    assert el2.bracing == new_bracing
    assert el.bracing is None  # original unchanged


def test_with_code_edition_for_seismic_replaces_edition() -> None:
    el = SECTION.element(material=A992)
    el2 = el.with_code_edition_for_seismic("AISC 341-10")
    assert el2.code_edition_for_seismic == "AISC 341-10"
    assert el.code_edition_for_seismic == "AISC 341-22"


def test_chained_builders_compose() -> None:
    el = SECTION.element(material=A992)
    el2 = el.with_material(S355).with_bracing(BRACING).with_construction("rolled")
    assert el2.material is S355
    assert el2.bracing == BRACING
    assert el2.construction == "rolled"


# ---------------------------------------------------------------------------
# Methods match pure-function results
# ---------------------------------------------------------------------------
def test_classify_flexural_matches_pure_function() -> None:
    el = SECTION.element(material=A992, construction="welded")
    method_report = el.classify_flexural()
    pure_report = classify_flexural_compactness_B4_1b(
        el.section_properties,
        A992,
        "welded",
    )
    assert method_report == pure_report


def test_classify_axial_compression_matches_pure_function() -> None:
    el = SECTION.element(material=A992, construction="welded")
    method_report = el.classify_axial_compression()
    pure_report = classify_axial_compression_B4_1a(
        el.section_properties,
        A992,
        "welded",
    )
    assert method_report == pure_report


def test_classify_seismic_matches_pure_function() -> None:
    el = SECTION.element(material=A992)
    method_report = el.classify_seismic("highly_ductile", axial_demand_ratio_Ca=0.05)
    pure_report = classify_seismic_compactness_341_D1(
        section_properties=el.section_properties,
        material=A992,
        ductility_level="highly_ductile",
        axial_demand_ratio_Ca=0.05,
        code_edition="AISC 341-22",
    )
    assert method_report == pure_report


def test_classify_seismic_uses_per_element_default_edition() -> None:
    el = SECTION.element(material=A992).with_code_edition_for_seismic("AISC 341-10")
    method_report = el.classify_seismic("highly_ductile")
    assert method_report.code_edition == "AISC 341-10"


def test_classify_seismic_can_override_default_edition_per_call() -> None:
    el = SECTION.element(material=A992).with_code_edition_for_seismic("AISC 341-22")
    method_report = el.classify_seismic("highly_ductile", code_edition="AISC 341-10")
    assert method_report.code_edition == "AISC 341-10"


def test_flexural_F2_top_flange_matches_pure_function() -> None:
    el = SECTION.element(material=A992, bracing=BRACING)
    method_report = el.flexural_strength_F2_top_flange()
    pure_report = compute_flexural_strength_F2_compact_doubly_symmetric(
        el.section_properties,
        A992,
        unbraced_length_Lb=BRACING.unbraced_length_top_flange_Lb_top,
        lateral_torsional_buckling_modification_factor_Cb=(
            BRACING.lateral_torsional_buckling_modification_factor_Cb
        ),
    )
    assert method_report == pure_report


def test_flexural_F2_bot_flange_matches_pure_function() -> None:
    el = SECTION.element(material=A992, bracing=BRACING)
    method_report = el.flexural_strength_F2_bot_flange()
    pure_report = compute_flexural_strength_F2_compact_doubly_symmetric(
        el.section_properties,
        A992,
        unbraced_length_Lb=BRACING.unbraced_length_bot_flange_Lb_bot,
        lateral_torsional_buckling_modification_factor_Cb=(
            BRACING.lateral_torsional_buckling_modification_factor_Cb
        ),
    )
    assert method_report == pure_report


# ---------------------------------------------------------------------------
# Both-flange wrapper + governing flange
# ---------------------------------------------------------------------------
def test_both_flanges_returns_BothFlangesFlexureF2Report() -> None:
    el = SECTION.element(material=A992, bracing=BRACING)
    both = el.flexural_strength_F2_both_flanges()
    assert isinstance(both, BothFlangesFlexureF2Report)


def test_both_flanges_top_and_bot_match_individual_calls() -> None:
    el = SECTION.element(material=A992, bracing=BRACING)
    both = el.flexural_strength_F2_both_flanges()
    assert both.top == el.flexural_strength_F2_top_flange()
    assert both.bot == el.flexural_strength_F2_bot_flange()


def test_governing_flange_is_lower_phi_Mn() -> None:
    el = SECTION.element(material=A992, bracing=BRACING)
    both = el.flexural_strength_F2_both_flanges()
    # Default 100x6/300x4 with Lb_top=0.001m, Lb_bot=4m: bot must govern.
    assert both.governing_flange == "bot"
    assert both.governing_report is both.bot
    assert both.bot.phi_strength_LRFD <= both.top.phi_strength_LRFD


def test_governing_flange_is_top_when_bottom_is_better_braced() -> None:
    """Reverse the bracing: top is more loaded laterally."""
    flipped = Bracing(
        unbraced_length_top_flange_Lb_top=4.0 * u.m,
        unbraced_length_bot_flange_Lb_bot=0.001 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    el = SECTION.element(material=A992, bracing=flipped)
    both = el.flexural_strength_F2_both_flanges()
    assert both.governing_flange == "top"
    assert both.governing_report is both.top


# ---------------------------------------------------------------------------
# LTB methods raise when bracing is None
# ---------------------------------------------------------------------------
def test_F2_top_raises_when_bracing_None() -> None:
    el = SECTION.element(material=A992)
    with pytest.raises(ValueError, match="bracing"):
        el.flexural_strength_F2_top_flange()


def test_F2_bot_raises_when_bracing_None() -> None:
    el = SECTION.element(material=A992)
    with pytest.raises(ValueError, match="bracing"):
        el.flexural_strength_F2_bot_flange()


def test_F2_both_raises_when_bracing_None() -> None:
    el = SECTION.element(material=A992)
    with pytest.raises(ValueError, match="bracing"):
        el.flexural_strength_F2_both_flanges()


def test_classification_methods_work_without_bracing() -> None:
    """The no-loading checks must still work when bracing is None."""
    el = SECTION.element(material=A992)
    el.classify_flexural()
    el.classify_axial_compression()
    el.classify_seismic("highly_ductile")


# ---------------------------------------------------------------------------
# Element immutability
# ---------------------------------------------------------------------------
def test_element_is_frozen() -> None:
    el = SECTION.element(material=A992)
    with pytest.raises(FrozenInstanceError):
        el.material = S355  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Numeric sanity (spreadsheet default at A992, Lb_top~0, Lb_bot=4m, Cb=1)
# ---------------------------------------------------------------------------
def test_default_section_governing_phi_Mn_matches_smoke_value() -> None:
    """Smoke check: governing phi*Mn ~= 21.2 kN.m for 100x6/300x4 at A992."""
    el = SECTION.element(material=A992, bracing=BRACING)
    both = el.flexural_strength_F2_both_flanges()
    phi_Mn_kN_m = both.governing_report.phi_strength_LRFD / u.MOMENT_DISPLAY_UNIT_kN_m
    assert math.isclose(phi_Mn_kN_m, 21.21, rel_tol=5e-3)


def test_S355_governing_phi_Mn_is_same_as_A992_in_elastic_LTB() -> None:
    """In the deep elastic-LTB regime, Mn = Cb*Mcr depends on E, J, Cw, Sx -
    NOT on Fy.  So A992 and S355 (same E, only Fy differs) should give the
    same phi*Mn (subject to the Mp cap).  This is a useful sanity check
    on the regime decision tree."""
    el_A992 = SECTION.element(material=A992, bracing=BRACING)
    el_S355 = el_A992.with_material(S355)
    both_A992 = el_A992.flexural_strength_F2_both_flanges()
    both_S355 = el_S355.flexural_strength_F2_both_flanges()
    # bot flange is in elastic_LTB regime; values must match.
    assert both_A992.bot.governing_limit_state == "elastic_LTB"
    assert both_S355.bot.governing_limit_state == "elastic_LTB"
    assert math.isclose(
        both_A992.bot.phi_strength_LRFD,
        both_S355.bot.phi_strength_LRFD,
        rel_tol=1e-12,
    )

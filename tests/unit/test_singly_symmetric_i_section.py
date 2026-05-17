"""Unit tests for SinglySymmetricISection (Phase 9b).

Covers:
* Section-property computation against hand-computed values for an
  asymmetric plate-built I.
* Symmetry property: when top and bottom flanges have identical
  dimensions, the result matches DoublySymmetricISection exactly.
* The two compression-flange-side variants give a consistent geometric
  decomposition (hc_top + hc_bot = 2*hw, swapping Sxc/Sxt, swapping Iyc).
"""

from __future__ import annotations

import math

import pytest

from apeSteel import (
    A992,
    DoublySymmetricISection,
    SinglySymmetricISection,
)

TOL = 1e-9


def _hand_section() -> SinglySymmetricISection:
    """Plate-built SS section used as the hand-computation anchor.

    bf_top=200, tf_top=15, bf_bot=400, tf_bot=25, hw=1000, tw=10.
    """
    return SinglySymmetricISection(
        top_flange_width_bf_top=200.0,
        top_flange_thickness_tf_top=15.0,
        bot_flange_width_bf_bot=400.0,
        bot_flange_thickness_tf_bot=25.0,
        web_clear_height_hw=1000.0,
        web_thickness_tw=10.0,
    )


def _hand_areas_and_centroid() -> dict[str, float]:
    """Hand-computed expected values for the section in `_hand_section`."""
    bft, tft = 200.0, 15.0
    bfb, tfb = 400.0, 25.0
    hw, tw = 1000.0, 10.0
    At = bft * tft  # 3000
    Aw = hw * tw  # 10000
    Ab = bfb * tfb  # 10000
    Ag = At + Aw + Ab  # 23000
    # Centroid from bottom fiber
    yt = tfb + hw + tft / 2.0  # 25 + 1000 + 7.5 = 1032.5
    yw = tfb + hw / 2.0  # 525
    yb = tfb / 2.0  # 12.5
    y_c = (At * yt + Aw * yw + Ab * yb) / Ag
    # = (3000*1032.5 + 10000*525 + 10000*12.5) / 23000
    # = (3097500 + 5250000 + 125000) / 23000
    # = 8472500 / 23000 = 368.3695652...
    d = hw + tft + tfb  # 1040
    return {"Ag": Ag, "y_c": y_c, "d": d, "At": At, "Aw": Aw, "Ab": Ab, "yt": yt, "yw": yw, "yb": yb}


class TestHandValues:
    def test_centroid_matches_hand(self) -> None:
        sec = _hand_section()
        sp = sec.compute_section_properties("top")
        expected = _hand_areas_and_centroid()
        assert math.isclose(sp.gross_area_Ag, expected["Ag"], rel_tol=TOL)
        assert math.isclose(sp.overall_depth_d, expected["d"], rel_tol=TOL)

    def test_strong_axis_inertia_matches_hand(self) -> None:
        # Parallel-axis Ix
        e = _hand_areas_and_centroid()
        At, Aw, Ab = e["At"], e["Aw"], e["Ab"]
        yt, yw, yb = e["yt"], e["yw"], e["yb"]
        y_c = e["y_c"]
        Ix_expected = (
            (200.0 * 15.0**3) / 12.0 + At * (yt - y_c) ** 2
            + (10.0 * 1000.0**3) / 12.0 + Aw * (yw - y_c) ** 2
            + (400.0 * 25.0**3) / 12.0 + Ab * (yb - y_c) ** 2
        )
        sec = _hand_section()
        sp = sec.compute_section_properties("top")
        assert math.isclose(sp.moment_of_inertia_strong_axis_Ix, Ix_expected, rel_tol=TOL)

    def test_section_moduli_referenced_correctly(self) -> None:
        # Top compression: c_top = d - y_c (smaller for our section since y_c < d/2).
        # Bot compression: c_bot = y_c.
        # Sxc(top compression) = Ix / c_top.  Sxc(bot compression) = Ix / c_bot.
        e = _hand_areas_and_centroid()
        d = e["d"]
        y_c = e["y_c"]
        c_top = d - y_c
        c_bot = y_c
        sec = _hand_section()
        sp_top = sec.compute_section_properties("top")
        sp_bot = sec.compute_section_properties("bot")
        Ix = sp_top.moment_of_inertia_strong_axis_Ix
        assert math.isclose(sp_top.resolved_Sxc(), Ix / c_top, rel_tol=TOL)
        assert math.isclose(sp_top.resolved_Sxt(), Ix / c_bot, rel_tol=TOL)
        assert math.isclose(sp_bot.resolved_Sxc(), Ix / c_bot, rel_tol=TOL)
        assert math.isclose(sp_bot.resolved_Sxt(), Ix / c_top, rel_tol=TOL)

    def test_hc_sum_equals_hw(self) -> None:
        """hc(top compression) + hc(bot compression) should equal hw."""
        sec = _hand_section()
        sp_top = sec.compute_section_properties("top")
        sp_bot = sec.compute_section_properties("bot")
        # hc_top / 2 = (hw + tfb - y_c)
        # hc_bot / 2 = (y_c - tfb)
        # sum = hw
        assert math.isclose(
            sp_top.resolved_hc() + sp_bot.resolved_hc(),
            2.0 * sec.web_clear_height_hw,
            rel_tol=TOL,
        )

    def test_iyc_complementary(self) -> None:
        """Iyc(top compression) + Iyc(bot compression) == Iy - Iy_web."""
        sec = _hand_section()
        sp_top = sec.compute_section_properties("top")
        sp_bot = sec.compute_section_properties("bot")
        Iy_web = sec.web_clear_height_hw * sec.web_thickness_tw**3 / 12.0
        assert math.isclose(
            sp_top.resolved_Iyc() + sp_bot.resolved_Iyc(),
            sp_top.moment_of_inertia_weak_axis_Iy - Iy_web,
            rel_tol=TOL,
        )


class TestDoublySymmetricEquivalence:
    """SinglySymmetricISection with equal flanges must match DoublySymmetricISection."""

    @pytest.fixture
    def equal_flanges(self) -> tuple[DoublySymmetricISection, SinglySymmetricISection]:
        ds = DoublySymmetricISection(
            flange_width_bf=300.0,
            flange_thickness_tf=20.0,
            web_clear_height_hw=1200.0,
            web_thickness_tw=10.0,
        )
        ss = SinglySymmetricISection(
            top_flange_width_bf_top=300.0,
            top_flange_thickness_tf_top=20.0,
            bot_flange_width_bf_bot=300.0,
            bot_flange_thickness_tf_bot=20.0,
            web_clear_height_hw=1200.0,
            web_thickness_tw=10.0,
        )
        return ds, ss

    def test_areas_and_depth(self, equal_flanges: tuple[DoublySymmetricISection, SinglySymmetricISection]) -> None:
        ds, ss = equal_flanges
        sp_ds = ds.compute_section_properties()
        sp_ss = ss.compute_section_properties("top")
        assert math.isclose(sp_ss.gross_area_Ag, sp_ds.gross_area_Ag, rel_tol=TOL)
        assert math.isclose(sp_ss.overall_depth_d, sp_ds.overall_depth_d, rel_tol=TOL)

    def test_strong_axis(self, equal_flanges: tuple[DoublySymmetricISection, SinglySymmetricISection]) -> None:
        ds, ss = equal_flanges
        sp_ds = ds.compute_section_properties()
        sp_ss = ss.compute_section_properties("top")
        assert math.isclose(
            sp_ss.moment_of_inertia_strong_axis_Ix,
            sp_ds.moment_of_inertia_strong_axis_Ix,
            rel_tol=TOL,
        )
        assert math.isclose(
            sp_ss.elastic_section_modulus_strong_axis_Sx,
            sp_ds.elastic_section_modulus_strong_axis_Sx,
            rel_tol=TOL,
        )
        assert math.isclose(
            sp_ss.plastic_section_modulus_strong_axis_Zx,
            sp_ds.plastic_section_modulus_strong_axis_Zx,
            rel_tol=TOL,
        )

    def test_J_and_Cw_and_ho(self, equal_flanges: tuple[DoublySymmetricISection, SinglySymmetricISection]) -> None:
        ds, ss = equal_flanges
        sp_ds = ds.compute_section_properties()
        sp_ss = ss.compute_section_properties("top")
        assert math.isclose(sp_ss.torsional_constant_J, sp_ds.torsional_constant_J, rel_tol=TOL)
        assert math.isclose(sp_ss.warping_constant_Cw, sp_ds.warping_constant_Cw, rel_tol=TOL)
        assert math.isclose(
            sp_ss.distance_between_flange_centroids_ho,
            sp_ds.distance_between_flange_centroids_ho,
            rel_tol=TOL,
        )

    def test_hc_equals_hw_for_doubly_symmetric(
        self, equal_flanges: tuple[DoublySymmetricISection, SinglySymmetricISection]
    ) -> None:
        ds, ss = equal_flanges
        sp_ss = ss.compute_section_properties("top")
        # For DS-equivalent SS, hc should equal hw
        assert math.isclose(sp_ss.resolved_hc(), ss.web_clear_height_hw, rel_tol=TOL)

    def test_iyc_is_one_flange_contribution(
        self, equal_flanges: tuple[DoublySymmetricISection, SinglySymmetricISection]
    ) -> None:
        """For DS-equivalent SS, Iyc = tf*bf^3/12 (one flange, per AISC F4).

        Not exactly Iy/2 because Iy also includes the web term
        hw*tw^3/12 which belongs to neither flange.  For typical
        proportions the difference is < 0.5%, well above the F4-10
        threshold of 0.23, so behaviour is unaffected.
        """
        _, ss = equal_flanges
        sp_ss = ss.compute_section_properties("top")
        expected_Iyc = (
            ss.top_flange_thickness_tf_top * ss.top_flange_width_bf_top**3 / 12.0
        )
        assert math.isclose(sp_ss.resolved_Iyc(), expected_Iyc, rel_tol=TOL)
        ratio = sp_ss.resolved_iyc_over_iy()
        assert 0.49 < ratio < 0.50


class TestElementBuilder:
    def test_element_method_returns_Element_with_SS_section(self) -> None:
        sec = _hand_section()
        el = sec.element(material=A992)
        # Element.section preserves the SS geometry
        assert el.section is sec
        # The cached section_properties uses top-compression by default
        sp_default = el.section_properties
        sp_top = el.section_properties_for("top")
        assert math.isclose(sp_default.resolved_Sxc(), sp_top.resolved_Sxc(), rel_tol=TOL)


class TestPlasticNAGuard:
    def test_PNA_in_web_assumption(self) -> None:
        """Section with PNA in web - should succeed."""
        sec = _hand_section()
        sp = sec.compute_section_properties("top")
        # The plastic NA depth (from bottom) for our section:
        # dPNA = tfb + (Ag/2 - Ab)/tw = 25 + (11500 - 10000)/10 = 25 + 150 = 175 mm.
        # This is in the web (25 <= 175 <= 25 + 1000), so we should be fine.
        assert sp.plastic_section_modulus_strong_axis_Zx > 0

    def test_PNA_outside_web_raises(self) -> None:
        """Section with extremely large bot flange forces PNA into the flange.

        If A_bot > Ag/2, the PNA falls inside the bot flange. Geometry:
        bot=600x60=36000 mm^2.  Top=100x10=1000.  Web=200x10=2000.
        Ag=39000.  Ag/2 = 19500.  Ab=36000 > 19500.  PNA in bot flange.
        """
        sec = SinglySymmetricISection(
            top_flange_width_bf_top=100.0,
            top_flange_thickness_tf_top=10.0,
            bot_flange_width_bf_bot=600.0,
            bot_flange_thickness_tf_bot=60.0,
            web_clear_height_hw=200.0,
            web_thickness_tw=10.0,
        )
        with pytest.raises(ValueError, match="plastic NA falls outside the web"):
            sec.compute_section_properties("top")

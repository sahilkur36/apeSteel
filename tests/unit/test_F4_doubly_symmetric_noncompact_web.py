"""Unit tests for AISC §F4 (doubly-symmetric I, non-compact web).

Covers each helper in isolation plus the public facade, the
`Element.flexural_strength_F4_*` wrappers, and the `beam_check` dispatch
route for noncompact-web sections.
"""

from __future__ import annotations

import math

import pytest

from apeSteel import (
    A992,
    Bracing,
    DoublySymmetricISection,
    Element,
    FlexureF4Report,
    compute_flexural_strength_F4_doubly_symmetric_noncompact_web,
)
from apeSteel.core import units as u
from apeSteel.flexure.F4_doubly_symmetric_noncompact_web import (
    compute_aw_for_F4,
    compute_compression_flange_local_buckling_moment_Mn_F4_13,
    compute_compression_flange_local_buckling_moment_Mn_F4_14,
    compute_Fcr_for_F4,
    compute_FL_for_F4,
    compute_inelastic_LTB_moment_Mn_F4_2,
    compute_Lp_for_F4,
    compute_Lr_for_F4,
    compute_rt_for_F4,
    compute_web_plastification_factor_Rpc,
)

TOL = 1e-9


def _plate_built_section_noncompact_web() -> DoublySymmetricISection:
    """A plate-built I with non-compact web at A992 (Fy=345)."""
    return DoublySymmetricISection(
        flange_width_bf=300.0 * u.mm,
        flange_thickness_tf=20.0 * u.mm,
        web_clear_height_hw=1200.0 * u.mm,
        web_thickness_tw=10.0 * u.mm,
    )


# ---------------------------------------------------------------------------
# Helper-level (pure functions)
# ---------------------------------------------------------------------------
class TestAwAndRt:
    def test_aw_F4_12(self) -> None:
        # aw = hc*tw / (bfc*tfc)
        aw = compute_aw_for_F4(
            web_clear_height_hc=1200.0,
            web_thickness_tw=10.0,
            compression_flange_width_bfc=300.0,
            compression_flange_thickness_tfc=20.0,
        )
        assert math.isclose(aw, (1200.0 * 10.0) / (300.0 * 20.0), rel_tol=TOL)

    def test_rt_F4_11(self) -> None:
        # rt = bfc / sqrt(12*(1 + aw/6))
        bf = 300.0
        aw = 2.0
        rt = compute_rt_for_F4(compression_flange_width_bfc=bf, web_to_flange_area_ratio_aw=aw)
        expected = bf / math.sqrt(12.0 * (1.0 + aw / 6.0))
        assert math.isclose(rt, expected, rel_tol=TOL)


class TestRpc:
    """AISC Eq. F4-9a / F4-9b / F4-10."""

    def test_compact_web_returns_Mp_over_Myc(self) -> None:
        # h/tw <= lambda_pw -> Rpc = Mp/Myc
        Rpc = compute_web_plastification_factor_Rpc(
            plastic_moment_Mp=1.10,
            yield_moment_compression_flange_Myc=1.0,
            web_slenderness_ratio_lambda=50.0,
            web_compact_limit_lambda_pw=90.0,
            web_noncompact_limit_lambda_rw=137.0,
            iyc_over_iy_ratio=0.5,
        )
        assert math.isclose(Rpc, 1.10, rel_tol=TOL)

    def test_at_lambda_pw_returns_Mp_over_Myc(self) -> None:
        # h/tw == lambda_pw exactly -> still F4-9a region (uses <=)
        Rpc = compute_web_plastification_factor_Rpc(
            plastic_moment_Mp=1.20,
            yield_moment_compression_flange_Myc=1.0,
            web_slenderness_ratio_lambda=90.0,
            web_compact_limit_lambda_pw=90.0,
            web_noncompact_limit_lambda_rw=137.0,
            iyc_over_iy_ratio=0.5,
        )
        assert math.isclose(Rpc, 1.20, rel_tol=TOL)

    def test_interpolation_F4_9b(self) -> None:
        # lambda_pw < h/tw < lambda_rw -> linear interpolation
        Mp = 1.20
        Myc = 1.00
        lam = 113.5  # midpoint of [90, 137]
        lam_pw = 90.0
        lam_rw = 137.0
        Rpc = compute_web_plastification_factor_Rpc(
            plastic_moment_Mp=Mp,
            yield_moment_compression_flange_Myc=Myc,
            web_slenderness_ratio_lambda=lam,
            web_compact_limit_lambda_pw=lam_pw,
            web_noncompact_limit_lambda_rw=lam_rw,
            iyc_over_iy_ratio=0.5,
        )
        # Mp/Myc = 1.20, drops linearly to 1.0 at lam_rw; midpoint = 1.10
        frac = (lam - lam_pw) / (lam_rw - lam_pw)
        expected = (Mp / Myc) - ((Mp / Myc) - 1.0) * frac
        assert math.isclose(Rpc, expected, rel_tol=TOL)

    def test_at_lambda_rw_returns_one(self) -> None:
        Rpc = compute_web_plastification_factor_Rpc(
            plastic_moment_Mp=1.50,
            yield_moment_compression_flange_Myc=1.0,
            web_slenderness_ratio_lambda=137.0,
            web_compact_limit_lambda_pw=90.0,
            web_noncompact_limit_lambda_rw=137.0,
            iyc_over_iy_ratio=0.5,
        )
        assert math.isclose(Rpc, 1.0, rel_tol=TOL)

    def test_iyc_iy_below_threshold_returns_one(self) -> None:
        # F4-10: Iyc/Iy <= 0.23 -> Rpc = 1.0
        Rpc = compute_web_plastification_factor_Rpc(
            plastic_moment_Mp=2.0,
            yield_moment_compression_flange_Myc=1.0,
            web_slenderness_ratio_lambda=50.0,
            web_compact_limit_lambda_pw=90.0,
            web_noncompact_limit_lambda_rw=137.0,
            iyc_over_iy_ratio=0.20,
        )
        assert math.isclose(Rpc, 1.0, rel_tol=TOL)


class TestFL:
    """AISC Eq. F4-6a / F4-6b."""

    def test_doubly_symmetric_returns_0p7_Fy(self) -> None:
        # Sxt = Sxc -> F4-6a: FL = 0.7*Fy
        FL = compute_FL_for_F4(
            yield_stress_Fy=345.0,
            elastic_section_modulus_tension_flange_Sxt=1.0,
            elastic_section_modulus_compression_flange_Sxc=1.0,
        )
        assert math.isclose(FL, 0.7 * 345.0, rel_tol=TOL)

    def test_at_ratio_0p7_uses_F4_6a(self) -> None:
        # Sxt/Sxc = 0.7 exactly -> F4-6a (>= 0.7)
        FL = compute_FL_for_F4(
            yield_stress_Fy=345.0,
            elastic_section_modulus_tension_flange_Sxt=0.7,
            elastic_section_modulus_compression_flange_Sxc=1.0,
        )
        assert math.isclose(FL, 0.7 * 345.0, rel_tol=TOL)

    def test_below_0p7_uses_ratio_floored_at_0p5(self) -> None:
        # Sxt/Sxc = 0.4 -> FL = Fy*0.4 = 138 MPa, but >= 0.5*Fy = 172.5 -> FL = 172.5
        FL = compute_FL_for_F4(
            yield_stress_Fy=345.0,
            elastic_section_modulus_tension_flange_Sxt=0.4,
            elastic_section_modulus_compression_flange_Sxc=1.0,
        )
        assert math.isclose(FL, 0.5 * 345.0, rel_tol=TOL)

    def test_between_0p5_and_0p7_uses_ratio(self) -> None:
        # Sxt/Sxc = 0.6 -> FL = Fy*0.6 = 207, which exceeds 0.5*Fy = 172.5
        FL = compute_FL_for_F4(
            yield_stress_Fy=345.0,
            elastic_section_modulus_tension_flange_Sxt=0.6,
            elastic_section_modulus_compression_flange_Sxc=1.0,
        )
        assert math.isclose(FL, 0.6 * 345.0, rel_tol=TOL)


class TestLpAndLr:
    def test_Lp_F4_7(self) -> None:
        Lp = compute_Lp_for_F4(
            effective_radius_rt=75.0, elastic_modulus_E=200_000.0, yield_stress_Fy=345.0
        )
        expected = 1.1 * 75.0 * math.sqrt(200_000.0 / 345.0)
        assert math.isclose(Lp, expected, rel_tol=TOL)

    def test_Lr_F4_8_positive(self) -> None:
        # Just confirm we get a finite, positive Lr larger than Lp.
        rt = 75.0
        E = 200_000.0
        FL = 0.7 * 345.0
        J = 1.0e6
        Sxc = 5.0e6
        ho = 1220.0
        Lr = compute_Lr_for_F4(
            effective_radius_rt=rt,
            elastic_modulus_E=E,
            limit_stress_FL=FL,
            torsional_constant_J=J,
            elastic_section_modulus_compression_flange_Sxc=Sxc,
            distance_between_flange_centroids_ho=ho,
        )
        Lp = compute_Lp_for_F4(rt, E, 345.0)
        assert Lr > Lp


class TestF42Inelastic:
    """F4-2 inelastic-LTB interpolation, with Rpc*Myc cap."""

    def test_at_Lp_returns_Rpc_Myc(self) -> None:
        Mn = compute_inelastic_LTB_moment_Mn_F4_2(
            plastic_anchor_moment_Rpc_times_Myc=1000.0,
            limit_anchor_moment_FL_times_Sxc=600.0,
            unbraced_length_Lb=1000.0,
            limiting_length_plastic_Lp=1000.0,
            limiting_length_inelastic_LTB_Lr=5000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        assert math.isclose(Mn, 1000.0, rel_tol=TOL)

    def test_at_Lr_returns_FL_Sxc(self) -> None:
        Mn = compute_inelastic_LTB_moment_Mn_F4_2(
            plastic_anchor_moment_Rpc_times_Myc=1000.0,
            limit_anchor_moment_FL_times_Sxc=600.0,
            unbraced_length_Lb=5000.0,
            limiting_length_plastic_Lp=1000.0,
            limiting_length_inelastic_LTB_Lr=5000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        assert math.isclose(Mn, 600.0, rel_tol=TOL)

    def test_Cb_amplification_capped_at_Rpc_Myc(self) -> None:
        # Cb large enough that Cb*[..] > Rpc*Myc; result must be capped.
        Mn = compute_inelastic_LTB_moment_Mn_F4_2(
            plastic_anchor_moment_Rpc_times_Myc=1000.0,
            limit_anchor_moment_FL_times_Sxc=600.0,
            unbraced_length_Lb=2000.0,
            limiting_length_plastic_Lp=1000.0,
            limiting_length_inelastic_LTB_Lr=5000.0,
            lateral_torsional_buckling_modification_factor_Cb=3.0,
        )
        assert math.isclose(Mn, 1000.0, rel_tol=TOL)


class TestFcrF45:
    def test_positive(self) -> None:
        # Sanity: Fcr > 0 and decreases with Lb.
        common = dict(
            lateral_torsional_buckling_modification_factor_Cb=1.0,
            effective_radius_rt=75.0,
            elastic_modulus_E=200_000.0,
            torsional_constant_J=1.0e6,
            elastic_section_modulus_compression_flange_Sxc=5.0e6,
            distance_between_flange_centroids_ho=1220.0,
        )
        Fcr_short = compute_Fcr_for_F4(unbraced_length_Lb=5000.0, **common)
        Fcr_long = compute_Fcr_for_F4(unbraced_length_Lb=20000.0, **common)
        assert Fcr_short > 0
        assert Fcr_long > 0
        assert Fcr_long < Fcr_short


class TestCFLB:
    def test_F4_13_at_lambda_pf_returns_Rpc_Myc(self) -> None:
        Mn = compute_compression_flange_local_buckling_moment_Mn_F4_13(
            plastic_anchor_moment_Rpc_times_Myc=1000.0,
            limit_anchor_moment_FL_times_Sxc=600.0,
            flange_slenderness_ratio_lambda_f=9.0,
            flange_compact_limit_lambda_pf=9.0,
            flange_noncompact_limit_lambda_rf=16.0,
        )
        assert math.isclose(Mn, 1000.0, rel_tol=TOL)

    def test_F4_13_at_lambda_rf_returns_FL_Sxc(self) -> None:
        Mn = compute_compression_flange_local_buckling_moment_Mn_F4_13(
            plastic_anchor_moment_Rpc_times_Myc=1000.0,
            limit_anchor_moment_FL_times_Sxc=600.0,
            flange_slenderness_ratio_lambda_f=16.0,
            flange_compact_limit_lambda_pf=9.0,
            flange_noncompact_limit_lambda_rf=16.0,
        )
        assert math.isclose(Mn, 600.0, rel_tol=TOL)

    def test_F4_14_decreases_with_lambda(self) -> None:
        common = dict(
            elastic_section_modulus_compression_flange_Sxc=5.0e6,
            elastic_modulus_E=200_000.0,
            flange_plate_buckling_coefficient_kc=0.5,
        )
        Mn_small = compute_compression_flange_local_buckling_moment_Mn_F4_14(
            flange_slenderness_ratio_lambda_f=20.0, **common
        )
        Mn_large = compute_compression_flange_local_buckling_moment_Mn_F4_14(
            flange_slenderness_ratio_lambda_f=30.0, **common
        )
        assert Mn_large < Mn_small


# ---------------------------------------------------------------------------
# Facade-level integration
# ---------------------------------------------------------------------------
class TestF4Facade:
    def test_rejects_nonpositive_Lb(self) -> None:
        sec = _plate_built_section_noncompact_web()
        with pytest.raises(ValueError, match="unbraced_length_Lb must be positive"):
            compute_flexural_strength_F4_doubly_symmetric_noncompact_web(
                sec.compute_section_properties(),
                A992,
                unbraced_length_Lb=0.0,
                lateral_torsional_buckling_modification_factor_Cb=1.0,
            )

    def test_short_Lb_governs_CFY(self) -> None:
        sec = _plate_built_section_noncompact_web()
        r = compute_flexural_strength_F4_doubly_symmetric_noncompact_web(
            sec.compute_section_properties(),
            A992,
            unbraced_length_Lb=500.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        assert r.governing_F4_limit_state == "compression_flange_yielding"
        assert r.governing_limit_state == "compression_flange_yielding"
        assert math.isclose(
            r.nominal_flexural_strength_Mn, r.nominal_CFY_moment_Mn_CFY, rel_tol=TOL
        )

    def test_long_Lb_governs_elastic_LTB(self) -> None:
        sec = _plate_built_section_noncompact_web()
        r = compute_flexural_strength_F4_doubly_symmetric_noncompact_web(
            sec.compute_section_properties(),
            A992,
            unbraced_length_Lb=10000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        assert r.governing_F4_limit_state == "lateral_torsional_buckling"
        assert r.governing_limit_state == "elastic_LTB"

    def test_phi_LRFD_is_0p9(self) -> None:
        sec = _plate_built_section_noncompact_web()
        r = compute_flexural_strength_F4_doubly_symmetric_noncompact_web(
            sec.compute_section_properties(),
            A992,
            unbraced_length_Lb=2000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        assert math.isclose(r.phi_LRFD, 0.90, rel_tol=TOL)
        assert math.isclose(r.phi_strength_LRFD, 0.90 * r.nominal_strength, rel_tol=TOL)

    def test_returns_FlexureF4Report(self) -> None:
        sec = _plate_built_section_noncompact_web()
        r = compute_flexural_strength_F4_doubly_symmetric_noncompact_web(
            sec.compute_section_properties(),
            A992,
            unbraced_length_Lb=2000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        assert isinstance(r, FlexureF4Report)


# ---------------------------------------------------------------------------
# Element wrappers + beam_check dispatch
# ---------------------------------------------------------------------------
def _noncompact_web_element(Lb: float = 2000.0) -> Element:
    sec = _plate_built_section_noncompact_web()
    br = Bracing(
        unbraced_length_top_flange_Lb_top=Lb,
        unbraced_length_bot_flange_Lb_bot=Lb,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    return sec.element(material=A992, construction="welded", bracing=br)


class TestElementWiring:
    def test_top_and_bot_methods_agree_when_Lb_equal(self) -> None:
        el = _noncompact_web_element()
        top = el.flexural_strength_F4_top_flange()
        bot = el.flexural_strength_F4_bot_flange()
        assert math.isclose(
            top.nominal_flexural_strength_Mn, bot.nominal_flexural_strength_Mn, rel_tol=TOL
        )

    def test_both_flanges_picks_lowest_phi_Mn(self) -> None:
        # Asymmetric bracing: top flange has shorter Lb -> stronger -> bot governs.
        sec = _plate_built_section_noncompact_web()
        br = Bracing(
            unbraced_length_top_flange_Lb_top=500.0,
            unbraced_length_bot_flange_Lb_bot=8000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        el = sec.element(material=A992, construction="welded", bracing=br)
        both = el.flexural_strength_F4_both_flanges()
        assert both.governing_flange == "bot"
        assert both.governing_report is both.bot
        assert both.bot.phi_strength_LRFD <= both.top.phi_strength_LRFD


class TestBeamCheckDispatch:
    def test_noncompact_web_routes_to_F4(self) -> None:
        el = _noncompact_web_element()
        full = el.run_full_check()
        f4_both = el.flexural_strength_F4_both_flanges()
        assert math.isclose(
            full.nominal_strength,
            f4_both.governing_report.nominal_flexural_strength_Mn,
            rel_tol=TOL,
        )

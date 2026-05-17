"""Unit tests for AISC §F4 applied to singly-symmetric I-sections (Phase 9b).

Phase 9a already covers F4 on doubly-symmetric I.  These tests focus on
the new behaviours that activate for singly-symmetric geometry:

* FL via Eq. F4-6b when Sxt/Sxc < 0.7
* Rpc, Rpt collapse to 1.0 when Iyc/Iy <= 0.23 (Eq. F4-10 / F4-17)
* TFY (F4-15) is active when Sxt < Sxc
* The two compression-flange-side variants give different Mn values
* beam_check dispatch routes SS sections to F4 regardless of web class
* Element guards F2/F3/F5/G2 with NotImplementedError for SS sections
"""

from __future__ import annotations

import math

import pytest

from apeSteel import (
    A992,
    Bracing,
    DoublySymmetricISection,
    SinglySymmetricISection,
    compute_flexural_strength_F4,
)
from apeSteel.flexure.F4 import (
    compute_FL_for_F4,
    compute_tension_flange_plastification_factor_Rpt,
)

TOL = 1e-9


# Sections used across the test suite
def _ss_small_top_flange() -> SinglySymmetricISection:
    """Compression-on-top governed by LTB (small top flange).

    Iyc/Iy ~ 0.07 -> Rpc = Rpt = 1.0 (F4-10/F4-17 path).
    Sxt/Sxc > 1 -> FL = 0.7*Fy (F4-6a).  TFY inactive.
    """
    return SinglySymmetricISection(
        top_flange_width_bf_top=200.0,
        top_flange_thickness_tf_top=15.0,
        bot_flange_width_bf_bot=400.0,
        bot_flange_thickness_tf_bot=25.0,
        web_clear_height_hw=1000.0,
        web_thickness_tw=10.0,
    )


# ---------------------------------------------------------------------------
# Helper-level tests for the new Rpt and FL-6b behaviours
# ---------------------------------------------------------------------------
class TestRpt:
    def test_iyc_below_threshold_returns_one(self) -> None:
        Rpt = compute_tension_flange_plastification_factor_Rpt(
            plastic_moment_Mp=2.0,
            yield_moment_tension_flange_Myt=1.0,
            web_slenderness_ratio_lambda=50.0,
            web_compact_limit_lambda_pw=90.0,
            web_noncompact_limit_lambda_rw=137.0,
            iyc_over_iy_ratio=0.20,
        )
        assert math.isclose(Rpt, 1.0, rel_tol=TOL)

    def test_compact_web_returns_Mp_over_Myt(self) -> None:
        Rpt = compute_tension_flange_plastification_factor_Rpt(
            plastic_moment_Mp=1.20,
            yield_moment_tension_flange_Myt=1.0,
            web_slenderness_ratio_lambda=50.0,
            web_compact_limit_lambda_pw=90.0,
            web_noncompact_limit_lambda_rw=137.0,
            iyc_over_iy_ratio=0.5,
        )
        assert math.isclose(Rpt, 1.20, rel_tol=TOL)

    def test_at_lambda_rw_returns_one(self) -> None:
        Rpt = compute_tension_flange_plastification_factor_Rpt(
            plastic_moment_Mp=1.50,
            yield_moment_tension_flange_Myt=1.0,
            web_slenderness_ratio_lambda=137.0,
            web_compact_limit_lambda_pw=90.0,
            web_noncompact_limit_lambda_rw=137.0,
            iyc_over_iy_ratio=0.5,
        )
        assert math.isclose(Rpt, 1.0, rel_tol=TOL)

    def test_interpolation(self) -> None:
        Mp = 1.50
        Myt = 1.0
        lam = 113.5
        lam_pw = 90.0
        lam_rw = 137.0
        Rpt = compute_tension_flange_plastification_factor_Rpt(
            plastic_moment_Mp=Mp,
            yield_moment_tension_flange_Myt=Myt,
            web_slenderness_ratio_lambda=lam,
            web_compact_limit_lambda_pw=lam_pw,
            web_noncompact_limit_lambda_rw=lam_rw,
            iyc_over_iy_ratio=0.5,
        )
        frac = (lam - lam_pw) / (lam_rw - lam_pw)
        expected = (Mp / Myt) - ((Mp / Myt) - 1.0) * frac
        assert math.isclose(Rpt, expected, rel_tol=TOL)


class TestFLBranches:
    def test_F4_6b_active_when_ratio_below_0p7(self) -> None:
        # Sxt/Sxc = 0.6 -> FL = 0.6*Fy
        FL = compute_FL_for_F4(
            yield_stress_Fy=345.0,
            elastic_section_modulus_tension_flange_Sxt=0.6,
            elastic_section_modulus_compression_flange_Sxc=1.0,
        )
        assert math.isclose(FL, 0.6 * 345.0, rel_tol=TOL)

    def test_F4_6b_floored_at_0p5_Fy(self) -> None:
        # Sxt/Sxc = 0.3 -> raw FL = 0.3*Fy = 103.5, floor = 0.5*Fy = 172.5
        FL = compute_FL_for_F4(
            yield_stress_Fy=345.0,
            elastic_section_modulus_tension_flange_Sxt=0.3,
            elastic_section_modulus_compression_flange_Sxc=1.0,
        )
        assert math.isclose(FL, 0.5 * 345.0, rel_tol=TOL)


# ---------------------------------------------------------------------------
# Facade-level: F4 on SS sections
# ---------------------------------------------------------------------------
class TestF4OnSinglySymmetric:
    def test_rpc_rpt_collapse_to_one_when_iyc_iy_below_threshold(self) -> None:
        sec = _ss_small_top_flange()
        sp_top = sec.compute_section_properties("top")
        r = compute_flexural_strength_F4(sp_top, A992, 2000.0, 1.0, "welded")
        # Iyc/Iy ~ 0.07 < 0.23 -> Rpc = Rpt = 1.0
        assert r.iyc_over_iy_ratio < 0.23
        assert math.isclose(r.web_plastification_factor_Rpc, 1.0, rel_tol=TOL)
        assert math.isclose(r.tension_flange_plastification_factor_Rpt, 1.0, rel_tol=TOL)

    def test_top_vs_bot_compression_differ(self) -> None:
        sec = _ss_small_top_flange()
        sp_top = sec.compute_section_properties("top")
        sp_bot = sec.compute_section_properties("bot")
        r_top = compute_flexural_strength_F4(sp_top, A992, 2000.0, 1.0, "welded")
        r_bot = compute_flexural_strength_F4(sp_bot, A992, 2000.0, 1.0, "welded")
        # The two scenarios are physically different (smaller flange weaker)
        assert not math.isclose(
            r_top.nominal_flexural_strength_Mn,
            r_bot.nominal_flexural_strength_Mn,
            rel_tol=1e-6,
        )

    def test_TFY_inactive_when_Sxt_ge_Sxc(self) -> None:
        # Small-top section, top in compression: Sxt > Sxc, so TFY inactive
        sec = _ss_small_top_flange()
        sp_top = sec.compute_section_properties("top")
        r = compute_flexural_strength_F4(sp_top, A992, 2000.0, 1.0, "welded")
        # TFY does not appear in governing candidates - the report
        # populates Mn_TFY with a sentinel that won't govern.
        assert r.Sxc_over_Sxt_ratio < 1.0  # Sxc < Sxt -> Sxt/Sxc > 1
        assert r.governing_limit_state != "tension_flange_yielding"

    def test_TFY_active_when_Sxt_lt_Sxc(self) -> None:
        # Bot-compression of small-top section: Sxt < Sxc -> TFY active.
        sec = _ss_small_top_flange()
        sp_bot = sec.compute_section_properties("bot")
        r = compute_flexural_strength_F4(sp_bot, A992, 2000.0, 1.0, "welded")
        assert r.Sxc_over_Sxt_ratio > 1.0
        # Mn_TFY should equal Rpt * Myt = 1.0 * Fy * Sxt
        Myt = A992.yield_stress_Fy * sp_bot.resolved_Sxt()
        Rpt = r.tension_flange_plastification_factor_Rpt
        assert math.isclose(r.nominal_TFY_moment_Mn_TFY, Rpt * Myt, rel_tol=TOL)

    def test_DS_equivalence(self) -> None:
        """SS with equal flanges should give the same F4 result as DS."""
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
        r_ds = compute_flexural_strength_F4(
            ds.compute_section_properties(), A992, 2000.0, 1.0, "welded"
        )
        r_ss = compute_flexural_strength_F4(
            ss.compute_section_properties("top"), A992, 2000.0, 1.0, "welded"
        )
        # Mn should agree to high precision (small differences from web's
        # Iy contribution are still well below the 0.23 threshold so the
        # Rpc/Rpt path is identical).
        assert math.isclose(
            r_ss.nominal_flexural_strength_Mn,
            r_ds.nominal_flexural_strength_Mn,
            rel_tol=1e-6,
        )


# ---------------------------------------------------------------------------
# Element wiring for SS
# ---------------------------------------------------------------------------
class TestElementSSWiring:
    def _ss_element(self) -> object:
        sec = _ss_small_top_flange()
        br = Bracing(
            unbraced_length_top_flange_Lb_top=2000.0,
            unbraced_length_bot_flange_Lb_bot=2000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        return sec.element(material=A992, construction="welded", bracing=br)

    def test_top_flange_method_uses_top_compression_properties(self) -> None:
        el = self._ss_element()
        r_top = el.flexural_strength_F4_top_flange()  # type: ignore[attr-defined]
        # The result corresponds to "top in compression", so Sxt > Sxc
        assert r_top.Sxc_over_Sxt_ratio < 1.0

    def test_bot_flange_method_uses_bot_compression_properties(self) -> None:
        el = self._ss_element()
        r_bot = el.flexural_strength_F4_bot_flange()  # type: ignore[attr-defined]
        # The result corresponds to "bot in compression", so Sxc > Sxt
        assert r_bot.Sxc_over_Sxt_ratio > 1.0

    def test_F2_raises_NotImplementedError_for_SS(self) -> None:
        el = self._ss_element()
        with pytest.raises(NotImplementedError, match="DoublySymmetricISection"):
            el.flexural_strength_F2_top_flange()  # type: ignore[attr-defined]

    def test_F3_raises_NotImplementedError_for_SS(self) -> None:
        el = self._ss_element()
        with pytest.raises(NotImplementedError, match="DoublySymmetricISection"):
            el.flexural_strength_F3_bot_flange()  # type: ignore[attr-defined]

    def test_F5_raises_NotImplementedError_for_SS(self) -> None:
        el = self._ss_element()
        with pytest.raises(NotImplementedError, match="DoublySymmetricISection"):
            el.flexural_strength_F5_top_flange()  # type: ignore[attr-defined]

    def test_G2_raises_NotImplementedError_for_SS(self) -> None:
        el = self._ss_element()
        with pytest.raises(NotImplementedError, match="DoublySymmetricISection"):
            el.shear_strength_G2()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# beam_check dispatch for SS
# ---------------------------------------------------------------------------
class TestBeamCheckDispatchSS:
    def test_SS_routes_to_F4(self) -> None:
        sec = _ss_small_top_flange()
        br = Bracing(
            unbraced_length_top_flange_Lb_top=2000.0,
            unbraced_length_bot_flange_Lb_bot=2000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        el = sec.element(material=A992, construction="welded", bracing=br)
        full = el.run_full_check()
        assert full.routed_flexure_chapter == "F4"
        # SS sections: shear is None (G2 SS not shipped)
        assert full.shear is None

    def test_SS_with_slender_web_raises(self) -> None:
        # Make hc/tw very large so web classifies as slender (>5.70*sqrt(E/Fy)~137)
        sec = SinglySymmetricISection(
            top_flange_width_bf_top=200.0,
            top_flange_thickness_tf_top=15.0,
            bot_flange_width_bf_bot=400.0,
            bot_flange_thickness_tf_bot=25.0,
            web_clear_height_hw=3000.0,  # very tall web
            web_thickness_tw=8.0,
        )
        br = Bracing(
            unbraced_length_top_flange_Lb_top=2000.0,
            unbraced_length_bot_flange_Lb_bot=2000.0,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        )
        el = sec.element(material=A992, construction="welded", bracing=br)
        with pytest.raises(NotImplementedError, match=r"F5 SS"):
            el.run_full_check()

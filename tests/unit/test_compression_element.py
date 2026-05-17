"""E-5: Element compression integration + φPn-vs-length curve.

These are consistency/contract tests (the numerical correctness of the
Chapter-E engine is anchored independently in
``tests/golden/test_chapterE_independent.py`` and
``tests/golden/test_compression_excel_anchor.py``).
"""

from __future__ import annotations

import math

import pytest

from apeSteel import (
    A992,
    DoublySymmetricISection,
    SinglySymmetricISection,
    compute_compression_strength_from_K_L,
    compute_phi_Pn_vs_length,
)
from apeSteel.core import units as u

_W = DoublySymmetricISection(
    flange_width_bf=300 * u.mm,
    flange_thickness_tf=20 * u.mm,
    web_clear_height_hw=400 * u.mm,
    web_thickness_tw=16 * u.mm,
)


def test_element_compression_matches_free_function() -> None:
    el = _W.element(material=A992)
    via_element = el.compression_strength(1.0, 4.0 * u.m, 1.0, 4.0 * u.m, 1.0, 4.0 * u.m)
    via_free = compute_compression_strength_from_K_L(
        _W.compute_compression_properties(A992, "welded"),
        A992,
        1.0,
        4.0 * u.m,
        1.0,
        4.0 * u.m,
        1.0,
        4.0 * u.m,
    )
    assert math.isclose(
        via_element.nominal_compressive_strength_Pn,
        via_free.nominal_compressive_strength_Pn,
        rel_tol=1e-12,
    )
    assert via_element.governing_compression_limit_state == "flexural_buckling"
    # phi_c = 0.90.
    assert math.isclose(
        via_element.phi_strength_LRFD,
        0.90 * via_element.nominal_compressive_strength_Pn,
        rel_tol=1e-12,
    )


def test_phi_Pn_vs_length_is_monotone_non_increasing() -> None:
    lengths = [L * u.m for L in (1.0, 2.0, 3.0, 5.0, 8.0, 12.0)]
    curve = compute_phi_Pn_vs_length(
        _W.compute_compression_properties(A992, "welded"), A992, lengths
    )
    assert len(curve) == len(lengths)
    phis = [p.design_strength_phi_Pn for p in curve]
    # Longer column -> not stronger (buckling); relative guard since
    # φPn is on the order of MN and flat on the Fy plateau at short L.
    for i in range(len(phis) - 1):
        assert phis[i + 1] <= phis[i] * (1.0 + 1e-9)
    # Each curve point equals a direct facade evaluation at that length.
    for pt in curve:
        direct = compute_compression_strength_from_K_L(
            _W.compute_compression_properties(A992, "welded"),
            A992,
            1.0,
            pt.length_L,
            1.0,
            pt.length_L,
            1.0,
            pt.length_L,
        )
        assert math.isclose(pt.design_strength_phi_Pn, direct.phi_strength_LRFD, rel_tol=1e-12)


def test_element_compression_rejects_singly_symmetric() -> None:
    ss = SinglySymmetricISection(
        top_flange_width_bf_top=200 * u.mm,
        top_flange_thickness_tf_top=12 * u.mm,
        bot_flange_width_bf_bot=300 * u.mm,
        bot_flange_thickness_tf_bot=16 * u.mm,
        web_clear_height_hw=500 * u.mm,
        web_thickness_tw=10 * u.mm,
    )
    el = ss.element(material=A992)
    with pytest.raises(NotImplementedError, match="compression_strength"):
        el.compression_strength(1.0, 3.0 * u.m, 1.0, 3.0 * u.m, 1.0, 3.0 * u.m)


def test_phi_Pn_vs_length_rejects_nonpositive() -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_phi_Pn_vs_length(
            _W.compute_compression_properties(A992, "welded"), A992, [1.0 * u.m, 0.0]
        )

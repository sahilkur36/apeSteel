"""H-7: Element.combined_strength_H1 facade integration (§H1.1).

Consistency/contract tests - the numerical correctness of the §H1.1
kernel is anchored independently in
``tests/golden/test_chapterH_independent.py``.  Here we only verify
that the ``Element`` convenience resolves ``Pc`` from Chapter E and
``Mcx`` from the governing Chapter-F result and feeds them to the
pure calculator unchanged.
"""

from __future__ import annotations

import math

import pytest

from apeSteel import (
    A992,
    Bracing,
    DoublySymmetricISection,
    compute_combined_strength_H1_1,
    compute_flexural_strength_F6_minor_axis,
)
from apeSteel.core import units as u

_W = DoublySymmetricISection(
    flange_width_bf=300 * u.mm,
    flange_thickness_tf=20 * u.mm,
    web_clear_height_hw=400 * u.mm,
    web_thickness_tw=16 * u.mm,
)
_BR = Bracing(
    unbraced_length_top_flange_Lb_top=4.0 * u.m,
    unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
    lateral_torsional_buckling_modification_factor_Cb=1.0,
)


def test_element_H1_matches_free_function_with_chapter_E_and_F_inputs() -> None:
    el = _W.element(material=A992, bracing=_BR)
    pr = 600.0e3
    mrx = 120.0e6

    compression = el.compression_strength(1.0, 4.0 * u.m, 1.0, 4.0 * u.m, 1.0, 4.0 * u.m)
    beam = el.run_full_check()
    expected = compute_combined_strength_H1_1(
        required_axial_Pr=pr,
        available_axial_Pc=compression.phi_strength_LRFD,
        required_moment_x_Mrx=mrx,
        available_moment_x_Mcx=beam.governing_flexural_phi_Mn,
    )

    via_element = el.combined_strength_H1(
        pr,
        mrx,
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
    )

    assert via_element.governing_equation == expected.governing_equation
    assert math.isclose(
        via_element.demand_capacity_ratio,
        expected.demand_capacity_ratio,
        rel_tol=1e-12,
    )
    assert math.isclose(
        via_element.available_axial_Pc, compression.phi_strength_LRFD, rel_tol=1e-12
    )
    assert math.isclose(
        via_element.available_moment_x_Mcx,
        beam.governing_flexural_phi_Mn,
        rel_tol=1e-12,
    )
    assert via_element.phi_LRFD == 1.0


def test_element_H1_biaxial_auto_resolves_Mcy_from_F6() -> None:
    """Phase F-8: biaxial with no explicit Mcy auto-resolves from §F6.

    Closes the design-note-09 H-7 gap.  Pre-F-8 this raised
    ``ValueError`` (apeSteel had no §F6); §F6 shipped in F-4, so the
    ``Element`` facade now auto-resolves ``Mcy = phi_b*Mny`` from the
    DS-I §F6 minor-axis strength.  Verify the facade feeds exactly that
    §F6 ``phi*Mn`` to the pure §H1.1 kernel.
    """
    el = _W.element(material=A992, bracing=_BR)
    pr = 500.0e3
    mrx = 100.0e6
    mry = 40.0e6

    f6 = compute_flexural_strength_F6_minor_axis(
        el.section_properties,
        A992,
        section_kind="doubly_symmetric_I",
        construction="welded",
    )
    compression = el.compression_strength(1.0, 4.0 * u.m, 1.0, 4.0 * u.m, 1.0, 4.0 * u.m)
    beam = el.run_full_check()
    expected = compute_combined_strength_H1_1(
        required_axial_Pr=pr,
        available_axial_Pc=compression.phi_strength_LRFD,
        required_moment_x_Mrx=mrx,
        available_moment_x_Mcx=beam.governing_flexural_phi_Mn,
        required_moment_y_Mry=mry,
        available_moment_y_Mcy=f6.phi_strength_LRFD,
    )

    via_element = el.combined_strength_H1(
        pr,
        mrx,
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
        required_moment_y_Mry=mry,
    )

    assert via_element.governing_equation == expected.governing_equation
    assert math.isclose(
        via_element.demand_capacity_ratio,
        expected.demand_capacity_ratio,
        rel_tol=1e-12,
    )
    assert math.isclose(via_element.available_moment_y_Mcy, f6.phi_strength_LRFD, rel_tol=1e-12)


def test_element_H1_biaxial_explicit_Mcy_is_used_verbatim() -> None:
    """An explicitly-supplied Mcy is still used unchanged (bit-identical).

    The F-8 auto-Mcy resolution must only fire when *no* Mcy is given;
    an explicit Mcy is forwarded verbatim - the prior behaviour, so the
    §F6 path is never invoked and the result is the pure-kernel value
    on the caller's own Mcy.
    """
    el = _W.element(material=A992, bracing=_BR)
    pr = 500.0e3
    mrx = 100.0e6
    mry = 40.0e6
    explicit_mcy = 99.0e6  # NOT the §F6 value - must be used as-is

    compression = el.compression_strength(1.0, 4.0 * u.m, 1.0, 4.0 * u.m, 1.0, 4.0 * u.m)
    beam = el.run_full_check()
    expected = compute_combined_strength_H1_1(
        required_axial_Pr=pr,
        available_axial_Pc=compression.phi_strength_LRFD,
        required_moment_x_Mrx=mrx,
        available_moment_x_Mcx=beam.governing_flexural_phi_Mn,
        required_moment_y_Mry=mry,
        available_moment_y_Mcy=explicit_mcy,
    )
    via_element = el.combined_strength_H1(
        pr,
        mrx,
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
        required_moment_y_Mry=mry,
        available_moment_y_Mcy=explicit_mcy,
    )
    assert math.isclose(via_element.available_moment_y_Mcy, explicit_mcy, rel_tol=1e-12)
    assert math.isclose(
        via_element.demand_capacity_ratio,
        expected.demand_capacity_ratio,
        rel_tol=1e-12,
    )


def test_element_H1_singly_symmetric_guarded() -> None:
    from apeSteel import SinglySymmetricISection  # noqa: PLC0415

    ss = SinglySymmetricISection(
        top_flange_width_bf_top=200 * u.mm,
        top_flange_thickness_tf_top=12 * u.mm,
        bot_flange_width_bf_bot=300 * u.mm,
        bot_flange_thickness_tf_bot=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=12 * u.mm,
    )
    el = ss.element(material=A992, bracing=_BR)
    with pytest.raises(NotImplementedError, match="combined_strength_H1"):
        el.combined_strength_H1(
            100.0e3,
            50.0e6,
            effective_length_factor_Kx=1.0,
            unbraced_length_Lx=4.0 * u.m,
            effective_length_factor_Ky=1.0,
            unbraced_length_Ly=4.0 * u.m,
            effective_length_factor_Kz=1.0,
            unbraced_length_Lz=4.0 * u.m,
        )

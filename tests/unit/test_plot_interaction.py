"""Smoke tests for the §H1.1 interaction-diagram plotters."""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from apeSteel import A992, DoublySymmetricISection  # noqa: E402
from apeSteel.bracing import Bracing  # noqa: E402
from apeSteel.core import units as u  # noqa: E402
from apeSteel.combined._common import (  # noqa: E402
    H1_1A_MOMENT_FACTOR,
    H1_1B_AXIAL_DIVISOR,
    H1_AXIAL_RATIO_BREAK,
)
from apeSteel.plotting.interaction import (  # noqa: E402
    _pm_envelope_vertices,
    _unity_H1_1,
    plot_mm_interaction,
    plot_pm_interaction,
    plot_pmm_interaction_3d,
)

_W = DoublySymmetricISection(
    flange_width_bf=300 * u.mm,
    flange_thickness_tf=20 * u.mm,
    web_clear_height_hw=400 * u.mm,
    web_thickness_tw=16 * u.mm,
)
_BRACING = Bracing(0.001 * u.m, 4.0 * u.m, 1.0)
_BC = dict(
    unbraced_length_Lx=4.0 * u.m,
    unbraced_length_Ly=4.0 * u.m,
    unbraced_length_Lz=4.0 * u.m,
    lateral_torsional_buckling_modification_factor_Cb=1.0,
)


@pytest.fixture
def element():
    return _W.element(material=A992, bracing=_BRACING)


@pytest.fixture
def element_no_bracing():
    return _W.element(material=A992)


@pytest.fixture
def fig_ax():
    fig, ax = plt.subplots()
    yield fig, ax
    plt.close(fig)


# ---------------------------------------------------------------------------
# Envelope geometry sanity
# ---------------------------------------------------------------------------
def test_pm_envelope_vertices_are_bilinear() -> None:
    Mxs, Ps = _pm_envelope_vertices(1000.0, 200.0)
    # Three vertices: (0, Pc), kink at (0.9*Mcx, 0.2*Pc), (Mcx, 0).
    assert Mxs == [0.0, 0.9 * 200.0, 200.0]
    assert Ps == [1000.0, 0.2 * 1000.0, 0.0]


def test_unity_continuity_at_break() -> None:
    # On the boundary at Pr/Pc = 0.2, both equations should match.
    Pc, Mcx = 1000.0, 200.0
    Pr = H1_AXIAL_RATIO_BREAK * Pc
    # Mrx that satisfies H1-1a at the break point: 0.2 + (8/9)*x = 1.
    Mrx_a = (1.0 - H1_AXIAL_RATIO_BREAK) / H1_1A_MOMENT_FACTOR * Mcx
    # Same Mrx via H1-1b: 0.1 + Mrx/Mcx = 1 -> Mrx = 0.9*Mcx.
    Mrx_b = (1.0 - Pr / (H1_1B_AXIAL_DIVISOR * Pc)) * Mcx
    assert abs(Mrx_a - Mrx_b) < 1e-9
    # Unity at this point should be exactly 1.0.
    assert abs(_unity_H1_1(Pr, Mrx_a, 0.0, Pc, Mcx, 1.0) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# plot_pm_interaction
# ---------------------------------------------------------------------------
def test_pm_returns_axes(element) -> None:
    ax = plot_pm_interaction(element, **_BC)
    assert isinstance(ax, matplotlib.axes.Axes)
    plt.close(ax.figure)


def test_pm_ax_passthrough(element, fig_ax) -> None:
    _, ax = fig_ax
    assert plot_pm_interaction(element, ax=ax, **_BC) is ax


def test_pm_which_both_draws_two_envelopes(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_pm_interaction(element, ax=ax, which="both", **_BC)
    assert len(ax.lines) == 2


def test_pm_normalized_axis_labels(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_pm_interaction(element, ax=ax, normalized=True, **_BC)
    assert "Mcx" in ax.get_xlabel()
    assert "Pc" in ax.get_ylabel()


def test_pm_fill_adds_polygon(element, fig_ax) -> None:
    _, ax = fig_ax
    before = len(ax.patches)
    plot_pm_interaction(element, ax=ax, fill=True, **_BC)
    assert len(ax.patches) > before


def test_pm_demand_inside_is_green_outside_is_red(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_pm_interaction(
        element,
        ax=ax,
        demand_points=[
            (10 * u.kN, 10 * u.kN * u.m, "tiny"),         # well inside
            (10_000 * u.kN, 10_000 * u.kN * u.m, "huge"),  # way outside
        ],
        **_BC,
    )
    # Demand markers are the only lines with a single (x, y) point.
    point_colors = [
        line.get_color()
        for line in ax.lines
        if len(line.get_xdata()) == 1
    ]
    assert "tab:green" in point_colors
    assert "tab:red" in point_colors


def test_pm_requires_bracing_or_params(element_no_bracing) -> None:
    with pytest.raises(ValueError, match="Lb_top / Lb_bot are required"):
        plot_pm_interaction(element_no_bracing, **_BC)


def test_pm_explicit_Lb_overrides_bracing(element, fig_ax) -> None:
    _, ax = fig_ax
    # Passing Lb explicitly should work even when bracing is set.
    plot_pm_interaction(
        element,
        ax=ax,
        unbraced_length_top_flange_Lb_top=0.5 * u.m,
        unbraced_length_bot_flange_Lb_bot=0.5 * u.m,
        **_BC,
    )
    assert len(ax.lines) >= 1


# ---------------------------------------------------------------------------
# plot_mm_interaction
# ---------------------------------------------------------------------------
def test_mm_returns_axes(element) -> None:
    ax = plot_mm_interaction(element, axial_load_Pr=500 * u.kN, **_BC)
    assert isinstance(ax, matplotlib.axes.Axes)
    plt.close(ax.figure)


def test_mm_rhombus_shrinks_with_axial(element, fig_ax) -> None:
    _, ax_low = fig_ax
    fig2, ax_high = plt.subplots()
    try:
        plot_mm_interaction(element, ax=ax_low, axial_load_Pr=100 * u.kN, **_BC)
        plot_mm_interaction(element, ax=ax_high, axial_load_Pr=1500 * u.kN, **_BC)
        # Compare envelope x-extents (line 0 has 5 closed verts).
        low_extent = max(ax_low.lines[0].get_xdata())
        high_extent = max(ax_high.lines[0].get_xdata())
        assert low_extent > high_extent
    finally:
        plt.close(fig2)


def test_mm_normalized_labels(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_mm_interaction(element, ax=ax, axial_load_Pr=500 * u.kN, normalized=True, **_BC)
    assert "Mcx" in ax.get_xlabel()
    assert "Mcy" in ax.get_ylabel()


# ---------------------------------------------------------------------------
# plot_pmm_interaction_3d
# ---------------------------------------------------------------------------
def test_3d_returns_3d_axes(element) -> None:
    ax = plot_pmm_interaction_3d(element, **_BC)
    assert type(ax).__name__ == "Axes3D"
    plt.close(ax.figure)


def test_3d_with_demand_points(element) -> None:
    ax = plot_pmm_interaction_3d(
        element,
        demand_points=[
            (100 * u.kN, 50 * u.kN * u.m, 10 * u.kN * u.m, "inside"),
            (5000 * u.kN, 500 * u.kN * u.m, 200 * u.kN * u.m, "outside"),
        ],
        **_BC,
    )
    # The Poly3DCollection envelope (1 collection) + 2 scatter point collections.
    assert len(ax.collections) >= 3
    plt.close(ax.figure)


# ---------------------------------------------------------------------------
# Element delegates
# ---------------------------------------------------------------------------
def test_element_pm_delegate_matches(element, fig_ax) -> None:
    _, ax_a = fig_ax
    fig_b, ax_b = plt.subplots()
    try:
        plot_pm_interaction(element, ax=ax_a, **_BC)
        element.plot_pm_interaction(ax=ax_b, **_BC)
        assert len(ax_a.lines) == len(ax_b.lines)
    finally:
        plt.close(fig_b)


def test_element_mm_delegate(element, fig_ax) -> None:
    _, ax = fig_ax
    returned = element.plot_mm_interaction(ax=ax, axial_load_Pr=500 * u.kN, **_BC)
    assert returned is ax


def test_element_3d_delegate(element) -> None:
    ax = element.plot_pmm_interaction_3d(**_BC)
    assert type(ax).__name__ == "Axes3D"
    plt.close(ax.figure)

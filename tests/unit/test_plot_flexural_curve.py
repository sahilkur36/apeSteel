# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false, reportPrivateUsage=false
"""Smoke tests for ``apeSteel.plotting.flexure.plot_flexural_curve``.

Mirrors the compression-plotter smoke suite, plus a landmarks test.
"""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from apeSteel import A992, DoublySymmetricISection  # noqa: E402
from apeSteel.core import units as u  # noqa: E402
from apeSteel.plotting.flexure import plot_flexural_curve  # noqa: E402

_W = DoublySymmetricISection(
    flange_width_bf=300 * u.mm,
    flange_thickness_tf=20 * u.mm,
    web_clear_height_hw=400 * u.mm,
    web_thickness_tw=16 * u.mm,
)
# Sweep covers plastic plateau (Lb<Lp), inelastic LTB, and elastic LTB.
_LBS = [Lb * u.m for Lb in (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0)]


@pytest.fixture
def element():
    return _W.element(material=A992)


@pytest.fixture
def fig_ax():
    fig, ax = plt.subplots()
    yield fig, ax
    plt.close(fig)


def test_returns_axes_when_ax_is_none(element) -> None:
    ax = plot_flexural_curve(element, _LBS)
    assert isinstance(ax, matplotlib.axes.Axes)
    plt.close(ax.figure)


def test_passing_ax_returns_same_ax(element, fig_ax) -> None:
    _, ax = fig_ax
    returned = plot_flexural_curve(element, _LBS, ax=ax)
    assert returned is ax


def test_xscale_log(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(element, _LBS, ax=ax, xscale="log")
    assert ax.get_xscale() == "log"


def test_xscale_linear_default(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(element, _LBS, ax=ax)
    assert ax.get_xscale() == "linear"


def test_overlay_two_elements_one_axes(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(element, _LBS, ax=ax, label="A")
    plot_flexural_curve(element, _LBS, ax=ax, label="B")
    assert len(ax.lines) == 2


def test_which_both_adds_two_lines(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(element, _LBS, ax=ax, which="both")
    assert len(ax.lines) == 2


def test_fill_adds_collection(element, fig_ax) -> None:
    _, ax = fig_ax
    before = len(ax.collections)
    plot_flexural_curve(element, _LBS, ax=ax, fill=True)
    assert len(ax.collections) == before + 1


def test_project_lengths_bare_floats(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(element, _LBS, ax=ax, project_lengths=[3.0 * u.m, 6.0 * u.m])
    # main curve + 2 markers + 2 axvline.
    assert len(ax.lines) == 1 + 2 + 2


def test_project_lengths_tuples_with_labels(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(
        element,
        _LBS,
        ax=ax,
        project_lengths=[(3.0 * u.m, "L1"), (6.0 * u.m, "L2")],
    )
    texts = [t.get_text() for t in ax.texts]
    assert any("L1" in t for t in texts)
    assert any("L2" in t for t in texts)


def test_color_by_limit_state_segments(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(element, _LBS, ax=ax, color_by_limit_state=True)
    # Sweep crosses yielding -> inelastic_LTB -> elastic_LTB.
    assert len(ax.lines) >= 2


def test_show_landmarks_draws_Lp_and_Lr(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(element, _LBS, ax=ax, show_landmarks=True)
    # 1 main curve + 2 axvline (Lp + Lr).
    assert len(ax.lines) == 1 + 2
    texts = [t.get_text() for t in ax.texts]
    assert "Lp" in texts
    assert "Lr" in texts


def test_custom_units_in_axis_labels(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(
        element,
        _LBS,
        ax=ax,
        length_unit=(u.ft, "ft"),
        moment_unit=(u.kip * u.ft, "kip·ft"),
    )
    assert "ft" in ax.get_xlabel()
    assert "kip" in ax.get_ylabel()


def test_too_few_lbs_raises(element) -> None:
    with pytest.raises(ValueError, match="at least two"):
        plot_flexural_curve(element, [3.0 * u.m])


def test_element_facade_method_matches_module_function(element, fig_ax) -> None:
    _, ax_a = fig_ax
    fig_b, ax_b = plt.subplots()
    try:
        plot_flexural_curve(element, _LBS, ax=ax_a)
        element.plot_flexural_curve(_LBS, ax=ax_b)
        assert len(ax_a.lines) == len(ax_b.lines)
        y_a = ax_a.lines[0].get_ydata()
        y_b = ax_b.lines[0].get_ydata()
        assert list(y_a) == list(y_b)
    finally:
        plt.close(fig_b)


def test_Cb_changes_curve(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_flexural_curve(
        element,
        _LBS,
        ax=ax,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
        label="Cb=1.0",
    )
    plot_flexural_curve(
        element,
        _LBS,
        ax=ax,
        lateral_torsional_buckling_modification_factor_Cb=1.67,
        label="Cb=1.67",
    )
    # Cb>1 boosts the inelastic-LTB regime, so the second curve sits
    # above (or equal to) the first at every Lb in the LTB range.
    y_low = ax.lines[0].get_ydata()
    y_high = ax.lines[1].get_ydata()
    assert all(b >= a - 1e-9 for a, b in zip(y_low, y_high, strict=True))

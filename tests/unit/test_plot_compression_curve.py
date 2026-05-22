"""Smoke tests for ``apeSteel.plotting.compression.plot_compression_curve``.

These verify wiring (ax pass-through, xscale, label, projections) but
not pixel-level rendering — that's matplotlib's job.
"""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")  # headless backend for CI / no-display envs
import matplotlib.pyplot as plt  # noqa: E402

from apeSteel import A992, DoublySymmetricISection  # noqa: E402
from apeSteel.core import units as u  # noqa: E402
from apeSteel.plotting.compression import plot_compression_curve  # noqa: E402

_W = DoublySymmetricISection(
    flange_width_bf=300 * u.mm,
    flange_thickness_tf=20 * u.mm,
    web_clear_height_hw=400 * u.mm,
    web_thickness_tw=16 * u.mm,
)
_LENGTHS = [L * u.m for L in (1.0, 2.0, 3.0, 5.0, 8.0, 12.0)]


@pytest.fixture
def element():
    return _W.element(material=A992)


@pytest.fixture
def fig_ax():
    fig, ax = plt.subplots()
    yield fig, ax
    plt.close(fig)


def test_returns_axes_when_ax_is_none(element) -> None:
    ax = plot_compression_curve(element, _LENGTHS)
    assert isinstance(ax, matplotlib.axes.Axes)
    plt.close(ax.figure)


def test_passing_ax_returns_same_ax(element, fig_ax) -> None:
    _, ax = fig_ax
    returned = plot_compression_curve(element, _LENGTHS, ax=ax)
    assert returned is ax


def test_xscale_log(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(element, _LENGTHS, ax=ax, xscale="log")
    assert ax.get_xscale() == "log"


def test_xscale_linear_default(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(element, _LENGTHS, ax=ax)
    assert ax.get_xscale() == "linear"


def test_overlay_two_elements_one_axes(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(element, _LENGTHS, ax=ax, label="W-300")
    plot_compression_curve(element, _LENGTHS, ax=ax, label="W-300 again")
    assert len(ax.lines) == 2


def test_which_both_adds_two_lines(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(element, _LENGTHS, ax=ax, which="both")
    assert len(ax.lines) == 2


def test_fill_adds_collection(element, fig_ax) -> None:
    _, ax = fig_ax
    before = len(ax.collections)
    plot_compression_curve(element, _LENGTHS, ax=ax, fill=True)
    assert len(ax.collections) == before + 1


def test_project_lengths_bare_floats(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(
        element,
        _LENGTHS,
        ax=ax,
        project_lengths=[3.0 * u.m, 6.0 * u.m],
    )
    # 1 main curve + 2 projection markers, plus 2 axvline lines.
    assert len(ax.lines) == 1 + 2 + 2


def test_project_lengths_tuples_with_labels(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(
        element,
        _LENGTHS,
        ax=ax,
        project_lengths=[(3.0 * u.m, "L1"), (6.0 * u.m, "L2")],
    )
    texts = [t.get_text() for t in ax.texts]
    assert any("L1" in t for t in texts)
    assert any("L2" in t for t in texts)


def test_color_by_limit_state_does_not_crash(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(element, _LENGTHS, ax=ax, color_by_limit_state=True)
    assert len(ax.lines) >= 1


def test_custom_units_in_axis_labels(element, fig_ax) -> None:
    _, ax = fig_ax
    plot_compression_curve(
        element,
        _LENGTHS,
        ax=ax,
        length_unit=(u.ft, "ft"),
        force_unit=(u.kip, "kip"),
    )
    assert "ft" in ax.get_xlabel()
    assert "kip" in ax.get_ylabel()


def test_too_few_lengths_raises(element) -> None:
    with pytest.raises(ValueError, match="at least two"):
        plot_compression_curve(element, [3.0 * u.m])


def test_element_facade_method_matches_module_function(element, fig_ax) -> None:
    _, ax_a = fig_ax
    fig_b, ax_b = plt.subplots()
    try:
        plot_compression_curve(element, _LENGTHS, ax=ax_a)
        element.plot_compression_curve(_LENGTHS, ax=ax_b)
        # Same number of artists -> wiring is equivalent.
        assert len(ax_a.lines) == len(ax_b.lines)
        # And the y-data on the main φPn line matches exactly.
        y_a = ax_a.lines[0].get_ydata()
        y_b = ax_b.lines[0].get_ydata()
        assert list(y_a) == list(y_b)
    finally:
        plt.close(fig_b)

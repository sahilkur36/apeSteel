"""Strength-vs-length capacity-curve plot for compression members.

Consumes :meth:`apeSteel.element.Element.phi_Pn_vs_length` (and a
per-projection call to :meth:`Element.compression_strength` for any
projected lengths) and draws the AISC 360-22 Chapter-E capacity curve
on a :class:`matplotlib.axes.Axes`.

Design notes
------------
* matplotlib is imported lazily inside the function so the rest of
  apeSteel runs without it.  Install with ``pip install
  "apeSteel[plot]"`` to enable.
* Lengths are passed in apeSteel's base unit (mm); the x-axis is
  rescaled to ``length_unit`` for display.  Same for force / y-axis.
  The ``(value, label)`` tuple convention matches
  :data:`apeSteel.core.units.CANONICAL_DISPLAY_UNITS`.
* ``ax=None`` creates a new ``Figure`` + ``Axes``; passing an existing
  ``Axes`` lets callers overlay multiple curves.  The function always
  returns the ``Axes`` so it composes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from apeSteel.core.units import kN, m

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.axes import Axes

    from apeSteel.element import Element


LengthProjection = float | tuple[float, str]
"""Either a bare length (mm) or ``(length_mm, label)``."""


_LIMIT_STATE_COLORS: dict[str, str] = {
    "flexural_buckling": "tab:blue",
    "torsional_buckling": "tab:orange",
    "flexural_torsional_buckling": "tab:green",
    "single_angle_flexural": "tab:purple",
}


def _import_matplotlib() -> tuple[object, object]:
    try:
        import matplotlib.pyplot as plt  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "apeSteel.plotting requires matplotlib. "
            'Install with: pip install "apeSteel[plot]"'
        ) from exc
    return plt, plt


def plot_compression_curve(
    element: Element,
    lengths_L: Sequence[float],
    *,
    effective_length_factor_Kx: float = 1.0,
    effective_length_factor_Ky: float = 1.0,
    effective_length_factor_Kz: float = 1.0,
    ax: Axes | None = None,
    xscale: Literal["linear", "log"] = "linear",
    length_unit: tuple[float, str] = (m, "m"),
    force_unit: tuple[float, str] = (kN, "kN"),
    which: Literal["phi_Pn", "Pn", "both"] = "phi_Pn",
    fill: bool = False,
    color_by_limit_state: bool = False,
    project_lengths: Sequence[LengthProjection] | None = None,
    label: str | None = None,
    **line_kwargs: object,
) -> Axes:
    """Plot the AISC 360-22 Chapter-E strength-vs-length curve.

    Parameters
    ----------
    element
        The :class:`apeSteel.element.Element` to plot.  Must be a
        doubly-symmetric I (the same restriction as
        :meth:`Element.phi_Pn_vs_length`).
    lengths_L
        Member lengths in **mm** (base units).  Build with
        ``np.linspace(0.5*m, 12*m, 200)`` or ``np.logspace(...)``.
    effective_length_factor_Kx, _Ky, _Kz
        Per-axis effective-length factors (default ``1.0``, the DAM
        value).  ``Lc_i = K_i * L`` is formed at every length.
    ax
        Existing axes to draw on; if ``None`` a new figure/axes is
        created.  Always returned so callers can chain overlays.
    xscale
        ``"linear"`` (default) or ``"log"``.
    length_unit, force_unit
        ``(value_in_base_units, label)`` tuples used to rescale the
        axes for display.  Defaults: ``(m, "m")`` and ``(kN, "kN")``.
    which
        ``"phi_Pn"`` (default), ``"Pn"``, or ``"both"``.
    fill
        Shade the region under the design curve (``which="phi_Pn"`` or
        ``"both"``) or under the nominal curve (``"Pn"``).  When
        ``which="both"``, the band between Pn and φPn is shaded.
    color_by_limit_state
        Segment-color the curve by governing limit state.  Useful for
        spotting where torsional / FTB transitions kick in.  Adds one
        legend entry per limit state observed.  Off by default.
    project_lengths
        Specific lengths to mark on the curve.  Each entry is either a
        bare length in **mm** or a ``(length_mm, label)`` tuple.  Each
        projection draws a vertical guide, a marker on the curve, and
        an annotation with the value.
    label
        Legend label for the main curve.  Required if ``ax`` already
        contains other curves and you want a meaningful legend.
    **line_kwargs
        Forwarded to ``ax.plot`` (``color``, ``linestyle``,
        ``linewidth``, ``alpha``, ``marker``, ...).  Ignored when
        ``color_by_limit_state=True`` for the ``color`` key.
    """
    plt, _ = _import_matplotlib()

    if ax is None:
        _, ax = plt.subplots()  # type: ignore[attr-defined]

    if len(lengths_L) < 2:
        raise ValueError("lengths_L must contain at least two points.")

    length_scale, length_label = length_unit
    force_scale, force_label = force_unit

    points = element.phi_Pn_vs_length(
        lengths_L=lengths_L,
        effective_length_factor_Kx=effective_length_factor_Kx,
        effective_length_factor_Ky=effective_length_factor_Ky,
        effective_length_factor_Kz=effective_length_factor_Kz,
    )

    L_disp = [p.length_L / length_scale for p in points]
    Pn_disp = [p.nominal_strength_Pn / force_scale for p in points]
    phi_Pn_disp = [p.design_strength_phi_Pn / force_scale for p in points]
    limit_states = [p.governing_limit_state for p in points]

    # ---- main curve(s) ------------------------------------------------
    if color_by_limit_state:
        _plot_segmented_by_state(
            ax=ax,
            L_disp=L_disp,
            phi_Pn_disp=phi_Pn_disp,
            Pn_disp=Pn_disp,
            which=which,
            limit_states=limit_states,
            base_label=label,
            line_kwargs=line_kwargs,
        )
    else:
        if which in ("phi_Pn", "both"):
            phi_label = label if which == "phi_Pn" else _suffix(label, "φPn")
            ax.plot(L_disp, phi_Pn_disp, label=phi_label, **line_kwargs)
        if which in ("Pn", "both"):
            pn_label = label if which == "Pn" else _suffix(label, "Pn")
            pn_kwargs = dict(line_kwargs)
            pn_kwargs.setdefault("linestyle", "--")
            ax.plot(L_disp, Pn_disp, label=pn_label, **pn_kwargs)

    # ---- fill ---------------------------------------------------------
    if fill:
        fill_color = line_kwargs.get("color")
        fill_alpha = 0.15
        if which == "both":
            ax.fill_between(
                L_disp,
                phi_Pn_disp,
                Pn_disp,
                color=fill_color,
                alpha=fill_alpha,
            )
        elif which == "phi_Pn":
            ax.fill_between(L_disp, 0.0, phi_Pn_disp, color=fill_color, alpha=fill_alpha)
        else:  # "Pn"
            ax.fill_between(L_disp, 0.0, Pn_disp, color=fill_color, alpha=fill_alpha)

    # ---- projections --------------------------------------------------
    if project_lengths:
        _draw_projections(
            ax=ax,
            element=element,
            projections=project_lengths,
            length_scale=length_scale,
            force_scale=force_scale,
            force_label=force_label,
            which=which,
            Kx=effective_length_factor_Kx,
            Ky=effective_length_factor_Ky,
            Kz=effective_length_factor_Kz,
        )

    # ---- decorations --------------------------------------------------
    ax.set_xscale(xscale)
    ax.set_xlabel(f"L ({length_label})")
    ax.set_ylabel(f"Compressive strength ({force_label})")
    ax.set_ylim(bottom=0.0)
    ax.grid(True, which="both", alpha=0.3)

    return ax


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _suffix(base: str | None, tag: str) -> str:
    return f"{base} ({tag})" if base else tag


def _plot_segmented_by_state(
    *,
    ax: Axes,
    L_disp: list[float],
    phi_Pn_disp: list[float],
    Pn_disp: list[float],
    which: Literal["phi_Pn", "Pn", "both"],
    limit_states: list[str],
    base_label: str | None,
    line_kwargs: dict[str, object],
) -> None:
    """Draw the curve as colored segments grouped by governing limit state.

    Consecutive points sharing the same limit state become one ``plot``
    call; transition points are duplicated into both adjacent segments
    so the line is visually continuous.  One legend entry per distinct
    limit state is emitted.
    """
    # Strip color from line_kwargs (we own it for segmentation).
    segment_kwargs = {k: v for k, v in line_kwargs.items() if k != "color"}

    series_for_which: list[tuple[list[float], str | None, dict[str, object]]] = []
    if which in ("phi_Pn", "both"):
        series_for_which.append((phi_Pn_disp, base_label, {}))
    if which in ("Pn", "both"):
        pn_extra = {"linestyle": segment_kwargs.get("linestyle", "--")}
        pn_label = _suffix(base_label, "Pn") if which == "both" else base_label
        series_for_which.append((Pn_disp, pn_label, pn_extra))

    for ys, ys_label, extra in series_for_which:
        seen_states: set[str] = set()
        i = 0
        n = len(L_disp)
        while i < n:
            j = i
            while j + 1 < n and limit_states[j + 1] == limit_states[i]:
                j += 1
            # extend by one to bridge the transition visually
            end = min(n, j + 2)
            state = limit_states[i]
            color = _LIMIT_STATE_COLORS.get(state, "tab:gray")
            seg_label: str | None
            if state in seen_states:
                seg_label = None
            else:
                seen_states.add(state)
                pretty = state.replace("_", " ")
                seg_label = _suffix(ys_label, pretty) if ys_label else pretty
            kwargs = dict(segment_kwargs, **extra)
            kwargs.setdefault("color", color)
            ax.plot(L_disp[i:end], ys[i:end], label=seg_label, **kwargs)
            i = j + 1


def _draw_projections(
    *,
    ax: Axes,
    element: Element,
    projections: Sequence[LengthProjection],
    length_scale: float,
    force_scale: float,
    force_label: str,
    which: Literal["phi_Pn", "Pn", "both"],
    Kx: float,
    Ky: float,
    Kz: float,
) -> None:
    """Drop verticals + markers + annotations at the requested lengths."""
    for proj in projections:
        if isinstance(proj, tuple):
            L_mm, tag = proj
        else:
            L_mm, tag = proj, None

        report = element.compression_strength(
            effective_length_factor_Kx=Kx,
            unbraced_length_Lx=L_mm,
            effective_length_factor_Ky=Ky,
            unbraced_length_Ly=L_mm,
            effective_length_factor_Kz=Kz,
            unbraced_length_Lz=L_mm,
        )
        L_disp = L_mm / length_scale
        phi_Pn = report.phi_strength_LRFD / force_scale
        Pn = report.nominal_compressive_strength_Pn / force_scale

        # primary y is φPn unless caller is only showing Pn
        y_primary = Pn if which == "Pn" else phi_Pn
        y_label_quantity = "Pn" if which == "Pn" else "φPn"

        ax.axvline(L_disp, color="gray", linestyle=":", alpha=0.5)
        ax.plot([L_disp], [y_primary], marker="o", color="black", markersize=5)
        annotation = (
            f"{tag}: {y_label_quantity} = {y_primary:.0f} {force_label}"
            if tag
            else f"{y_label_quantity} = {y_primary:.0f} {force_label}"
        )
        ax.annotate(
            annotation,
            xy=(L_disp, y_primary),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )


__all__ = ["LengthProjection", "plot_compression_curve"]

"""Strength-vs-Lb capacity-curve plot for flexural members.

Consumes :meth:`apeSteel.element.Element.phi_Mn_vs_Lb` and draws the
AISC 360-22 Chapter-F capacity curve.  Mirrors the structure of
:mod:`apeSteel.plotting.compression`; the differences are:

* x-axis is the unbraced length **Lb**, not the member length L.
* y-axis is moment, displayed in ``MOMENT_DISPLAY_UNIT_kN_m`` by
  default.
* ``Cb`` is a parameter (default 1.0) instead of an effective-length
  factor.
* ``show_landmarks=True`` adds vertical guides at **Lp** and **Lr**
  (taken from the first curve point — same for every Lb when
  classification doesn't change along the sweep).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from apeSteel.core.units import MOMENT_DISPLAY_UNIT_kN_m, m

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.axes import Axes

    from apeSteel.element import Element


LengthProjection = float | tuple[float, str]
"""Either a bare unbraced length (mm) or ``(Lb_mm, label)``."""


# Limit-state -> color.  Chapter-F regimes plus FLB / WLB tags.
_LIMIT_STATE_COLORS: dict[str, str] = {
    "yielding": "tab:blue",
    "inelastic_LTB": "tab:orange",
    "elastic_LTB": "tab:red",
    "flange_local_buckling": "tab:green",
    "web_local_buckling": "tab:olive",
    "compression_flange_yielding": "tab:purple",
    "tension_flange_yielding": "tab:brown",
}


def _import_matplotlib() -> object:
    try:
        import matplotlib.pyplot as plt  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "apeSteel.plotting requires matplotlib. "
            'Install with: pip install "apeSteel[plot]"'
        ) from exc
    return plt


def plot_flexural_curve(
    element: Element,
    unbraced_lengths_Lb: Sequence[float],
    *,
    lateral_torsional_buckling_modification_factor_Cb: float = 1.0,
    flange: Literal["top", "bot", "governing"] = "governing",
    ax: Axes | None = None,
    xscale: Literal["linear", "log"] = "linear",
    length_unit: tuple[float, str] = (m, "m"),
    moment_unit: tuple[float, str] = (MOMENT_DISPLAY_UNIT_kN_m, "kN·m"),
    which: Literal["phi_Mn", "Mn", "both"] = "phi_Mn",
    fill: bool = False,
    color_by_limit_state: bool = False,
    project_lengths: Sequence[LengthProjection] | None = None,
    show_landmarks: bool = False,
    label: str | None = None,
    **line_kwargs: object,
) -> Axes:
    """Plot the AISC 360-22 Chapter-F φMn-vs-Lb curve.

    Parameters
    ----------
    element
        The :class:`apeSteel.element.Element` to plot.  Must be an
        I-section (DS or SS); same restriction as
        :meth:`Element.phi_Mn_vs_Lb`.
    unbraced_lengths_Lb
        Unbraced lengths in **mm** (base units).  Symmetric sweep:
        ``Lb_top = Lb_bot = Lb`` at every point.
    lateral_torsional_buckling_modification_factor_Cb
        ``Cb`` per AISC F1-1.  Default 1.0.
    flange
        ``"top"``, ``"bot"``, or ``"governing"`` (default).
    ax
        Existing axes to draw on; if ``None`` a new figure/axes is
        created.  Always returned.
    xscale
        ``"linear"`` (default) or ``"log"``.
    length_unit, moment_unit
        ``(value_in_base_units, label)`` tuples for axis rescaling.
        Defaults: ``(m, "m")`` and ``(kN·m, "kN·m")``.
    which
        ``"phi_Mn"`` (default), ``"Mn"``, or ``"both"``.
    fill
        Shade under the curve (or between Mn and φMn when
        ``which="both"``).
    color_by_limit_state
        Segment-color by governing limit state (plastic plateau →
        inelastic LTB → elastic LTB, plus FLB/WLB tags where they
        apply).  One legend entry per distinct state.
    project_lengths
        Specific Lb values to mark.  Bare floats or ``(Lb, label)``
        tuples; mm.
    show_landmarks
        Draw vertical guides at **Lp** and **Lr** (read from the first
        curve point).  Lp/Lr depend only on geometry/material, so
        they're constant across the sweep.
    label
        Legend label for the main curve.
    **line_kwargs
        Forwarded to ``ax.plot``.
    """
    plt = _import_matplotlib()

    if ax is None:
        _, ax = plt.subplots()  # type: ignore[attr-defined]

    if len(unbraced_lengths_Lb) < 2:
        raise ValueError("unbraced_lengths_Lb must contain at least two points.")

    length_scale, length_label = length_unit
    moment_scale, moment_label = moment_unit

    points = element.phi_Mn_vs_Lb(
        unbraced_lengths_Lb=unbraced_lengths_Lb,
        lateral_torsional_buckling_modification_factor_Cb=(
            lateral_torsional_buckling_modification_factor_Cb
        ),
        flange=flange,
    )

    Lb_disp = [p.unbraced_length_Lb / length_scale for p in points]
    Mn_disp = [p.nominal_strength_Mn / moment_scale for p in points]
    phi_Mn_disp = [p.design_strength_phi_Mn / moment_scale for p in points]
    limit_states = [p.governing_limit_state for p in points]

    # ---- main curve(s) ------------------------------------------------
    if color_by_limit_state:
        _plot_segmented_by_state(
            ax=ax,
            x=Lb_disp,
            phi=phi_Mn_disp,
            nom=Mn_disp,
            which=which,
            limit_states=limit_states,
            base_label=label,
            line_kwargs=line_kwargs,
        )
    else:
        if which in ("phi_Mn", "both"):
            phi_label = label if which == "phi_Mn" else _suffix(label, "φMn")
            ax.plot(Lb_disp, phi_Mn_disp, label=phi_label, **line_kwargs)
        if which in ("Mn", "both"):
            mn_label = label if which == "Mn" else _suffix(label, "Mn")
            mn_kwargs = dict(line_kwargs)
            mn_kwargs.setdefault("linestyle", "--")
            ax.plot(Lb_disp, Mn_disp, label=mn_label, **mn_kwargs)

    # ---- fill ---------------------------------------------------------
    if fill:
        fill_color = line_kwargs.get("color")
        fill_alpha = 0.15
        if which == "both":
            ax.fill_between(
                Lb_disp,
                phi_Mn_disp,
                Mn_disp,
                color=fill_color,
                alpha=fill_alpha,
            )
        elif which == "phi_Mn":
            ax.fill_between(Lb_disp, 0.0, phi_Mn_disp, color=fill_color, alpha=fill_alpha)
        else:
            ax.fill_between(Lb_disp, 0.0, Mn_disp, color=fill_color, alpha=fill_alpha)

    # ---- landmarks (Lp / Lr) -----------------------------------------
    if show_landmarks and points:
        Lp_disp = points[0].limiting_length_plastic_Lp / length_scale
        Lr_disp = points[0].limiting_length_inelastic_LTB_Lr / length_scale
        for x_val, tag in ((Lp_disp, "Lp"), (Lr_disp, "Lr")):
            if x_val > 0.0:
                ax.axvline(x_val, color="gray", linestyle="-.", alpha=0.4)
                ax.annotate(
                    tag,
                    xy=(x_val, 0.0),
                    xytext=(2, 2),
                    textcoords="offset points",
                    fontsize=8,
                    color="gray",
                )

    # ---- projections --------------------------------------------------
    if project_lengths:
        _draw_projections(
            ax=ax,
            element=element,
            projections=project_lengths,
            length_scale=length_scale,
            moment_scale=moment_scale,
            moment_label=moment_label,
            which=which,
            Cb=lateral_torsional_buckling_modification_factor_Cb,
            flange=flange,
        )

    # ---- decorations --------------------------------------------------
    ax.set_xscale(xscale)
    ax.set_xlabel(f"Lb ({length_label})")
    ax.set_ylabel(f"Flexural strength ({moment_label})")
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
    x: list[float],
    phi: list[float],
    nom: list[float],
    which: Literal["phi_Mn", "Mn", "both"],
    limit_states: list[str],
    base_label: str | None,
    line_kwargs: dict[str, object],
) -> None:
    segment_kwargs = {k: v for k, v in line_kwargs.items() if k != "color"}

    series: list[tuple[list[float], str | None, dict[str, object]]] = []
    if which in ("phi_Mn", "both"):
        series.append((phi, base_label, {}))
    if which in ("Mn", "both"):
        mn_extra = {"linestyle": segment_kwargs.get("linestyle", "--")}
        mn_label = _suffix(base_label, "Mn") if which == "both" else base_label
        series.append((nom, mn_label, mn_extra))

    for ys, ys_label, extra in series:
        seen_states: set[str] = set()
        i = 0
        n = len(x)
        while i < n:
            j = i
            while j + 1 < n and limit_states[j + 1] == limit_states[i]:
                j += 1
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
            ax.plot(x[i:end], ys[i:end], label=seg_label, **kwargs)
            i = j + 1


def _draw_projections(
    *,
    ax: Axes,
    element: Element,
    projections: Sequence[LengthProjection],
    length_scale: float,
    moment_scale: float,
    moment_label: str,
    which: Literal["phi_Mn", "Mn", "both"],
    Cb: float,
    flange: Literal["top", "bot", "governing"],
) -> None:
    """Drop verticals + markers + annotations at the requested Lb values."""
    Lbs_mm = [proj[0] if isinstance(proj, tuple) else proj for proj in projections]
    tags = [proj[1] if isinstance(proj, tuple) else None for proj in projections]

    pts = element.phi_Mn_vs_Lb(
        unbraced_lengths_Lb=Lbs_mm,
        lateral_torsional_buckling_modification_factor_Cb=Cb,
        flange=flange,
    )

    for Lb_mm, tag, point in zip(Lbs_mm, tags, pts, strict=True):
        Lb_disp = Lb_mm / length_scale
        phi_Mn = point.design_strength_phi_Mn / moment_scale
        Mn = point.nominal_strength_Mn / moment_scale

        y_primary = Mn if which == "Mn" else phi_Mn
        y_label_quantity = "Mn" if which == "Mn" else "φMn"

        ax.axvline(Lb_disp, color="gray", linestyle=":", alpha=0.5)
        ax.plot([Lb_disp], [y_primary], marker="o", color="black", markersize=5)
        annotation = (
            f"{tag}: {y_label_quantity} = {y_primary:.1f} {moment_label}"
            if tag
            else f"{y_label_quantity} = {y_primary:.1f} {moment_label}"
        )
        ax.annotate(
            annotation,
            xy=(Lb_disp, y_primary),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )


__all__ = ["LengthProjection", "plot_flexural_curve"]

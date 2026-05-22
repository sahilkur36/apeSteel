"""AISC 360-22 §H1.1 interaction-diagram plots.

Three views of the P-Mx-My envelope:

* :func:`plot_pm_interaction` — 2D uniaxial P vs Mx (Mry = 0).  The
  classical bilinear beam-column envelope.
* :func:`plot_mm_interaction` — 2D Mrx vs Mry at a fixed Pr (a slice
  through the 3D envelope at constant axial level).  Linear in
  normalized space, so the envelope is a rhombus.
* :func:`plot_pmm_interaction_3d` — full 3D envelope: a cone-frustum
  composite (apex at ``(0, 0, Pc)``, break rhombus at
  ``P = 0.2·Pc``, base rhombus at ``P = 0``).

All three resolve capacities the same way:

* ``Pc`` from :meth:`Element.compression_strength` (Chapter E).
* ``Mcx`` from :meth:`Element.run_full_check` (classification routes
  to F2/F3/F4/F5).
* ``Mcy`` from :func:`compute_flexural_strength_F6_minor_axis`
  (minor-axis flexure; only needed for M-M and 3D).

If ``Lb_top``/``Lb_bot``/``Cb`` are not supplied, they are read from
``element.bracing``.  If the element has no bracing and no params are
given, a clear ``ValueError`` is raised.

Restriction: doubly-symmetric I-sections only (same as
:meth:`Element.combined_strength_H1`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from apeSteel.combined._common import (
    H1_1A_MOMENT_FACTOR,
    H1_1B_AXIAL_DIVISOR,
    H1_AXIAL_RATIO_BREAK,
)
from apeSteel.core.units import MOMENT_DISPLAY_UNIT_kN_m, kN
from apeSteel.flexure import compute_flexural_strength_F6_minor_axis

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.axes import Axes

    from apeSteel.element import Element


Which = Literal["phi", "nominal", "both"]

PMDemand = tuple[float, float] | tuple[float, float, str]
"""(P, M) or (P, M, label).  Forces in N, moments in N·mm."""

MMDemand = tuple[float, float] | tuple[float, float, str]
"""(Mx, My) or (Mx, My, label).  Both in N·mm."""

PMMDemand = tuple[float, float, float] | tuple[float, float, float, str]
"""(P, Mx, My) or (P, Mx, My, label)."""


# ---------------------------------------------------------------------------
# Capacity resolution
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class _Capacities:
    """Available strengths used by every interaction-diagram view.

    Both nominal and phi-factored values are pre-computed so each
    plotter can pick ``which`` cheaply.
    """

    Pc_nominal: float
    Pc_phi: float
    Mcx_nominal: float
    Mcx_phi: float
    Mcy_nominal: float
    Mcy_phi: float


def _resolve_capacities(
    element: Element,
    *,
    Kx: float,
    Lx: float,
    Ky: float,
    Ly: float,
    Kz: float,
    Lz: float,
    Lb_top: float | None,
    Lb_bot: float | None,
    Cb: float,
    need_minor_axis: bool,
) -> _Capacities:
    """Resolve (Pc, Mcx, Mcy) at this element's as-built BCs.

    Mirrors :meth:`Element.combined_strength_H1` internals: Pc from
    Chapter E, Mcx from the routed Chapter-F engine (via
    ``run_full_check``), Mcy from §F6 minor-axis (only when needed).
    """
    from apeSteel.bracing import Bracing  # noqa: PLC0415
    from apeSteel.sections.geometry import DoublySymmetricISection  # noqa: PLC0415

    if not isinstance(element.section, DoublySymmetricISection):
        raise NotImplementedError(
            "Interaction-diagram plots are currently doubly-symmetric I only "
            "(same restriction as Element.combined_strength_H1)."
        )

    # Resolve bracing.  Lb_top/Lb_bot fall back to element.bracing when None;
    # Cb is always taken from the parameter (default 1.0) since it has a
    # sensible default and the caller can't ambiguously omit it.
    if Lb_top is None or Lb_bot is None:
        if element.bracing is None:
            raise ValueError(
                "Lb_top / Lb_bot are required when element.bracing is None. "
                "Either pass them explicitly or attach a Bracing first via "
                "element.with_bracing(Bracing(...))."
            )
        Lb_top_eff = (
            Lb_top
            if Lb_top is not None
            else element.bracing.unbraced_length_top_flange_Lb_top
        )
        Lb_bot_eff = (
            Lb_bot
            if Lb_bot is not None
            else element.bracing.unbraced_length_bot_flange_Lb_bot
        )
    else:
        Lb_top_eff = Lb_top
        Lb_bot_eff = Lb_bot
    Cb_eff = Cb

    # --- Pc (Chapter E) ------------------------------------------------
    compression = element.compression_strength(
        effective_length_factor_Kx=Kx,
        unbraced_length_Lx=Lx,
        effective_length_factor_Ky=Ky,
        unbraced_length_Ly=Ly,
        effective_length_factor_Kz=Kz,
        unbraced_length_Lz=Lz,
    )

    # --- Mcx (Chapter F via run_full_check) ----------------------------
    el_for_flexure = element.with_bracing(
        Bracing(
            unbraced_length_top_flange_Lb_top=Lb_top_eff,
            unbraced_length_bot_flange_Lb_bot=Lb_bot_eff,
            lateral_torsional_buckling_modification_factor_Cb=Cb_eff,
        )
    )
    beam_check = el_for_flexure.run_full_check()
    if beam_check.flexure_both_flanges is None:
        raise RuntimeError("run_full_check produced no flexure result")
    Mcx_nominal = beam_check.flexure_both_flanges.governing_report.nominal_strength
    Mcx_phi = beam_check.flexure_both_flanges.governing_report.phi_strength_LRFD

    # --- Mcy (§F6 minor-axis) — only if needed -------------------------
    if need_minor_axis:
        f6 = compute_flexural_strength_F6_minor_axis(
            element.section_properties,
            element.material,
            section_kind="doubly_symmetric_I",
            construction=element.construction,
        )
        Mcy_nominal = f6.nominal_strength
        Mcy_phi = f6.phi_strength_LRFD
    else:
        Mcy_nominal = 0.0
        Mcy_phi = 0.0

    return _Capacities(
        Pc_nominal=compression.nominal_compressive_strength_Pn,
        Pc_phi=compression.phi_strength_LRFD,
        Mcx_nominal=Mcx_nominal,
        Mcx_phi=Mcx_phi,
        Mcy_nominal=Mcy_nominal,
        Mcy_phi=Mcy_phi,
    )


# ---------------------------------------------------------------------------
# Envelope geometry
# ---------------------------------------------------------------------------
def _pm_envelope_vertices(Pc: float, Mcx: float) -> tuple[list[float], list[float]]:
    """Three vertices of the bilinear H1.1 P-Mx envelope.

    Returns ``(Mxs, Ps)``, in order: (0, Pc), (kink), (Mcx, 0).
    """
    # At Pr/Pc = 0.2 the H1-1b branch gives Mrx/Mcx = 1 - 0.1 = 0.9
    # (and H1-1a gives (9/8)*(1-0.2) = 0.9 — continuous).
    M_break = (1.0 - H1_AXIAL_RATIO_BREAK / H1_1B_AXIAL_DIVISOR) * Mcx
    P_break = H1_AXIAL_RATIO_BREAK * Pc
    return [0.0, M_break, Mcx], [Pc, P_break, 0.0]


def _mm_envelope_vertices_at_P(
    Pr: float, Pc: float, Mcx: float, Mcy: float
) -> tuple[list[float], list[float]]:
    """Rhombus of the H1.1 envelope at a fixed Pr (full ±Mx, ±My).

    Solves the H1.1 equation for the moment ratio sum:

    * Pr/Pc >= 0.2 → Mrx/Mcx + Mry/Mcy = (9/8)*(1 - Pr/Pc)
    * Pr/Pc <  0.2 → Mrx/Mcx + Mry/Mcy = 1 - Pr/(2*Pc)

    Result is a rhombus with vertices at (±Mx_max, 0) and (0, ±My_max);
    Mx_max = ratio_sum * Mcx.  Returns the four vertices closed
    (5 points) so the polygon can be plotted directly.
    """
    ratio = Pr / Pc if Pc > 0.0 else 0.0
    if ratio >= H1_AXIAL_RATIO_BREAK:
        moment_ratio_sum = (1.0 / H1_1A_MOMENT_FACTOR) * (1.0 - ratio)
    else:
        moment_ratio_sum = 1.0 - ratio / H1_1B_AXIAL_DIVISOR
    moment_ratio_sum = max(moment_ratio_sum, 0.0)
    Mx_max = moment_ratio_sum * Mcx
    My_max = moment_ratio_sum * Mcy
    xs = [Mx_max, 0.0, -Mx_max, 0.0, Mx_max]
    ys = [0.0, My_max, 0.0, -My_max, 0.0]
    return xs, ys


def _unity_H1_1(
    Pr: float, Mrx: float, Mry: float, Pc: float, Mcx: float, Mcy: float
) -> float:
    """Demand-to-capacity ratio per §H1.1 (no abs sign — caller passes magnitudes)."""
    if Pc <= 0.0:
        return float("inf")
    ratio_axial = abs(Pr) / Pc
    moment_term = (abs(Mrx) / Mcx if Mcx > 0.0 else 0.0) + (
        abs(Mry) / Mcy if Mcy > 0.0 else 0.0
    )
    if ratio_axial >= H1_AXIAL_RATIO_BREAK:
        return ratio_axial + H1_1A_MOMENT_FACTOR * moment_term
    return ratio_axial / H1_1B_AXIAL_DIVISOR + moment_term


# ---------------------------------------------------------------------------
# matplotlib lazy import
# ---------------------------------------------------------------------------
def _import_matplotlib() -> object:
    try:
        import matplotlib.pyplot as plt  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "apeSteel.plotting requires matplotlib. "
            'Install with: pip install "apeSteel[plot]"'
        ) from exc
    return plt


# ---------------------------------------------------------------------------
# 1. Uniaxial P-Mx
# ---------------------------------------------------------------------------
def plot_pm_interaction(
    element: Element,
    *,
    effective_length_factor_Kx: float = 1.0,
    unbraced_length_Lx: float,
    effective_length_factor_Ky: float = 1.0,
    unbraced_length_Ly: float,
    effective_length_factor_Kz: float = 1.0,
    unbraced_length_Lz: float,
    unbraced_length_top_flange_Lb_top: float | None = None,
    unbraced_length_bot_flange_Lb_bot: float | None = None,
    lateral_torsional_buckling_modification_factor_Cb: float = 1.0,
    ax: Axes | None = None,
    which: Which = "phi",
    normalized: bool = False,
    fill: bool = False,
    force_unit: tuple[float, str] = (kN, "kN"),
    moment_unit: tuple[float, str] = (MOMENT_DISPLAY_UNIT_kN_m, "kN·m"),
    demand_points: Sequence[PMDemand] | None = None,
    label: str | None = None,
    **line_kwargs: object,
) -> Axes:
    """Plot the uniaxial §H1.1 P-Mx interaction envelope.

    Parameters
    ----------
    element
        Doubly-symmetric I element.
    effective_length_factor_Kx/Ky/Kz, unbraced_length_Lx/Ly/Lz
        Compression boundary conditions (Chapter E).  All lengths in mm.
    unbraced_length_top_flange_Lb_top, unbraced_length_bot_flange_Lb_bot,
    lateral_torsional_buckling_modification_factor_Cb
        Flexure boundary conditions (Chapter F).  ``Lb_top``/``Lb_bot``
        default to ``element.bracing`` values when ``None``; an explicit
        ``Cb`` always wins.
    ax
        Existing axes; ``None`` creates a new figure/axes.
    which
        ``"phi"`` (LRFD design envelope, default), ``"nominal"``, or
        ``"both"``.
    normalized
        If True, plot ``M/Mcx`` vs ``P/Pc`` (unit envelope: kink at
        (0.9, 0.2), corners at (0,1) and (1,0)).
    fill
        Shade the safe interior of the envelope.
    force_unit, moment_unit
        ``(value, label)`` tuples for axis rescaling.  Ignored when
        ``normalized=True``.
    demand_points
        Sequence of ``(P, M)`` or ``(P, M, label)``.  Drawn as scatter,
        green if inside the envelope (unity ≤ 1), red otherwise.
        Forces/moments in base units (N, N·mm).
    label
        Legend label for the envelope curve.
    **line_kwargs
        Forwarded to ``ax.plot``.
    """
    plt = _import_matplotlib()
    if ax is None:
        _, ax = plt.subplots()  # type: ignore[attr-defined]

    caps = _resolve_capacities(
        element,
        Kx=effective_length_factor_Kx,
        Lx=unbraced_length_Lx,
        Ky=effective_length_factor_Ky,
        Ly=unbraced_length_Ly,
        Kz=effective_length_factor_Kz,
        Lz=unbraced_length_Lz,
        Lb_top=unbraced_length_top_flange_Lb_top,
        Lb_bot=unbraced_length_bot_flange_Lb_bot,
        Cb=lateral_torsional_buckling_modification_factor_Cb,
        need_minor_axis=False,
    )

    if normalized:
        x_label = "Mrx / Mcx"
        y_label = "Pr / Pc"
        # In normalized space the envelope is the same unit shape regardless
        # of phi vs nominal — draw it once.  `which="both"` is meaningless
        # here, so we collapse to a single curve.
        Mxs_n, Ps_n = _pm_envelope_vertices(1.0, 1.0)
        ax.plot(Mxs_n, Ps_n, label=label or "envelope", **line_kwargs)
        if fill:
            fill_color = line_kwargs.get("color")
            ax.fill(Mxs_n, Ps_n, alpha=0.15, color=fill_color)
    else:
        x_scale = moment_unit[0]
        y_scale = force_unit[0]
        x_label = f"Mrx ({moment_unit[1]})"
        y_label = f"Pr ({force_unit[1]})"
        if which in ("phi", "both"):
            Mxs, Ps = _pm_envelope_vertices(caps.Pc_phi, caps.Mcx_phi)
            Mxs_disp = [v / x_scale for v in Mxs]
            Ps_disp = [v / y_scale for v in Ps]
            phi_label = label if which == "phi" else _suffix(label, "φ")
            ax.plot(Mxs_disp, Ps_disp, label=phi_label, **line_kwargs)
            if fill:
                fill_color = line_kwargs.get("color")
                ax.fill(Mxs_disp, Ps_disp, alpha=0.15, color=fill_color)
        if which in ("nominal", "both"):
            Mxs, Ps = _pm_envelope_vertices(caps.Pc_nominal, caps.Mcx_nominal)
            Mxs_disp = [v / x_scale for v in Mxs]
            Ps_disp = [v / y_scale for v in Ps]
            nom_kwargs = dict(line_kwargs)
            nom_kwargs.setdefault("linestyle", "--")
            nom_label = label if which == "nominal" else _suffix(label, "nominal")
            ax.plot(Mxs_disp, Ps_disp, label=nom_label, **nom_kwargs)
            if fill and which == "nominal":
                fill_color = nom_kwargs.get("color")
                ax.fill(Mxs_disp, Ps_disp, alpha=0.15, color=fill_color)

    # Demand points -----------------------------------------------------
    if demand_points:
        Pc_use = caps.Pc_phi if which != "nominal" else caps.Pc_nominal
        Mcx_use = caps.Mcx_phi if which != "nominal" else caps.Mcx_nominal
        for pt in demand_points:
            if len(pt) == 3:
                Pr, Mrx, tag = pt
            else:
                Pr, Mrx = pt
                tag = None
            unity = _unity_H1_1(Pr, Mrx, 0.0, Pc_use, Mcx_use, 1.0)
            color = "tab:green" if unity <= 1.0 else "tab:red"
            if normalized:
                xv = abs(Mrx) / Mcx_use if Mcx_use > 0.0 else 0.0
                yv = abs(Pr) / Pc_use if Pc_use > 0.0 else 0.0
            else:
                xv = abs(Mrx) / x_scale
                yv = abs(Pr) / y_scale
            ax.plot([xv], [yv], marker="o", color=color, markersize=6)
            ax.annotate(
                f"{tag + ': ' if tag else ''}DCR={unity:.2f}",
                xy=(xv, yv),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
            )

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=0.0)
    ax.grid(True, alpha=0.3)
    return ax


# ---------------------------------------------------------------------------
# 2. M-M slice at fixed P
# ---------------------------------------------------------------------------
def plot_mm_interaction(
    element: Element,
    *,
    axial_load_Pr: float,
    effective_length_factor_Kx: float = 1.0,
    unbraced_length_Lx: float,
    effective_length_factor_Ky: float = 1.0,
    unbraced_length_Ly: float,
    effective_length_factor_Kz: float = 1.0,
    unbraced_length_Lz: float,
    unbraced_length_top_flange_Lb_top: float | None = None,
    unbraced_length_bot_flange_Lb_bot: float | None = None,
    lateral_torsional_buckling_modification_factor_Cb: float = 1.0,
    ax: Axes | None = None,
    which: Which = "phi",
    normalized: bool = False,
    fill: bool = False,
    moment_unit: tuple[float, str] = (MOMENT_DISPLAY_UNIT_kN_m, "kN·m"),
    demand_points: Sequence[MMDemand] | None = None,
    label: str | None = None,
    **line_kwargs: object,
) -> Axes:
    """Plot the §H1.1 Mrx-Mry envelope at a fixed axial load Pr.

    The envelope is a rhombus shrinking with axial load.  At
    ``Pr/Pc = 0.2`` it has vertices at ``(±0.9·Mcx, 0)`` and
    ``(0, ±0.9·Mcy)``; at ``Pr/Pc = 1`` it collapses to the origin.
    """
    plt = _import_matplotlib()
    if ax is None:
        _, ax = plt.subplots()  # type: ignore[attr-defined]

    caps = _resolve_capacities(
        element,
        Kx=effective_length_factor_Kx,
        Lx=unbraced_length_Lx,
        Ky=effective_length_factor_Ky,
        Ly=unbraced_length_Ly,
        Kz=effective_length_factor_Kz,
        Lz=unbraced_length_Lz,
        Lb_top=unbraced_length_top_flange_Lb_top,
        Lb_bot=unbraced_length_bot_flange_Lb_bot,
        Cb=lateral_torsional_buckling_modification_factor_Cb,
        need_minor_axis=True,
    )

    def _draw(Pc: float, Mcx: float, Mcy: float, kw: dict[str, object], lbl: str | None) -> None:
        xs, ys = _mm_envelope_vertices_at_P(axial_load_Pr, Pc, Mcx, Mcy)
        if normalized:
            xs = [v / Mcx if Mcx > 0.0 else 0.0 for v in xs]
            ys = [v / Mcy if Mcy > 0.0 else 0.0 for v in ys]
        else:
            xs = [v / moment_unit[0] for v in xs]
            ys = [v / moment_unit[0] for v in ys]
        ax.plot(xs, ys, label=lbl, **kw)
        if fill:
            fc = kw.get("color")
            ax.fill(xs, ys, alpha=0.15, color=fc)

    if which in ("phi", "both"):
        _draw(
            caps.Pc_phi, caps.Mcx_phi, caps.Mcy_phi,
            dict(line_kwargs),
            label if which == "phi" else _suffix(label, "φ"),
        )
    if which in ("nominal", "both"):
        kw = dict(line_kwargs)
        kw.setdefault("linestyle", "--")
        _draw(
            caps.Pc_nominal, caps.Mcx_nominal, caps.Mcy_nominal,
            kw,
            label if which == "nominal" else _suffix(label, "nominal"),
        )

    # Demand points -----------------------------------------------------
    if demand_points:
        Pc_use = caps.Pc_phi if which != "nominal" else caps.Pc_nominal
        Mcx_use = caps.Mcx_phi if which != "nominal" else caps.Mcx_nominal
        Mcy_use = caps.Mcy_phi if which != "nominal" else caps.Mcy_nominal
        for pt in demand_points:
            if len(pt) == 3:
                Mrx, Mry, tag = pt
            else:
                Mrx, Mry = pt
                tag = None
            unity = _unity_H1_1(axial_load_Pr, Mrx, Mry, Pc_use, Mcx_use, Mcy_use)
            color = "tab:green" if unity <= 1.0 else "tab:red"
            if normalized:
                xv = Mrx / Mcx_use if Mcx_use > 0.0 else 0.0
                yv = Mry / Mcy_use if Mcy_use > 0.0 else 0.0
            else:
                xv = Mrx / moment_unit[0]
                yv = Mry / moment_unit[0]
            ax.plot([xv], [yv], marker="o", color=color, markersize=6)
            ax.annotate(
                f"{tag + ': ' if tag else ''}DCR={unity:.2f}",
                xy=(xv, yv),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
            )

    if normalized:
        ax.set_xlabel("Mrx / Mcx")
        ax.set_ylabel("Mry / Mcy")
    else:
        ax.set_xlabel(f"Mrx ({moment_unit[1]})")
        ax.set_ylabel(f"Mry ({moment_unit[1]})")
    ax.axhline(0.0, color="gray", linewidth=0.5, alpha=0.5)
    ax.axvline(0.0, color="gray", linewidth=0.5, alpha=0.5)
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    return ax


# ---------------------------------------------------------------------------
# 3. 3D P-Mx-My envelope
# ---------------------------------------------------------------------------
def plot_pmm_interaction_3d(
    element: Element,
    *,
    effective_length_factor_Kx: float = 1.0,
    unbraced_length_Lx: float,
    effective_length_factor_Ky: float = 1.0,
    unbraced_length_Ly: float,
    effective_length_factor_Kz: float = 1.0,
    unbraced_length_Lz: float,
    unbraced_length_top_flange_Lb_top: float | None = None,
    unbraced_length_bot_flange_Lb_bot: float | None = None,
    lateral_torsional_buckling_modification_factor_Cb: float = 1.0,
    ax: Axes | None = None,
    which: Literal["phi", "nominal"] = "phi",
    force_unit: tuple[float, str] = (kN, "kN"),
    moment_unit: tuple[float, str] = (MOMENT_DISPLAY_UNIT_kN_m, "kN·m"),
    demand_points: Sequence[PMMDemand] | None = None,
    surface_alpha: float = 0.25,
    edge_color: str | None = "tab:blue",
    face_color: str | None = "tab:blue",
) -> Axes:
    """Plot the full 3D §H1.1 P-Mx-My envelope.

    The envelope is a cone (apex at ``(0, 0, Pc)``, base rhombus at
    ``P = 0.2·Pc``) glued to a frustum (top rhombus at ``P = 0.2·Pc``,
    base rhombus at ``P = 0``).  Drawn with
    :class:`mpl_toolkits.mplot3d.art3d.Poly3DCollection`.

    Pass ``ax`` with ``projection='3d'`` to overlay multiple sections;
    if omitted a new 3D figure is created.  ``which`` is "phi" or
    "nominal" — drawing both is unhelpful in 3D and not supported.
    """
    plt = _import_matplotlib()
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: PLC0415

    if ax is None:
        fig = plt.figure()  # type: ignore[attr-defined]
        ax = fig.add_subplot(111, projection="3d")

    caps = _resolve_capacities(
        element,
        Kx=effective_length_factor_Kx,
        Lx=unbraced_length_Lx,
        Ky=effective_length_factor_Ky,
        Ly=unbraced_length_Ly,
        Kz=effective_length_factor_Kz,
        Lz=unbraced_length_Lz,
        Lb_top=unbraced_length_top_flange_Lb_top,
        Lb_bot=unbraced_length_bot_flange_Lb_bot,
        Cb=lateral_torsional_buckling_modification_factor_Cb,
        need_minor_axis=True,
    )

    Pc = caps.Pc_phi if which == "phi" else caps.Pc_nominal
    Mcx = caps.Mcx_phi if which == "phi" else caps.Mcx_nominal
    Mcy = caps.Mcy_phi if which == "phi" else caps.Mcy_nominal

    P_break = H1_AXIAL_RATIO_BREAK * Pc
    moment_scale_at_break = 1.0 - H1_AXIAL_RATIO_BREAK / H1_1B_AXIAL_DIVISOR  # = 0.9

    # Four base vertices (P=0): rhombus at full Mcx/Mcy.
    base = [
        (Mcx, 0.0, 0.0),
        (0.0, Mcy, 0.0),
        (-Mcx, 0.0, 0.0),
        (0.0, -Mcy, 0.0),
    ]
    # Four mid-level vertices at P = 0.2*Pc, rhombus at 0.9*scale.
    mid = [
        (moment_scale_at_break * Mcx, 0.0, P_break),
        (0.0, moment_scale_at_break * Mcy, P_break),
        (-moment_scale_at_break * Mcx, 0.0, P_break),
        (0.0, -moment_scale_at_break * Mcy, P_break),
    ]
    apex = (0.0, 0.0, Pc)

    # Rescale to display units.
    fs = force_unit[0]
    ms = moment_unit[0]

    def _scale(
        verts: list[tuple[float, float, float]],
    ) -> list[tuple[float, float, float]]:
        return [(x / ms, y / ms, z / fs) for (x, y, z) in verts]

    base_s = _scale(base)
    mid_s = _scale(mid)
    apex_s = _scale([apex])[0]

    # Build faces.
    faces: list[list[tuple[float, float, float]]] = []
    # 4 frustum quads (base[i], base[i+1], mid[i+1], mid[i]).
    for i in range(4):
        j = (i + 1) % 4
        faces.append([base_s[i], base_s[j], mid_s[j], mid_s[i]])
    # 4 cone triangles (mid[i], mid[i+1], apex).
    for i in range(4):
        j = (i + 1) % 4
        faces.append([mid_s[i], mid_s[j], apex_s])

    surface = Poly3DCollection(
        faces,
        alpha=surface_alpha,
        facecolors=face_color,
        edgecolors=edge_color,
        linewidths=0.8,
    )
    ax.add_collection3d(surface)

    # Demand points ------------------------------------------------------
    if demand_points:
        for pt in demand_points:
            if len(pt) == 4:
                Pr, Mrx, Mry, tag = pt
            else:
                Pr, Mrx, Mry = pt
                tag = None
            unity = _unity_H1_1(Pr, Mrx, Mry, Pc, Mcx, Mcy)
            color = "tab:green" if unity <= 1.0 else "tab:red"
            ax.scatter([Mrx / ms], [Mry / ms], [Pr / fs], color=color, s=40)
            if tag:
                ax.text(Mrx / ms, Mry / ms, Pr / fs, f" {tag} (DCR={unity:.2f})", fontsize=8)

    # Axis limits and labels --------------------------------------------
    ax.set_xlim(-Mcx / ms, Mcx / ms)
    ax.set_ylim(-Mcy / ms, Mcy / ms)
    ax.set_zlim(0.0, Pc / fs)
    ax.set_xlabel(f"Mrx ({moment_unit[1]})")
    ax.set_ylabel(f"Mry ({moment_unit[1]})")
    ax.set_zlabel(f"Pr ({force_unit[1]})")
    return ax


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _suffix(base: str | None, tag: str) -> str:
    return f"{base} ({tag})" if base else tag


__all__ = [
    "MMDemand",
    "PMDemand",
    "PMMDemand",
    "plot_mm_interaction",
    "plot_pm_interaction",
    "plot_pmm_interaction_3d",
]

"""Section-kind-driven flexural-strength facade (full Chapter F).

This is the Phase-F-8 *non-I* flexural dispatch.  It mirrors the
compression facade precedent
(:func:`apeSteel.compression.compute_compression_strength`, which
switches on :data:`CompressionSectionKind`): a single entry point that
takes a Chapter-F geometry, computes its
:class:`~apeSteel.sections.flexural_properties.FlexuralSectionProperties`
and routes it - **by ``section_kind``, not by a string ``match`` on a
shape name** (ARCHITECTURE.md §7) - to the correct shipped §F engine:

============================  ===================================
``section_kind``              §F engine
============================  ===================================
``channel`` (major axis)      §F2 (Eq. F2-1..F2-8b ``c``)
``channel`` (minor axis)      §F6 (full-flange-width ``b``)
``rectangular_HSS``           §F7 (both axes)
``round_HSS``                 §F8
``tee`` / ``double_angle``    §F9
``single_angle``              §F10
``rectangular_bar`` /
``round_bar``                 §F11
``unsymmetric``               §F12
============================  ===================================

The shipped doubly-/singly-symmetric **I-shape** path
(``DoublySymmetricISection`` / ``SinglySymmetricISection`` ->
``Element`` / :func:`apeSteel.checks.run_full_beam_check` ->
B4.1b -> §F2/§F3/§F4/§F5) is **not** routed here and is **byte-
unchanged**: this module is a *purely additive* sibling, exactly as
``apeSteel.compression.compute_compression_strength`` sits beside the
DS-I-only ``Element.compression_strength``.  An I-shape geometry is
rejected here with a pointer to the I-shape path (the two never
overlap, so no shipped I-shape number can move).

Every routed engine is the **shipped, frozen** §F calculator; this
module owns **no flexural math** - it only computes the section's
:class:`FlexuralSectionProperties` (via the geometry's own
``compute_section_properties``) and the slenderness ratios the engine
needs from the plate dimensions, then delegates.  The returned report
is the concrete §F :class:`~apeSteel.core.result_types.Report`
subclass (``FlexureF6Report`` / ``FlexureF7Report`` / ...), so every
intermediate the engine exposes is preserved.

See ``docs/design_notes/10_flexure_full_F.md`` §5 (F-8 line) and §7.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeSteel.flexure.F2_compact_doubly_symmetric import (
    FlexureF2Report,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)
from apeSteel.flexure.F6_minor_axis import (
    FlexureF6Report,
    compute_flexural_strength_F6_minor_axis_channel,
)
from apeSteel.flexure.F7_rect_hss import (
    FlexureF7Report,
    compute_flexural_strength_F7_rect_hss,
)
from apeSteel.flexure.F8_round_hss import (
    FlexureF8Report,
    compute_flexural_strength_F8_round_hss,
)
from apeSteel.flexure.F9_tee_double_angle import (
    FlexureF9Report,
    compute_flexural_strength_F9_tee_double_angle,
)
from apeSteel.flexure.F10_single_angle import (
    FlexureF10Report,
    SingleAngleBendingMode,
    SingleAngleToeState,
    compute_flexural_strength_F10_single_angle,
)
from apeSteel.flexure.F11_F12_bar_unsymmetric import (
    FlexureF11Report,
    FlexureF12Report,
    compute_flexural_strength_F11_bar,
    compute_flexural_strength_F12_unsymmetric,
)

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.flexural_properties import BendingAxis
    from apeSteel.sections.geometry import (
        ChannelSection,
        DoubleAngleSection,
        RectangularHSS,
        RoundHSS,
        SingleAngleSection,
        TeeSection,
    )
    from apeSteel.sections.geometry.bar_section import RectangularBar, RoundBar

#: Every concrete §F report a non-I geometry can produce through this
#: facade (each a frozen :class:`Report` subclass; they share
#: ``nominal_strength`` / ``phi_strength_LRFD`` / ``governing_limit_state``).
NonISectionFlexureReport = (
    FlexureF2Report
    | FlexureF6Report
    | FlexureF7Report
    | FlexureF8Report
    | FlexureF9Report
    | FlexureF10Report
    | FlexureF11Report
    | FlexureF12Report
)


def compute_flexural_strength_channel(
    section: ChannelSection,
    material: SteelMaterial,
    *,
    bending_axis: BendingAxis = "major",
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float = 1.0,
    construction: SectionConstruction = "rolled",
) -> FlexureF2Report | FlexureF6Report:
    """Route a :class:`ChannelSection` to §F2 (major) or §F6 (minor).

    AISC 360-22 §F2 covers channels bent about their **major** axis
    (the Eq. F2-8b section constant ``c`` - carried natively on the
    channel's :class:`FlexuralSectionProperties`).  §F6 covers channels
    bent about their **minor** axis with ``b`` = the *full* nominal
    flange width (§F6.2 spec note), not ``bf/2``.

    Parameters
    ----------
    section : ChannelSection
    material : SteelMaterial
    bending_axis : {"major", "minor"}, optional
        ``"major"`` -> §F2; ``"minor"`` -> §F6.  Default ``"major"``.
    unbraced_length_Lb : float, keyword-only
        ``Lb`` (mm), > 0.  Required for §F2 (major-axis LTB); §F6
        (minor axis) has no LTB limit state but ``Lb`` is accepted for
        a uniform call signature and ignored there.
    lateral_torsional_buckling_modification_factor_Cb : float, optional
        ``Cb`` (Eq. F1-1).  Used only by the §F2 major-axis path.
        Default ``1.0``.
    construction : {"rolled", "welded"}, optional
        Table B4.1b flange Case 10 vs Case 11.  Default ``"rolled"``
        (channels are rolled in practice).

    Returns
    -------
    FlexureF2Report (major axis) or FlexureF6Report (minor axis)
    """
    if bending_axis == "major":
        # §F2 major axis.  The shipped §F2 engine takes the *legacy*
        # SectionProperties + ``section_kind="channel"`` (its
        # from_legacy lifts the Eq. F2-8b ``c``).  The channel's native
        # FlexuralSectionProperties already carries Sx/Zx/ry/rts/ho/J
        # and the Eq. F2-8b ``c``; wrap it in the minimal legacy view
        # the §F2 signature expects via the shared adapter so no §F2
        # math changes (the F-1 channel anchor pins this exact path).
        return _channel_major_axis_F2(
            section,
            material,
            unbraced_length_Lb=unbraced_length_Lb,
            lateral_torsional_buckling_modification_factor_Cb=(
                lateral_torsional_buckling_modification_factor_Cb
            ),
        )

    # §F6 minor axis - channel ``b`` = the FULL flange width.
    fsp = section.compute_section_properties()
    channel_flange_b_t: float = section.flange_width_bf / section.flange_thickness_tf
    return compute_flexural_strength_F6_minor_axis_channel(
        fsp,
        material,
        channel_flange_slenderness_b_t=channel_flange_b_t,
        construction=construction,
    )


def _channel_major_axis_F2(
    section: ChannelSection,
    material: SteelMaterial,
    *,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
) -> FlexureF2Report:
    """§F2 major-axis for a channel via the shipped §F2 engine.

    The shipped ``compute_flexural_strength_F2_compact_doubly_
    symmetric`` consumes the *legacy* :class:`SectionProperties` and
    derives the Eq. F2-8b ``c`` inside
    ``FlexuralSectionProperties.from_legacy`` when
    ``section_kind="channel"``.  Build the minimal legacy view the §F2
    signature needs from the channel's own closed forms - the *same*
    Galambos/DG-9 forms the F-1 anchor
    (``test_chapterF_F1_additions``) pins - so the §F2 math is
    byte-identical to that verified channel path and **no shipped §F2
    number moves**.
    """
    from apeSteel.sections.properties import SectionProperties  # noqa: PLC0415

    fsp = section.compute_section_properties()
    bf: float = section.flange_width_bf
    tf: float = section.flange_thickness_tf
    d: float = section.overall_depth_d
    tw: float = section.web_thickness_tw
    clear_web: float = d - 2.0 * tf

    # Legacy SectionProperties view.  Only the fields §F2 reads
    # (Sx, Zx, ry, rts, ho, J, Cw) are load-bearing; the rest are
    # consistent closed forms / neutral so the dataclass constructs.
    # ``section_kind="channel"`` makes §F2's from_legacy re-derive the
    # Eq. F2-8b ``c`` from these ho/Iy/Cw - identical to the value the
    # channel's FlexuralSectionProperties carries (both are the same
    # closed form), so the channel §F2 result is the F-1-pinned one.
    legacy = SectionProperties(
        overall_depth_d=d,
        gross_area_Ag=fsp.gross_area_Ag,
        nominal_weight_per_unit_length_w=0.0,
        moment_of_inertia_strong_axis_Ix=fsp.moment_of_inertia_Ix,
        elastic_section_modulus_strong_axis_Sx=fsp.elastic_modulus_Sx,
        plastic_section_modulus_strong_axis_Zx=fsp.plastic_modulus_Zx,
        radius_of_gyration_strong_axis_rx=fsp.radius_of_gyration_rx,
        moment_of_inertia_weak_axis_Iy=fsp.moment_of_inertia_Iy,
        elastic_section_modulus_weak_axis_Sy=fsp.elastic_modulus_Sy,
        plastic_section_modulus_weak_axis_Zy=fsp.plastic_modulus_Zy,
        radius_of_gyration_weak_axis_ry=fsp.radius_of_gyration_ry,
        torsional_constant_J=fsp.torsional_constant_J,
        warping_constant_Cw=fsp.warping_constant_Cw,
        distance_between_flange_centroids_ho=fsp.distance_between_flange_centroids_ho,
        effective_radius_of_gyration_for_LTB_rts=(fsp.effective_radius_of_gyration_for_LTB_rts),
        flange_width_to_thickness_ratio_bf_2tf=bf / tf,
        web_height_to_thickness_ratio_h_tw=clear_web / tw,
        web_thickness_tw=tw,
        flange_width_bf=bf,
        flange_thickness_tf=tf,
    )
    return compute_flexural_strength_F2_compact_doubly_symmetric(
        legacy,
        material,
        unbraced_length_Lb,
        lateral_torsional_buckling_modification_factor_Cb,
        section_kind="channel",
    )


def compute_flexural_strength_rectangular_hss(
    section: RectangularHSS,
    material: SteelMaterial,
    *,
    bending_axis: BendingAxis = "major",
    unbraced_length_Lb: float | None = None,
    Cb: float = 1.0,
) -> FlexureF7Report:
    """Route a :class:`RectangularHSS` to §F7 (either axis)."""
    return compute_flexural_strength_F7_rect_hss(
        section.compute_section_properties(),
        material,
        bending_axis=bending_axis,
        unbraced_length_Lb=unbraced_length_Lb,
        Cb=Cb,
    )


def compute_flexural_strength_round_hss(
    section: RoundHSS,
    material: SteelMaterial,
) -> FlexureF8Report:
    """Route a :class:`RoundHSS` / Pipe to §F8 (no LTB)."""
    return compute_flexural_strength_F8_round_hss(
        section.compute_section_properties(),
        material,
    )


def compute_flexural_strength_tee_or_double_angle(
    section: TeeSection | DoubleAngleSection,
    material: SteelMaterial,
    *,
    unbraced_length_Lb: float,
    flange_slenderness_bf_2tf: float,
    stem_slenderness_d_tw: float,
    lateral_torsional_buckling_factor_Cb: float = 1.0,
    stem_in_tension: bool = True,
) -> FlexureF9Report:
    """Route a :class:`TeeSection` / :class:`DoubleAngleSection` to §F9.

    The tee-flange ``bf/2tf`` and stem ``d/tw`` (or, for a double
    angle, the leg ``b/t`` for both) are passed explicitly because the
    generalized :class:`FlexuralSectionProperties` does not carry the
    raw plate ratios - exactly as the §F9 engine's own contract
    (mirrors the §F9 golden's ``_run_tee`` / ``_run_da`` helpers).
    """
    return compute_flexural_strength_F9_tee_double_angle(
        section.compute_section_properties(),
        material,
        unbraced_length_Lb=unbraced_length_Lb,
        flange_slenderness_bf_2tf=flange_slenderness_bf_2tf,
        stem_slenderness_d_tw=stem_slenderness_d_tw,
        lateral_torsional_buckling_factor_Cb=lateral_torsional_buckling_factor_Cb,
        stem_in_tension=stem_in_tension,
    )


def compute_flexural_strength_single_angle(
    section: SingleAngleSection,
    material: SteelMaterial,
    *,
    unbraced_length_Lb: float,
    Cb: float = 1.0,
    bending_mode: SingleAngleBendingMode = "principal_major",
    toe_state: SingleAngleToeState = "compression_at_toe",
    section_modulus_S: float,
    lateral_torsional_restraint_at_max_moment: bool = False,
) -> FlexureF10Report:
    """Route a :class:`SingleAngleSection` to §F10.

    ``section_modulus_S`` is explicit (the §F10 engine's contract):
    which fibre governs depends on the load case (the Manual's
    ``SwC`` / ``SzB`` / geometric ``Sx``), and the §F10.2/§F10.3
    ``0.80`` geometric reduction is applied inside the engine.
    """
    return compute_flexural_strength_F10_single_angle(
        section.compute_section_properties(),
        material,
        unbraced_length_Lb=unbraced_length_Lb,
        Cb=Cb,
        bending_mode=bending_mode,
        toe_state=toe_state,
        section_modulus_S=section_modulus_S,
        lateral_torsional_restraint_at_max_moment=(lateral_torsional_restraint_at_max_moment),
    )


def compute_flexural_strength_bar(
    section: RectangularBar | RoundBar,
    material: SteelMaterial,
    *,
    laterally_unbraced_length_Lb: float | None = None,
    lateral_torsional_modification_Cb: float = 1.0,
    bending_axis: BendingAxis = "major",
) -> FlexureF11Report:
    """Route a :class:`RectangularBar` / :class:`RoundBar` to §F11."""
    return compute_flexural_strength_F11_bar(
        section.compute_section_properties(),
        material,
        laterally_unbraced_length_Lb=laterally_unbraced_length_Lb,
        lateral_torsional_modification_Cb=lateral_torsional_modification_Cb,
        bending_axis=bending_axis,
    )


def compute_flexural_strength_unsymmetric_F12(
    section: RectangularBar | RoundBar,
    material: SteelMaterial,
    *,
    lateral_torsional_buckling_stress_Fcr: float | None = None,
    local_buckling_stress_Fcr: float | None = None,
) -> FlexureF12Report:
    """Route any geometry carrying ``extreme_fibre_moduli`` to §F12.

    §F12 is the elastic catch-all (``Mn = Fn*Smin``); it reads only
    :attr:`FlexuralSectionProperties.extreme_fibre_moduli`, so any
    geometry that populates it is accepted (the section-agnostic
    elastic floor; design note 10 §5, F-7 line).
    """
    return compute_flexural_strength_F12_unsymmetric(
        section.compute_section_properties(),
        material,
        lateral_torsional_buckling_stress_Fcr=lateral_torsional_buckling_stress_Fcr,
        local_buckling_stress_Fcr=local_buckling_stress_Fcr,
    )


__all__ = [
    "NonISectionFlexureReport",
    "compute_flexural_strength_bar",
    "compute_flexural_strength_channel",
    "compute_flexural_strength_rectangular_hss",
    "compute_flexural_strength_round_hss",
    "compute_flexural_strength_single_angle",
    "compute_flexural_strength_tee_or_double_angle",
    "compute_flexural_strength_unsymmetric_F12",
]

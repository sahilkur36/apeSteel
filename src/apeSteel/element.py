"""Element - the composite of section, material, construction, and bracing.

`Element` aggregates the three primary domain objects (Section,
SteelMaterial, Bracing - each its own node in the model graph) plus
the construction type, and exposes every AISC check as a method.

Construction:

    section = DoublySymmetricISection(bf=300*u.mm, ...)
    bracing = Bracing(Lb_top=0.001*u.m, Lb_bot=4.0*u.m, Cb=1.0)
    element = section.element(material=A992, construction="welded",
                              bracing=bracing)

Usage:

    flex   = element.classify_flexural()                  # B4.1b
    axial  = element.classify_axial_compression()         # B4.1a
    seism  = element.classify_seismic("highly_ductile")   # 341 D1.1
    F2     = element.flexural_strength_F2_both_flanges()  # F2 LTB
    F3     = element.flexural_strength_F3_both_flanges()  # F3 LTB+FLB
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal

from apeSteel.classification import (
    AxialCompressionClassificationReport,
    DuctilityLevel,
    FlexuralCompactnessReport,
    SectionConstruction,
    SeismicCodeEdition,
    SeismicCompactnessReport,
    classify_axial_compression_B4_1a,
    classify_flexural_compactness_B4_1b,
    classify_seismic_compactness_341_D1,
)
from apeSteel.combined import (
    CombinedH1Report,
    compute_combined_strength_H1_1,
)
from apeSteel.compression import (
    CapacityCurvePoint,
    CompressionStrengthReport,
    compute_compression_strength_from_K_L,
    compute_phi_Pn_vs_length,
)
from apeSteel.flexure import (
    FlexuralCurvePoint,
    FlexureF2Report,
    FlexureF3Report,
    FlexureF4Report,
    FlexureF5Report,
    RoutedFlexureChapterCurve,
    compute_flexural_strength_F2_compact_doubly_symmetric,
    compute_flexural_strength_F3_noncompact_or_slender_flange,
    compute_flexural_strength_F4,
    compute_flexural_strength_F5_slender_web_plate_girder,
    compute_flexural_strength_F6_minor_axis,
)
from apeSteel.serviceability import (
    DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    CantileverUDLAndTipLoadDeflectionReport,
    SimplySupportedPointLoadArbitraryDeflectionReport,
    SimplySupportedPointLoadMidspanDeflectionReport,
    SimplySupportedUDLDeflectionReport,
    compute_deflection_cantilever_udl_and_tip_load,
    compute_deflection_simply_supported_point_load_arbitrary,
    compute_deflection_simply_supported_point_load_midspan,
    compute_deflection_simply_supported_udl,
)
from apeSteel.shear import (
    ShearG2Report,
    compute_shear_strength_G2_doubly_symmetric,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.axes import Axes

    from apeSteel.beam_column_connection import BeamColumnConnection
    from apeSteel.bracing import Bracing
    from apeSteel.checks.beam_check import BeamCheckReport
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.plotting.compression import LengthProjection
    from apeSteel.plotting.flexure import (
        LengthProjection as FlexuralLengthProjection,
    )
    from apeSteel.sections.geometry import (
        CompressionFlangeSide,
        ISection,
    )
    from apeSteel.sections.properties import SectionProperties


GoverningFlange = Literal["top", "bot"]


# ---------------------------------------------------------------------------
# Both-flange wrappers - each itself a composite of two sub-reports
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BothFlangesFlexureF2Report:
    """Top + bottom + governing AISC F2 result."""

    top: FlexureF2Report
    bot: FlexureF2Report
    governing_flange: GoverningFlange
    governing_report: FlexureF2Report


@dataclass(frozen=True, slots=True)
class BothFlangesFlexureF3Report:
    """Top + bottom + governing AISC F3 result."""

    top: FlexureF3Report
    bot: FlexureF3Report
    governing_flange: GoverningFlange
    governing_report: FlexureF3Report


@dataclass(frozen=True, slots=True)
class BothFlangesFlexureF4Report:
    """Top + bottom + governing AISC F4 (doubly-sym, noncompact-web) result."""

    top: FlexureF4Report
    bot: FlexureF4Report
    governing_flange: GoverningFlange
    governing_report: FlexureF4Report


@dataclass(frozen=True, slots=True)
class BothFlangesFlexureF5Report:
    """Top + bottom + governing AISC F5 (plate girder) result."""

    top: FlexureF5Report
    bot: FlexureF5Report
    governing_flange: GoverningFlange
    governing_report: FlexureF5Report


# ---------------------------------------------------------------------------
# Element - the central composite
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Element:
    """A structural-steel element: section + material + construction + bracing.

    The ``section`` field accepts either :class:`DoublySymmetricISection`
    or :class:`SinglySymmetricISection` (the :data:`ISection` union).
    For singly-symmetric sections the F4 methods (compact / non-compact
    web) and the F5 methods (slender web - AISC §F5 covers DS *and* SS)
    are the canonical flexural-strength interface; F2 / F3 (which assume
    doubly-symmetric geometry) raise :class:`NotImplementedError`.
    """

    section: ISection
    material: SteelMaterial
    construction: SectionConstruction = "welded"
    bracing: Bracing | None = None
    code_edition_for_seismic: SeismicCodeEdition = "AISC 341-22"

    # ------------------------------------------------------------------ #
    # Derived characteristic (cached)
    # ------------------------------------------------------------------ #
    @cached_property
    def section_properties(self) -> SectionProperties:
        """The derived section properties (top-flange compression by default).

        For doubly-symmetric sections the side does not matter (results
        are symmetric).  For singly-symmetric sections this returns the
        properties for the "top flange in compression" case; use
        :meth:`section_properties_for` to get the bot-compression case.
        """
        from apeSteel.sections.geometry import SinglySymmetricISection  # noqa: PLC0415

        if isinstance(self.section, SinglySymmetricISection):
            return self.section.compute_section_properties("top")
        return self.section.compute_section_properties()

    def section_properties_for(
        self,
        compression_flange_side: CompressionFlangeSide,
    ) -> SectionProperties:
        """Section properties for the given compression-flange direction.

        For doubly-symmetric sections this is independent of side and
        returns the same cached :attr:`section_properties`.  For
        singly-symmetric sections it computes the side-specific values
        (different Sxc, Sxt, Iyc, hc, hp depending on which flange is
        in compression).
        """
        from apeSteel.sections.geometry import SinglySymmetricISection  # noqa: PLC0415

        if isinstance(self.section, SinglySymmetricISection):
            return self.section.compute_section_properties(compression_flange_side)
        return self.section_properties

    def _require_doubly_symmetric_section(self, check_name: str) -> None:
        """Guard for F2/F3/F5 and other DS-only checks.

        Raises NotImplementedError when called on an Element whose
        section is singly-symmetric.
        """
        from apeSteel.sections.geometry import SinglySymmetricISection  # noqa: PLC0415

        if isinstance(self.section, SinglySymmetricISection):
            raise NotImplementedError(
                f"{check_name} is only implemented for DoublySymmetricISection. "
                "For singly-symmetric I-sections use the F4 methods "
                "(flexural_strength_F4_top_flange / _bot_flange / _both_flanges)."
            )

    # ------------------------------------------------------------------ #
    # Builders - return a new Element with one field replaced
    # ------------------------------------------------------------------ #
    @classmethod
    def from_section(
        cls,
        section: ISection,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
        bracing: Bracing | None = None,
        code_edition_for_seismic: SeismicCodeEdition = "AISC 341-22",
    ) -> Element:
        return cls(
            section=section,
            material=material,
            construction=construction,
            bracing=bracing,
            code_edition_for_seismic=code_edition_for_seismic,
        )

    def with_material(self, material: SteelMaterial) -> Element:
        return replace(self, material=material)

    def with_construction(self, construction: SectionConstruction) -> Element:
        return replace(self, construction=construction)

    def with_bracing(self, bracing: Bracing) -> Element:
        return replace(self, bracing=bracing)

    def with_code_edition_for_seismic(
        self,
        code_edition_for_seismic: SeismicCodeEdition,
    ) -> Element:
        return replace(self, code_edition_for_seismic=code_edition_for_seismic)

    # ------------------------------------------------------------------ #
    # Connection composite builder (Phase 8c)
    # ------------------------------------------------------------------ #
    def connected_to(self, column: Element) -> BeamColumnConnection:
        """Return a BeamColumnConnection treating ``self`` as the beam.

        Convenience builder so chained construction reads naturally::

            joint = beam_section.element(A992).connected_to(column_element)
            joint.check_panel_zone_column_flange_tension()
        """
        # Local import to break the cycle:
        # apeSteel.beam_column_connection imports Element via TYPE_CHECKING,
        # Element imports BeamColumnConnection here.
        from apeSteel.beam_column_connection import BeamColumnConnection  # noqa: PLC0415

        return BeamColumnConnection(beam=self, column=column)

    # ------------------------------------------------------------------ #
    # Classification (do not require bracing)
    # ------------------------------------------------------------------ #
    def classify_flexural(self) -> FlexuralCompactnessReport:
        return classify_flexural_compactness_B4_1b(
            self.section_properties,
            self.material,
            self.construction,
        )

    def classify_axial_compression(self) -> AxialCompressionClassificationReport:
        return classify_axial_compression_B4_1a(
            self.section_properties,
            self.material,
            self.construction,
        )

    def classify_seismic(
        self,
        ductility_level: DuctilityLevel,
        axial_demand_ratio_Ca: float = 0.0,
        code_edition: SeismicCodeEdition | None = None,
    ) -> SeismicCompactnessReport:
        edition = code_edition if code_edition is not None else self.code_edition_for_seismic
        return classify_seismic_compactness_341_D1(
            section_properties=self.section_properties,
            material=self.material,
            ductility_level=ductility_level,
            axial_demand_ratio_Ca=axial_demand_ratio_Ca,
            code_edition=edition,
        )

    # ------------------------------------------------------------------ #
    # Flexural strength (require bracing)
    # ------------------------------------------------------------------ #
    def _require_bracing(self) -> Bracing:
        if self.bracing is None:
            raise ValueError(
                "Element.bracing is None; bind a Bracing via "
                "`element.with_bracing(...)` before calling LTB methods."
            )
        return self.bracing

    # --- F2 ---
    def flexural_strength_F2_top_flange(self) -> FlexureF2Report:
        self._require_doubly_symmetric_section("flexural_strength_F2_top_flange")
        br = self._require_bracing()
        return compute_flexural_strength_F2_compact_doubly_symmetric(
            section_properties=self.section_properties,
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_top_flange_Lb_top,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
        )

    def flexural_strength_F2_bot_flange(self) -> FlexureF2Report:
        self._require_doubly_symmetric_section("flexural_strength_F2_bot_flange")
        br = self._require_bracing()
        return compute_flexural_strength_F2_compact_doubly_symmetric(
            section_properties=self.section_properties,
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_bot_flange_Lb_bot,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
        )

    def flexural_strength_F2_both_flanges(self) -> BothFlangesFlexureF2Report:
        """Both F2 flange checks + the governing one (lowest phi*Mn)."""
        top = self.flexural_strength_F2_top_flange()
        bot = self.flexural_strength_F2_bot_flange()
        if top.phi_strength_LRFD <= bot.phi_strength_LRFD:
            return BothFlangesFlexureF2Report(
                top=top,
                bot=bot,
                governing_flange="top",
                governing_report=top,
            )
        return BothFlangesFlexureF2Report(
            top=top,
            bot=bot,
            governing_flange="bot",
            governing_report=bot,
        )

    # --- F3 ---
    def flexural_strength_F3_top_flange(self) -> FlexureF3Report:
        self._require_doubly_symmetric_section("flexural_strength_F3_top_flange")
        br = self._require_bracing()
        return compute_flexural_strength_F3_noncompact_or_slender_flange(
            section_properties=self.section_properties,
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_top_flange_Lb_top,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
            construction=self.construction,
        )

    def flexural_strength_F3_bot_flange(self) -> FlexureF3Report:
        self._require_doubly_symmetric_section("flexural_strength_F3_bot_flange")
        br = self._require_bracing()
        return compute_flexural_strength_F3_noncompact_or_slender_flange(
            section_properties=self.section_properties,
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_bot_flange_Lb_bot,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
            construction=self.construction,
        )

    def flexural_strength_F3_both_flanges(self) -> BothFlangesFlexureF3Report:
        """Both F3 flange checks + the governing one (lowest phi*Mn)."""
        top = self.flexural_strength_F3_top_flange()
        bot = self.flexural_strength_F3_bot_flange()
        if top.phi_strength_LRFD <= bot.phi_strength_LRFD:
            return BothFlangesFlexureF3Report(
                top=top,
                bot=bot,
                governing_flange="top",
                governing_report=top,
            )
        return BothFlangesFlexureF3Report(
            top=top,
            bot=bot,
            governing_flange="bot",
            governing_report=bot,
        )

    # ------------------------------------------------------------------ #
    # F4 - doubly- and singly-symmetric I (Phase 9a + 9b)
    # ------------------------------------------------------------------ #
    def flexural_strength_F4_top_flange(self) -> FlexureF4Report:
        """F4 strength assuming the **top** flange is in compression.

        For singly-symmetric sections this picks the top-compression
        SectionProperties (top-flange geometry, ``Sxc=Sx_top_fiber``,
        ``Iyc=Iy_top``, ``hc`` computed accordingly).  For doubly-
        symmetric sections the result is identical to ``_bot_flange``
        when Lb is the same.
        """
        br = self._require_bracing()
        return compute_flexural_strength_F4(
            section_properties=self.section_properties_for("top"),
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_top_flange_Lb_top,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
            construction=self.construction,
        )

    def flexural_strength_F4_bot_flange(self) -> FlexureF4Report:
        """F4 strength assuming the **bottom** flange is in compression."""
        br = self._require_bracing()
        return compute_flexural_strength_F4(
            section_properties=self.section_properties_for("bot"),
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_bot_flange_Lb_bot,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
            construction=self.construction,
        )

    def flexural_strength_F4_both_flanges(self) -> BothFlangesFlexureF4Report:
        """Both F4 flange checks + the governing one (lowest phi*Mn)."""
        top = self.flexural_strength_F4_top_flange()
        bot = self.flexural_strength_F4_bot_flange()
        if top.phi_strength_LRFD <= bot.phi_strength_LRFD:
            return BothFlangesFlexureF4Report(
                top=top,
                bot=bot,
                governing_flange="top",
                governing_report=top,
            )
        return BothFlangesFlexureF4Report(
            top=top,
            bot=bot,
            governing_flange="bot",
            governing_report=bot,
        )

    # ------------------------------------------------------------------ #
    # Shear (G2) - no top/bottom distinction; one check on the web
    # ------------------------------------------------------------------ #
    def shear_strength_G2(
        self,
        transverse_stiffener_spacing_a: float | None = None,
    ) -> ShearG2Report:
        """Return Vn per AISC §G2 for this element's web.

        Currently DS-only.  For singly-symmetric sections the G2 web
        check is the same physical phenomenon (web shear capacity), but
        the current ``compute_shear_strength_G2_doubly_symmetric``
        calculator was derived assuming doubly-symmetric geometry; a
        future phase will add SS support.

        Parameters
        ----------
        transverse_stiffener_spacing_a : float or None, optional
            Stiffener spacing in mm.  None (default) means unstiffened.
        """
        self._require_doubly_symmetric_section("shear_strength_G2")
        return compute_shear_strength_G2_doubly_symmetric(
            section_properties=self.section_properties,
            material=self.material,
            construction=self.construction,
            transverse_stiffener_spacing_a=transverse_stiffener_spacing_a,
        )

    # ------------------------------------------------------------------ #
    # Compression - AISC 360-22 Chapter E (doubly-symmetric I via Element;
    # the other section families use the free-function facade /
    # apeSteel.compression directly)
    # ------------------------------------------------------------------ #
    def compression_strength(
        self,
        effective_length_factor_Kx: float,
        unbraced_length_Lx: float,
        effective_length_factor_Ky: float,
        unbraced_length_Ly: float,
        effective_length_factor_Kz: float,
        unbraced_length_Lz: float,
    ) -> CompressionStrengthReport:
        """AISC 360-22 Chapter-E nominal compressive strength.

        Doubly-symmetric I only (the ``Element`` composition spine is the
        ``ISection`` union).  Tee / channel / HSS / angle compression use
        the dedicated geometries with
        :func:`apeSteel.compression.compute_compression_strength`.
        """
        self._require_doubly_symmetric_section("compression_strength")
        from apeSteel.sections.geometry import (  # noqa: PLC0415
            DoublySymmetricISection,
        )

        assert isinstance(self.section, DoublySymmetricISection)
        props = self.section.compute_compression_properties(self.material, self.construction)
        return compute_compression_strength_from_K_L(
            section_properties=props,
            material=self.material,
            effective_length_factor_Kx=effective_length_factor_Kx,
            unbraced_length_Lx=unbraced_length_Lx,
            effective_length_factor_Ky=effective_length_factor_Ky,
            unbraced_length_Ly=unbraced_length_Ly,
            effective_length_factor_Kz=effective_length_factor_Kz,
            unbraced_length_Lz=unbraced_length_Lz,
        )

    def phi_Pn_vs_length(
        self,
        lengths_L: Sequence[float],
        effective_length_factor_Kx: float = 1.0,
        effective_length_factor_Ky: float = 1.0,
        effective_length_factor_Kz: float = 1.0,
    ) -> tuple[CapacityCurvePoint, ...]:
        """The φPn-vs-length capacity curve (doubly-symmetric I)."""
        self._require_doubly_symmetric_section("phi_Pn_vs_length")
        from apeSteel.sections.geometry import (  # noqa: PLC0415
            DoublySymmetricISection,
        )

        assert isinstance(self.section, DoublySymmetricISection)
        props = self.section.compute_compression_properties(self.material, self.construction)
        return compute_phi_Pn_vs_length(
            section_properties=props,
            material=self.material,
            lengths_L=lengths_L,
            effective_length_factor_Kx=effective_length_factor_Kx,
            effective_length_factor_Ky=effective_length_factor_Ky,
            effective_length_factor_Kz=effective_length_factor_Kz,
        )

    def plot_compression_curve(
        self,
        lengths_L: Sequence[float],
        *,
        effective_length_factor_Kx: float = 1.0,
        effective_length_factor_Ky: float = 1.0,
        effective_length_factor_Kz: float = 1.0,
        ax: Axes | None = None,
        xscale: Literal["linear", "log"] = "linear",
        length_unit: tuple[float, str] | None = None,
        force_unit: tuple[float, str] | None = None,
        which: Literal["phi_Pn", "Pn", "both"] = "phi_Pn",
        fill: bool = False,
        color_by_limit_state: bool = False,
        project_lengths: Sequence[LengthProjection] | None = None,
        label: str | None = None,
        **line_kwargs: Any,
    ) -> Axes:
        """Plot the AISC 360-22 Chapter-E strength-vs-length curve.

        Thin delegate to
        :func:`apeSteel.plotting.compression.plot_compression_curve`;
        see that function for the full parameter reference.  Requires
        the optional ``plot`` extra (``pip install
        "apeSteel[plot]"``).
        """
        from apeSteel.plotting.compression import (  # noqa: PLC0415
            plot_compression_curve,
        )

        kwargs: dict[str, Any] = dict(
            effective_length_factor_Kx=effective_length_factor_Kx,
            effective_length_factor_Ky=effective_length_factor_Ky,
            effective_length_factor_Kz=effective_length_factor_Kz,
            ax=ax,
            xscale=xscale,
            which=which,
            fill=fill,
            color_by_limit_state=color_by_limit_state,
            project_lengths=project_lengths,
            label=label,
        )
        if length_unit is not None:
            kwargs["length_unit"] = length_unit
        if force_unit is not None:
            kwargs["force_unit"] = force_unit
        return plot_compression_curve(self, lengths_L, **kwargs, **line_kwargs)

    def plot_flexural_curve(
        self,
        unbraced_lengths_Lb: Sequence[float],
        *,
        lateral_torsional_buckling_modification_factor_Cb: float = 1.0,
        flange: Literal["top", "bot", "governing"] = "governing",
        ax: Axes | None = None,
        xscale: Literal["linear", "log"] = "linear",
        length_unit: tuple[float, str] | None = None,
        moment_unit: tuple[float, str] | None = None,
        which: Literal["phi_Mn", "Mn", "both"] = "phi_Mn",
        fill: bool = False,
        color_by_limit_state: bool = False,
        project_lengths: Sequence[FlexuralLengthProjection] | None = None,
        show_landmarks: bool = False,
        label: str | None = None,
        **line_kwargs: Any,
    ) -> Axes:
        """Plot the AISC 360-22 Chapter-F φMn-vs-Lb curve.

        Thin delegate to
        :func:`apeSteel.plotting.flexure.plot_flexural_curve`; see that
        function for the full parameter reference.  Requires the
        optional ``plot`` extra (``pip install "apeSteel[plot]"``).
        """
        from apeSteel.plotting.flexure import (  # noqa: PLC0415
            plot_flexural_curve,
        )

        kwargs: dict[str, Any] = dict(
            lateral_torsional_buckling_modification_factor_Cb=(
                lateral_torsional_buckling_modification_factor_Cb
            ),
            flange=flange,
            ax=ax,
            xscale=xscale,
            which=which,
            fill=fill,
            color_by_limit_state=color_by_limit_state,
            project_lengths=project_lengths,
            show_landmarks=show_landmarks,
            label=label,
        )
        if length_unit is not None:
            kwargs["length_unit"] = length_unit
        if moment_unit is not None:
            kwargs["moment_unit"] = moment_unit
        return plot_flexural_curve(self, unbraced_lengths_Lb, **kwargs, **line_kwargs)

    # ------------------------------------------------------------------ #
    # §H1.1 interaction-diagram plots
    # ------------------------------------------------------------------ #
    def plot_pm_interaction(self, **kwargs: object) -> Axes:
        """Plot the uniaxial §H1.1 P-Mx interaction envelope.

        Thin delegate to
        :func:`apeSteel.plotting.interaction.plot_pm_interaction`.  See
        that function for the full parameter reference.
        """
        from apeSteel.plotting.interaction import (  # noqa: PLC0415
            plot_pm_interaction,
        )

        return plot_pm_interaction(self, **kwargs)  # type: ignore[arg-type]

    def plot_mm_interaction(self, **kwargs: object) -> Axes:
        """Plot the §H1.1 Mrx-Mry envelope at a fixed Pr.

        Thin delegate to
        :func:`apeSteel.plotting.interaction.plot_mm_interaction`.
        Requires ``axial_load_Pr`` as a keyword argument.
        """
        from apeSteel.plotting.interaction import (  # noqa: PLC0415
            plot_mm_interaction,
        )

        return plot_mm_interaction(self, **kwargs)  # type: ignore[arg-type]

    def plot_pmm_interaction_3d(self, **kwargs: object) -> Axes:
        """Plot the full 3D §H1.1 P-Mx-My envelope.

        Thin delegate to
        :func:`apeSteel.plotting.interaction.plot_pmm_interaction_3d`.
        """
        from apeSteel.plotting.interaction import (  # noqa: PLC0415
            plot_pmm_interaction_3d,
        )

        return plot_pmm_interaction_3d(self, **kwargs)  # type: ignore[arg-type]

    # ------------------------------------------------------------------ #
    # Combined flexure + axial - AISC 360-22 §H1.1 (Eq. H1-1a/H1-1b)
    # ------------------------------------------------------------------ #
    def combined_strength_H1(
        self,
        required_axial_Pr: float,
        required_moment_x_Mrx: float,
        *,
        effective_length_factor_Kx: float,
        unbraced_length_Lx: float,
        effective_length_factor_Ky: float,
        unbraced_length_Ly: float,
        effective_length_factor_Kz: float,
        unbraced_length_Lz: float,
        required_moment_y_Mry: float = 0.0,
        available_moment_y_Mcy: float = 0.0,
        transverse_stiffener_spacing_a: float | None = None,
    ) -> CombinedH1Report:
        """AISC 360-22 §H1.1 beam-column interaction (Eq. H1-1a/H1-1b).

        Resolves ``Pc`` from this element's Chapter-E strength
        (``phi_c*Pn``) and ``Mcx`` from its governing Chapter-F major-
        axis strength (``phi_b*Mnx``), then evaluates the §H1.1 unity
        equation.  Doubly-symmetric I only (the ``Element`` spine; the
        same restriction as :meth:`compression_strength` /
        :meth:`run_full_check`).

        ``Pr``/``Mrx``/``Mry`` are the *required second-order* strengths
        (Direct Analysis Method - already amplified; no Appendix-8
        machinery, per design note 09).

        **Biaxial ``Mcy`` (Phase F-8 - closes the design-note-09 H-7
        gap).**  ``Mcy`` is the available **minor-axis** flexural
        strength ``phi_b*Mny``:

        * If ``available_moment_y_Mcy`` is supplied (``> 0``) it is used
          **verbatim** - the prior explicit-``Mcy`` behaviour is
          byte-unchanged.
        * If ``required_moment_y_Mry != 0`` and no ``Mcy`` is given,
          ``Mcy`` is now **auto-resolved** from this element's AISC
          360-22 **§F6** minor-axis strength
          (:func:`~apeSteel.flexure.compute_flexural_strength_F6_minor_axis`,
          ``section_kind="doubly_symmetric_I"``) - shipped in Phase
          F-4; before F-8 apeSteel had no §F6, so this used to raise.
        * If the check is uniaxial (``Mry == 0`` and no ``Mcy``),
          ``Mcy`` stays ``0.0`` and §F6 is **not** evaluated - the
          uniaxial path (and every shipped Chapter-H number) is
          byte-unchanged.

        Requires :attr:`bracing` to be set (for the Chapter-F ``Mcx``).
        """
        self._require_doubly_symmetric_section("combined_strength_H1")
        compression = self.compression_strength(
            effective_length_factor_Kx,
            unbraced_length_Lx,
            effective_length_factor_Ky,
            unbraced_length_Ly,
            effective_length_factor_Kz,
            unbraced_length_Lz,
        )
        beam_check = self.run_full_check(
            transverse_stiffener_spacing_a=transverse_stiffener_spacing_a,
        )
        # Resolve Mcy.  An explicitly-supplied Mcy (> 0) is used
        # verbatim (the prior behaviour - bit-identical).  Only when the
        # check is biaxial *and* no Mcy was given is §F6 invoked to
        # auto-resolve it (the F-8 gap closure); the uniaxial path never
        # touches §F6, so it is byte-unchanged.
        resolved_Mcy: float = available_moment_y_Mcy
        if required_moment_y_Mry != 0.0 and available_moment_y_Mcy <= 0.0:
            f6 = compute_flexural_strength_F6_minor_axis(
                self.section_properties,
                self.material,
                section_kind="doubly_symmetric_I",
                construction=self.construction,
            )
            resolved_Mcy = f6.phi_strength_LRFD
        return compute_combined_strength_H1_1(
            required_axial_Pr=required_axial_Pr,
            available_axial_Pc=compression.phi_strength_LRFD,
            required_moment_x_Mrx=required_moment_x_Mrx,
            available_moment_x_Mcx=beam_check.governing_flexural_phi_Mn,
            required_moment_y_Mry=required_moment_y_Mry,
            available_moment_y_Mcy=resolved_Mcy,
        )

    # ------------------------------------------------------------------ #
    # F5 LTB + CFY + FLB - plate girder (slender web)
    # ------------------------------------------------------------------ #
    def flexural_strength_F5_top_flange(self) -> FlexureF5Report:
        """§F5 strength assuming the **top** flange is in compression.

        AISC 360-22 §F5 covers doubly- *and* singly-symmetric slender-web
        I-shapes.  For a singly-symmetric section this passes the
        top-compression :class:`SectionProperties` (top-flange geometry,
        ``Sxc``/``Sxt``/``hc``/``hp`` for that direction).  For a
        doubly-symmetric section ``section_properties_for("top")``
        returns the same cached :attr:`section_properties`, so the result
        is byte-identical to the prior DS-only behaviour.
        """
        br = self._require_bracing()
        return compute_flexural_strength_F5_slender_web_plate_girder(
            section_properties=self.section_properties_for("top"),
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_top_flange_Lb_top,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
            construction=self.construction,
        )

    def flexural_strength_F5_bot_flange(self) -> FlexureF5Report:
        """§F5 strength assuming the **bottom** flange is in compression.

        Singly- and doubly-symmetric (see
        :meth:`flexural_strength_F5_top_flange`); DS is byte-identical to
        the prior behaviour.
        """
        br = self._require_bracing()
        return compute_flexural_strength_F5_slender_web_plate_girder(
            section_properties=self.section_properties_for("bot"),
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_bot_flange_Lb_bot,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
            construction=self.construction,
        )

    def flexural_strength_F5_both_flanges(self) -> BothFlangesFlexureF5Report:
        top = self.flexural_strength_F5_top_flange()
        bot = self.flexural_strength_F5_bot_flange()
        if top.phi_strength_LRFD <= bot.phi_strength_LRFD:
            return BothFlangesFlexureF5Report(
                top=top,
                bot=bot,
                governing_flange="top",
                governing_report=top,
            )
        return BothFlangesFlexureF5Report(
            top=top,
            bot=bot,
            governing_flange="bot",
            governing_report=bot,
        )

    # ------------------------------------------------------------------ #
    # φMn-vs-Lb capacity curve
    # ------------------------------------------------------------------ #
    def phi_Mn_vs_Lb(  # noqa: PLR0912
        self,
        unbraced_lengths_Lb: Sequence[float],
        *,
        lateral_torsional_buckling_modification_factor_Cb: float = 1.0,
        flange: Literal["top", "bot", "governing"] = "governing",
    ) -> tuple[FlexuralCurvePoint, ...]:
        """Sweep φMn as a function of unbraced length Lb (symmetric).

        Classification is geometry-based, so the AISC §B4.1b classifier
        runs **once** to pick the routed engine (F2 / F3 / F4 / F5).
        That engine is then evaluated at each Lb in ``unbraced_lengths_Lb``.

        The sweep is symmetric: at every point ``Lb_top = Lb_bot = Lb``.
        Both flanges are checked and ``flange`` selects which value to
        return:

        * ``"governing"`` (default) — lower of top/bot φMn (changes
          along the curve only for singly-symmetric sections).
        * ``"top"`` / ``"bot"`` — force that flange.

        ``Cb`` is taken from this parameter (default ``1.0``) rather
        than from ``element.bracing``, since the bracing's Cb describes
        the as-built case and the sweep is a parameter study.

        Parameters
        ----------
        unbraced_lengths_Lb : sequence of float
            Lb values to sweep (mm).  All must be positive.
        lateral_torsional_buckling_modification_factor_Cb : float
            Cb per AISC F1-1.  Default 1.0.
        flange : {"top", "bot", "governing"}
            Which flange's check to report.  Default ``"governing"``.

        Returns
        -------
        tuple of FlexuralCurvePoint
        """
        from apeSteel.sections.geometry import (  # noqa: PLC0415
            SinglySymmetricISection,
        )

        # The Element spine restricts `section` to ISection
        # (DoublySymmetricISection | SinglySymmetricISection) already, so
        # an isinstance guard here would be tautological.

        classification = self.classify_flexural()
        is_singly_symmetric = isinstance(self.section, SinglySymmetricISection)
        web_class = classification.web.classification
        flange_class = classification.flange.classification

        routed: RoutedFlexureChapterCurve
        if is_singly_symmetric:
            routed = "F5" if web_class == "slender" else "F4"
        elif web_class == "slender":
            routed = "F5"
        elif web_class == "non_compact":
            routed = "F4"
        elif flange_class == "compact":
            routed = "F2"
        else:
            routed = "F3"

        # Pre-compute per-flange section_properties (matters for SS).
        props_top = self.section_properties_for("top")
        props_bot = self.section_properties_for("bot")
        Cb = lateral_torsional_buckling_modification_factor_Cb

        def _evaluate(
            Lb: float,
            props: SectionProperties,
        ) -> FlexureF2Report | FlexureF3Report | FlexureF4Report | FlexureF5Report:
            if routed == "F2":
                return compute_flexural_strength_F2_compact_doubly_symmetric(
                    section_properties=props,
                    material=self.material,
                    unbraced_length_Lb=Lb,
                    lateral_torsional_buckling_modification_factor_Cb=Cb,
                )
            if routed == "F3":
                return compute_flexural_strength_F3_noncompact_or_slender_flange(
                    section_properties=props,
                    material=self.material,
                    unbraced_length_Lb=Lb,
                    lateral_torsional_buckling_modification_factor_Cb=Cb,
                    construction=self.construction,
                )
            if routed == "F4":
                return compute_flexural_strength_F4(
                    section_properties=props,
                    material=self.material,
                    unbraced_length_Lb=Lb,
                    lateral_torsional_buckling_modification_factor_Cb=Cb,
                    construction=self.construction,
                )
            return compute_flexural_strength_F5_slender_web_plate_girder(
                section_properties=props,
                material=self.material,
                unbraced_length_Lb=Lb,
                lateral_torsional_buckling_modification_factor_Cb=Cb,
                construction=self.construction,
            )

        points: list[FlexuralCurvePoint] = []
        for Lb in unbraced_lengths_Lb:
            if Lb <= 0.0:
                raise ValueError(f"unbraced_lengths_Lb must all be positive, got {Lb!r}")
            top_report = _evaluate(Lb, props_top)
            bot_report = _evaluate(Lb, props_bot)
            if flange == "top":
                chosen, chosen_flange = top_report, "top"
            elif flange == "bot":
                chosen, chosen_flange = bot_report, "bot"
            elif top_report.phi_strength_LRFD <= bot_report.phi_strength_LRFD:
                chosen, chosen_flange = top_report, "top"
            else:
                chosen, chosen_flange = bot_report, "bot"
            # F2/F3 vs F4/F5 carry differently-named Lp/Lr fields
            # (F4/F5 suffix the field name with _F4 / _F5).
            if isinstance(chosen, FlexureF2Report | FlexureF3Report):
                Lp = chosen.limiting_length_plastic_Lp
                Lr = chosen.limiting_length_inelastic_LTB_Lr
            elif isinstance(chosen, FlexureF4Report):
                Lp = chosen.limiting_length_plastic_Lp_F4
                Lr = chosen.limiting_length_inelastic_LTB_Lr_F4
            else:  # FlexureF5Report
                Lp = chosen.limiting_length_plastic_Lp_F5
                Lr = chosen.limiting_length_inelastic_LTB_Lr_F5
            points.append(
                FlexuralCurvePoint(
                    unbraced_length_Lb=Lb,
                    nominal_strength_Mn=chosen.nominal_strength,
                    design_strength_phi_Mn=chosen.phi_strength_LRFD,
                    routed_chapter=routed,
                    governing_flange=chosen_flange,
                    governing_limit_state=chosen.governing_limit_state,
                    limiting_length_plastic_Lp=Lp,
                    limiting_length_inelastic_LTB_Lr=Lr,
                )
            )
        return tuple(points)

    # ------------------------------------------------------------------ #
    # Serviceability - elastic deflections (Phase 8b)
    # ------------------------------------------------------------------ #
    def serviceability_simply_supported_udl(
        self,
        span_length_L: float,
        distributed_load_dead_w_dead: float = 0.0,
        distributed_load_superdead_w_sd: float = 0.0,
        distributed_load_live_w_live: float = 0.0,
        live_load_limit_denominator: float = DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
        total_load_limit_denominator: float = DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    ) -> SimplySupportedUDLDeflectionReport:
        """Mid-span deflection of this element as a simply-supported UDL beam."""
        return compute_deflection_simply_supported_udl(
            section_properties=self.section_properties,
            material=self.material,
            span_length_L=span_length_L,
            distributed_load_dead_w_dead=distributed_load_dead_w_dead,
            distributed_load_superdead_w_sd=distributed_load_superdead_w_sd,
            distributed_load_live_w_live=distributed_load_live_w_live,
            live_load_limit_denominator=live_load_limit_denominator,
            total_load_limit_denominator=total_load_limit_denominator,
        )

    def serviceability_simply_supported_point_load_midspan(
        self,
        span_length_L: float,
        point_load_dead_P_dead: float = 0.0,
        point_load_live_P_live: float = 0.0,
        live_load_limit_denominator: float = DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
        total_load_limit_denominator: float = DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    ) -> SimplySupportedPointLoadMidspanDeflectionReport:
        """Mid-span deflection under a centred point load."""
        return compute_deflection_simply_supported_point_load_midspan(
            section_properties=self.section_properties,
            material=self.material,
            span_length_L=span_length_L,
            point_load_dead_P_dead=point_load_dead_P_dead,
            point_load_live_P_live=point_load_live_P_live,
            live_load_limit_denominator=live_load_limit_denominator,
            total_load_limit_denominator=total_load_limit_denominator,
        )

    def serviceability_simply_supported_point_load_arbitrary(
        self,
        span_length_L: float,
        distance_from_left_support_a: float,
        point_load_total_P_total: float,
        total_load_limit_denominator: float = DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    ) -> SimplySupportedPointLoadArbitraryDeflectionReport:
        """Deflection under a point load at distance ``a`` from the left support."""
        return compute_deflection_simply_supported_point_load_arbitrary(
            section_properties=self.section_properties,
            material=self.material,
            span_length_L=span_length_L,
            distance_from_left_support_a=distance_from_left_support_a,
            point_load_total_P_total=point_load_total_P_total,
            total_load_limit_denominator=total_load_limit_denominator,
        )

    def serviceability_cantilever_udl_and_tip_load(
        self,
        cantilever_length_L: float,
        distributed_load_w: float = 0.0,
        tip_point_load_P: float = 0.0,
        deflection_limit_denominator: float = DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    ) -> CantileverUDLAndTipLoadDeflectionReport:
        """Tip deflection of a cantilever under combined UDL + tip load."""
        return compute_deflection_cantilever_udl_and_tip_load(
            section_properties=self.section_properties,
            material=self.material,
            cantilever_length_L=cantilever_length_L,
            distributed_load_w=distributed_load_w,
            tip_point_load_P=tip_point_load_P,
            deflection_limit_denominator=deflection_limit_denominator,
        )

    # ------------------------------------------------------------------ #
    # Full beam check - classify + flexure routing (F2/F3/F4/F5) + shear
    # ------------------------------------------------------------------ #
    def run_full_check(
        self,
        transverse_stiffener_spacing_a: float | None = None,
    ) -> BeamCheckReport:
        """Run the full beam-check facade on this element.

        Classifies per AISC B4.1b, routes flexure to F2 / F3 / F4 / F5
        accordingly, and runs G2 shear.  Singly-symmetric I-sections
        route to F4 (compact / non-compact web) or F5 (slender web -
        AISC §F5 covers DS *and* SS).

        Requires `self.bracing` to be set.
        """
        from apeSteel.checks.beam_check import run_full_beam_check  # noqa: PLC0415

        return run_full_beam_check(
            self,
            transverse_stiffener_spacing_a=transverse_stiffener_spacing_a,
        )


__all__ = [
    "BothFlangesFlexureF2Report",
    "BothFlangesFlexureF3Report",
    "BothFlangesFlexureF4Report",
    "BothFlangesFlexureF5Report",
    "CombinedH1Report",
    "Element",
    "GoverningFlange",
    "ShearG2Report",
]

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
from typing import TYPE_CHECKING, Literal

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
from apeSteel.compression import (
    CapacityCurvePoint,
    CompressionStrengthReport,
    compute_compression_strength_from_K_L,
    compute_phi_Pn_vs_length,
)
from apeSteel.flexure import (
    FlexureF2Report,
    FlexureF3Report,
    FlexureF4Report,
    FlexureF5Report,
    compute_flexural_strength_F2_compact_doubly_symmetric,
    compute_flexural_strength_F3_noncompact_or_slender_flange,
    compute_flexural_strength_F4,
    compute_flexural_strength_F5_slender_web_plate_girder,
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

    from apeSteel.beam_column_connection import BeamColumnConnection
    from apeSteel.bracing import Bracing
    from apeSteel.checks import BeamCheckReport
    from apeSteel.core.materials import SteelMaterial
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
    For singly-symmetric sections the F4 methods are the canonical
    flexural-strength interface; F2 / F3 / F5 (which assume doubly-
    symmetric geometry) raise :class:`NotImplementedError`.
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

    # ------------------------------------------------------------------ #
    # F5 LTB + CFY + FLB - plate girder (slender web)
    # ------------------------------------------------------------------ #
    def flexural_strength_F5_top_flange(self) -> FlexureF5Report:
        self._require_doubly_symmetric_section("flexural_strength_F5_top_flange")
        br = self._require_bracing()
        return compute_flexural_strength_F5_slender_web_plate_girder(
            section_properties=self.section_properties,
            material=self.material,
            unbraced_length_Lb=br.unbraced_length_top_flange_Lb_top,
            lateral_torsional_buckling_modification_factor_Cb=(
                br.lateral_torsional_buckling_modification_factor_Cb
            ),
            construction=self.construction,
        )

    def flexural_strength_F5_bot_flange(self) -> FlexureF5Report:
        self._require_doubly_symmetric_section("flexural_strength_F5_bot_flange")
        br = self._require_bracing()
        return compute_flexural_strength_F5_slender_web_plate_girder(
            section_properties=self.section_properties,
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
        always route to F4 (slender-web SS is not yet supported).

        Requires `self.bracing` to be set.
        """
        from apeSteel.checks import run_full_beam_check  # noqa: PLC0415

        return run_full_beam_check(
            self,
            transverse_stiffener_spacing_a=transverse_stiffener_spacing_a,
        )


__all__ = [
    "BothFlangesFlexureF2Report",
    "BothFlangesFlexureF3Report",
    "BothFlangesFlexureF4Report",
    "BothFlangesFlexureF5Report",
    "Element",
    "GoverningFlange",
    "ShearG2Report",
]

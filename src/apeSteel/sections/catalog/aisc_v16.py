"""AISC v16 shapes catalog.

The :class:`AISCv16Catalog` is the user-facing interface to the AISC
v16 shapes database that ships with apeSteel. It exposes three
adapters:

* :meth:`~AISCv16Catalog.get_row` - return the raw
  :class:`~apeSteel.sections.catalog._aisc_v16_row.CatalogRowAISCv16`
  for ad-hoc queries against any of the 2 299 shapes in the database
  (including channels, angles, HSS, pipes).
* :meth:`~AISCv16Catalog.get_section_properties` - adapt a row into the
  universal :class:`~apeSteel.sections.properties.SectionProperties`
  frozen dataclass for use by every downstream calculator
  (classification, F2/F3/F5, G2). Only doubly-symmetric I-shapes
  (``W``/``M``/``S``/``HP``) can be adapted today; other types raise
  :class:`~apeSteel.sections.catalog.exceptions.SectionTypeNotAdaptableError`.
* :meth:`~AISCv16Catalog.get_doubly_symmetric_i_geometry` - reconstruct
  a plate-built :class:`~apeSteel.sections.geometry.DoublySymmetricISection`
  from the published ``(bf, tf, h, tw)`` plate dimensions. Useful for
  verification (compare the plate-built ``Ag, Ix, J, Cw`` against the
  AISC published values) and for cases where the calculator needs raw
  plate-element dimensions.

Fuzzy matching
--------------
Looking up a label that doesn't match any row exactly triggers a
RapidFuzz fuzzy fallback. If the best similarity score is at least
:data:`DEFAULT_FUZZY_SIMILARITY_THRESHOLD` (80/100) the chosen
alternative is returned and a warning is emitted through the standard
:mod:`logging` framework. Below the threshold,
:class:`~apeSteel.sections.catalog.exceptions.SectionNotFoundError` is
raised with the best candidate attached for debugging.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Final

from rapidfuzz import process

from apeSteel.sections.catalog._aisc_v16_row import (
    DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES,
    CatalogRowAISCv16,
)
from apeSteel.sections.catalog._data_loader import (
    build_catalog_row_aisc_v16,
    load_aisc_v16_dataframe,
)
from apeSteel.sections.catalog.exceptions import (
    SectionNotFoundError,
    SectionTypeNotAdaptableError,
)
from apeSteel.sections.flexural_properties import (
    FlexuralPlateElement,
    FlexuralSectionProperties,
)
from apeSteel.sections.geometry import DoublySymmetricISection
from apeSteel.sections.properties import SectionProperties

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

#: AISC 360-22 Eq. F2-8b channel section-constant ``ho`` divisor
#: ``c = (ho/2)*sqrt(Iy/Cw)`` (spec_chapterF.txt printed 16.1-54).
_EQ_F2_8B_HO_DIVISOR: float = 2.0

LOGGER: logging.Logger = logging.getLogger(__name__)

DEFAULT_FUZZY_SIMILARITY_THRESHOLD: Final[float] = 80.0
"""RapidFuzz score floor for an acceptable fuzzy fallback (0 - 100).

A typical typo such as ``"W24x94"`` -> ``"W24X94"`` scores 100;
``"W24X95"`` -> ``"W24X94"`` scores ~93. 80 leaves room for one-
character differences without admitting unrelated sections."""


class AISCv16Catalog:
    """In-memory wrapper around the AISC v16 SI shapes database."""

    def __init__(
        self,
        csv_path: Path | None = None,
        *,
        fuzzy_similarity_threshold: float = DEFAULT_FUZZY_SIMILARITY_THRESHOLD,
    ) -> None:
        self._csv_path: Path | None = csv_path
        self._fuzzy_similarity_threshold: float = fuzzy_similarity_threshold

    def _dataframe(self) -> pd.DataFrame:
        return load_aisc_v16_dataframe(self._csv_path)

    def _resolve_label(self, requested_label: str) -> str:
        """Exact match first; fuzzy fallback via RapidFuzz."""
        normalised: str = requested_label.upper().strip()
        labels = self._dataframe()["AISC_Manual_Label"].tolist()

        if normalised in labels:
            return normalised

        # rapidfuzz returns (choice, score, index) tuple — or None when
        # the haystack is empty. The library's stubs are not fully
        # typed so we narrow explicitly here.
        # rapidfuzz returns (choice, score, index); the typestub does
        # not model the empty-haystack case (the catalog CSV is always
        # non-empty, so that branch is unreachable here anyway).
        best = process.extractOne(normalised, labels)
        best_label: str = str(best[0])
        best_score: float = float(best[1])
        if best_score < self._fuzzy_similarity_threshold:
            raise SectionNotFoundError(
                requested_label,
                best_fuzzy_match=best_label,
                best_fuzzy_score=best_score,
                similarity_threshold=self._fuzzy_similarity_threshold,
            )
        LOGGER.warning(
            "AISCv16Catalog: '%s' not found exactly; using fuzzy match '%s' (score=%.1f).",
            requested_label,
            best_label,
            best_score,
        )
        return best_label

    def get_row(self, label: str) -> CatalogRowAISCv16:
        """Return the validated row for ``label`` (case-insensitive, fuzzy fallback)."""
        canonical: str = self._resolve_label(label)
        df = self._dataframe()
        row = df.loc[df["AISC_Manual_Label"] == canonical].iloc[0]
        return build_catalog_row_aisc_v16(row)

    def get_section_properties(self, label: str) -> SectionProperties:
        """Adapt a doubly-symmetric I row into a SectionProperties dataclass."""
        row: CatalogRowAISCv16 = self.get_row(label)
        if row.Type not in DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES:
            raise SectionTypeNotAdaptableError(
                row.AISC_Manual_Label,
                section_type=row.Type,
                requested_adapter="get_section_properties",
                reason=(
                    "only doubly-symmetric I-shapes (W/M/S/HP) currently adapt to "
                    "SectionProperties; downstream channel/angle/HSS calculators "
                    "are not yet implemented in apeSteel."
                ),
            )
        return _build_section_properties_from_aisc_v16_row(row)

    def get_flexural_section_properties(self, label: str) -> FlexuralSectionProperties:
        """Adapt a catalog row into a Chapter-F ``FlexuralSectionProperties``.

        The Phase-F-8 catalog flexure path.  Returns the generalized
        Chapter-F currency
        (:class:`~apeSteel.sections.flexural_properties.FlexuralSectionProperties`)
        wired to the correct §F family by the AISC v16 ``Type`` code:

        ================  ==========================================
        AISC ``Type``     ``section_kind`` / governing §F
        ================  ==========================================
        W/M/S/HP          ``doubly_symmetric_I`` (§F2-§F5; the
                          **same** bit-identical lift the legacy
                          :meth:`get_section_properties` produces,
                          via ``FlexuralSectionProperties.from_legacy``)
        C/MC              ``channel`` (§F2 major / §F6 minor; Eq.
                          F2-8b ``c``)
        HSS (rect)        ``rectangular_HSS`` (§F7, both axes)
        HSS (round)/PIPE  ``round_HSS`` (§F8)
        WT/MT/ST          ``tee`` (§F9)
        L                 ``single_angle`` (§F10)
        ================  ==========================================

        Properties are taken **verbatim from the published AISC v16
        row** (already in base units by the loader) - *not*
        plate-reconstructed - so a catalog-anchored golden can
        cross-check apeSteel's §F ``phi*Mn`` against the §F engine on
        the catalog's own ``Z``/``S``/``I``/``J`` (the documented
        rolled-vs-plate ``k``-radius gap would otherwise swamp the
        comparison; design note 10 §6).

        Parameters
        ----------
        label : str
            AISC Manual label (case-insensitive, RapidFuzz fallback).

        Returns
        -------
        FlexuralSectionProperties

        Raises
        ------
        SectionTypeNotAdaptableError
            If the row's ``Type`` has no §F flexural mapping (only
            ``2L`` among the catalogued types: the AISC v16 ``2L`` row
            does **not** publish ``J``/``ry``, which §F9 requires - a
            genuine catalog-data gap, *not* an invented value), or a
            required published column is missing for this row.
        """
        row: CatalogRowAISCv16 = self.get_row(label)
        if row.Type in DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES:
            # W/M/S/HP: lift the *legacy* I currency losslessly - the
            # exact same SectionProperties get_section_properties()
            # returns - so the I-shape catalog path stays bit-identical
            # (the catalog-F2 golden is pinned on get_section_properties).
            legacy = _build_section_properties_from_aisc_v16_row(row)
            return FlexuralSectionProperties.from_legacy(
                legacy,
                kind="doubly_symmetric_I",
                symmetry="doubly_symmetric",
                construction="rolled",
            )
        if row.Type in ("C", "MC"):
            return _flexural_channel_from_aisc_v16_row(row)
        if row.Type == "HSS":
            return _flexural_hss_from_aisc_v16_row(row)
        if row.Type == "PIPE":
            return _flexural_round_hss_from_aisc_v16_row(row)
        if row.Type in ("WT", "MT", "ST"):
            return _flexural_tee_from_aisc_v16_row(row)
        if row.Type == "L":
            return _flexural_single_angle_from_aisc_v16_row(row)
        # 2L: the AISC v16 double-angle row publishes neither J nor ry
        # (both empty in data/AISC_v16_shapes.csv), and §F9 requires
        # both (Eq. F9-9/F9-10/F9-11).  Refuse rather than invent.
        raise SectionTypeNotAdaptableError(
            row.AISC_Manual_Label,
            section_type=row.Type,
            requested_adapter="get_flexural_section_properties",
            reason=(
                "the AISC v16 2L (double-angle) row does not publish J or ry, "
                "which AISC 360-22 §F9 (Eq. F9-9/F9-10/F9-11) requires; build a "
                "DoubleAngleSection from the component-angle plate dimensions "
                "and use its compute_section_properties() instead "
                "(no AISC value is invented here)."
            ),
        )

    def get_doubly_symmetric_i_geometry(self, label: str) -> DoublySymmetricISection:
        """Return a plate-built DoublySymmetricISection for ``label``.

        Uses the AISC v16 ``(bf, tf, tw, d)`` columns and derives
        ``hw = d - 2*tf``. This is a plate-built reconstruction: it
        omits the root-radius fillets at the flange-web junction and
        therefore produces a slightly smaller ``Ag``, ``Ix``, and ``J``
        than the AISC published values for rolled shapes.
        """
        row: CatalogRowAISCv16 = self.get_row(label)
        if row.Type not in DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES:
            raise SectionTypeNotAdaptableError(
                row.AISC_Manual_Label,
                section_type=row.Type,
                requested_adapter="get_doubly_symmetric_i_geometry",
                reason="only doubly-symmetric I-shapes (W/M/S/HP) have a four-plate description.",
            )
        missing: list[str] = [
            name
            for name, value in (
                ("d", row.d),
                ("bf", row.bf),
                ("tf", row.tf),
                ("tw", row.tw),
            )
            if value is None
        ]
        if missing:
            raise SectionTypeNotAdaptableError(
                row.AISC_Manual_Label,
                section_type=row.Type,
                requested_adapter="get_doubly_symmetric_i_geometry",
                reason=f"required plate dimensions missing in catalog: {missing}",
            )
        assert row.d is not None
        assert row.bf is not None
        assert row.tf is not None
        assert row.tw is not None
        web_clear_height_hw: float = row.d - 2.0 * row.tf
        return DoublySymmetricISection(
            flange_width_bf=row.bf,
            flange_thickness_tf=row.tf,
            web_clear_height_hw=web_clear_height_hw,
            web_thickness_tw=row.tw,
        )


def _build_section_properties_from_aisc_v16_row(row: CatalogRowAISCv16) -> SectionProperties:
    """Build SectionProperties from a doubly-symmetric I row.

    Pre-conditions: ``row.Type`` is one of ``"W"``, ``"M"``, ``"S"``,
    ``"HP"`` and every flexural field is populated.
    """
    required_fields: tuple[tuple[str, float | None], ...] = (
        ("A", row.A),
        ("d", row.d),
        ("W", row.W),
        ("Ix", row.Ix),
        ("Sx", row.Sx),
        ("Zx", row.Zx),
        ("rx", row.rx),
        ("Iy", row.Iy),
        ("Sy", row.Sy),
        ("Zy", row.Zy),
        ("ry", row.ry),
        ("J", row.J),
        ("Cw", row.Cw),
        ("ho", row.ho),
        ("rts", row.rts),
        ("bf_2tf", row.bf_2tf),
        ("h_tw", row.h_tw),
        ("tw", row.tw),
        ("bf", row.bf),
        ("tf", row.tf),
    )
    missing: list[str] = [name for name, value in required_fields if value is None]
    if missing:
        raise SectionTypeNotAdaptableError(
            row.AISC_Manual_Label,
            section_type=row.Type,
            requested_adapter="get_section_properties",
            reason=f"required AISC v16 columns missing for this row: {missing}",
        )
    assert row.A is not None
    assert row.d is not None
    assert row.W is not None
    assert row.Ix is not None
    assert row.Sx is not None
    assert row.Zx is not None
    assert row.rx is not None
    assert row.Iy is not None
    assert row.Sy is not None
    assert row.Zy is not None
    assert row.ry is not None
    assert row.J is not None
    assert row.Cw is not None
    assert row.ho is not None
    assert row.rts is not None
    assert row.bf_2tf is not None
    assert row.h_tw is not None
    assert row.tw is not None
    assert row.bf is not None
    assert row.tf is not None

    # AISC publishes W in kg/m, stored as tonne/mm in apeSteel base.
    # SectionProperties exposes weight as a force per length (N/mm)
    # so downstream serviceability code uses it directly. Multiply
    # by g in base units to land in N/mm.
    from apeSteel.core.units import g as gravitational_acceleration_g  # noqa: PLC0415

    nominal_weight_per_unit_length_w_force: float = row.W * gravitational_acceleration_g

    return SectionProperties(
        overall_depth_d=row.d,
        gross_area_Ag=row.A,
        nominal_weight_per_unit_length_w=nominal_weight_per_unit_length_w_force,
        moment_of_inertia_strong_axis_Ix=row.Ix,
        elastic_section_modulus_strong_axis_Sx=row.Sx,
        plastic_section_modulus_strong_axis_Zx=row.Zx,
        radius_of_gyration_strong_axis_rx=row.rx,
        moment_of_inertia_weak_axis_Iy=row.Iy,
        elastic_section_modulus_weak_axis_Sy=row.Sy,
        plastic_section_modulus_weak_axis_Zy=row.Zy,
        radius_of_gyration_weak_axis_ry=row.ry,
        torsional_constant_J=row.J,
        warping_constant_Cw=row.Cw,
        distance_between_flange_centroids_ho=row.ho,
        effective_radius_of_gyration_for_LTB_rts=row.rts,
        flange_width_to_thickness_ratio_bf_2tf=row.bf_2tf,
        web_height_to_thickness_ratio_h_tw=row.h_tw,
        web_thickness_tw=row.tw,
        flange_width_bf=row.bf,
        flange_thickness_tf=row.tf,
        # Detailing offsets - default to 0.0 when the AISC row leaves
        # them blank (W/M/S/HP shapes always have them populated).
        k_design_kdes=row.kdes if row.kdes is not None else 0.0,
        k_detailing_kdet=row.kdet if row.kdet is not None else 0.0,
        k_one_k1=row.k1 if row.k1 is not None else 0.0,
    )


def _require_row_fields(
    row: CatalogRowAISCv16,
    named_values: tuple[tuple[str, float | None], ...],
) -> None:
    """Raise :class:`SectionTypeNotAdaptableError` if any value is None.

    The AISC v16 database uses the en-dash marker for "not applicable
    for this section type"; the loader maps that to ``None``.  A §F
    builder that needs a column it does not have must fail loudly with
    the missing names (the existing
    :func:`_build_section_properties_from_aisc_v16_row` pattern), never
    silently substitute or invent a value.
    """
    missing: list[str] = [name for name, value in named_values if value is None]
    if missing:
        raise SectionTypeNotAdaptableError(
            row.AISC_Manual_Label,
            section_type=row.Type,
            requested_adapter="get_flexural_section_properties",
            reason=f"required AISC v16 columns missing for this row: {missing}",
        )


def _flexural_channel_from_aisc_v16_row(row: CatalogRowAISCv16) -> FlexuralSectionProperties:
    """``C`` / ``MC`` -> ``channel`` §F2(major)/§F6(minor) currency.

    Properties verbatim from the published row.  The Eq. F2-8b channel
    section constant ``c = (ho/2)*sqrt(Iy/Cw)`` is derived from the
    published ``ho``/``Iy``/``Cw`` - the *same* closed form
    :meth:`FlexuralSectionProperties.from_legacy` /
    :meth:`ChannelSection.compute_section_properties` use.
    """
    _require_row_fields(
        row,
        (
            ("d", row.d),
            ("bf", row.bf),
            ("tf", row.tf),
            ("A", row.A),
            ("Ix", row.Ix),
            ("Sx", row.Sx),
            ("Zx", row.Zx),
            ("rx", row.rx),
            ("Iy", row.Iy),
            ("Sy", row.Sy),
            ("Zy", row.Zy),
            ("ry", row.ry),
            ("J", row.J),
            ("Cw", row.Cw),
            ("ho", row.ho),
            ("rts", row.rts),
        ),
    )
    assert row.d is not None
    assert row.bf is not None
    assert row.tf is not None
    assert row.A is not None
    assert row.Ix is not None
    assert row.Sx is not None
    assert row.Zx is not None
    assert row.rx is not None
    assert row.Iy is not None
    assert row.Sy is not None
    assert row.Zy is not None
    assert row.ry is not None
    assert row.J is not None
    assert row.Cw is not None
    assert row.ho is not None
    assert row.rts is not None
    section_constant_c: float = (row.ho / _EQ_F2_8B_HO_DIVISOR) * math.sqrt(row.Iy / row.Cw)
    return FlexuralSectionProperties(
        section_kind="channel",
        symmetry="singly_symmetric",
        overall_depth_d=row.d,
        gross_area_Ag=row.A,
        moment_of_inertia_Ix=row.Ix,
        elastic_modulus_Sx=row.Sx,
        plastic_modulus_Zx=row.Zx,
        radius_of_gyration_rx=row.rx,
        moment_of_inertia_Iy=row.Iy,
        elastic_modulus_Sy=row.Sy,
        plastic_modulus_Zy=row.Zy,
        radius_of_gyration_ry=row.ry,
        torsional_constant_J=row.J,
        warping_constant_Cw=row.Cw,
        distance_between_flange_centroids_ho=row.ho,
        effective_radius_of_gyration_for_LTB_rts=row.rts,
        section_constant_c=section_constant_c,
        plate_elements=(),
    )


def _flexural_hss_from_aisc_v16_row(row: CatalogRowAISCv16) -> FlexuralSectionProperties:
    """Rectangular ``HSS`` -> ``rectangular_HSS`` §F7 currency.

    The two flat walls (``wall_B`` flat width ``B - 2t``, ``wall_H``
    flat width ``H - 2t``) are built with the AISC welded-box clear
    width convention - identical to
    :meth:`RectangularHSS.compute_section_properties` - so the §F7
    engine extracts them by name and classifies them itself
    (``lambda_p``/``lambda_r`` stay the neutral 0.0 sentinel).
    """
    _require_row_fields(
        row,
        (
            ("Ht", row.Ht),
            ("B", row.B),
            ("tdes", row.tdes),
            ("A", row.A),
            ("Ix", row.Ix),
            ("Sx", row.Sx),
            ("Zx", row.Zx),
            ("rx", row.rx),
            ("Iy", row.Iy),
            ("Sy", row.Sy),
            ("Zy", row.Zy),
            ("ry", row.ry),
            ("J", row.J),
        ),
    )
    assert row.Ht is not None
    assert row.B is not None
    assert row.tdes is not None
    assert row.A is not None
    assert row.Ix is not None
    assert row.Sx is not None
    assert row.Zx is not None
    assert row.rx is not None
    assert row.Iy is not None
    assert row.Sy is not None
    assert row.Zy is not None
    assert row.ry is not None
    assert row.J is not None
    h_depth: float = row.Ht
    b_width: float = row.B
    t: float = row.tdes
    wall_b = FlexuralPlateElement(
        name="wall_B",
        role="hss_flange",  # flange in major-axis bending
        aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-1/EC-2
        slenderness_ratio_lambda=(b_width - 2.0 * t) / t,
        compact_limit_lambda_p=0.0,
        noncompact_limit_lambda_r=0.0,
    )
    wall_h = FlexuralPlateElement(
        name="wall_H",
        role="hss_web",  # web in major-axis bending
        aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-1/EC-2
        slenderness_ratio_lambda=(h_depth - 2.0 * t) / t,
        compact_limit_lambda_p=0.0,
        noncompact_limit_lambda_r=0.0,
    )
    return FlexuralSectionProperties(
        section_kind="rectangular_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=h_depth,
        gross_area_Ag=row.A,
        moment_of_inertia_Ix=row.Ix,
        elastic_modulus_Sx=row.Sx,
        plastic_modulus_Zx=row.Zx,
        radius_of_gyration_rx=row.rx,
        moment_of_inertia_Iy=row.Iy,
        elastic_modulus_Sy=row.Sy,
        plastic_modulus_Zy=row.Zy,
        radius_of_gyration_ry=row.ry,
        torsional_constant_J=row.J,
        warping_constant_Cw=0.0,
        wall_thickness_t=t,
        plate_elements=(wall_b, wall_h),
    )


def _flexural_round_hss_from_aisc_v16_row(row: CatalogRowAISCv16) -> FlexuralSectionProperties:
    """``PIPE`` (and round ``HSS``) -> ``round_HSS`` §F8 currency."""
    _require_row_fields(
        row,
        (
            ("OD", row.OD),
            ("tdes", row.tdes),
            ("A", row.A),
            ("Ix", row.Ix),
            ("Sx", row.Sx),
            ("Zx", row.Zx),
            ("rx", row.rx),
        ),
    )
    assert row.OD is not None
    assert row.tdes is not None
    assert row.A is not None
    assert row.Ix is not None
    assert row.Sx is not None
    assert row.Zx is not None
    assert row.rx is not None
    # Axisymmetric: Iy/Sy/Zy/ry == the x-axis values.
    return FlexuralSectionProperties(
        section_kind="round_HSS",
        symmetry="doubly_symmetric",
        overall_depth_d=row.OD,
        gross_area_Ag=row.A,
        moment_of_inertia_Ix=row.Ix,
        elastic_modulus_Sx=row.Sx,
        plastic_modulus_Zx=row.Zx,
        radius_of_gyration_rx=row.rx,
        moment_of_inertia_Iy=row.Ix,
        elastic_modulus_Sy=row.Sx,
        plastic_modulus_Zy=row.Zx,
        radius_of_gyration_ry=row.rx,
        diameter_D=row.OD,
        wall_thickness_t=row.tdes,
        plate_elements=(),
    )


def _flexural_tee_from_aisc_v16_row(row: CatalogRowAISCv16) -> FlexuralSectionProperties:
    """``WT`` / ``MT`` / ``ST`` -> ``tee`` §F9 currency.

    The AISC v16 ``Sx`` for a tee is the elastic modulus to the
    **stem-tip** extreme fibre (the smaller modulus).  §F9.3 reads
    ``Sxc`` (the *flange* fibre).  From the published ``Ix``/``Sx``/
    ``d`` the centroid depth from the flange face is
    ``ybar = d - Ix/Sx`` (since published ``Sx = Ix/(d - ybar)``), so
    ``Sxc = Ix/ybar`` and ``Sxt = Sx`` - all exact from the row, no
    invented value.
    """
    _require_row_fields(
        row,
        (
            ("d", row.d),
            ("bf", row.bf),
            ("tf", row.tf),
            ("tw", row.tw),
            ("A", row.A),
            ("Ix", row.Ix),
            ("Sx", row.Sx),
            ("Zx", row.Zx),
            ("rx", row.rx),
            ("Iy", row.Iy),
            ("Sy", row.Sy),
            ("Zy", row.Zy),
            ("ry", row.ry),
            ("J", row.J),
        ),
    )
    assert row.d is not None
    assert row.bf is not None
    assert row.tf is not None
    assert row.tw is not None
    assert row.A is not None
    assert row.Ix is not None
    assert row.Sx is not None
    assert row.Zx is not None
    assert row.rx is not None
    assert row.Iy is not None
    assert row.Sy is not None
    assert row.Zy is not None
    assert row.ry is not None
    assert row.J is not None
    depth_to_stem_tip: float = row.Ix / row.Sx  # published Sx = Ix/(d - ybar)
    ybar: float = row.d - depth_to_stem_tip
    Sxc: float = row.Ix / ybar  # to the flange (compression) fibre
    Sxt: float = row.Sx  # to the stem tip (tension)
    ho: float = row.d - row.tf / 2.0
    return FlexuralSectionProperties(
        section_kind="tee",
        symmetry="singly_symmetric",
        overall_depth_d=row.d,
        gross_area_Ag=row.A,
        moment_of_inertia_Ix=row.Ix,
        elastic_modulus_Sx=row.Sx,
        plastic_modulus_Zx=row.Zx,
        radius_of_gyration_rx=row.rx,
        moment_of_inertia_Iy=row.Iy,
        elastic_modulus_Sy=row.Sy,
        plastic_modulus_Zy=row.Zy,
        radius_of_gyration_ry=row.ry,
        torsional_constant_J=row.J,
        distance_between_flange_centroids_ho=ho,
        elastic_modulus_compression_flange_Sxc=Sxc,
        elastic_modulus_tension_flange_Sxt=Sxt,
        plate_elements=(),
    )


def _flexural_single_angle_from_aisc_v16_row(row: CatalogRowAISCv16) -> FlexuralSectionProperties:
    """``L`` -> ``single_angle`` §F10 currency.

    Principal-axis constants come straight from the published row:
    ``Iz`` is the minor principal moment; the major principal moment
    is the invariant ``Iw = Ix + Iy - Iz`` (the in-plane
    moment-of-inertia sum is rotation-invariant); ``rz`` is published.
    ``equal_leg`` is decided from the published long/short leg ``b``
    (the AISC v16 ``b`` column is the long leg; an equal-leg L has the
    geometric ``Ix == Iy``).  The §F10 engine reads the geometric
    ``Sx``/``overall_depth_d`` (= leg width) for its geometric-axis
    option and re-derives the leg ``b/t`` from ``b``/``Ag``.
    """
    _require_row_fields(
        row,
        (
            ("b", row.b),
            ("A", row.A),
            ("Ix", row.Ix),
            ("Sx", row.Sx),
            ("Zx", row.Zx),
            ("rx", row.rx),
            ("Iy", row.Iy),
            ("Sy", row.Sy),
            ("Zy", row.Zy),
            ("ry", row.ry),
            ("Iz", row.Iz),
            ("rz", row.rz),
        ),
    )
    assert row.b is not None
    assert row.A is not None
    assert row.Ix is not None
    assert row.Sx is not None
    assert row.Zx is not None
    assert row.rx is not None
    assert row.Iy is not None
    assert row.Sy is not None
    assert row.Zy is not None
    assert row.ry is not None
    assert row.Iz is not None
    assert row.rz is not None
    # Major principal moment: the in-plane I-sum is rotation-invariant
    # (Ix + Iy = Iw + Iz), so Iw = Ix + Iy - Iz (exact, not invented).
    principal_I_major_Iw: float = row.Ix + row.Iy - row.Iz
    equal_leg: bool = math.isclose(row.Ix, row.Iy, rel_tol=1e-9)
    return FlexuralSectionProperties(
        section_kind="single_angle",
        symmetry="singly_symmetric",
        overall_depth_d=row.b,  # leg width (the §F10 ``b``)
        gross_area_Ag=row.A,
        moment_of_inertia_Ix=row.Ix,
        elastic_modulus_Sx=row.Sx,
        plastic_modulus_Zx=row.Zx,
        radius_of_gyration_rx=row.rx,
        moment_of_inertia_Iy=row.Iy,
        elastic_modulus_Sy=row.Sy,
        plastic_modulus_Zy=row.Zy,
        radius_of_gyration_ry=row.ry,
        principal_I_major_Iw=principal_I_major_Iw,
        principal_I_minor_Iz=row.Iz,
        min_principal_radius_rz=row.rz,
        equal_leg=equal_leg,
        geometric_axis_bending=False,
        plate_elements=(),
    )


__all__ = ["DEFAULT_FUZZY_SIMILARITY_THRESHOLD", "AISCv16Catalog"]

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
from apeSteel.sections.geometry import DoublySymmetricISection
from apeSteel.sections.properties import SectionProperties

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

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


__all__ = ["DEFAULT_FUZZY_SIMILARITY_THRESHOLD", "AISCv16Catalog"]

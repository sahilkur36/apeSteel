"""European IPE shapes catalog (EN 10365).

apeSteel ships a small but verifiable subset of EN 10365 IPE rolled
shapes - IPE 200, 300, 400, 500, 600 - in
``data/european_IPE_subset.csv``.  Users who need other sizes can
either edit the CSV directly or point :class:`EuropeanIPECatalog` at
their own CSV via the ``csv_path`` argument.

The subset was chosen to cover the practical range of European moment-
frame and beam sizes (IPE 200 is the smallest commonly used floor
beam; IPE 600 sits near the upper end of rolled European I-beams).

Surface
-------
The class mirrors :class:`~apeSteel.sections.catalog.aisc_v16.AISCv16Catalog`:

* :meth:`get_row` - return a validated
  :class:`~apeSteel.sections.catalog._european_ipe_row.CatalogRowEuropeanIPE`.
* :meth:`get_section_properties` - adapt the row into the universal
  :class:`~apeSteel.sections.properties.SectionProperties` frozen
  dataclass that every downstream calculator consumes.
* :meth:`get_doubly_symmetric_i_geometry` - reconstruct a plate-built
  :class:`~apeSteel.sections.geometry.DoublySymmetricISection` from
  the published ``(b, h, tw, tf)`` plate dimensions.

Fuzzy lookup mirrors the AISC catalog: exact match (case-insensitive,
trimmed) first, then RapidFuzz with a configurable similarity
threshold.

Eurocode-to-AISC axis renaming is performed once, inside the row->
SectionProperties adapter, so downstream calculators only ever see the
AISC convention (strong = x, weak = y).
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Final

import pandas as pd
from rapidfuzz import process

from apeSteel.sections.catalog._european_ipe_row import CatalogRowEuropeanIPE
from apeSteel.sections.catalog.exceptions import SectionNotFoundError
from apeSteel.sections.geometry import DoublySymmetricISection
from apeSteel.sections.properties import SectionProperties

LOGGER: logging.Logger = logging.getLogger(__name__)

DEFAULT_EUROPEAN_IPE_CSV_PATH: Final[Path] = (
    Path(__file__).resolve().parent / "data" / "european_IPE_subset.csv"
)
"""Path to the shipped EN 10365 IPE subset CSV."""

DEFAULT_FUZZY_SIMILARITY_THRESHOLD: Final[float] = 80.0
"""RapidFuzz score floor (0 - 100) for an acceptable fuzzy fallback."""

# Eurocode publishes mass per length in kg/m.  apeSteel base is
# tonne/mm.  Conversion factor: 1 kg/m = 1e-6 tonne/mm.
_LINEAR_MASS_kg_per_m_TO_tonne_per_mm: Final[float] = 1.0e-6


@lru_cache(maxsize=4)
def _load_dataframe_cached(csv_path: str) -> pd.DataFrame:
    df: pd.DataFrame = pd.read_csv(Path(csv_path))
    df["designation"] = df["designation"].astype(str).str.strip()
    return df


class EuropeanIPECatalog:
    """In-memory wrapper around the European IPE catalog.

    Parameters
    ----------
    csv_path : Path or None
        Override the bundled CSV.  ``None`` uses
        :data:`DEFAULT_EUROPEAN_IPE_CSV_PATH`.
    fuzzy_similarity_threshold : float
        RapidFuzz similarity floor for fuzzy fallback (default 80).
    """

    def __init__(
        self,
        csv_path: Path | None = None,
        *,
        fuzzy_similarity_threshold: float = DEFAULT_FUZZY_SIMILARITY_THRESHOLD,
    ) -> None:
        self._csv_path: Path = csv_path if csv_path is not None else DEFAULT_EUROPEAN_IPE_CSV_PATH
        self._fuzzy_similarity_threshold: float = fuzzy_similarity_threshold

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _dataframe(self) -> pd.DataFrame:
        return _load_dataframe_cached(str(self._csv_path.resolve()))

    def _resolve_label(self, requested: str) -> str:
        normalised: str = " ".join(requested.upper().split())
        # Build an upper-case copy of the designation column for matching.
        df = self._dataframe()
        upper_designations: list[str] = [str(s).upper() for s in df["designation"].tolist()]
        if normalised in upper_designations:
            return df["designation"].iloc[upper_designations.index(normalised)]
        # rapidfuzz returns (choice, score, index) tuple — or None when
        # the haystack is empty.  The library's stubs are not fully
        # typed so we narrow explicitly here.
        # rapidfuzz returns (choice, score, index); the typestub does
        # not model the empty-haystack case (the catalog CSV is always
        # non-empty, so that branch is unreachable here anyway).
        best = process.extractOne(normalised, upper_designations)
        match_score: float = float(best[1])
        match_idx: int = int(best[2])
        if match_score < self._fuzzy_similarity_threshold:
            raise SectionNotFoundError(
                requested,
                best_fuzzy_match=df["designation"].iloc[match_idx],
                best_fuzzy_score=match_score,
                similarity_threshold=self._fuzzy_similarity_threshold,
            )
        canonical: str = df["designation"].iloc[match_idx]
        LOGGER.warning(
            "EuropeanIPECatalog: '%s' not found exactly; using fuzzy match '%s' (score=%.1f).",
            requested,
            canonical,
            match_score,
        )
        return canonical

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_row(self, designation: str) -> CatalogRowEuropeanIPE:
        """Return the validated row for ``designation`` (e.g. ``"IPE 300"``)."""
        canonical: str = self._resolve_label(designation)
        df = self._dataframe()
        row = df.loc[df["designation"] == canonical].iloc[0]
        # Map CSV columns -> pydantic field names + unit conversion for G.
        payload: dict[str, object] = {
            "designation": str(row["designation"]),
            "h": float(row["h_mm"]),
            "b": float(row["b_mm"]),
            "tw": float(row["tw_mm"]),
            "tf": float(row["tf_mm"]),
            "r": float(row["r_mm"]),
            "G": float(row["G_kg_per_m"]) * _LINEAR_MASS_kg_per_m_TO_tonne_per_mm,
            "A": float(row["A_mm2"]),
            "Iy": float(row["Iy_mm4"]),
            "Wel_y": float(row["Wel_y_mm3"]),
            "Wpl_y": float(row["Wpl_y_mm3"]),
            "iy": float(row["iy_mm"]),
            "Iz": float(row["Iz_mm4"]),
            "Wel_z": float(row["Wel_z_mm3"]),
            "Wpl_z": float(row["Wpl_z_mm3"]),
            "iz": float(row["iz_mm"]),
            "It": float(row["It_mm4"]),
            "Iw": float(row["Iw_mm6"]),
        }
        return CatalogRowEuropeanIPE.model_validate(payload)

    def get_section_properties(self, designation: str) -> SectionProperties:
        """Adapt a row into a ``SectionProperties`` (Eurocode -> AISC axes)."""
        row: CatalogRowEuropeanIPE = self.get_row(designation)
        return _build_section_properties_from_european_ipe_row(row)

    def get_doubly_symmetric_i_geometry(self, designation: str) -> DoublySymmetricISection:
        """Reconstruct a plate-built ``DoublySymmetricISection``.

        Uses ``h``, ``b``, ``t_f``, ``t_w`` from the catalog and derives
        ``hw = h - 2*tf``.  Like the AISC catalog version this omits the
        root-radius fillets at the flange-web junction; expect a <2 %
        gap in ``A_g`` and ``I_x``.
        """
        row: CatalogRowEuropeanIPE = self.get_row(designation)
        return DoublySymmetricISection(
            flange_width_bf=row.b,
            flange_thickness_tf=row.tf,
            web_clear_height_hw=row.h - 2.0 * row.tf,
            web_thickness_tw=row.tw,
        )


def _build_section_properties_from_european_ipe_row(
    row: CatalogRowEuropeanIPE,
) -> SectionProperties:
    """Map a European IPE row (Eurocode y/z) to ``SectionProperties`` (AISC x/y).

    Computes the two AISC-specific intermediates that EN 10365 does not
    publish:

    * ``ho = h - tf``    (distance between flange centroids)
    * ``rts`` per AISC F2-7 from ``Iz`` (weak), ``Iw``, ``Wel_y``.
    """
    # Local imports to avoid an import cycle with apeSteel.core.units.
    from apeSteel.core.units import g as gravitational_acceleration_g  # noqa: PLC0415

    # Eurocode strong (y) -> AISC strong (x); Eurocode weak (z) -> AISC weak (y).
    moment_of_inertia_strong_axis_Ix: float = row.Iy
    elastic_section_modulus_strong_axis_Sx: float = row.Wel_y
    plastic_section_modulus_strong_axis_Zx: float = row.Wpl_y
    radius_of_gyration_strong_axis_rx: float = row.iy

    moment_of_inertia_weak_axis_Iy: float = row.Iz
    elastic_section_modulus_weak_axis_Sy: float = row.Wel_z
    plastic_section_modulus_weak_axis_Zy: float = row.Wpl_z
    radius_of_gyration_weak_axis_ry: float = row.iz

    torsional_constant_J: float = row.It
    warping_constant_Cw: float = row.Iw

    # AISC ho = distance between flange centroids = h - tf.
    distance_between_flange_centroids_ho: float = row.h - row.tf

    # AISC F2-7: rts^2 = sqrt(Iy_weak * Cw) / Sx_strong.
    rts_squared: float = (
        math.sqrt(moment_of_inertia_weak_axis_Iy * warping_constant_Cw)
        / elastic_section_modulus_strong_axis_Sx
    )
    effective_radius_of_gyration_for_LTB_rts: float = math.sqrt(rts_squared)

    # Plate-element slenderness ratios.  Eurocode's "c" parameter for
    # flange Class 1/2/3 uses (b - tw)/2 - r, but for apeSteel's AISC
    # path we use bf / (2 tf) which is the AISC convention.  The web
    # ratio in EN parlance is c_w/t_w with c_w = h - 2 tf - 2 r; AISC
    # uses h/tw where h is the clear distance between fillets.  We
    # follow the AISC formula and use (h - 2 tf - 2 r) for the clear web.
    flange_width_to_thickness_ratio_bf_2tf: float = row.b / (2.0 * row.tf)
    clear_web_height_h_aisc: float = row.h - 2.0 * row.tf - 2.0 * row.r
    web_height_to_thickness_ratio_h_tw: float = clear_web_height_h_aisc / row.tw

    nominal_weight_per_unit_length_w_force: float = row.G * gravitational_acceleration_g

    return SectionProperties(
        overall_depth_d=row.h,
        gross_area_Ag=row.A,
        nominal_weight_per_unit_length_w=nominal_weight_per_unit_length_w_force,
        moment_of_inertia_strong_axis_Ix=moment_of_inertia_strong_axis_Ix,
        elastic_section_modulus_strong_axis_Sx=elastic_section_modulus_strong_axis_Sx,
        plastic_section_modulus_strong_axis_Zx=plastic_section_modulus_strong_axis_Zx,
        radius_of_gyration_strong_axis_rx=radius_of_gyration_strong_axis_rx,
        moment_of_inertia_weak_axis_Iy=moment_of_inertia_weak_axis_Iy,
        elastic_section_modulus_weak_axis_Sy=elastic_section_modulus_weak_axis_Sy,
        plastic_section_modulus_weak_axis_Zy=plastic_section_modulus_weak_axis_Zy,
        radius_of_gyration_weak_axis_ry=radius_of_gyration_weak_axis_ry,
        torsional_constant_J=torsional_constant_J,
        warping_constant_Cw=warping_constant_Cw,
        distance_between_flange_centroids_ho=distance_between_flange_centroids_ho,
        effective_radius_of_gyration_for_LTB_rts=effective_radius_of_gyration_for_LTB_rts,
        flange_width_to_thickness_ratio_bf_2tf=flange_width_to_thickness_ratio_bf_2tf,
        web_height_to_thickness_ratio_h_tw=web_height_to_thickness_ratio_h_tw,
        web_thickness_tw=row.tw,
        flange_width_bf=row.b,
        flange_thickness_tf=row.tf,
        # EN 10365 publishes only the root radius r at the flange-web
        # junction; we derive AISC-style detailing offsets from it.
        # kdes ~ kdet ~ tf + r (depth from outer flange face to where
        # the web becomes flat).  k1 ~ tw/2 + r (half-web plus the
        # fillet shoulder).
        k_design_kdes=row.tf + row.r,
        k_detailing_kdet=row.tf + row.r,
        k_one_k1=row.tw / 2.0 + row.r,
    )


__all__ = [
    "DEFAULT_EUROPEAN_IPE_CSV_PATH",
    "DEFAULT_FUZZY_SIMILARITY_THRESHOLD",
    "EuropeanIPECatalog",
]

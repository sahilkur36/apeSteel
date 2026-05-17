"""Per-column unit conversion factors for the AISC v16 shapes database.

The CSV at ``data/AISC_v16_shapes.csv`` preserves the *AISC v16 SI
Manual* mixed-unit conventions exactly — that way each CSV row can be
diffed against a printed AISC v16 SI page during review.  The cost is
that the loader has to scale each column to apeSteel's canonical
``N-mm-tonne-s`` base before handing rows to the calculators.

This module is the *only* place that mapping lives.  Every other module
in :mod:`apeSteel.sections.catalog` consumes
:data:`AISC_V16_COLUMN_UNIT_TO_BASE_FACTOR` rather than re-deriving the
factors.

Unit conventions (AISC v16 SI Manual)
-------------------------------------
The AISC v16 SI Manual stores section properties in a mixed-prefix
system that is convenient for tabulation:

* Lengths and detailing dimensions: millimetres
* Cross-sectional area :math:`A`: square millimetres
* Linear mass :math:`W`: kilograms per metre
* Second moments :math:`I_x, I_y, I_z, I_w`: :math:`10^6` mm⁴
* Section moduli :math:`S_x, S_y, S_z, Z_x, Z_y` and the warping section
  moduli :math:`S_{w}, S_{z,A..C}`, :math:`Q_f, Q_w, C`: :math:`10^3` mm³
* Torsional constant :math:`J`: :math:`10^3` mm⁴
* Warping constant :math:`C_w`: :math:`10^9` mm⁶
* Slenderness ratios (``bf/2tf``, ``h/tw``, ``D/t``, ...): dimensionless
* Sectorial coordinates (``wA``, ``wB``, ``wC``) and warping torsion
  parameter ``H``: tabulated as :math:`10^3` mm² and ``Wno`` (normalised
  warping function) in mm².

The factors below scale "value in AISC v16 SI Manual" → "value in
apeSteel base ``N-mm-tonne-s``".

References
----------
.. [1] American Institute of Steel Construction, *Shapes Database
       v16.0 (SI units)*, 2019.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Conversion factors
# ---------------------------------------------------------------------------
# Each factor multiplies the CSV value to produce the apeSteel
# base-units float.  Columns absent from this table are treated as
# already-in-base or dimensionless and pass through unchanged.

_LINEAR_MASS_kg_per_m_TO_tonne_per_mm: Final[float] = 1.0e-6
"""1 kg/m  =  10^-3 tonne / 10^3 mm  =  10^-6 tonne/mm."""

_SECOND_MOMENT_OF_AREA_1e6_mm4_TO_mm4: Final[float] = 1.0e6
"""AISC v16 reports I in 10^6 mm⁴; multiply to land in mm⁴."""

_SECTION_MODULUS_1e3_mm3_TO_mm3: Final[float] = 1.0e3
"""AISC v16 reports S and Z (and warping section moduli) in 10^3 mm³."""

_TORSIONAL_CONSTANT_1e3_mm4_TO_mm4: Final[float] = 1.0e3
"""AISC v16 reports J in 10^3 mm⁴."""

_WARPING_CONSTANT_1e9_mm6_TO_mm6: Final[float] = 1.0e9
"""AISC v16 reports Cw in 10^9 mm⁶."""

_SECTORIAL_AREA_1e3_mm2_TO_mm2: Final[float] = 1.0e3
"""AISC v16 reports the sectorial-coordinate columns (wA, wB, wC) in
10^3 mm²."""


AISC_V16_COLUMN_UNIT_TO_BASE_FACTOR: Final[dict[str, float]] = {
    # Linear mass per length.
    "W": _LINEAR_MASS_kg_per_m_TO_tonne_per_mm,
    # Second moments of area I_x, I_y, I_z, I_w stored as 10^6 mm⁴.
    "Ix": _SECOND_MOMENT_OF_AREA_1e6_mm4_TO_mm4,
    "Iy": _SECOND_MOMENT_OF_AREA_1e6_mm4_TO_mm4,
    "Iz": _SECOND_MOMENT_OF_AREA_1e6_mm4_TO_mm4,
    "Iw": _SECOND_MOMENT_OF_AREA_1e6_mm4_TO_mm4,
    # Section moduli S_x, S_y, S_z, Z_x, Z_y and warping section moduli.
    "Sx": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Sy": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Sz": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Zx": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Zy": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Sw1": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Sw2": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Sw3": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "SwA": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "SwB": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "SwC": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "SzA": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "SzB": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "SzC": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Qf": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "Qw": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    "C": _SECTION_MODULUS_1e3_mm3_TO_mm3,
    # Torsion and warping constants.
    "J": _TORSIONAL_CONSTANT_1e3_mm4_TO_mm4,
    "Cw": _WARPING_CONSTANT_1e9_mm6_TO_mm6,
    # AISC v16 H parameter for warping torsion (channels, WT, etc.):
    # tabulated as a length^4 entry in 10^6 mm⁴.
    "H": _SECOND_MOMENT_OF_AREA_1e6_mm4_TO_mm4,
    # Normalised sectorial coordinates / area columns.  wA/wB/wC are
    # listed in 10^3 mm²; Wno (the normalised warping function) is
    # already in mm².
    "wA": _SECTORIAL_AREA_1e3_mm2_TO_mm2,
    "wB": _SECTORIAL_AREA_1e3_mm2_TO_mm2,
    "wC": _SECTORIAL_AREA_1e3_mm2_TO_mm2,
}
"""Mapping from AISC v16 CSV column name to the multiplicative factor
that yields the value in apeSteel's ``N-mm-tonne-s`` base.

Any column absent from this dict is either dimensionless (slenderness
ratios, ``tan(α)``) or already in base units (millimetre lengths and
``A`` in mm²) and is passed through unchanged at load time.

Notes
-----
The ``H``, ``Wno``, and ``Iw`` columns are conservative best-effort
mappings based on the AISC v16 SI Manual conventions for sectional and
warping properties.  Phase 6 only exercises ``Ix..rts`` for
doubly-symmetric I-shapes, so the exotic columns are mapped for
completeness but not yet exercised by tests.
"""

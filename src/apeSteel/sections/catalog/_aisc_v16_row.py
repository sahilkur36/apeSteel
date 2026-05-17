"""Typed pydantic v2 row model for the AISC v16 shapes database.

A :class:`CatalogRowAISCv16` is one row of the AISC v16 SI shapes
database, validated and frozen.  Every numeric field is already in
apeSteel's canonical ``N-mm-tonne-s`` base units — the load-time
adapter in :mod:`apeSteel.sections.catalog._data_loader` is responsible
for the unit scaling, so by the time a row is constructed the values
are ready to hand straight to the calculators.

The pydantic boundary is intentionally **read-only and load-only**:
once a row is built we leave the pydantic world and only ever pass
:class:`~apeSteel.sections.properties.SectionProperties` (or, for the
plate-built reconstruction adapter, a
:class:`~apeSteel.sections.geometry.DoublySymmetricISection`)
downstream.

Field naming
------------
For columns whose AISC v16 CSV name is a valid Python identifier we
keep the CSV name verbatim (``bf``, ``tf``, ``Ix``, ``Cw``, ...) so a
reader can place a CSV row next to the dataclass without translation.

CSV columns whose names are not valid Python identifiers (``bf/2tf``,
``h/tw``, ``D/t``, ``twdet/2``, ``tan(α)``) are renamed to
underscore-flat equivalents (``bf_2tf``, ``h_tw``, ``D_t``,
``twdet_2``, ``tan_alpha``) by
:func:`apeSteel.sections.catalog._data_loader.rename_invalid_identifier_columns`
before they reach pydantic.

Every numeric field is :class:`float` ``| None`` because the AISC v16
database uses the en-dash marker ``"–"`` to denote "not applicable for
this section type" (an angle has no ``bf``, a pipe has no ``Iy`` ≠
``Ix``, etc.).  The :class:`SectionType`-aware adapters reject ``None``
values when the requested adapter needs them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# AISC v16 "Type" column values — restrict to the published set so
# typos in a future re-ingest can be caught at load time.
SectionType = Literal[
    "W",
    "M",
    "S",
    "HP",
    "C",
    "MC",
    "L",
    "2L",
    "WT",
    "MT",
    "ST",
    "HSS",
    "PIPE",
]
"""Closed set of AISC v16 ``Type`` codes.  Order matches the AISC v16
table-of-contents."""

# The five "I-shape" types — the ones our doubly-symmetric calculators
# can consume directly.  Channels, angles, HSS, pipes, and tees stay in
# the catalog but their rows refuse to adapt into
# ``DoublySymmetricISection``.
DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES: frozenset[SectionType] = frozenset({"W", "M", "S", "HP"})
"""AISC v16 ``Type`` codes that ``DoublySymmetricISection`` accepts.

``HP`` (bearing pile) shapes are included even though they are stockier
than a typical W; their geometry is still strictly a doubly-symmetric I
in the AISC catalogue."""


class CatalogRowAISCv16(BaseModel):
    """One row of the AISC v16 SI shapes database, in base units.

    Every attribute is documented with its AISC v16 SI column name and
    the physical meaning.  Numeric attributes are stored in apeSteel
    base ``N-mm-tonne-s`` units; the load-time adapter handles the
    scaling from the CSV's mixed-prefix units (mm, kg/m, :math:`10^{6}`
    mm⁴, ...).

    The model is frozen (``model_config["frozen"] = True``) and rejects
    unknown columns (``extra="forbid"``) so a future re-ingest of the
    AISC database that introduces a new column fails loudly instead of
    silently dropping data.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=False)

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    Type: SectionType
    """AISC v16 ``Type`` code, e.g. ``"W"``."""

    AISC_Manual_Label: str
    """Canonical AISC Manual label, e.g. ``"W24X94"``."""

    # ------------------------------------------------------------------
    # Mass and area
    # ------------------------------------------------------------------
    W: float | None = None
    """Nominal weight per unit length (tonne/mm in base; ``kg/m`` in
    the AISC v16 SI Manual)."""

    A: float | None = None
    """Gross cross-sectional area :math:`A_g` (mm²)."""

    # ------------------------------------------------------------------
    # Overall geometry — I-shapes, channels, tees
    # ------------------------------------------------------------------
    d: float | None = None
    """Overall depth :math:`d` (mm). For I, C, WT/MT/ST shapes."""

    ddet: float | None = None
    """Detailing depth (mm). Generally equal to ``d`` for design but
    rounded for shop drawings."""

    Ht: float | None = None
    """Overall HSS-rectangular height :math:`H` (mm)."""

    h: float | None = None
    """Clear distance between fillets (W/M/S/HP, channels, tees) or
    clear flat depth (HSS-rectangular) :math:`h` (mm)."""

    OD: float | None = None
    """Outside diameter for HSS round and Pipe (mm)."""

    bf: float | None = None
    """Flange width :math:`b_f` (mm). I-shapes, channels, tees."""

    bfdet: float | None = None
    """Detailing flange width (mm)."""

    B: float | None = None
    """Overall HSS-rectangular width :math:`B` (mm)."""

    b: float | None = None
    """Width of HSS clear flat or angle long leg :math:`b` (mm)."""

    ID: float | None = None
    """Inside diameter for Pipe sections (mm)."""

    # ------------------------------------------------------------------
    # Thicknesses
    # ------------------------------------------------------------------
    tw: float | None = None
    """Web thickness :math:`t_w` (mm). I-shapes, channels, tees."""

    twdet: float | None = None
    """Detailing web thickness (mm)."""

    twdet_2: float | None = None
    """``twdet/2`` from the AISC CSV (mm)."""

    tf: float | None = None
    """Flange thickness :math:`t_f` (mm). I-shapes, channels, tees."""

    tfdet: float | None = None
    """Detailing flange thickness (mm)."""

    t: float | None = None
    """Single-thickness column used by angles (leg thickness) and HSS
    (wall thickness) (mm)."""

    tnom: float | None = None
    """Nominal HSS wall thickness (mm)."""

    tdes: float | None = None
    """Design HSS wall thickness :math:`t = 0.93\\,t_{nom}` for ERW HSS
    per AISC §B4.2 (mm)."""

    # ------------------------------------------------------------------
    # Detailing offsets
    # ------------------------------------------------------------------
    kdes: float | None = None
    """Design distance from flange face to web toe of fillet (mm)."""

    kdet: float | None = None
    """Detailing distance from flange face to web toe of fillet (mm)."""

    k1: float | None = None
    """Distance from centre of web to web toe of fillet (mm)."""

    x: float | None = None
    """Distance from major-axis to shear centre, channels and angles
    (mm)."""

    y: float | None = None
    """Distance from minor-axis to shear centre / centroid offset
    (mm)."""

    eo: float | None = None
    """Horizontal distance from outer face of web to shear centre,
    channels (mm)."""

    xp: float | None = None
    """Distance to plastic neutral axis, x-direction (mm)."""

    yp: float | None = None
    """Distance to plastic neutral axis, y-direction (mm)."""

    # ------------------------------------------------------------------
    # Slenderness ratios (dimensionless)
    # ------------------------------------------------------------------
    bf_2tf: float | None = None
    """``bf/(2*tf)`` slenderness ratio (AISC v16 CSV column
    ``bf/2tf``)."""

    b_t: float | None = None
    """``b/t`` slenderness ratio (AISC v16 CSV column ``b/t``)."""

    b_tdes: float | None = None
    """``b/tdes`` slenderness ratio (AISC v16 CSV column ``b/tdes``)."""

    h_tw: float | None = None
    """``h/tw`` web slenderness (AISC v16 CSV column ``h/tw``)."""

    h_tdes: float | None = None
    """``h/tdes`` HSS slenderness (AISC v16 CSV column ``h/tdes``)."""

    D_t: float | None = None
    """``D/t`` round-HSS / Pipe slenderness (AISC v16 CSV column
    ``D/t``)."""

    # ------------------------------------------------------------------
    # Strong-axis section properties (about the geometric x-axis)
    # ------------------------------------------------------------------
    Ix: float | None = None
    """Strong-axis moment of inertia :math:`I_x` (mm⁴)."""

    Zx: float | None = None
    """Strong-axis plastic section modulus :math:`Z_x` (mm³)."""

    Sx: float | None = None
    """Strong-axis elastic section modulus :math:`S_x` (mm³)."""

    rx: float | None = None
    """Strong-axis radius of gyration :math:`r_x` (mm)."""

    # ------------------------------------------------------------------
    # Weak-axis section properties (about the geometric y-axis)
    # ------------------------------------------------------------------
    Iy: float | None = None
    """Weak-axis moment of inertia :math:`I_y` (mm⁴)."""

    Zy: float | None = None
    """Weak-axis plastic section modulus :math:`Z_y` (mm³)."""

    Sy: float | None = None
    """Weak-axis elastic section modulus :math:`S_y` (mm³)."""

    ry: float | None = None
    """Weak-axis radius of gyration :math:`r_y` (mm)."""

    # ------------------------------------------------------------------
    # Principal-axis properties — angles and double-angles
    # ------------------------------------------------------------------
    Iz: float | None = None
    """Principal-axis moment of inertia :math:`I_z` (mm⁴) — angles."""

    rz: float | None = None
    """Principal-axis radius of gyration :math:`r_z` (mm) — angles."""

    Sz: float | None = None
    """Principal-axis elastic section modulus :math:`S_z` (mm³) —
    angles."""

    # ------------------------------------------------------------------
    # Torsion and warping
    # ------------------------------------------------------------------
    J: float | None = None
    """Saint-Venant torsional constant :math:`J` (mm⁴)."""

    Cw: float | None = None
    """Warping constant :math:`C_w` (mm⁶)."""

    C: float | None = None
    """HSS torsional shear constant :math:`C` (mm³)."""

    # Normalised warping / sectorial coordinates (AISC v16 columns).
    # Not exercised by Phase 6 calculators; included for completeness.
    Wno: float | None = None
    Sw1: float | None = None
    Sw2: float | None = None
    Sw3: float | None = None
    Qf: float | None = None
    Qw: float | None = None
    ro: float | None = None
    """Polar radius of gyration about the shear centre (mm) —
    angles."""
    H: float | None = None
    """Flexural-torsional constant (mm⁴) — AISC commentary E4."""
    tan_alpha: float | None = None
    """Tangent of the principal axis rotation (dimensionless) —
    angles (AISC v16 CSV column ``tan(α)``)."""
    Iw: float | None = None
    """Sectorial moment of inertia (mm⁴) — torsion analysis."""

    # Coordinate / sectorial-coordinate columns — angles, channels.
    zA: float | None = None
    zB: float | None = None
    zC: float | None = None
    wA: float | None = None
    wB: float | None = None
    wC: float | None = None
    SwA: float | None = None
    SwB: float | None = None
    SwC: float | None = None
    SzA: float | None = None
    SzB: float | None = None
    SzC: float | None = None

    # ------------------------------------------------------------------
    # LTB-specific bookkeeping (I-shapes)
    # ------------------------------------------------------------------
    rts: float | None = None
    """Effective LTB radius of gyration :math:`r_{ts}` (mm)."""

    ho: float | None = None
    """Distance between flange centroids :math:`h_o` (mm)."""

    # ------------------------------------------------------------------
    # Workable gauges / detailing (mm)
    # ------------------------------------------------------------------
    PA: float | None = None
    PA2: float | None = None
    PB: float | None = None
    PC: float | None = None
    PD: float | None = None
    T: float | None = None
    """Workable flat depth between flanges (mm)."""
    WGi: float | None = None
    """Workable inside gauge (mm)."""
    WGo: float | None = None
    """Workable outside gauge (mm)."""


__all__ = [
    "DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES",
    "CatalogRowAISCv16",
    "SectionType",
]

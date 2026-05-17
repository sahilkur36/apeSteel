"""Typed pydantic v2 row model for the European IPE catalog.

A :class:`CatalogRowEuropeanIPE` is one row of an EN 10365 IPE table,
validated and frozen.  Every numeric field is already in apeSteel's
canonical ``N-mm-tonne-s`` base units - the load-time adapter handles
unit scaling, so by the time a row is constructed the values are ready
to hand straight to the calculators.

Eurocode axis convention
------------------------
European steel codes use a different axis convention from AISC:

* ``y`` = strong axis (= AISC ``x``)
* ``z`` = weak axis  (= AISC ``y``)

This row model keeps the *Eurocode* names (``Iy``, ``Iz``, ``iy``,
``iz``, ``Wel_y``, ``Wpl_y``) because that is what an EN 10365 table
publishes; the catalog adapter that converts a row into
:class:`~apeSteel.sections.properties.SectionProperties` performs the
axis renaming once, in one place.

Two further Eurocode-to-AISC mappings happen at the adapter boundary:

* ``It`` (Eurocode torsion constant) -> ``J`` in AISC.
* ``Iw`` (Eurocode warping constant) -> ``C_w`` in AISC.

Field naming
------------
Field names match the column names in the shipped CSV
``data/european_IPE_subset.csv``.  Apart from the unit-suffixed
identifiers (``h_mm``, ``A_mm2``, ...) every field corresponds 1:1 to a
named column.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CatalogRowEuropeanIPE(BaseModel):
    """One row of the European IPE catalog, in apeSteel base units.

    Numeric values are stored in N-mm-tonne-s base units; the
    load-time adapter handles the conversion from the CSV's mixed
    units (mm, kg/m, mm^4, mm^6).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=False)

    designation: str
    """IPE designation, e.g. ``"IPE 300"``."""

    h: float
    """Overall depth ``h`` (mm)."""

    b: float
    """Flange width ``b`` (mm)."""

    tw: float
    """Web thickness ``t_w`` (mm)."""

    tf: float
    """Flange thickness ``t_f`` (mm)."""

    r: float
    """Root radius at the flange-web junction (mm)."""

    G: float
    """Mass per unit length (tonne/mm in apeSteel base; ``kg/m`` in the
    EN 10365 table)."""

    A: float
    """Gross cross-sectional area ``A`` (mm^2)."""

    # Strong axis (Eurocode y == AISC x).
    Iy: float
    """Strong-axis moment of inertia ``I_y`` (mm^4) - Eurocode notation."""
    Wel_y: float
    """Strong-axis elastic section modulus ``W_{el,y}`` (mm^3)."""
    Wpl_y: float
    """Strong-axis plastic section modulus ``W_{pl,y}`` (mm^3)."""
    iy: float
    """Strong-axis radius of gyration ``i_y`` (mm)."""

    # Weak axis (Eurocode z == AISC y).
    Iz: float
    """Weak-axis moment of inertia ``I_z`` (mm^4) - Eurocode notation."""
    Wel_z: float
    """Weak-axis elastic section modulus ``W_{el,z}`` (mm^3)."""
    Wpl_z: float
    """Weak-axis plastic section modulus ``W_{pl,z}`` (mm^3)."""
    iz: float
    """Weak-axis radius of gyration ``i_z`` (mm)."""

    # Torsion and warping.
    It: float
    """Saint-Venant torsion constant ``I_t`` (mm^4) - == AISC ``J``."""
    Iw: float
    """Warping constant ``I_w`` (mm^6) - == AISC ``C_w``."""


__all__ = ["CatalogRowEuropeanIPE"]

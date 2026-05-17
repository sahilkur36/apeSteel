"""Steel material catalog for apeSteel.

A :class:`SteelMaterial` is the immutable description of a steel grade as
needed by AISC 360 and AISC 341 strength formulas. All numeric attributes
are stored in apeSteel's canonical ``N-mm-tonne-s`` base units, so
``yield_stress_Fy`` is in :data:`~apeSteel.core.units.MPa`,
``elastic_modulus_E`` is in :data:`~apeSteel.core.units.MPa`,
``density_rho`` is in tonne/mm³, etc.

Pre-built instances cover the most common AISC and European grades. The
expected-strength factors ``Ry`` and ``Rt`` follow AISC 341-22 Table A3.1
(seismic provisions); they are pinned in this module so they cannot be
silently inconsistent with the rest of the library.

References
----------
.. [1] AISC 360-22, "Specification for Structural Steel Buildings",
       Appendix 2 and Chapter D. American Institute of Steel
       Construction, 2022.
.. [2] AISC 341-22, "Seismic Provisions for Structural Steel Buildings",
       Table A3.1 "Expected Material Properties". American Institute of
       Steel Construction, 2022.
.. [3] EN 1993-1-1:2005 + A1:2014, "Eurocode 3: Design of Steel
       Structures - Part 1-1". CEN, 2014. (European grades)
"""

from __future__ import annotations

from dataclasses import dataclass

from apeSteel.core import units as u


# ---------------------------------------------------------------------------
# SteelMaterial frozen dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SteelMaterial:
    """Immutable description of a structural steel grade.

    Attributes
    ----------
    name : str
        Free-form designation, e.g. ``"ASTM A992"``.
    yield_stress_Fy : float
        Minimum specified yield stress :math:`F_y` in base units (MPa).
    tensile_stress_Fu : float
        Minimum specified tensile stress :math:`F_u` in base units (MPa).
    elastic_modulus_E : float
        Young's modulus :math:`E` in base units (MPa). For carbon and
        low-alloy steels, AISC 360 §J3 commentary takes
        :math:`E = 29\\,000\\,\\mathrm{ksi} \\approx 199\\,948\\,\\mathrm{MPa}`.
    shear_modulus_G : float
        Shear modulus :math:`G` in base units (MPa). AISC takes
        :math:`G = 11\\,200\\,\\mathrm{ksi} \\approx 77\\,200\\,\\mathrm{MPa}`.
    density_rho : float
        Mass density :math:`\\rho` in base units (tonne/mm³).
        For carbon steel, :math:`\\rho \\approx 7.85\\,\\mathrm{tonne/m^3} =
        7.85 \\times 10^{-9}\\,\\mathrm{tonne/mm^3}`.
    expected_yield_ratio_Ry : float
        AISC 341 :math:`R_y`, the ratio of expected yield stress to
        minimum specified yield stress. Used in capacity-design demand
        (e.g. expected probable moment :math:`M_{pr} = R_y \\cdot F_y \\cdot Z_x`).
    expected_tensile_ratio_Rt : float
        AISC 341 :math:`R_t`, the corresponding ratio for tensile stress.

    Notes
    -----
    The dataclass is frozen and uses ``slots=True``. Attempts to mutate
    raise :class:`dataclasses.FrozenInstanceError`.

    Stored numeric values are expressed in apeSteel's canonical base
    units; users construct grades with explicit multiplication by the
    matching :mod:`apeSteel.core.units` constants
    (``345 * u.MPa``, etc.).
    """

    name: str
    yield_stress_Fy: float
    tensile_stress_Fu: float
    elastic_modulus_E: float
    shear_modulus_G: float
    density_rho: float
    expected_yield_ratio_Ry: float
    expected_tensile_ratio_Rt: float


# ---------------------------------------------------------------------------
# Standard moduli (AISC values, in apeSteel base units = MPa)
# ---------------------------------------------------------------------------
# AISC 360-22 §B4 commentary lists E = 29,000 ksi and G = 11,200 ksi as
# the canonical values for the design of carbon and low-alloy structural
# steels. We pin those values once and reuse them.
ELASTIC_MODULUS_AISC_E: float = 29_000.0 * u.ksi  # ~ 199 948 MPa
SHEAR_MODULUS_AISC_G: float = 11_200.0 * u.ksi  # ~  77 211 MPa

# Carbon-steel mass density: 7.85 tonne/m^3 = 7.85e-9 tonne/mm^3.
CARBON_STEEL_DENSITY_rho: float = 7.85 * u.tonne / (u.m**3)


# ---------------------------------------------------------------------------
# Pre-built ASTM and European grades
# ---------------------------------------------------------------------------
# ASTM A992 — the workhorse W-shape grade. AISC 341 Table A3.1: Ry = 1.1,
# Rt = 1.1.
A992: SteelMaterial = SteelMaterial(
    name="ASTM A992",
    yield_stress_Fy=50.0 * u.ksi,  # 50 ksi  =  344.74 MPa
    tensile_stress_Fu=65.0 * u.ksi,  # 65 ksi  =  448.16 MPa
    elastic_modulus_E=ELASTIC_MODULUS_AISC_E,
    shear_modulus_G=SHEAR_MODULUS_AISC_G,
    density_rho=CARBON_STEEL_DENSITY_rho,
    expected_yield_ratio_Ry=1.1,
    expected_tensile_ratio_Rt=1.1,
)

# ASTM A572 Grade 50 — plates and HSS in moderate-strength applications.
# AISC 341 Table A3.1: Ry = 1.1, Rt = 1.1.
A572_Gr50: SteelMaterial = SteelMaterial(
    name="ASTM A572 Gr.50",
    yield_stress_Fy=50.0 * u.ksi,
    tensile_stress_Fu=65.0 * u.ksi,
    elastic_modulus_E=ELASTIC_MODULUS_AISC_E,
    shear_modulus_G=SHEAR_MODULUS_AISC_G,
    density_rho=CARBON_STEEL_DENSITY_rho,
    expected_yield_ratio_Ry=1.1,
    expected_tensile_ratio_Rt=1.1,
)

# ASTM A36 — older mild structural carbon steel. Still common in legacy
# tags and small built-up sections. AISC 341 Table A3.1: Ry = 1.5,
# Rt = 1.2 (much higher expected over-strength due to mill practice
# delivering well above the 36 ksi floor).
A36: SteelMaterial = SteelMaterial(
    name="ASTM A36",
    yield_stress_Fy=36.0 * u.ksi,
    tensile_stress_Fu=58.0 * u.ksi,
    elastic_modulus_E=ELASTIC_MODULUS_AISC_E,
    shear_modulus_G=SHEAR_MODULUS_AISC_G,
    density_rho=CARBON_STEEL_DENSITY_rho,
    expected_yield_ratio_Ry=1.5,
    expected_tensile_ratio_Rt=1.2,
)

# EN 10025 S275 — European mild structural steel.
# Ry / Rt approximated from AISC 341 commentary for non-AISC grades.
S275: SteelMaterial = SteelMaterial(
    name="EN 10025 S275",
    yield_stress_Fy=275.0 * u.MPa,
    tensile_stress_Fu=430.0 * u.MPa,
    elastic_modulus_E=ELASTIC_MODULUS_AISC_E,
    shear_modulus_G=SHEAR_MODULUS_AISC_G,
    density_rho=CARBON_STEEL_DENSITY_rho,
    expected_yield_ratio_Ry=1.25,
    expected_tensile_ratio_Rt=1.20,
)

# EN 10025 S355 — the European workhorse for moment frames.
S355: SteelMaterial = SteelMaterial(
    name="EN 10025 S355",
    yield_stress_Fy=355.0 * u.MPa,
    tensile_stress_Fu=510.0 * u.MPa,
    elastic_modulus_E=ELASTIC_MODULUS_AISC_E,
    shear_modulus_G=SHEAR_MODULUS_AISC_G,
    density_rho=CARBON_STEEL_DENSITY_rho,
    expected_yield_ratio_Ry=1.25,
    expected_tensile_ratio_Rt=1.20,
)

# EN 10025 S460 — high-strength European grade for heavily loaded girders.
S460: SteelMaterial = SteelMaterial(
    name="EN 10025 S460",
    yield_stress_Fy=460.0 * u.MPa,
    tensile_stress_Fu=550.0 * u.MPa,
    elastic_modulus_E=ELASTIC_MODULUS_AISC_E,
    shear_modulus_G=SHEAR_MODULUS_AISC_G,
    density_rho=CARBON_STEEL_DENSITY_rho,
    expected_yield_ratio_Ry=1.20,
    expected_tensile_ratio_Rt=1.15,
)


__all__ = [
    "A36",
    "A992",
    "ELASTIC_MODULUS_AISC_E",
    "S275",
    "S355",
    "S460",
    "SHEAR_MODULUS_AISC_G",
    "A572_Gr50",
    "CARBON_STEEL_DENSITY_rho",
    "SteelMaterial",
]

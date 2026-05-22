"""SteelMaterial dataclass and the apeSteel pre-built grades.

apeSteel stores every material property in the canonical
``N-mm-tonne-s`` base. The pre-built grades are immutable
:class:`SteelMaterial` instances pinned at module scope; users
construct custom grades by multiplying the human-facing value by the
matching :mod:`apeSteel.core.units` constant.
"""

from __future__ import annotations

from apeSteel import (
    A36,
    A572_Gr50,
    A992,
    S355,
    S460,
    SteelMaterial,
)
from apeSteel.core import units as u


def main() -> None:
    # Pre-built grades — Fy, Fu, E, G, rho, Ry, Rt stored in base units.
    for grade in (A36, A992, A572_Gr50, S355, S460):
        print(
            f"{grade.name:18s}"
            f"  Fy = {grade.yield_stress_Fy / u.MPa:6.1f} MPa"
            f"   Fu = {grade.tensile_stress_Fu / u.MPa:6.1f} MPa"
            f"   Ry = {grade.expected_yield_ratio_Ry:.2f}"
        )

    # Custom grade — assemble the SteelMaterial directly with explicit
    # unit multiplications.  Values land in the same N-mm-tonne-s base.
    custom = SteelMaterial(
        name="Custom Q420",
        yield_stress_Fy=420 * u.MPa,
        tensile_stress_Fu=540 * u.MPa,
        elastic_modulus_E=200_000 * u.MPa,
        shear_modulus_G=77_200 * u.MPa,
        density_rho=7.85 * u.tonne / (u.m**3),
        expected_yield_ratio_Ry=1.20,
        expected_tensile_ratio_Rt=1.15,
    )
    print(
        f"{custom.name:18s}"
        f"  Fy = {custom.yield_stress_Fy / u.MPa:6.1f} MPa"
        f"   Fu = {custom.tensile_stress_Fu / u.MPa:6.1f} MPa"
        f"   Ry = {custom.expected_yield_ratio_Ry:.2f}"
    )

    # Unit-arithmetic at the boundary: 300 mm reads as a length, 50 ksi
    # as a stress, 1.2 kN as a force; multiplying by the unit constant
    # converts to the N-mm-tonne-s base float that apeSteel stores.
    length_300_mm: float = 300 * u.mm
    stress_50_ksi: float = 50 * u.ksi
    force_1p2_kN: float = 1.2 * u.kN
    print(
        f"300 mm  -> {length_300_mm:.3f} (base mm)\n"
        f"50 ksi  -> {stress_50_ksi:.3f} (base MPa)\n"
        f"1.2 kN  -> {force_1p2_kN:.3f} (base N)"
    )


if __name__ == "__main__":
    main()

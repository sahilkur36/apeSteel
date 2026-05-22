"""AISC 360-22 Chapter E compression example.

Demonstrates ``Element.compression_strength`` for a welded
doubly-symmetric I-section in A992. The orchestrator routes §E2
(slenderness advisory), §E3 (flexural buckling), §E4 (torsional
buckling for the doubly-symmetric I), and §E7 (slender-element
reduction) automatically; the report carries every intermediate.
"""

from __future__ import annotations

from apeSteel import A992, DoublySymmetricISection
from apeSteel.core import units as u


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=16 * u.mm,
    )
    element = section.element(material=A992, construction="welded")

    compression = element.compression_strength(
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
    )

    Pn = compression.nominal_compressive_strength_Pn
    phi_Pn = compression.phi_strength_LRFD
    print(f"Governing limit state : {compression.governing_compression_limit_state}")
    print(f"Lc/r (governing)      : {compression.governing_slenderness_Lc_over_r:6.2f}")
    print(f"Fcr (governing)       : {compression.governing_critical_stress_Fcr:6.2f} MPa")
    print(f"Pn                    : {Pn / u.kN:8.1f} kN")
    print(f"phi*Pn (LRFD)         : {phi_Pn / u.kN:8.1f} kN")


if __name__ == "__main__":
    main()

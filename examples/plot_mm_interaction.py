"""M-M envelope (§H1.1) at a fixed axial load Pr.

Draws the rhombus-shaped Mrx-Mry envelope sliced at a single axial
level for a doubly-symmetric I-section.  At Pr/Pc ≥ 0.2 the rhombus
shrinks linearly with axial load.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from apeSteel import A992, DoublySymmetricISection
from apeSteel.bracing import Bracing
from apeSteel.core import units as u

_OUT = Path(__file__).resolve().parents[1] / "assets" / "plots"


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=16 * u.mm,
    )
    element = section.element(
        material=A992,
        construction="welded",
        bracing=Bracing(0.001 * u.m, 4.0 * u.m, 1.0),
    )

    fig, ax = plt.subplots(figsize=(6, 6))
    element.plot_mm_interaction(
        axial_load_Pr=500 * u.kN,
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
        ax=ax,
        which="phi",
        fill=True,
        demand_points=[
            (200 * u.kN * u.m, 30 * u.kN * u.m, "D1"),
            (400 * u.kN * u.m, 80 * u.kN * u.m, "D2"),
        ],
        label="Pr = 500 kN",
        color="tab:blue",
    )
    ax.set_title("§H1.1 Mrx-Mry envelope at Pr = 500 kN")
    ax.legend(loc="upper right", fontsize=9)

    _OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(_OUT / "plot_mm_interaction.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

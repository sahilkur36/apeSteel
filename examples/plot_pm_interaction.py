"""P-Mx interaction envelope (§H1.1) with demand points.

Plots the design envelope (``which="phi"``) and the nominal envelope
together, fills the safe interior, and overlays four demand
``(Pr, Mrx)`` points.  Points inside the envelope are coloured green;
overstressed points are red.
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
        bracing=Bracing(
            unbraced_length_top_flange_Lb_top=0.001 * u.m,
            unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
        ),
    )

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    element.plot_pm_interaction(
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
        ax=ax,
        which="both",
        fill=True,
        demand_points=[
            (200 * u.kN, 150 * u.kN * u.m, "D1"),
            (800 * u.kN, 200 * u.kN * u.m, "D2"),
            (1800 * u.kN, 250 * u.kN * u.m, "D3"),
            (2500 * u.kN, 350 * u.kN * u.m, "D4"),
        ],
        label="W 300×20 / 400×16",
        color="tab:blue",
    )
    ax.set_title("§H1.1 P-Mx interaction envelope")
    ax.legend(loc="upper right", fontsize=9)

    _OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(_OUT / "plot_pm_interaction.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

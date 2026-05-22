"""3D P-Mx-My §H1.1 envelope.

Renders the full cone+frustum interaction surface: a cone apex at
(0, 0, Pc), a break rhombus at P = 0.2·Pc, and the full rhombus base
at P = 0.  Two demand points illustrate the green/red DCR colouring.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from apeSteel import A992, DoublySymmetricISection  # noqa: E402
from apeSteel.bracing import Bracing  # noqa: E402
from apeSteel.core import units as u  # noqa: E402

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

    fig = plt.figure(figsize=(7, 6))
    ax = fig.add_subplot(111, projection="3d")
    element.plot_pmm_interaction_3d(
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
        ax=ax,
        which="phi",
        demand_points=[
            (400 * u.kN, 100 * u.kN * u.m, 20 * u.kN * u.m, "D1"),
            (2500 * u.kN, 350 * u.kN * u.m, 120 * u.kN * u.m, "D2"),
        ],
        face_color="tab:blue",
        edge_color="tab:blue",
        surface_alpha=0.25,
    )
    ax.set_title("§H1.1 3D P-Mx-My envelope")
    ax.view_init(elev=20, azim=35)

    _OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(_OUT / "plot_pmm_3d.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Recipe: uniaxial beam-column check (AISC 360-22 §H1.1).

Given an ASTM A992 W-shape with second-order axial and major-axis
demands, evaluate the §H1.1 unity equation and plot the demand point
on the P-Mx envelope.
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
    # --- Member ----------------------------------------------------------
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

    # --- Second-order demands (DAM-amplified by the caller) --------------
    required_axial_Pr = 1200 * u.kN
    required_moment_x_Mrx = 250 * u.kN * u.m

    # --- §H1.1 unity check ----------------------------------------------
    h1 = element.combined_strength_H1(
        required_axial_Pr=required_axial_Pr,
        required_moment_x_Mrx=required_moment_x_Mrx,
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
    )

    print(f"Governing equation : {h1.governing_equation}")
    print(f"Pr/Pc              : {h1.axial_ratio_Pr_Pc:.3f}")
    print(f"Mrx/Mcx            : {h1.required_moment_x_Mrx / h1.available_moment_x_Mcx:.3f}")
    print(f"DCR (unity)        : {h1.demand_capacity_ratio:.3f}")
    print(f"Pass               : {h1.unity_check_passes}")

    # --- Plot the envelope with the demand overlay ----------------------
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    element.plot_pm_interaction(
        effective_length_factor_Kx=1.0,
        unbraced_length_Lx=4.0 * u.m,
        effective_length_factor_Ky=1.0,
        unbraced_length_Ly=4.0 * u.m,
        effective_length_factor_Kz=1.0,
        unbraced_length_Lz=4.0 * u.m,
        ax=ax,
        which="phi",
        fill=True,
        demand_points=[(required_axial_Pr, required_moment_x_Mrx, "demand")],
        label="φ envelope",
        color="tab:blue",
    )
    ax.set_title("§H1.1 beam-column check")
    ax.legend(loc="upper right", fontsize=9)

    _OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(_OUT / "recipe_beam_column_H1.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

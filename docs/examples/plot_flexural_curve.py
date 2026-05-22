"""Flexural capacity curve (φMn vs Lb) for a W-shape.

Draws the AISC 360-22 Chapter-F φMn-vs-Lb curve with Lp/Lr landmarks,
limit-state-coloured segments (plastic plateau → inelastic LTB →
elastic LTB) and two projected unbraced lengths.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from apeSteel import A992, DoublySymmetricISection
from apeSteel.core import units as u

_OUT = Path(__file__).resolve().parents[1] / "assets" / "plots"


def main() -> None:
    section = DoublySymmetricISection(
        flange_width_bf=300 * u.mm,
        flange_thickness_tf=20 * u.mm,
        web_clear_height_hw=400 * u.mm,
        web_thickness_tw=16 * u.mm,
    )
    element = section.element(material=A992, construction="welded")

    unbraced_lengths_Lb = np.linspace(0.2 * u.m, 12.0 * u.m, 200)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    element.plot_flexural_curve(
        unbraced_lengths_Lb=unbraced_lengths_Lb,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
        ax=ax,
        which="phi_Mn",
        color_by_limit_state=True,
        show_landmarks=True,
        project_lengths=[(2.0 * u.m, "Lb = 2 m"), (6.0 * u.m, "Lb = 6 m")],
    )
    ax.set_title("Chapter-F flexural capacity curve")
    ax.legend(loc="upper right", fontsize=9)

    _OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(_OUT / "plot_flexural_curve.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

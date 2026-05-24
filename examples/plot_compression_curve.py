"""Compression capacity curve (φPn vs L) for a W-shape.

Renders the AISC 360-22 Chapter-E strength-vs-length curve, with a
fill under φPn, two projected design lengths, and limit-state-coloured
segments to show where flexural buckling hands over to torsional /
flexural-torsional buckling.
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

    lengths_L = np.linspace(0.5 * u.m, 12.0 * u.m, 200)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    element.plot_compression_curve(
        lengths_L=lengths_L,
        effective_length_factor_Kx=1.0,
        effective_length_factor_Ky=1.0,
        effective_length_factor_Kz=1.0,
        ax=ax,
        which="both",
        fill=True,
        project_lengths=[(3.0 * u.m, "L = 3 m"), (6.0 * u.m, "L = 6 m")],
        label="W 300×20 / 400×16",
        color="tab:blue",
    )
    ax.set_title("Chapter-E compression capacity curve")
    ax.legend(loc="upper right", fontsize=9)

    _OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(_OUT / "plot_compression_curve.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

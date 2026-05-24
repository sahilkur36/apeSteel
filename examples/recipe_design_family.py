"""Recipe: overlay capacity curves for a W-shape family.

Compares the Chapter-F φMn-vs-Lb curves of three W14 sections on a
single axes — the typical "which member is most efficient at this Lb?"
sizing question.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from apeSteel import A992, AISCv16Catalog
from apeSteel.core import units as u

_OUT = Path(__file__).resolve().parents[1] / "assets" / "plots"


def main() -> None:
    catalog = AISCv16Catalog()
    family = ["W14X90", "W14X132", "W14X176"]

    unbraced_lengths_Lb = np.linspace(0.5 * u.m, 12.0 * u.m, 200)

    fig, ax = plt.subplots(figsize=(7.5, 5))

    palette = ["tab:blue", "tab:orange", "tab:green"]
    for label, color in zip(family, palette, strict=True):
        section = catalog.get_doubly_symmetric_i_geometry(label)
        element = section.element(material=A992, construction="rolled")
        element.plot_flexural_curve(
            unbraced_lengths_Lb=unbraced_lengths_Lb,
            lateral_torsional_buckling_modification_factor_Cb=1.0,
            ax=ax,
            which="phi_Mn",
            label=label,
            color=color,
            linewidth=1.8,
        )

    ax.set_title("Design-family overlay — W14 series, Cb = 1.0")
    ax.legend(loc="upper right", fontsize=9)

    _OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(_OUT / "recipe_design_family.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Optional plotting helpers for apeSteel.

Plotting depends on :mod:`matplotlib`, which is **not** a core
dependency of apeSteel.  Install the ``plot`` extra to enable it::

    pip install "apeSteel[plot]"

Modules in this package import ``matplotlib`` lazily inside the
plotting functions, so the rest of apeSteel is usable without it.
"""

from apeSteel.plotting.compression import plot_compression_curve
from apeSteel.plotting.flexure import plot_flexural_curve
from apeSteel.plotting.interaction import (
    plot_mm_interaction,
    plot_pm_interaction,
    plot_pmm_interaction_3d,
)

__all__ = [
    "plot_compression_curve",
    "plot_flexural_curve",
    "plot_mm_interaction",
    "plot_pm_interaction",
    "plot_pmm_interaction_3d",
]

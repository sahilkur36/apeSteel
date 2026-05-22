# Plotting

Optional matplotlib helpers. Install with `pip install "apeSteel[plot]"`.

Three families of plots ship today:

- **Capacity curves** — `phi*Pn(KL)` and `phi*Mn(Lb)`.
- **Interaction diagrams** — uniaxial P-M, biaxial M-M, and the full 3D P-M-M envelope.
- Each plotter also lives as an `Element` delegate (e.g. `Element.plot_compression_curve(...)`).

## Capacity curves

::: apeSteel.plotting.compression.plot_compression_curve

::: apeSteel.plotting.flexure.plot_flexural_curve

## Interaction diagrams

::: apeSteel.plotting.interaction.plot_pm_interaction

::: apeSteel.plotting.interaction.plot_mm_interaction

::: apeSteel.plotting.interaction.plot_pmm_interaction_3d

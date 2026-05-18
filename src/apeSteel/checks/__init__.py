"""High-level facades that orchestrate multiple AISC checks.

Currently shipped:
* ``run_full_beam_check`` - the **I-shape** facade: classify per
  B4.1b + route to §F2/§F3/§F4/§F5 + run §G2 shear (doubly-/singly-
  symmetric I only; byte-unchanged since Phase 7 / F-1).
* ``compute_flexural_strength_*`` (``flexure_dispatch``) - the
  Phase-F-8 **non-I** ``section_kind``-driven dispatch: channel ->
  §F2(major)/§F6(minor), HSS -> §F7/§F8, tee/2L -> §F9, single
  angle -> §F10, bar -> §F11, unsymmetric -> §F12.  Additive sibling
  of ``run_full_beam_check`` (mirrors how
  ``apeSteel.compression.compute_compression_strength`` sits beside
  the DS-I-only ``Element.compression_strength``).

See docs/design_notes/04_flexure_F2_F3_F4_F5.md (I-shape routing tree)
and docs/design_notes/10_flexure_full_F.md §5/§7 (full Chapter F).
"""

from apeSteel.checks.beam_check import (
    BeamCheckReport,
    RoutedFlexureChapter,
    run_full_beam_check,
)
from apeSteel.checks.flexure_dispatch import (
    NonISectionFlexureReport,
    compute_flexural_strength_bar,
    compute_flexural_strength_channel,
    compute_flexural_strength_rectangular_hss,
    compute_flexural_strength_round_hss,
    compute_flexural_strength_single_angle,
    compute_flexural_strength_tee_or_double_angle,
    compute_flexural_strength_unsymmetric_F12,
)

__all__ = [
    "BeamCheckReport",
    "NonISectionFlexureReport",
    "RoutedFlexureChapter",
    "compute_flexural_strength_bar",
    "compute_flexural_strength_channel",
    "compute_flexural_strength_rectangular_hss",
    "compute_flexural_strength_round_hss",
    "compute_flexural_strength_single_angle",
    "compute_flexural_strength_tee_or_double_angle",
    "compute_flexural_strength_unsymmetric_F12",
    "run_full_beam_check",
]

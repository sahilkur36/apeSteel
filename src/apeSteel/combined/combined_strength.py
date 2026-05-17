"""AISC 360-22 Chapter H facade - combined-force interaction.

H-0 scaffold stub.  The orchestrator that routes a member to §H1.1 /
§H1.2 / §H1.3 / §H2 / §H3.2 (consuming the existing Chapter-E
``phi*Pn`` and Chapter-F ``phi*Mn``) lands incrementally across phases
H-1..H-5 and is wired to :class:`apeSteel.element.Element` in phase
H-7.  See ``docs/design_notes/09_combined_H.md`` §3-§8.
"""

from __future__ import annotations

from typing import NoReturn

_DESIGN_NOTE = "docs/design_notes/09_combined_H.md"


def compute_combined_strength(*_args: object, **_kwargs: object) -> NoReturn:
    """Not yet implemented - the Chapter-H facade lands across H-1..H-7."""
    raise NotImplementedError(
        f"The AISC 360-22 Chapter-H facade is scheduled across phases H-1..H-7; see {_DESIGN_NOTE}."
    )


__all__ = ["compute_combined_strength"]

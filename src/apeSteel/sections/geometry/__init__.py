"""Plate-built geometry classes.

Each concrete class here describes a steel cross-section purely in terms
of its plate dimensions (no material, no unbraced length). Each exposes
a ``compute_section_properties()`` method that returns the universal
:class:`SectionProperties` frozen dataclass downstream calculators
consume.

Currently supported geometries:

* :class:`DoublySymmetricISection` - welded built-up I, equal flanges.
* :class:`SinglySymmetricISection` - welded built-up I, unequal flanges
  (web attached at flange mid-width, Phase 9b).

The :data:`ISection` union is exported for downstream typing.
"""

from apeSteel.sections.geometry.channel_section import ChannelSection
from apeSteel.sections.geometry.doubly_symmetric_i_section import (
    DoublySymmetricISection,
)
from apeSteel.sections.geometry.rectangular_hss import RectangularHSS
from apeSteel.sections.geometry.round_hss import RoundHSS
from apeSteel.sections.geometry.singly_symmetric_i_section import (
    CompressionFlangeSide,
    SinglySymmetricISection,
)
from apeSteel.sections.geometry.tee_section import TeeSection

#: Either doubly- or singly-symmetric I-section.  Use as the geometry
#: type when downstream code does not need to discriminate (e.g.,
#: ``Element.section``).
ISection = DoublySymmetricISection | SinglySymmetricISection

__all__ = [
    "ChannelSection",
    "CompressionFlangeSide",
    "DoublySymmetricISection",
    "ISection",
    "RectangularHSS",
    "RoundHSS",
    "SinglySymmetricISection",
    "TeeSection",
]

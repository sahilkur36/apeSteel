"""AISC 360-22 §E6 - built-up compression members.

For a built-up member (e.g. a double angle) buckling about the axis
that engages relative deformation of the components, the geometric
slenderness ``(Lc/r)o`` (the member acting as a unit) is replaced by a
**modified slenderness** ``(Lc/r)m`` that accounts for shear flexibility
between intermediate connectors:

* Eq. E6-1  intermediate connectors *snug-tight bolted*:
  ``(Lc/r)m = sqrt( (Lc/r)o^2 + (a/ri)^2 )``
* Eq. E6-2  intermediate connectors *welded or pretensioned bolted*:
  - ``a/ri <= 40`` : ``(Lc/r)m = (Lc/r)o``
  - ``a/ri >  40`` : ``(Lc/r)m = sqrt( (Lc/r)o^2 + (Ki a/ri)^2 )``

with ``Ki = 0.50`` for back-to-back angles, ``0.75`` for back-to-back
channels, ``0.86`` for all other cases; ``a`` = connector spacing,
``ri`` = minimum radius of gyration of an individual component.

§E6.2 also requires the slenderness of an individual component between
connectors not to exceed ``0.75`` times the governing slenderness of
the built-up member - exposed here as :func:`connector_spacing_ok`.

References
----------
.. [1] AISC 360-22 §E6 "Built-up Members", Eq. E6-1 / E6-2, §E6.2,
       p. 16.1-42.
"""

from __future__ import annotations

import math
from typing import Literal

#: §E6.2 cap on an individual component's between-connector slenderness,
#: as a fraction of the governing built-up member slenderness.
E6_COMPONENT_SLENDERNESS_FRACTION: float = 0.75

#: Eq. E6-2 Ki by built-up arrangement.
KI_BACK_TO_BACK_ANGLES: float = 0.50
KI_BACK_TO_BACK_CHANNELS: float = 0.75
KI_OTHER: float = 0.86

ConnectorType = Literal["snug_bolted", "welded_or_pretensioned"]


def compute_modified_slenderness_E6(
    builtup_slenderness_Lc_over_r_o: float,
    connector_spacing_a: float,
    component_min_radius_of_gyration_ri: float,
    connector_type: ConnectorType,
    Ki: float = KI_BACK_TO_BACK_ANGLES,
) -> float:
    """Return ``(Lc/r)m`` per AISC 360-22 Eq. E6-1 / E6-2.

    Parameters
    ----------
    builtup_slenderness_Lc_over_r_o : float
        ``(Lc/r)o`` of the built-up member acting as a unit about the
        axis being modified (dimensionless).
    connector_spacing_a : float
        Longitudinal spacing ``a`` between intermediate connectors (mm).
    component_min_radius_of_gyration_ri : float
        Minimum radius of gyration ``ri`` of one component (mm).  Must
        be > 0.
    connector_type : {"snug_bolted", "welded_or_pretensioned"}
    Ki : float, optional
        Eq. E6-2 ``Ki`` (default 0.50 for back-to-back angles).

    Returns
    -------
    float
        Modified slenderness ``(Lc/r)m`` (dimensionless).

    Raises
    ------
    ValueError
        If ``component_min_radius_of_gyration_ri <= 0``.
    """
    if component_min_radius_of_gyration_ri <= 0.0:
        raise ValueError(
            f"component_min_radius_of_gyration_ri must be positive, "
            f"got {component_min_radius_of_gyration_ri!r}"
        )
    a_over_ri: float = connector_spacing_a / component_min_radius_of_gyration_ri
    base: float = builtup_slenderness_Lc_over_r_o

    if connector_type == "snug_bolted":
        return math.sqrt(base**2 + a_over_ri**2)  # Eq. E6-1

    # welded or pretensioned bolted (Eq. E6-2)
    if a_over_ri <= 40.0:
        return base
    return math.sqrt(base**2 + (Ki * a_over_ri) ** 2)


def connector_spacing_ok(
    connector_spacing_a: float,
    component_min_radius_of_gyration_ri: float,
    governing_member_slenderness: float,
) -> bool:
    """True iff §E6.2 component-between-connectors slenderness is satisfied.

    ``a / ri <= 0.75 * (governing built-up member slenderness)``.
    """
    if component_min_radius_of_gyration_ri <= 0.0:
        raise ValueError(
            f"component_min_radius_of_gyration_ri must be positive, "
            f"got {component_min_radius_of_gyration_ri!r}"
        )
    a_over_ri: float = connector_spacing_a / component_min_radius_of_gyration_ri
    return a_over_ri <= E6_COMPONENT_SLENDERNESS_FRACTION * governing_member_slenderness


__all__ = [
    "E6_COMPONENT_SLENDERNESS_FRACTION",
    "KI_BACK_TO_BACK_ANGLES",
    "KI_BACK_TO_BACK_CHANNELS",
    "KI_OTHER",
    "ConnectorType",
    "compute_modified_slenderness_E6",
    "connector_spacing_ok",
]

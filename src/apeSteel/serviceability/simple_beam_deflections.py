"""Elastic deflection formulas for simple and cantilever beams.

This module reproduces the closed-form deflection expressions taught
in any first-course mechanics-of-materials textbook. It is **not**
part of AISC 360 - it is the serviceability companion used to size
beams for stiffness once their strength has been verified.

Four cases ship today (Phase 8b):

* ``compute_deflection_simply_supported_udl`` -
  :math:`\\delta_{midspan} = 5 w L^{4} / (384 E I_x)` per Roark Case 6.
* ``compute_deflection_simply_supported_point_load_midspan`` -
  :math:`\\delta_{midspan} = P L^{3} / (48 E I_x)` per Roark Case 5.
* ``compute_deflection_simply_supported_point_load_arbitrary`` -
  point load ``P`` at distance ``a`` from the left support;
  returns both the mid-span and the absolute-maximum deflection.
* ``compute_deflection_cantilever_udl_and_tip_load`` -
  tip deflection :math:`\\delta_{tip} = w L^{4} / (8 E I_x) +
  P L^{3} / (3 E I_x)`.

Each calculator returns a frozen
:class:`~apeSteel.core.result_types.Report` subclass populated with
the inputs (Young's modulus, moment of inertia, span, loads), the
computed deflection, the corresponding ``L / ratio`` limits, and the
acceptance flags.

Loads, deflections, and limits are all stored in apeSteel base
``N-mm-tonne-s`` units (force in N, length in mm, distributed load in
N/mm).

References
----------
.. [Roark] Roark's Formulas for Stress and Strain, 9th ed., Table
   8.1 (simply-supported) and Table 8.2 (cantilever).
.. [DesignNote06] ``docs/design_notes/06_serviceability.md``
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties


# ---------------------------------------------------------------------------
# Spreadsheet defaults
# ---------------------------------------------------------------------------
DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR: float = 360.0
"""Default ``L / live_limit`` ratio - typical AISC live-load limit
for floor beams supporting plastered ceilings (Table 1604.3 IBC)."""

DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR: float = 240.0
"""Default ``L / total_limit`` ratio - typical total-load limit for
floor beams."""

DEFAULT_CAMBER_FRACTION_OF_DEAD_LOAD_DEFLECTION: float = 0.8
"""Default camber as a fraction of the deflection under unfactored
dead load. Shop practice varies between 0.75 and 1.0; 0.8 matches
the spreadsheet's default."""


# Serviceability has no AISC chapter; we cite the design note + Roark.
_CITATIONS_SERVICEABILITY: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="Roark's Formulas for Stress and Strain (9th ed.)",
        section="Table 8.1 - simply-supported beams",
    ),
    AISCClauseReference(
        specification="Roark's Formulas for Stress and Strain (9th ed.)",
        section="Table 8.2 - cantilever beams",
    ),
    AISCClauseReference(
        specification="apeSteel design notes",
        section="docs/design_notes/06_serviceability.md",
    ),
)


# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SimplySupportedUDLDeflectionReport(Report):
    """Mid-span elastic deflection of a simply-supported beam under UDL.

    All quantities are in apeSteel base ``N-mm-tonne-s`` units.

    Attributes
    ----------
    elastic_modulus_E, moment_of_inertia_Ix, span_length_L : float
        Echoed inputs.
    distributed_load_dead_w_dead, distributed_load_superdead_w_sd,
    distributed_load_live_w_live : float
        Echoed UDL inputs (N/mm).
    distributed_load_total_w_total : float
        ``w_dead + w_sd + w_live``.
    deflection_under_live_load_delta_live : float
        :math:`\\delta_{live} = 5 w_{live} L^{4} / (384 E I_x)`.
    deflection_under_total_load_delta_total : float
        :math:`\\delta_{total} = 5 w_{total} L^{4} / (384 E I_x)`.
    deflection_under_dead_load_delta_dead : float
        Convenience: :math:`5 w_{dead} L^{4} / (384 E I_x)` - input for
        the camber recommendation.
    deflection_limit_live : float
        ``L / live_load_limit_denominator``.
    deflection_limit_total : float
        ``L / total_load_limit_denominator``.
    is_live_load_deflection_acceptable, is_total_load_deflection_acceptable : bool
    """

    elastic_modulus_E: float = 0.0
    moment_of_inertia_Ix: float = 0.0
    span_length_L: float = 0.0
    distributed_load_dead_w_dead: float = 0.0
    distributed_load_superdead_w_sd: float = 0.0
    distributed_load_live_w_live: float = 0.0
    distributed_load_total_w_total: float = 0.0
    deflection_under_live_load_delta_live: float = 0.0
    deflection_under_total_load_delta_total: float = 0.0
    deflection_under_dead_load_delta_dead: float = 0.0
    deflection_limit_live: float = 0.0
    deflection_limit_total: float = 0.0
    is_live_load_deflection_acceptable: bool = True
    is_total_load_deflection_acceptable: bool = True


@dataclass(frozen=True, slots=True)
class SimplySupportedPointLoadMidspanDeflectionReport(Report):
    """Mid-span elastic deflection of a simply-supported beam under a
    centred point load.
    """

    elastic_modulus_E: float = 0.0
    moment_of_inertia_Ix: float = 0.0
    span_length_L: float = 0.0
    point_load_dead_P_dead: float = 0.0
    point_load_live_P_live: float = 0.0
    point_load_total_P_total: float = 0.0
    deflection_under_live_load_delta_live: float = 0.0
    deflection_under_total_load_delta_total: float = 0.0
    deflection_under_dead_load_delta_dead: float = 0.0
    deflection_limit_live: float = 0.0
    deflection_limit_total: float = 0.0
    is_live_load_deflection_acceptable: bool = True
    is_total_load_deflection_acceptable: bool = True


@dataclass(frozen=True, slots=True)
class SimplySupportedPointLoadArbitraryDeflectionReport(Report):
    """Elastic deflection of a simply-supported beam under a point load
    applied at distance ``a`` from the left support.

    Reports both the mid-span deflection (the value typically compared
    against ``L/ratio``) and the absolute-maximum deflection along the
    span (which occurs between the load and the farther support).
    """

    elastic_modulus_E: float = 0.0
    moment_of_inertia_Ix: float = 0.0
    span_length_L: float = 0.0
    distance_from_left_support_a: float = 0.0
    distance_from_right_support_b: float = 0.0
    point_load_total_P_total: float = 0.0
    deflection_at_midspan_delta_midspan: float = 0.0
    deflection_maximum_delta_max: float = 0.0
    location_of_max_from_left_support_x_max: float = 0.0
    deflection_limit_total: float = 0.0
    is_max_deflection_acceptable: bool = True


@dataclass(frozen=True, slots=True)
class CantileverUDLAndTipLoadDeflectionReport(Report):
    """Tip deflection of a cantilever under UDL ``w`` plus tip load ``P``.

    The two contributions are linear-elastic and superpose exactly:

    .. math::

        \\delta_{tip} = \\frac{w L^{4}}{8 E I_x} + \\frac{P L^{3}}{3 E I_x}.
    """

    elastic_modulus_E: float = 0.0
    moment_of_inertia_Ix: float = 0.0
    cantilever_length_L: float = 0.0
    distributed_load_w: float = 0.0
    tip_point_load_P: float = 0.0
    deflection_from_udl_delta_udl: float = 0.0
    deflection_from_tip_load_delta_tip_load: float = 0.0
    deflection_at_tip_delta_tip: float = 0.0
    deflection_limit: float = 0.0
    is_tip_deflection_acceptable: bool = True


# ---------------------------------------------------------------------------
# Calculators
# ---------------------------------------------------------------------------
def compute_deflection_simply_supported_udl(
    section_properties: SectionProperties,
    material: SteelMaterial,
    span_length_L: float,
    distributed_load_dead_w_dead: float = 0.0,
    distributed_load_superdead_w_sd: float = 0.0,
    distributed_load_live_w_live: float = 0.0,
    live_load_limit_denominator: float = DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    total_load_limit_denominator: float = DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
) -> SimplySupportedUDLDeflectionReport:
    """Mid-span deflection of a simply-supported beam under UDL.

    Computes the elastic mid-span deflection
    :math:`\\delta = 5 w L^{4} / (384 E I_x)` for live load, dead load,
    and the total ``w_dead + w_sd + w_live`` UDL.

    Parameters
    ----------
    section_properties : SectionProperties
        Source of ``I_x`` (strong-axis moment of inertia).
    material : SteelMaterial
        Source of ``E``.
    span_length_L : float
        Beam span (mm).
    distributed_load_dead_w_dead, distributed_load_superdead_w_sd,
    distributed_load_live_w_live : float
        UDL components (N/mm).  Defaults to zero so any subset can be
        supplied.
    live_load_limit_denominator : float
        Denominator of the live-load deflection limit ``L / N``.
        Default 360.
    total_load_limit_denominator : float
        Denominator of the total-load deflection limit ``L / N``.
        Default 240.

    Returns
    -------
    SimplySupportedUDLDeflectionReport
        Frozen report.  ``governing_limit_state`` is ``"deflection_acceptable"``
        if both checks pass, otherwise names the failing check.
    """
    E: float = material.elastic_modulus_E
    Ix: float = section_properties.moment_of_inertia_strong_axis_Ix
    L: float = span_length_L

    w_total: float = (
        distributed_load_dead_w_dead
        + distributed_load_superdead_w_sd
        + distributed_load_live_w_live
    )

    # 5 w L^4 / (384 E I)
    constant_5_over_384: float = 5.0 / 384.0
    L_to_the_fourth: float = L**4
    delta_live: float = (
        constant_5_over_384 * distributed_load_live_w_live * L_to_the_fourth / (E * Ix)
    )
    delta_total: float = constant_5_over_384 * w_total * L_to_the_fourth / (E * Ix)
    delta_dead: float = (
        constant_5_over_384 * distributed_load_dead_w_dead * L_to_the_fourth / (E * Ix)
    )

    limit_live: float = L / live_load_limit_denominator
    limit_total: float = L / total_load_limit_denominator
    is_live_ok: bool = delta_live <= limit_live
    is_total_ok: bool = delta_total <= limit_total

    if is_live_ok and is_total_ok:
        governing: str = "deflection_acceptable"
    elif not is_live_ok and not is_total_ok:
        governing = "live_and_total_load_deflection_exceeded"
    elif not is_live_ok:
        governing = "live_load_deflection_exceeded"
    else:
        governing = "total_load_deflection_exceeded"

    return SimplySupportedUDLDeflectionReport(
        cited_clauses=_CITATIONS_SERVICEABILITY,
        governing_limit_state=governing,
        elastic_modulus_E=E,
        moment_of_inertia_Ix=Ix,
        span_length_L=L,
        distributed_load_dead_w_dead=distributed_load_dead_w_dead,
        distributed_load_superdead_w_sd=distributed_load_superdead_w_sd,
        distributed_load_live_w_live=distributed_load_live_w_live,
        distributed_load_total_w_total=w_total,
        deflection_under_live_load_delta_live=delta_live,
        deflection_under_total_load_delta_total=delta_total,
        deflection_under_dead_load_delta_dead=delta_dead,
        deflection_limit_live=limit_live,
        deflection_limit_total=limit_total,
        is_live_load_deflection_acceptable=is_live_ok,
        is_total_load_deflection_acceptable=is_total_ok,
    )


def compute_deflection_simply_supported_point_load_midspan(
    section_properties: SectionProperties,
    material: SteelMaterial,
    span_length_L: float,
    point_load_dead_P_dead: float = 0.0,
    point_load_live_P_live: float = 0.0,
    live_load_limit_denominator: float = DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    total_load_limit_denominator: float = DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
) -> SimplySupportedPointLoadMidspanDeflectionReport:
    """Mid-span deflection of a simply-supported beam under a centred
    point load.

    :math:`\\delta_{midspan} = P L^{3} / (48 E I_x)`.
    """
    E: float = material.elastic_modulus_E
    Ix: float = section_properties.moment_of_inertia_strong_axis_Ix
    L: float = span_length_L
    P_total: float = point_load_dead_P_dead + point_load_live_P_live
    L_cubed: float = L**3

    delta_live: float = point_load_live_P_live * L_cubed / (48.0 * E * Ix)
    delta_total: float = P_total * L_cubed / (48.0 * E * Ix)
    delta_dead: float = point_load_dead_P_dead * L_cubed / (48.0 * E * Ix)

    limit_live: float = L / live_load_limit_denominator
    limit_total: float = L / total_load_limit_denominator
    is_live_ok: bool = delta_live <= limit_live
    is_total_ok: bool = delta_total <= limit_total

    if is_live_ok and is_total_ok:
        governing = "deflection_acceptable"
    elif not is_live_ok and not is_total_ok:
        governing = "live_and_total_load_deflection_exceeded"
    elif not is_live_ok:
        governing = "live_load_deflection_exceeded"
    else:
        governing = "total_load_deflection_exceeded"

    return SimplySupportedPointLoadMidspanDeflectionReport(
        cited_clauses=_CITATIONS_SERVICEABILITY,
        governing_limit_state=governing,
        elastic_modulus_E=E,
        moment_of_inertia_Ix=Ix,
        span_length_L=L,
        point_load_dead_P_dead=point_load_dead_P_dead,
        point_load_live_P_live=point_load_live_P_live,
        point_load_total_P_total=P_total,
        deflection_under_live_load_delta_live=delta_live,
        deflection_under_total_load_delta_total=delta_total,
        deflection_under_dead_load_delta_dead=delta_dead,
        deflection_limit_live=limit_live,
        deflection_limit_total=limit_total,
        is_live_load_deflection_acceptable=is_live_ok,
        is_total_load_deflection_acceptable=is_total_ok,
    )


def compute_deflection_simply_supported_point_load_arbitrary(
    section_properties: SectionProperties,
    material: SteelMaterial,
    span_length_L: float,
    distance_from_left_support_a: float,
    point_load_total_P_total: float,
    total_load_limit_denominator: float = DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
) -> SimplySupportedPointLoadArbitraryDeflectionReport:
    """Deflection of a simply-supported beam under a point load at
    distance ``a`` from the left support.

    Reports both the mid-span deflection and the absolute-maximum
    deflection.

    Closed-form (Roark Table 8.1, case 5):

    Let ``b = L - a``.  Assume without loss of generality that ``a
    >= b`` (otherwise swap a and b - the maximum lives on the longer
    segment).  Then the maximum deflection occurs at

    .. math::

        x_{max} = \\sqrt{(L^{2} - b^{2}) / 3}

    measured from the left support, with magnitude

    .. math::

        \\delta_{max} = \\frac{P b (L^{2} - b^{2})^{3/2}}{9 \\sqrt{3} L E I}.

    The mid-span deflection (compared against ``L / N``) is:

    .. math::

        \\delta_{midspan} = \\frac{P b (3 L^{2} - 4 b^{2})}{48 E I}
        \\quad \\text{(midspan on the longer segment).}
    """
    if not 0.0 < distance_from_left_support_a < span_length_L:
        msg = (
            "distance_from_left_support_a must satisfy 0 < a < L, "
            f"got a={distance_from_left_support_a}, L={span_length_L}."
        )
        raise ValueError(msg)

    E: float = material.elastic_modulus_E
    Ix: float = section_properties.moment_of_inertia_strong_axis_Ix
    L: float = span_length_L
    a: float = distance_from_left_support_a
    b: float = L - a

    # Identify the shorter of the two load-to-support distances; the
    # Roark closed-form expresses both delta_max and its location
    # entirely in terms of that shorter distance (call it ``c`` here).
    shorter_distance_c: float = min(a, b)
    longer_distance_d: float = max(a, b)

    # Roark Table 8.1 case 5e:
    #   delta_max = P c (L^2 - c^2)^(3/2) / (9 sqrt(3) L E I)
    # located at x_far = sqrt((L^2 - c^2) / 3) measured from the support
    # ADJACENT to the longer segment (i.e. the support farther from the
    # load).
    L_squared: float = L**2
    shorter_squared: float = shorter_distance_c**2
    delta_max: float = (
        point_load_total_P_total * shorter_distance_c * (L_squared - shorter_squared) ** 1.5
    ) / (9.0 * math.sqrt(3.0) * L * E * Ix)
    x_max_from_far_support: float = math.sqrt((L_squared - shorter_squared) / 3.0)
    # Convert to a left-support origin.  The "far support" is end A
    # when the load is closer to end B (a > b), else end B.
    location_of_max_from_left: float = (
        x_max_from_far_support if a >= b else L - x_max_from_far_support
    )

    # Mid-span deflection.  By symmetry, Pa(3L^2 - 4a^2)/(48 EI) uses
    # the SHORTER of the two distances in place of `a`.
    delta_midspan: float = (
        point_load_total_P_total * shorter_distance_c * (3.0 * L_squared - 4.0 * shorter_squared)
    ) / (48.0 * E * Ix)
    # Silence unused-variable warning - kept for trace clarity.
    _ = longer_distance_d

    limit_total: float = L / total_load_limit_denominator
    is_max_ok: bool = delta_max <= limit_total

    governing: str = "deflection_acceptable" if is_max_ok else "max_deflection_exceeded"

    return SimplySupportedPointLoadArbitraryDeflectionReport(
        cited_clauses=_CITATIONS_SERVICEABILITY,
        governing_limit_state=governing,
        elastic_modulus_E=E,
        moment_of_inertia_Ix=Ix,
        span_length_L=L,
        distance_from_left_support_a=a,
        distance_from_right_support_b=b,
        point_load_total_P_total=point_load_total_P_total,
        deflection_at_midspan_delta_midspan=delta_midspan,
        deflection_maximum_delta_max=delta_max,
        location_of_max_from_left_support_x_max=location_of_max_from_left,
        deflection_limit_total=limit_total,
        is_max_deflection_acceptable=is_max_ok,
    )


def compute_deflection_cantilever_udl_and_tip_load(
    section_properties: SectionProperties,
    material: SteelMaterial,
    cantilever_length_L: float,
    distributed_load_w: float = 0.0,
    tip_point_load_P: float = 0.0,
    deflection_limit_denominator: float = DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
) -> CantileverUDLAndTipLoadDeflectionReport:
    """Tip deflection of a cantilever under combined UDL + tip load.

    .. math::

        \\delta_{tip} = \\frac{w L^{4}}{8 E I_x} + \\frac{P L^{3}}{3 E I_x}

    Parameters
    ----------
    section_properties, material : as elsewhere.
    cantilever_length_L : float
        Cantilever span (mm).
    distributed_load_w : float
        UDL on the cantilever (N/mm).
    tip_point_load_P : float
        Concentrated tip load (N).
    deflection_limit_denominator : float
        For a cantilever, AISC typically allows ``L / 180`` to
        ``L / 360`` depending on use.  We expose the denominator so
        the caller picks; default 360 to be conservative.
    """
    E: float = material.elastic_modulus_E
    Ix: float = section_properties.moment_of_inertia_strong_axis_Ix
    L: float = cantilever_length_L

    delta_udl: float = distributed_load_w * (L**4) / (8.0 * E * Ix)
    delta_tip_load: float = tip_point_load_P * (L**3) / (3.0 * E * Ix)
    delta_tip: float = delta_udl + delta_tip_load

    deflection_limit: float = L / deflection_limit_denominator
    is_tip_ok: bool = delta_tip <= deflection_limit

    governing: str = "deflection_acceptable" if is_tip_ok else "tip_deflection_exceeded"

    return CantileverUDLAndTipLoadDeflectionReport(
        cited_clauses=_CITATIONS_SERVICEABILITY,
        governing_limit_state=governing,
        elastic_modulus_E=E,
        moment_of_inertia_Ix=Ix,
        cantilever_length_L=L,
        distributed_load_w=distributed_load_w,
        tip_point_load_P=tip_point_load_P,
        deflection_from_udl_delta_udl=delta_udl,
        deflection_from_tip_load_delta_tip_load=delta_tip_load,
        deflection_at_tip_delta_tip=delta_tip,
        deflection_limit=deflection_limit,
        is_tip_deflection_acceptable=is_tip_ok,
    )


def recommend_camber_from_dead_load_deflection(
    deflection_under_dead_load: float,
    camber_factor: float = DEFAULT_CAMBER_FRACTION_OF_DEAD_LOAD_DEFLECTION,
) -> float:
    """Return ``camber_factor * deflection_under_dead_load`` (mm).

    The spreadsheet's default ``camber_factor`` is 0.8 - shop practice
    typically rounds the result to the nearest 1/4 inch in US shops
    or 5 mm in metric shops.  apeSteel does **not** round; the caller
    is expected to apply rounding appropriate to their shop's
    practice.
    """
    return camber_factor * deflection_under_dead_load


__all__ = [
    "DEFAULT_CAMBER_FRACTION_OF_DEAD_LOAD_DEFLECTION",
    "DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR",
    "DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR",
    "CantileverUDLAndTipLoadDeflectionReport",
    "SimplySupportedPointLoadArbitraryDeflectionReport",
    "SimplySupportedPointLoadMidspanDeflectionReport",
    "SimplySupportedUDLDeflectionReport",
    "compute_deflection_cantilever_udl_and_tip_load",
    "compute_deflection_simply_supported_point_load_arbitrary",
    "compute_deflection_simply_supported_point_load_midspan",
    "compute_deflection_simply_supported_udl",
    "recommend_camber_from_dead_load_deflection",
]

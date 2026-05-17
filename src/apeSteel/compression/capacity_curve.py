"""φPn-vs-length capacity curve (the source workbook's Data-Table column).

Every workbook sheet builds a 21-point ``phi*Pn`` vs effective-length
curve via an Excel Data Table.  This reproduces it as a pure function:
given a section, material and per-axis ``K`` factors, evaluate the
Chapter-E governing ``phi*Pn`` over a sequence of member lengths.

Used for design charts / capacity envelopes; it simply re-evaluates the
validated :func:`compute_compression_strength` facade at each length,
so it inherits the same oracle/Excel anchoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.compression.compression_strength import (
    compute_compression_strength_from_K_L,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeSteel.compression.single_angle_E5 import SingleAngleE5Case
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.compression_properties import CompressionSectionProperties


@dataclass(frozen=True, slots=True)
class CapacityCurvePoint:
    """One point on the φPn-vs-length curve.

    Attributes
    ----------
    length_L : float
        The (un-factored) member length used for all three axes (mm).
    nominal_strength_Pn : float
        Governing ``Pn`` at this length (N).
    design_strength_phi_Pn : float
        ``phi_c * Pn`` (N).
    governing_limit_state : str
    """

    length_L: float
    nominal_strength_Pn: float
    design_strength_phi_Pn: float
    governing_limit_state: str


def compute_phi_Pn_vs_length(
    section_properties: CompressionSectionProperties,
    material: SteelMaterial,
    lengths_L: Sequence[float],
    *,
    effective_length_factor_Kx: float = 1.0,
    effective_length_factor_Ky: float = 1.0,
    effective_length_factor_Kz: float = 1.0,
    single_angle_E5_case: SingleAngleE5Case | None = None,
    builtup_connector_spacing_a: float | None = None,
) -> tuple[CapacityCurvePoint, ...]:
    """Return the φPn-vs-length capacity curve.

    Parameters
    ----------
    section_properties : CompressionSectionProperties
    material : SteelMaterial
    lengths_L : sequence of float
        Member lengths (mm).  ``Lc = K * L`` is formed per axis at each.
    effective_length_factor_Kx/Ky/Kz : float
        Per-axis ``K`` (default 1.0, the DAM value).
    single_angle_E5_case : {"a","b"} or None
        Forwarded to the facade for single angles.
    builtup_connector_spacing_a : float or None
        Forwarded to the facade for double-angle §E6.

    Returns
    -------
    tuple of CapacityCurvePoint
        One point per input length, in the input order.

    Raises
    ------
    ValueError
        If any length is non-positive.
    """
    points: list[CapacityCurvePoint] = []
    for length in lengths_L:
        if length <= 0.0:
            raise ValueError(f"lengths_L must all be positive, got {length!r}")
        report = compute_compression_strength_from_K_L(
            section_properties=section_properties,
            material=material,
            effective_length_factor_Kx=effective_length_factor_Kx,
            unbraced_length_Lx=length,
            effective_length_factor_Ky=effective_length_factor_Ky,
            unbraced_length_Ly=length,
            effective_length_factor_Kz=effective_length_factor_Kz,
            unbraced_length_Lz=length,
            single_angle_E5_case=single_angle_E5_case,
            builtup_connector_spacing_a=builtup_connector_spacing_a,
        )
        points.append(
            CapacityCurvePoint(
                length_L=length,
                nominal_strength_Pn=report.nominal_compressive_strength_Pn,
                design_strength_phi_Pn=report.phi_strength_LRFD,
                governing_limit_state=report.governing_compression_limit_state,
            )
        )
    return tuple(points)


__all__ = ["CapacityCurvePoint", "compute_phi_Pn_vs_length"]

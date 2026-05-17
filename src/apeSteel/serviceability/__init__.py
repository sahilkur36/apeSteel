"""Serviceability - elastic deflections and camber (Phase 8b).

See ``docs/design_notes/06_serviceability.md`` for the design.
"""

from __future__ import annotations

from apeSteel.serviceability.simple_beam_deflections import (
    DEFAULT_CAMBER_FRACTION_OF_DEAD_LOAD_DEFLECTION,
    DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    CantileverUDLAndTipLoadDeflectionReport,
    SimplySupportedPointLoadArbitraryDeflectionReport,
    SimplySupportedPointLoadMidspanDeflectionReport,
    SimplySupportedUDLDeflectionReport,
    compute_deflection_cantilever_udl_and_tip_load,
    compute_deflection_simply_supported_point_load_arbitrary,
    compute_deflection_simply_supported_point_load_midspan,
    compute_deflection_simply_supported_udl,
    recommend_camber_from_dead_load_deflection,
)

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

"""Golden-file regression tests for the AISC 341 §E3.6e column-flange
tension check.

The companion CSV ``panel_zone_341.csv`` pins eight representative
beam/column pairings (catalog W shapes + plate-built mixes, three
material combinations) at ``rel_tol = abs_tol = 1e-9``.  If any
constant or formula in ``apeSteel.seismic.panel_zone_341`` drifts,
the relevant row fails loudly.
"""

from __future__ import annotations

import ast
import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING

import baseUnits as u
import pytest

from apeSteel import (
    A36,
    A992,
    S355,
    AISCv16Catalog,
    DoublySymmetricISection,
    check_column_flange_tension_341,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

GOLDEN_CSV_PATH: Path = Path(__file__).parent / "panel_zone_341.csv"
TOL: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {
    "ASTM A992": A992,
    "ASTM A36": A36,
    "EN 10025 S355": S355,
}


def _load_rows() -> list[dict[str, str]]:
    with GOLDEN_CSV_PATH.open() as fp:
        return list(csv.DictReader(fp))


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOL, abs_tol=TOL)


def _section_properties_from_csv(kind: str, value_repr: str) -> SectionProperties:
    """Build section properties from one row's beam/column spec.

    ``kind`` is ``"catalog"`` or ``"plate"``.  ``value_repr`` is the
    ``str()`` of a catalog label (e.g. ``"W24X94"``) or of a 4-tuple
    of plate dimensions in mm (e.g. ``"(127.0, 8.0, 339.0, 6.0)"``).
    """
    if kind == "catalog":
        catalog = AISCv16Catalog()
        return catalog.get_section_properties(value_repr)
    if kind == "plate":
        # value_repr is a Python repr of a tuple of floats.
        plate_dims = ast.literal_eval(value_repr)
        bf, tf, hw, tw = plate_dims
        section = DoublySymmetricISection(
            flange_width_bf=float(bf) * u.mm,
            flange_thickness_tf=float(tf) * u.mm,
            web_clear_height_hw=float(hw) * u.mm,
            web_thickness_tw=float(tw) * u.mm,
        )
        return section.compute_section_properties()
    raise AssertionError(f"Unknown section kind: {kind!r}")


@pytest.mark.golden
@pytest.mark.parametrize(
    "row",
    _load_rows(),
    ids=[r["case_label"] for r in _load_rows()],
)
def test_panel_zone_golden(row: dict[str, str]) -> None:
    beam_props = _section_properties_from_csv(row["beam_kind"], row["beam_value"])
    column_props = _section_properties_from_csv(row["column_kind"], row["column_value"])
    beam_mat = _MATERIAL_BY_NAME[row["beam_material_name"]]
    col_mat = _MATERIAL_BY_NAME[row["column_material_name"]]

    r = check_column_flange_tension_341(beam_props, beam_mat, column_props, col_mat)

    assert _isclose(r.beam_flange_tension_demand_Tu, float(row["Tu_N"]))
    assert _isclose(r.column_flange_tension_capacity_Rn, float(row["Rn_N"]))
    assert _isclose(r.phi_column_flange_tension_capacity_phi_Rn_LRFD, float(row["phi_Rn_N"]))
    assert _isclose(r.column_flange_thickness_tcf, float(row["tcf_mm"]))
    assert _isclose(
        r.minimum_column_flange_thickness_geometric_tcf_min_1,
        float(row["tcf_min_1_mm"]),
    )
    assert _isclose(
        r.minimum_column_flange_thickness_capacity_tcf_min_2,
        float(row["tcf_min_2_mm"]),
    )
    assert _isclose(r.minimum_column_flange_thickness_required_tcf_min, float(row["tcf_min_mm"]))
    assert _isclose(r.demand_to_capacity_ratio, float(row["DCR"]))
    assert int(r.is_thickness_acceptable) == int(row["is_thickness_ok"])
    assert int(r.is_demand_to_capacity_acceptable) == int(row["is_dcr_ok"])
    assert r.governing_limit_state == row["governing_limit_state"]

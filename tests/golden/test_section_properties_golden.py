"""Golden-file regression tests for DoublySymmetricISection.

The companion CSV at section_properties_doubly_symmetric_i.csv pins the
*exact* float values that compute_section_properties() must produce for
a handful of plate-built I-shapes spanning small, medium, plate-girder,
and IPE-like sizes. If any AISC formula in the codebase ever drifts even
in the 9th significant figure, this test fails loudly.

The CSV is committed to git so changes are diffable. To regenerate after
an intentional change, rerun the generator script (see commit history)
and review the diff before committing.

This test layer is the bottom of the regression net: even when unit
tests pass, a 1-line bug in compute_section_properties() that flips a
sign or swaps a factor would surface here.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from apeSteel.core import units as u
from apeSteel.sections.geometry import DoublySymmetricISection

if TYPE_CHECKING:
    from apeSteel.sections.properties import SectionProperties

GOLDEN_CSV_PATH: Path = Path(__file__).parent / "section_properties_doubly_symmetric_i.csv"

#: Numeric tolerance for golden comparison. 1e-9 is well below any
#: realistic floating-point round-off path through the section formulas.
GOLDEN_RELATIVE_TOLERANCE: float = 1e-9
GOLDEN_ABSOLUTE_TOLERANCE: float = 1e-9


def _load_golden_rows() -> list[dict[str, str]]:
    with GOLDEN_CSV_PATH.open() as fp:
        return list(csv.DictReader(fp))


def _build_section_from_row(row: dict[str, str]) -> DoublySymmetricISection:
    return DoublySymmetricISection(
        flange_width_bf=float(row["flange_width_bf_mm"]) * u.mm,
        flange_thickness_tf=float(row["flange_thickness_tf_mm"]) * u.mm,
        web_clear_height_hw=float(row["web_clear_height_hw_mm"]) * u.mm,
        web_thickness_tw=float(row["web_thickness_tw_mm"]) * u.mm,
    )


GOLDEN_ATTRIBUTES: list[str] = [
    "overall_depth_d",
    "gross_area_Ag",
    "nominal_weight_per_unit_length_w",
    "moment_of_inertia_strong_axis_Ix",
    "elastic_section_modulus_strong_axis_Sx",
    "plastic_section_modulus_strong_axis_Zx",
    "radius_of_gyration_strong_axis_rx",
    "moment_of_inertia_weak_axis_Iy",
    "elastic_section_modulus_weak_axis_Sy",
    "plastic_section_modulus_weak_axis_Zy",
    "radius_of_gyration_weak_axis_ry",
    "torsional_constant_J",
    "warping_constant_Cw",
    "distance_between_flange_centroids_ho",
    "effective_radius_of_gyration_for_LTB_rts",
    "flange_width_to_thickness_ratio_bf_2tf",
    "web_height_to_thickness_ratio_h_tw",
]


@pytest.mark.regression
@pytest.mark.parametrize(
    "row",
    _load_golden_rows(),
    ids=[r["case_label"] for r in _load_golden_rows()],
)
def test_golden_section_properties(row: dict[str, str]) -> None:
    """Every section property must match the golden CSV within 1e-9."""
    section = _build_section_from_row(row)
    computed: SectionProperties = section.compute_section_properties()
    for attribute_name in GOLDEN_ATTRIBUTES:
        expected = float(row[attribute_name])  # repr() round-trips losslessly
        actual = getattr(computed, attribute_name)
        assert math.isclose(
            actual,
            expected,
            rel_tol=GOLDEN_RELATIVE_TOLERANCE,
            abs_tol=GOLDEN_ABSOLUTE_TOLERANCE,
        ), (
            f"{row['case_label']}.{attribute_name}: "
            f"got {actual!r}, expected {expected!r} (delta={actual - expected!r})"
        )

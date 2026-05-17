"""Classification - AISC 360 §B4.1a, AISC 360 §B4.1b, and AISC 341 §D1.1.

Three classifiers live here, each a pure function returning a frozen
report:

* `classify_axial_compression_B4_1a` - non_slender vs slender for axial
  compression elements (Table B4.1a).
* `classify_flexural_compactness_B4_1b` - compact / non-compact /
  slender for flexure (Table B4.1b).
* `classify_seismic_compactness_341_D1` - highly-ductile or
  moderately-ductile acceptance check for fuse elements in seismic-
  force-resisting systems (Table D1.1), with code_edition support.

All three take `SectionProperties` + `SteelMaterial` and the
appropriate flags, and return a frozen Report subclass with per-
element `PlateElementClassification` records.

See docs/design_notes/02_classification_B4.md and
docs/design_notes/03_seismic_compactness_341.md for the design.
"""

from apeSteel.classification._common import (
    AxialPlateClass,
    DuctilityLevel,
    FlexuralPlateClass,
    PlateElementClassification,
    SectionConstruction,
    SeismicCodeEdition,
    compute_kc_for_built_up_flange,
)
from apeSteel.classification.axial_compression_B4_1a import (
    AxialCompressionClassificationReport,
    classify_axial_compression_B4_1a,
)
from apeSteel.classification.flexural_compactness_B4_1b import (
    FlexuralCompactnessReport,
    classify_flexural_compactness_B4_1b,
)
from apeSteel.classification.seismic_compactness_341_D1 import (
    SeismicCompactnessReport,
    classify_seismic_compactness_341_D1,
)

__all__ = [
    "AxialCompressionClassificationReport",
    "AxialPlateClass",
    "DuctilityLevel",
    "FlexuralCompactnessReport",
    "FlexuralPlateClass",
    "PlateElementClassification",
    "SectionConstruction",
    "SeismicCodeEdition",
    "SeismicCompactnessReport",
    "classify_axial_compression_B4_1a",
    "classify_flexural_compactness_B4_1b",
    "classify_seismic_compactness_341_D1",
    "compute_kc_for_built_up_flange",
]

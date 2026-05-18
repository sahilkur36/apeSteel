"""Independent AISC 360-22 §F7 (square/rect HSS & box) oracle - Phase F-3.

This is a deliberately *separate*, standalone re-derivation of AISC
360-22 §F7 nominal flexural strength.  It imports **only** the
standard-library ``math`` module - nothing from ``apeSteel`` and in
particular nothing from :mod:`apeSteel.flexure`.

It is kept distinct from the shared
:mod:`tests.golden._chapterF_full_aisc_oracle` on purpose: that shared
scaffold has a Phase-F-3 ``mn_F7`` *stub*; per the F-3 contract that
stub is **left untouched** here to avoid a cross-phase merge seam, and
§F7 is re-derived in this self-contained module instead.  (Note for the
orchestrator: ``_chapterF_full_aisc_oracle.mn_F7`` remains the
unmodified F-0 stub; wiring it is out of F-3 scope.)

Per design note 10 §6 this oracle is the **primary, bit-exact
(`rel_tol=1e-9`) regression pin** for the §F7 calculator, so its
correctness never rests on a snapshot of its own output.  Section
properties (``Z``, ``S``, ``I``, ``Ag``, ``J``, ``r``, the two flat
wall widths and ``t``) are supplied by the caller (the golden test);
only the §F7 *strength composition* (Eq. F7-1 .. F7-13 + the Table
B4.1b flange/web regime split + the §F7.4 square/minor-axis LTB
exclusion) is re-derived here.

Every constant is written as a literal transcribed from the printed
spec, intentionally *not* shared with the library, so a typo in either
implementation surfaces as a disagreement.

References
----------
AISC 360-22, Specification for Structural Steel Buildings, §F7
"Square and Rectangular HSS and Box Sections", pp. 16.1-63 .. 16.1-65:

* Eq. F7-1   ``Mn = Mp = Fy*Z``                       (yielding)
* Eq. F7-2   ``Mn = Mp - (Mp - Fy*S)(l-lpf)/(lrf-lpf) <= Mp``  (NC flange)
* Eq. F7-3   ``Mn = Fy*Se``                           (slender flange)
* Eq. F7-4   ``be = 1.92 t sqrt(E/Fy)(1 - 0.38/(b/t) sqrt(E/Fy)) <= b``
* Eq. F7-5   box: same with ``0.34``
* Eq. F7-6   ``Mn = Mp - (Mp - Fy*S)(l-lpw)/(lrw-lpw) <= Mp``   (NC web)
* Eq. F7-7   ``Mn = Rpg*Fy*S``                        (slender web)
* Eq. F7-10  ``Mn = Cb[Mp - (Mp - 0.7 Fy Sx)(Lb-Lp)/(Lr-Lp)] <= Mp``
* Eq. F7-11  ``Mn = 2 E Cb sqrt(J Ag)/(Lb/ry) <= Mp``
* Eq. F7-12  ``Lp = 0.13 E ry sqrt(J Ag)/Mp``
* Eq. F7-13  ``Lr = 2 E ry sqrt(J Ag)/(0.7 Fy Sx)``
* §F7.4 User Note - LTB does not apply to square sections or to
  minor-axis bending.

``ry`` in Eq. F7-11/F7-12/F7-13 is the **minor-axis** radius of
gyration (the spec writes ``ry`` literally; AISC Manual v15.1 Ex. F.7B
uses the weak-axis radius for a strong-axis-bent HSS).  §F7.4 LTB only
applies to major-axis bending, so this oracle takes it as a dedicated
``ry_minor`` input.

Eq. F5-6 (reused by §F7.3(c) for ``Rpg``, slender web):
``Rpg = 1 - aw/(1200 + 300 aw)(hc/tw - 5.7 sqrt(E/Fy)) <= 1`` with
``aw = 2 h tw/(b tf) <= 10`` (§F7.3, spec 16.1-64).

Table B4.1b square/rectangular HSS flexure limits (transcribed from
``docs/design_notes/_aisc_src_extract/skill_reference_chapterF.md`` and
the AISC Manual v15.1 Ex. F.7B/F.8B printed values): flange
``lambda_p = 1.12 sqrt(E/Fy)``, ``lambda_r = 1.40 sqrt(E/Fy)``; web
``lambda_p = 2.42 sqrt(E/Fy)``, ``lambda_r = 5.70 sqrt(E/Fy)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AISC 360-22 §F7 + Table B4.1b literal constants (printed 16.1-63..65).
# Duplicated here (NOT imported from apeSteel) on purpose.
# ---------------------------------------------------------------------------
#: Table B4.1b HSS flange flexure: lambda_p = 1.12 sqrt(E/Fy).
_B4_1B_HSS_FLANGE_LAMBDA_P_COEFF: float = 1.12
#: Table B4.1b HSS flange flexure: lambda_r = 1.40 sqrt(E/Fy).
_B4_1B_HSS_FLANGE_LAMBDA_R_COEFF: float = 1.40
#: Table B4.1b HSS web flexure: lambda_p = 2.42 sqrt(E/Fy).
_B4_1B_HSS_WEB_LAMBDA_P_COEFF: float = 2.42
#: Table B4.1b HSS web flexure: lambda_r = 5.70 sqrt(E/Fy).
_B4_1B_HSS_WEB_LAMBDA_R_COEFF: float = 5.70

#: Eq. F7-4 / F7-5 lead coefficient 1.92.
_EQ_F7_4_5_LEAD: float = 1.92
#: Eq. F7-4 inner coefficient 0.38 (HSS effective width).
_EQ_F7_4_HSS_INNER: float = 0.38
#: Eq. F7-5 inner coefficient 0.34 (box effective width).
_EQ_F7_5_BOX_INNER: float = 0.34

#: §F7.4 LTB stress fraction 0.7 Fy (Eq. F7-10 / Eq. F7-13).
_EQ_F7_LTB_07: float = 0.7
#: Eq. F7-12 coefficient 0.13.
_EQ_F7_12_LP: float = 0.13
#: Eq. F7-11 / Eq. F7-13 leading 2.
_EQ_F7_11_13_LEAD: float = 2.0

#: Eq. F5-6 web term 5.7 sqrt(E/Fy) and denominator constants.
_EQ_F5_6_WEB: float = 5.7
_EQ_F5_6_DENOM_A: float = 1200.0
_EQ_F5_6_DENOM_B: float = 300.0
#: §F7.3 aw = 2 h tw/(b tf), capped at 10.
_F7_3_AW_LEAD: float = 2.0
_F7_3_AW_MAX: float = 10.0


@dataclass(frozen=True)
class F7OracleProps:
    """Plain-float rectangular-HSS section properties for the §F7 oracle.

    All values in apeSteel base units (N-mm-tonne-s): ``Fy``/``E`` in
    MPa, lengths in mm, ``Z``/``S`` in mm^3, ``I`` in mm^4, ``Ag`` in
    mm^2, ``J`` in mm^4.  ``B``/``H`` are the overall outer dimensions
    and ``t`` the uniform wall thickness; the flat-wall clear widths are
    ``B - 2t`` and ``H - 2t`` (AISC welded-box convention).

    ``Z``/``S``/``I``/``r`` are the values *for the requested bending
    axis* (the golden test passes the axis-correct ones), so the oracle
    re-derives only the §F7 strength composition.
    """

    Fy: float
    E: float
    B: float  # overall width (mm)
    H: float  # overall depth (mm)
    t: float  # wall thickness (mm)
    Z: float  # plastic modulus about the bending axis (mm^3)
    S: float  # elastic modulus about the bending axis (mm^3)
    I_axis: float  # second moment about the bending axis (mm^4)
    ry_minor: float  # MINOR-axis radius of gyration (Eq. F7-11/12/13) (mm)
    Ag: float  # gross area (mm^2)
    J: float  # St-Venant torsion constant (mm^4)
    bending_axis: str  # "major" | "minor"
    section_depth: float  # H for major-axis, B for minor-axis (mm)
    flange_flat: float  # compression-flange flat width for this axis (mm)
    web_flat: float  # web flat depth for this axis (mm)
    Lb: float | None = None  # unbraced length (mm); None -> LTB not evaluated
    Cb: float = 1.0
    is_box: bool = False  # True -> Eq. F7-5 (box) instead of Eq. F7-4 (HSS)


@dataclass(frozen=True)
class F7OracleResult:
    """Oracle §F7 outcome."""

    Mn: float
    governing: str  # yielding|flange_local_buckling|web_local_buckling|lateral_torsional_buckling
    Mp: float
    flange_class: str  # compact|non_compact|slender
    web_class: str  # compact|non_compact|slender
    Se: float  # Eq. F7-3 effective modulus (0.0 unless slender flange)
    Mn_flb: float
    Mn_wlb: float
    Mn_ltb: float
    Lp: float
    Lr: float
    ltb_applies: bool


def _classify(lam: float, lam_p: float, lam_r: float) -> str:
    if lam <= lam_p:
        return "compact"
    if lam <= lam_r:
        return "non_compact"
    return "slender"


def _interp(Mp: float, Fy_S: float, lam: float, lam_p: float, lam_r: float) -> float:
    """Eq. F7-2 / Eq. F7-6 noncompact interpolation, capped at Mp."""
    return min(Mp - (Mp - Fy_S) * (lam - lam_p) / (lam_r - lam_p), Mp)


def _flb(
    p: F7OracleProps, flange_class: str, flange_lambda: float, Mp: float, sqrt_E_Fy: float
) -> tuple[float, float]:
    """§F7.2 flange-local-buckling ``Mn`` + ``Se`` (Eq. F7-2 / F7-3..F7-5)."""
    if flange_class == "compact":
        return Mp, 0.0  # §F7.2(a): does not apply
    lpf = _B4_1B_HSS_FLANGE_LAMBDA_P_COEFF * sqrt_E_Fy
    lrf = _B4_1B_HSS_FLANGE_LAMBDA_R_COEFF * sqrt_E_Fy
    if flange_class == "non_compact":
        return _interp(Mp, p.Fy * p.S, flange_lambda, lpf, lrf), 0.0  # Eq. F7-2
    # Eq. F7-3: Mn = Fy*Se; be per Eq. F7-4 (HSS) / F7-5 (box).
    inner = _EQ_F7_5_BOX_INNER if p.is_box else _EQ_F7_4_HSS_INNER
    b_t = p.flange_flat / p.t
    be_raw = _EQ_F7_4_5_LEAD * p.t * sqrt_E_Fy * (1.0 - inner / b_t * sqrt_E_Fy)
    be = min(be_raw, p.flange_flat)
    # Conservative symmetric-removal Se (AISC Manual v15.1 Ex. F.8B):
    # remove the ineffective width from both flanges (no NA shift).
    ineffective = p.flange_flat - be
    if ineffective <= 0.0:
        Se = p.I_axis / (p.section_depth / 2.0)
    else:
        arm = (p.section_depth - p.t) / 2.0
        I_removed = 2.0 * (ineffective * p.t**3 / 12.0 + ineffective * p.t * arm**2)
        Se = (p.I_axis - I_removed) / (p.section_depth / 2.0)
    return p.Fy * Se, Se


def _wlb(p: F7OracleProps, web_class: str, web_lambda: float, Mp: float, sqrt_E_Fy: float) -> float:
    """§F7.3 web-local-buckling ``Mn`` (Eq. F7-6 / Eq. F7-7)."""
    if web_class == "compact":
        return Mp  # §F7.3(a): does not apply
    lpw = _B4_1B_HSS_WEB_LAMBDA_P_COEFF * sqrt_E_Fy
    lrw = _B4_1B_HSS_WEB_LAMBDA_R_COEFF * sqrt_E_Fy
    if web_class == "non_compact":
        return _interp(Mp, p.Fy * p.S, web_lambda, lpw, lrw)  # Eq. F7-6
    # Eq. F7-7: Mn = Rpg*Fy*S, Rpg per Eq. F5-6, aw = 2 h tw/(b tf).
    aw = min(_F7_3_AW_LEAD * (p.web_flat * p.t) / (p.flange_flat * p.t), _F7_3_AW_MAX)
    rpg_term = (aw / (_EQ_F5_6_DENOM_A + _EQ_F5_6_DENOM_B * aw)) * (
        web_lambda - _EQ_F5_6_WEB * sqrt_E_Fy
    )
    rpg = min(1.0 - rpg_term, 1.0)
    return rpg * p.Fy * p.S


def _ltb(p: F7OracleProps, Mp: float) -> tuple[float, float, float, bool]:
    """§F7.4 LTB ``(Mn, Lp, Lr, ltb_applies)`` (Eq. F7-10..F7-13).

    §F7.4 User Note: LTB will not occur in square sections or sections
    bent about their minor axis.  "Square" <=> the two flat walls are
    identical (equal flat width at equal t <=> equal b/t) - the same
    convention-robust invariant the library uses.
    """
    is_square = math.isclose(p.flange_flat, p.web_flat, rel_tol=1e-12, abs_tol=0.0)
    if is_square or p.bending_axis == "minor" or p.Lb is None:
        return Mp, 0.0, 0.0, False
    sqrt_JAg = math.sqrt(p.J * p.Ag)
    Lp = _EQ_F7_12_LP * p.E * p.ry_minor * sqrt_JAg / Mp  # Eq. F7-12
    Lr_denom = _EQ_F7_LTB_07 * p.Fy * p.S  # 0.7 Fy Sx
    Lr = _EQ_F7_11_13_LEAD * p.E * p.ry_minor * sqrt_JAg / Lr_denom  # Eq. F7-13
    if p.Lb <= Lp:
        return Mp, Lp, Lr, False  # §F7.4(a)
    if p.Lb <= Lr:
        # Eq. F7-10 (inelastic LTB).
        bracket = Mp - (Mp - Lr_denom) * (p.Lb - Lp) / (Lr - Lp)
        return min(p.Cb * bracket, Mp), Lp, Lr, True
    # Eq. F7-11 (elastic LTB).
    mn = min(_EQ_F7_11_13_LEAD * p.E * p.Cb * sqrt_JAg / (p.Lb / p.ry_minor), Mp)
    return mn, Lp, Lr, True


def mn_F7(p: F7OracleProps) -> F7OracleResult:
    """Independent AISC 360-22 §F7 ``Mn`` for a square/rect HSS or box.

    Re-derives Eq. F7-1 / F7-2..F7-5 / F7-6..F7-7 / F7-10..F7-13 + the
    §F7.4 square/minor-axis LTB exclusion from the spec literals above,
    with **no** apeSteel import.
    """
    sqrt_E_Fy = math.sqrt(p.E / p.Fy)
    lpf = _B4_1B_HSS_FLANGE_LAMBDA_P_COEFF * sqrt_E_Fy
    lrf = _B4_1B_HSS_FLANGE_LAMBDA_R_COEFF * sqrt_E_Fy
    lpw = _B4_1B_HSS_WEB_LAMBDA_P_COEFF * sqrt_E_Fy
    lrw = _B4_1B_HSS_WEB_LAMBDA_R_COEFF * sqrt_E_Fy

    flange_lambda = p.flange_flat / p.t
    web_lambda = p.web_flat / p.t
    flange_class = _classify(flange_lambda, lpf, lrf)
    web_class = _classify(web_lambda, lpw, lrw)

    Mp = p.Fy * p.Z  # Eq. F7-1
    Mn_flb, Se = _flb(p, flange_class, flange_lambda, Mp, sqrt_E_Fy)
    Mn_wlb = _wlb(p, web_class, web_lambda, Mp, sqrt_E_Fy)
    Mn_ltb, Lp, Lr, ltb_applies = _ltb(p, Mp)

    Mn = min(Mp, Mn_flb, Mn_wlb, Mn_ltb)
    if Mn_flb < Mp and Mn == Mn_flb:
        governing = "flange_local_buckling"
    elif Mn_wlb < Mp and Mn == Mn_wlb:
        governing = "web_local_buckling"
    elif ltb_applies and Mn_ltb < Mp and Mn == Mn_ltb:
        governing = "lateral_torsional_buckling"
    else:
        governing = "yielding"

    return F7OracleResult(
        Mn=Mn,
        governing=governing,
        Mp=Mp,
        flange_class=flange_class,
        web_class=web_class,
        Se=Se,
        Mn_flb=Mn_flb,
        Mn_wlb=Mn_wlb,
        Mn_ltb=Mn_ltb,
        Lp=Lp,
        Lr=Lr,
        ltb_applies=ltb_applies,
    )


__all__ = ["F7OracleProps", "F7OracleResult", "mn_F7"]

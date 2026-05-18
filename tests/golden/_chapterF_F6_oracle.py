"""Independent AISC 360-22 §F6 (minor-axis I-shape) oracle - Phase F-4.

This is a deliberately *separate*, standalone re-derivation of AISC
360-22 §F6 nominal flexural strength for a doubly- or singly-symmetric
I-shape bent about its minor (y) axis.  It imports **only** the
standard-library ``math`` module - nothing from ``apeSteel`` and in
particular nothing from :mod:`apeSteel.flexure` (the architecture layer
rule for oracles).

Per design note 10 §6 this oracle is the **primary, bit-exact
(`rel_tol=1e-9`) regression pin** for the §F6 calculator, so its
correctness never rests on a snapshot of its own output.  Section
properties (``Zy``, ``Sy``) and the flange slenderness ``lambda``
(``= b/tf`` with ``b = bf/2`` for an I-shape) are supplied by the caller
(the golden test); only the §F6 *strength composition* (Eq. F6-1 ..
F6-4 + the Table B4.1b Case 10/11 flange-FLB regime split) is re-derived
here.

Every constant is written as a literal transcribed from the printed
spec / the Chapter-F citation source-of-truth, intentionally *not*
shared with the library, so a typo in either implementation surfaces as
a disagreement.

References
----------
AISC 360-22, Specification for Structural Steel Buildings, §F6
"I-Shaped Members and Channels Bent About Their Minor Axis",
p. 16.1-62 (transcribed from
``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` and the
Chapter-F citation source-of-truth
``docs/design_notes/_chapterF_citation_reference.md``, §F6 row):

* §F6 - no lateral-torsional-buckling limit state (minor axis).
* Eq. F6-1  ``Mn = Mp = Fy*Zy <= 1.6*Fy*Sy``      (yielding)
* §F6.2(a)  compact flange -> FLB does not apply
* Eq. F6-2  ``Mn = Mp - (Mp - 0.70 Fy Sy)
                       (lambda - lambda_pf)/(lambda_rf - lambda_pf)``
            (noncompact flange)
* Eq. F6-3  ``Mn = Fcr*Sy``                        (slender flange)
* Eq. F6-4  ``Fcr = 0.70 E/(b/tf)^2``

Table B4.1b Case 10 (rolled) / Case 11 (welded) - I-shape flange in
flexure: ``lambda_pf = 0.38 sqrt(E/Fy)``;
``lambda_rf = 1.0 sqrt(E/Fy)`` (rolled) or
``0.95 sqrt(kc E / FL)``, ``FL = 0.70 Fy``,
``kc = 4/sqrt(h/tw)`` clamped to ``[0.35, 0.76]`` (welded) -
transcribed from
``docs/design_notes/_chapterF_citation_reference.md`` Part 2 (the
*same* ``lambda_pf`` / ``lambda_rf`` §F3/§F4 use; §F6.2 says
"lambda_pf = lambda_p ... as defined in Table B4.1b").

ENGINEER-CONFIRM **F6-EC-1 - RESOLVED**: AISC 360-22 §F6 Eq. F6-4
``Fcr=0.70E/lambda^2`` and §F6.2 plateau ``0.70*Fy*Sy``, verbatim
a360-22w.pdf (orchestrator-verified, spec_chapterF.txt L1293/L1312);
360-16 used 0.69 - documented edition delta per design-note §9.  The
"0 70" in the staged extract is PyMuPDF stripping the decimal point of
"0.70" (text extraction does not transpose digits), so the coefficient
is unambiguously 0.70.  ``0.70`` is used here AND in the library, so
the bit-exact tier-1 anchor does not mask the choice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AISC 360-22 §F6 literal constants (printed 16.1-62) + Table B4.1b
# Case 10/11.  Duplicated here (NOT imported from apeSteel) on purpose.
# ---------------------------------------------------------------------------
#: Eq. F6-1 plastic-moment shape-factor cap: Mn = Fy*Zy <= 1.6*Fy*Sy.
_EQ_F6_1_CAP: float = 1.6

#: Eq. F6-2 residual term / Eq. F6-4 Fcr numerator coefficient: 0.70
#: (the §F6 elastic factor).  F6-EC-1 RESOLVED: AISC 360-22 §F6 Eq. F6-4
#: ``Fcr=0.70E/lambda^2`` and §F6.2 plateau ``0.70*Fy*Sy``, verbatim
#: a360-22w.pdf (orchestrator-verified, spec_chapterF.txt L1293/L1312);
#: 360-16 used 0.69 - documented edition delta per design-note §9.
_EQ_F6_2_F6_4_COEFF: float = 0.70

#: Table B4.1b Case 10/11 I-shape flange compact limit:
#: lambda_pf = 0.38 sqrt(E/Fy).
_B4_1B_I_FLANGE_COMPACT_COEFF: float = 0.38

#: Table B4.1b Case 10 (rolled) I-shape flange noncompact limit:
#: lambda_rf = 1.0 sqrt(E/Fy).
_B4_1B_ROLLED_I_FLANGE_NONCOMPACT_COEFF: float = 1.00

#: Table B4.1b Case 11 (welded) I-shape flange noncompact limit:
#: lambda_rf = 0.95 sqrt(kc E / FL).
_B4_1B_WELDED_I_FLANGE_NONCOMPACT_COEFF: float = 0.95

#: Welded Case 11 FL = 0.70 Fy (Eq. F4-6a residual-stress level).
_B4_1B_WELDED_I_FLANGE_FL_FRACTION_OF_FY: float = 0.70

#: Table B4.1b note [c]: kc = 4/sqrt(h/tw), clamped to [0.35, 0.76].
_KC_NUMERATOR: float = 4.0
_KC_MIN: float = 0.35
_KC_MAX: float = 0.76


@dataclass(frozen=True)
class F6OracleProps:
    """Plain-float minor-axis I-shape section properties for the oracle.

    All values in apeSteel base units (N-mm-tonne-s): ``Fy``/``E`` in
    MPa, ``Zy``/``Sy`` in mm^3, ``lambda_flange`` (= b/tf with b = bf/2
    for an I-shape) and ``web_h_tw`` dimensionless.  ``construction`` is
    ``"rolled"`` (Case 10) or ``"welded"`` (Case 11).
    """

    Fy: float
    E: float
    Zy: float  # minor-axis plastic section modulus (mm^3)
    Sy: float  # minor-axis elastic section modulus (mm^3)
    lambda_flange: float  # b/tf, b = bf/2 for an I-shape (= bf/2tf)
    web_h_tw: float = 0.0  # only for the welded Case 11 kc factor
    construction: str = "rolled"  # "rolled" (Case 10) | "welded" (Case 11)


@dataclass(frozen=True)
class F6OracleResult:
    """Oracle §F6 outcome."""

    Mn: float
    governing: str  # "yielding" | "flange_local_buckling"
    lambda_flange: float
    lambda_pf: float
    lambda_rf: float
    classification: str  # "compact" | "non_compact" | "slender"
    Mp: float  # Fy*Zy (uncapped)
    My: float  # Fy*Sy
    cap_1_6_Fy_Sy: float  # Eq. F6-1 cap
    Mn_F6_1: float  # min(Fy*Zy, 1.6*Fy*Sy) - capped plateau
    Fcr: float  # Eq. F6-4 stress (MPa); 0.0 unless slender


def _kc(web_h_tw: float) -> float:
    """Table B4.1b note [c] ``kc = 4/sqrt(h/tw)`` clamped to [0.35,0.76]."""
    if web_h_tw <= 0.0:
        # Degenerate web ratio: fall back to the lower clamp (matches the
        # shared classification helper's conservative behaviour).
        return _KC_MIN
    kc = _KC_NUMERATOR / math.sqrt(web_h_tw)
    return min(max(kc, _KC_MIN), _KC_MAX)


def mn_F6(p: F6OracleProps) -> F6OracleResult:
    """Independent AISC 360-22 §F6 ``Mn`` for a minor-axis-bent I-shape.

    Re-derives the Table B4.1b Case 10/11 flange-FLB regime split and
    Eq. F6-1 / F6-2 / F6-3 + F6-4 from the spec literals above, with
    **no** apeSteel import.  A minor-axis-bent I-shape has no LTB limit
    state, so ``Mn`` is the lower of yielding (Eq. F6-1) and flange
    local buckling.
    """
    sqrt_E_Fy = math.sqrt(p.E / p.Fy)

    # Table B4.1b Case 10/11 flange limits.
    lambda_pf = _B4_1B_I_FLANGE_COMPACT_COEFF * sqrt_E_Fy
    if p.construction == "rolled":
        lambda_rf = _B4_1B_ROLLED_I_FLANGE_NONCOMPACT_COEFF * sqrt_E_Fy
    elif p.construction == "welded":
        kc = _kc(p.web_h_tw)
        FL = _B4_1B_WELDED_I_FLANGE_FL_FRACTION_OF_FY * p.Fy
        lambda_rf = _B4_1B_WELDED_I_FLANGE_NONCOMPACT_COEFF * math.sqrt(kc * p.E / FL)
    else:  # pragma: no cover - guarded by the golden test inputs
        raise ValueError(f"unknown construction {p.construction!r}")

    # Eq. F6-1 yielding plateau (capped).
    Mp = p.Fy * p.Zy
    My = p.Fy * p.Sy
    cap = _EQ_F6_1_CAP * p.Fy * p.Sy
    Mn_F6_1 = min(Mp, cap)

    Fcr = 0.0
    if p.lambda_flange <= lambda_pf:
        classification = "compact"
        governing = "yielding"
        Mn = Mn_F6_1  # §F6.2(a): FLB does not apply
    elif p.lambda_flange <= lambda_rf:
        classification = "non_compact"
        governing = "flange_local_buckling"
        # Eq. F6-2: interpolate from the capped plateau Mn_F6_1 down to
        # 0.70*Fy*Sy.
        residual = _EQ_F6_2_F6_4_COEFF * p.Fy * p.Sy
        Mn = Mn_F6_1 - (Mn_F6_1 - residual) * (p.lambda_flange - lambda_pf) / (
            lambda_rf - lambda_pf
        )
    else:
        classification = "slender"
        governing = "flange_local_buckling"
        Fcr = _EQ_F6_2_F6_4_COEFF * p.E / p.lambda_flange**2  # Eq. F6-4
        Mn = Fcr * p.Sy  # Eq. F6-3

    return F6OracleResult(
        Mn=Mn,
        governing=governing,
        lambda_flange=p.lambda_flange,
        lambda_pf=lambda_pf,
        lambda_rf=lambda_rf,
        classification=classification,
        Mp=Mp,
        My=My,
        cap_1_6_Fy_Sy=cap,
        Mn_F6_1=Mn_F6_1,
        Fcr=Fcr,
    )


__all__ = ["F6OracleProps", "F6OracleResult", "mn_F6"]

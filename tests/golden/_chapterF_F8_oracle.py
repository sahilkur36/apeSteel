"""Independent AISC 360-22 §F8 (round HSS / Pipe) oracle - Phase F-2.

This is a deliberately *separate*, standalone re-derivation of AISC
360-22 §F8 nominal flexural strength.  It imports **only** the
standard-library ``math`` module - nothing from ``apeSteel`` and in
particular nothing from :mod:`apeSteel.flexure`.

It is kept distinct from the shared
:mod:`tests.golden._chapterF_full_aisc_oracle` on purpose: that shared
scaffold has a Phase-F-2 ``mn_F8`` *stub* (``raise
NotImplementedError("Phase F-2")``); per the F-2 contract that stub is
**left untouched** here to avoid a cross-phase merge seam, and §F8 is
re-derived in this self-contained module instead.  (Note for the
orchestrator: ``_chapterF_full_aisc_oracle.mn_F8`` remains the
unmodified F-0 stub; wiring it is out of F-2 scope.)

Per design note 10 §6 this oracle is the **primary, bit-exact
(`rel_tol=1e-9`) regression pin** for the §F8 calculator, so its
correctness never rests on a snapshot of its own output.  Section
properties are supplied by the caller (the golden test); only the §F8
*strength composition* (Eq. F8-1 .. F8-4 + the Table B4.1b Case 20
regime split) is re-derived here.

Every constant is written as a literal transcribed from the printed
spec, intentionally *not* shared with the library, so a typo in either
implementation surfaces as a disagreement.

References
----------
AISC 360-22, Specification for Structural Steel Buildings, §F8
"Round HSS", p. 16.1-65:

* §F8 lead paragraph - applicability ``D/t < 0.45 E/Fy``.
* Eq. F8-1  ``Mn = Mp = Fy*Z``                (compact wall)
* Eq. F8-2  ``Mn = (0.021 E/(D/t) + Fy) * S`` (noncompact wall)
* Eq. F8-3  ``Mn = Fcr * S``                  (slender wall)
* Eq. F8-4  ``Fcr = 0.33 E/(D/t)``

Table B4.1b Case 20 (round HSS, flexure): ``lambda_p = 0.07 E/Fy``,
``lambda_r = 0.31 E/Fy`` (ratios of ``E/Fy``, NOT ``sqrt(E/Fy)``) -
CONFIRMED as Case 20 from AISC Manual v15.1 Ex. F.9B; transcribed from
``docs/design_notes/_aisc_src_extract/skill_reference_chapterF.md`` and
``_chapterF_citation_reference.md`` (§F8 row / EC-3).
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AISC 360-22 §F8 literal constants (printed 16.1-65) + Table B4.1b
# Case 20.  Duplicated here (NOT imported from apeSteel) on purpose.
# ---------------------------------------------------------------------------
#: §F8 lead paragraph: §F8 applies to round HSS with D/t < 0.45 E/Fy.
_F8_APPLICABILITY_D_T_COEFF: float = 0.45

#: Table B4.1b Case 20 compact limit: lambda_p = 0.07 * (E/Fy).
_B4_1B_CASE20_LAMBDA_P_COEFF: float = 0.07

#: Table B4.1b Case 20 noncompact limit: lambda_r = 0.31 * (E/Fy).
_B4_1B_CASE20_LAMBDA_R_COEFF: float = 0.31

#: Eq. F8-2 noncompact coefficient: Mn = (0.021 E/(D/t) + Fy) * S.
_EQ_F8_2_COEFF: float = 0.021

#: Eq. F8-4 slender Fcr coefficient: Fcr = 0.33 E/(D/t).
_EQ_F8_4_COEFF: float = 0.33


@dataclass(frozen=True)
class F8OracleProps:
    """Plain-float round-HSS section properties for the §F8 oracle.

    All values in apeSteel base units (N-mm-tonne-s): ``Fy``/``E`` in
    MPa, ``D``/``t`` in mm, ``Z``/``S`` in mm^3.
    """

    Fy: float
    E: float
    D: float
    t: float
    Z: float  # plastic section modulus (mm^3)
    S: float  # elastic section modulus (mm^3)


@dataclass(frozen=True)
class F8OracleResult:
    """Oracle §F8 outcome."""

    Mn: float
    governing: str  # "yielding" | "flange_local_buckling"
    D_t: float
    lambda_p: float
    lambda_r: float
    classification: str  # "compact" | "non_compact" | "slender"
    Fcr: float  # Eq. F8-4 stress (MPa); 0.0 unless slender


def mn_F8(p: F8OracleProps) -> F8OracleResult:
    """Independent AISC 360-22 §F8 ``Mn`` for a round HSS / Pipe.

    Re-derives the regime split and Eq. F8-1 / F8-2 / F8-3 + F8-4 from
    the spec literals above, with **no** apeSteel import.  Raises
    :class:`ValueError` if ``D/t`` is at or beyond the §F8
    applicability bound ``0.45 E/Fy`` (mirrors the library, so the
    "outside §F8" path is anchored too).
    """
    D_t = p.D / p.t
    ratio_E_Fy = p.E / p.Fy

    # §F8 lead paragraph applicability: D/t < 0.45 E/Fy.
    if D_t >= _F8_APPLICABILITY_D_T_COEFF * ratio_E_Fy:
        raise ValueError("D/t outside AISC 360-22 §F8 applicability (0.45 E/Fy)")

    # Table B4.1b Case 20 (round HSS, flexure) - ratios of E/Fy.
    lambda_p = _B4_1B_CASE20_LAMBDA_P_COEFF * ratio_E_Fy
    lambda_r = _B4_1B_CASE20_LAMBDA_R_COEFF * ratio_E_Fy

    Mp = p.Fy * p.Z  # Eq. F8-1
    Fcr = 0.0

    if D_t <= lambda_p:
        classification = "compact"
        governing = "yielding"
        Mn = Mp  # Eq. F8-1
    elif D_t <= lambda_r:
        classification = "non_compact"
        governing = "flange_local_buckling"
        # Eq. F8-2
        Mn = (_EQ_F8_2_COEFF * p.E / D_t + p.Fy) * p.S
    else:
        classification = "slender"
        governing = "flange_local_buckling"
        Fcr = _EQ_F8_4_COEFF * p.E / D_t  # Eq. F8-4
        Mn = Fcr * p.S  # Eq. F8-3

    return F8OracleResult(
        Mn=Mn,
        governing=governing,
        D_t=D_t,
        lambda_p=lambda_p,
        lambda_r=lambda_r,
        classification=classification,
        Fcr=Fcr,
    )


__all__ = ["F8OracleProps", "F8OracleResult", "mn_F8"]

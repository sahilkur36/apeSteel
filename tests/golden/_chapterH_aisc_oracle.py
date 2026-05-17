"""Independent AISC 360-22 Chapter-H oracle.

A deliberately *separate* implementation of AISC 360-22 Chapter H
(design of members for combined forces and torsion): §H1.1, §H1.2,
§H1.3, §H2, §H3.1, §H3.2 and §H3.3.  Imports **only** the standard-
library ``math`` - nothing from :mod:`apeSteel.combined`.

Provenance standard (same as the Chapter-E / Chapter-F oracles)
---------------------------------------------------------------
Chapter H is an *interaction* chapter: it composes available strengths
that Chapters D/E/F/G already produced.  Following the established
standard, the *available strengths* ``Pc``/``Mc``/``Vc``/``Tc`` (already
phi-reduced by the upstream chapters) are supplied by the caller; only
the Chapter-H *interaction composition* is re-derived here.

The one genuine Chapter-H *strength* with no upstream source is the HSS
torsional critical stress ``Fcr`` of §H3.1 (Eq. H3-2a/2b for round,
Eq. H3-3..H3-5 for rectangular).  That is re-derived here from first
principles - it is not "consumed" from any other chapter.

Open-section (non-HSS) warping-stress evaluation per Design Guide 9 is
**out of scope** (documented in ``docs/design_notes/09_combined_H.md``);
§H3.3 here only re-derives the code-level limiting stresses ``Fn`` and a
caller-supplied stress-ratio check.

Every equation carries its AISC 360-22 citation in a comment.  The
constants are written as literals from the printed spec, intentionally
*not* shared with the library, so a typo in either implementation
surfaces as a disagreement.

References
----------
AISC 360-22, Specification for Structural Steel Buildings, Chapter H
"Design of Members for Combined Forces and Torsion", pp. 16.1-83 -
16.1-88:

  * §H1.1  Eq. H1-1a, H1-1b.
  * §H1.2  Cb amplification sqrt(1 + alpha*Pr/Pey).
  * §H1.3  Eq. H1-1 (in-plane) + Eq. H1-2 (out-of-plane).
  * §H2    Eq. H2-1.
  * §H3.1  Eq. H3-1, H3-2a, H3-2b, H3-3, H3-4, H3-5.
  * §H3.2  Eq. H3-6.
  * §H3.3  Eq. H3-7, H3-8, H3-9.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OracleInteraction:
    """A single combined-force unity check."""

    dcr: float
    equation: str
    passes: bool


@dataclass(frozen=True)
class OracleTorsion:
    """An §H3.1 HSS torsional strength."""

    Fcr: float
    C: float
    Tn: float
    governing: str


# ---------------------------------------------------------------------------
# §H1.1 - doubly / singly symmetric members, flexure + axial (Eq. H1-1a/1b)
# ---------------------------------------------------------------------------
def interaction_H1_1(
    Pr: float,
    Pc: float,
    Mrx: float,
    Mcx: float,
    Mry: float = 0.0,
    Mcy: float = 0.0,
) -> OracleInteraction:
    """AISC 360-22 §H1.1 - Eq. H1-1a / H1-1b.

    ``Pc`` is the available axial strength (phi_c*Pn for compression,
    phi_t*Pn for the §H1.2 tension case); ``Mcx``/``Mcy`` are the
    available flexural strengths (phi_b*Mn).  ``Pr``/``Mr`` are the
    required second-order strengths.
    """
    if Pc <= 0.0:
        raise ValueError("Pc must be positive")
    if Mrx != 0.0 and Mcx <= 0.0:
        raise ValueError("Mcx must be positive when Mrx is non-zero")
    if Mry != 0.0 and Mcy <= 0.0:
        raise ValueError("Mcy must be positive when Mry is non-zero")
    ratio_p = Pr / Pc
    moment_ratio = (Mrx / Mcx if Mrx != 0.0 else 0.0) + (Mry / Mcy if Mry != 0.0 else 0.0)
    if ratio_p >= 0.2:  # Eq. H1-1a
        dcr = ratio_p + (8.0 / 9.0) * moment_ratio
        eq = "H1-1a"
    else:  # Eq. H1-1b
        dcr = ratio_p / 2.0 + moment_ratio
        eq = "H1-1b"
    return OracleInteraction(dcr=dcr, equation=eq, passes=dcr <= 1.0)


# ---------------------------------------------------------------------------
# §H1.2 - flexure + axial tension: Cb amplification
# ---------------------------------------------------------------------------
def Pey_H1_2(E: float, Iy: float, Lb: float) -> float:
    """Out-of-plane Euler load ``Pey = pi^2 E Iy / Lb^2`` (§H1.2)."""
    if Lb <= 0.0:
        raise ValueError("Lb must be positive")
    return math.pi**2 * E * Iy / Lb**2


def cb_amplification_H1_2(Pr_tension: float, Pey: float, alpha: float = 1.0) -> float:
    """AISC 360-22 §H1.2 - ``Cb`` amplifier ``sqrt(1 + alpha*Pr/Pey)``.

    For doubly-symmetric members with axial *tension* concurrent with
    bending, ``Cb`` may be multiplied by this factor (alpha = 1.0 LRFD,
    1.6 ASD).  ``Pr_tension`` is the required tensile strength (>= 0).
    """
    if Pey <= 0.0:
        raise ValueError("Pey must be positive")
    if Pr_tension < 0.0:
        raise ValueError("Pr_tension (tension) must be >= 0")
    return math.sqrt(1.0 + alpha * Pr_tension / Pey)


# ---------------------------------------------------------------------------
# §H1.3 - doubly-symmetric rolled compact, single-axis flexure + compression
# ---------------------------------------------------------------------------
def interaction_H1_3_in_plane(
    Pr: float,
    Pc_in_plane: float,
    Mrx: float,
    Mcx_in_plane: float,
) -> OracleInteraction:
    """§H1.3(a) in-plane instability - Eq. H1-1 with in-plane Pc, Mcx.

    ``Pc_in_plane`` uses the in-plane (axis-of-bending) effective
    length; ``Mcx_in_plane`` is the available flexural strength with no
    LTB reduction (it may reach phi_b*Mp).
    """
    return interaction_H1_1(Pr, Pc_in_plane, Mrx, Mcx_in_plane, 0.0, 0.0)


def interaction_H1_3_out_of_plane(
    Pr: float,
    Pcy: float,
    Mrx: float,
    Cb: float,
    Mcx_ltb_cb1: float,
    phi_b_Mp: float,
) -> OracleInteraction:
    """§H1.3(b) out-of-plane / LTB - Eq. H1-2.

    ``Pr/Pcy*(1.5 - 0.5*Pr/Pcy) + (Mrx/(Cb*Mcx))^2 <= 1.0``

    ``Pcy`` = available compressive strength out of the plane of
    bending.  ``Mcx_ltb_cb1`` = available LTB strength for strong-axis
    flexure with Cb = 1.0.  ``Cb*Mcx`` is capped at ``phi_b*Mp``
    (the amplified term need not exceed the plastic strength).
    """
    if Pcy <= 0.0:
        raise ValueError("Pcy must be positive")
    cb_mcx = min(Cb * Mcx_ltb_cb1, phi_b_Mp)
    if cb_mcx <= 0.0:
        raise ValueError("Cb*Mcx must be positive")
    rp = Pr / Pcy
    dcr = rp * (1.5 - 0.5 * rp) + (Mrx / cb_mcx) ** 2  # Eq. H1-2
    return OracleInteraction(dcr=dcr, equation="H1-2", passes=dcr <= 1.0)


# ---------------------------------------------------------------------------
# §H2 - unsymmetric and other members, flexure + axial (Eq. H2-1)
# ---------------------------------------------------------------------------
def interaction_H2(
    fra: float,
    Fca: float,
    frbw: float,
    Fcbw: float,
    frbz: float,
    Fcbz: float,
) -> OracleInteraction:
    """AISC 360-22 §H2 - Eq. H2-1 elastic stress interaction.

    ``|fra/Fca + frbw/Fcbw + frbz/Fcbz| <= 1.0`` - evaluated at the
    point of consideration with the *signs* of the required stresses
    taken into account (the caller passes signed required stresses and
    positive available stresses).
    """
    for name, val in (("Fca", Fca), ("Fcbw", Fcbw), ("Fcbz", Fcbz)):
        if val <= 0.0:
            raise ValueError(f"{name} (available stress) must be positive")
    dcr = abs(fra / Fca + frbw / Fcbw + frbz / Fcbz)  # Eq. H2-1
    return OracleInteraction(dcr=dcr, equation="H2-1", passes=dcr <= 1.0)


# ---------------------------------------------------------------------------
# §H3.1 - round and rectangular HSS subject to torsion (Eq. H3-1..H3-5)
# ---------------------------------------------------------------------------
def torsion_round_HSS_H3_1(
    Fy: float,
    E: float,
    D: float,
    t: float,
    L: float,
) -> OracleTorsion:
    """AISC 360-22 §H3.1(a) - round HSS torsional strength.

    ``C = pi*(D - t)^2 * t / 2`` ; ``Tn = Fcr*C`` (Eq. H3-1).
    ``Fcr`` = larger of Eq. H3-2a / Eq. H3-2b, but <= 0.6*Fy.
    """
    dt = D / t
    fcr_2a = 1.23 * E / (math.sqrt(L / D) * dt**1.25)  # Eq. H3-2a
    fcr_2b = 0.60 * E / dt**1.5  # Eq. H3-2b
    fcr_buckling = max(fcr_2a, fcr_2b)
    cap = 0.6 * Fy
    if fcr_buckling >= cap:
        fcr = cap
        gov = "shear_yielding_0p6Fy"
    elif fcr_2a >= fcr_2b:
        fcr = fcr_2a
        gov = "H3-2a"
    else:
        fcr = fcr_2b
        gov = "H3-2b"
    c_const = math.pi * (D - t) ** 2 * t / 2.0
    return OracleTorsion(Fcr=fcr, C=c_const, Tn=fcr * c_const, governing=gov)


def torsion_rect_HSS_H3_1(
    Fy: float,
    E: float,
    h_over_t: float,
    C: float,
) -> OracleTorsion:
    """AISC 360-22 §H3.1(b) - rectangular HSS torsional strength.

    ``h_over_t`` is the larger flat-wall width-to-thickness ratio; ``C``
    is the HSS torsional constant (supplied - it is a tabulated section
    property, not a Chapter-H quantity).  ``Tn = Fcr*C`` (Eq. H3-1).
    """
    s = math.sqrt(E / Fy)
    lim_1 = 2.45 * s
    lim_2 = 3.07 * s
    if h_over_t <= lim_1:
        fcr = 0.6 * Fy  # §H3.1(b)(i)
        gov = "shear_yielding_0p6Fy"
    elif h_over_t <= lim_2:
        fcr = 0.6 * Fy * lim_1 / h_over_t  # Eq. H3-4
        gov = "H3-4"
    elif h_over_t <= 260.0:
        fcr = 0.458 * math.pi**2 * E / h_over_t**2  # Eq. H3-5
        gov = "H3-5"
    else:
        raise ValueError("rectangular HSS h/t over 260 - outside §H3.1 scope")
    return OracleTorsion(Fcr=fcr, C=C, Tn=fcr * C, governing=gov)


# ---------------------------------------------------------------------------
# §H3.2 - HSS combined torsion, shear, flexure, axial (Eq. H3-6)
# ---------------------------------------------------------------------------
def interaction_H3_2(
    Pr: float,
    Pc: float,
    Mr: float,
    Mc: float,
    Vr: float,
    Vc: float,
    Tr: float,
    Tc: float,
) -> tuple[OracleInteraction | None, bool]:
    """AISC 360-22 §H3.2 - Eq. H3-6 for HSS under combined effects.

    Returns ``(result, torsion_negligible)``.  When ``Tr <= 0.2*Tc``
    torsion is permitted to be neglected (the member is then checked by
    §H1); the result is ``None`` and the flag is ``True``.  Otherwise
    Eq. H3-6 ``(Pr/Pc + Mr/Mc) + (Vr/Vc + Tr/Tc)^2 <= 1.0``.
    """
    for name, val in (("Pc", Pc), ("Mc", Mc), ("Vc", Vc), ("Tc", Tc)):
        if val <= 0.0:
            raise ValueError(f"{name} (available strength) must be positive")
    if Tr <= 0.2 * Tc:  # §H3.2 - torsion may be neglected
        return None, True
    dcr = (Pr / Pc + Mr / Mc) + (Vr / Vc + Tr / Tc) ** 2  # Eq. H3-6
    return OracleInteraction(dcr=dcr, equation="H3-6", passes=dcr <= 1.0), False


# ---------------------------------------------------------------------------
# §H3.3 - non-HSS members subject to torsion (Eq. H3-7/8/9 limiting Fn)
# ---------------------------------------------------------------------------
def nonHSS_limiting_Fn_H3_3(
    Fy: float,
    Fcr: float | None = None,
) -> tuple[float, float, float | None, float, str]:
    """AISC 360-22 §H3.3 - the three limiting nominal stresses ``Fn``.

    Returns ``(Fn_yield, Fn_shear, Fn_buckling, Fn_governing, label)``:

      * Eq. H3-7 yielding under normal stress: ``Fn = Fy``
      * Eq. H3-8 shear yielding under shear stress: ``Fn = 0.6*Fy``
      * Eq. H3-9 buckling: ``Fn = Fcr`` (``None`` -> not evaluated)

    The actual warping / St-Venant stress demands require Design Guide 9
    and are intentionally out of scope here; this only re-derives the
    code-level limiting stresses.
    """
    fn_yield = Fy  # Eq. H3-7
    fn_shear = 0.6 * Fy  # Eq. H3-8
    candidates: list[tuple[float, str]] = [(fn_yield, "H3-7"), (fn_shear, "H3-8")]
    if Fcr is not None:  # Eq. H3-9
        candidates.append((Fcr, "H3-9"))
    fn_gov, label = min(candidates, key=lambda kv: kv[0])
    return fn_yield, fn_shear, Fcr, fn_gov, label

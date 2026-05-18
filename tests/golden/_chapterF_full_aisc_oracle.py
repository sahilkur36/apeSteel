"""Independent AISC 360-22 *full* Chapter-F oracle (F-0 scaffold).

This module is a deliberately *separate* implementation of AISC 360-22
Chapter F for the **whole** chapter (§F2-§F12 + Table B4.1b), extending
the I-only :mod:`tests.golden._chapterF_aisc_oracle` to every section
family. It imports **only** the standard-library ``math`` module - no
``apeSteel``, and in particular nothing from :mod:`apeSteel.flexure`.

Its purpose, per design note 10 §6, is to be the *primary, bit-exact
regression pin* for the generalized classifier and (in later phases) the
per-section ``Mn`` calculators, so their correctness never rests on a
snapshot of their own output.

Status (Phase F-0)
------------------
* **Implemented now:** the generalized Table B4.1b ``lambda_p`` /
  ``lambda_r`` oracle per :data:`section_kind`
  (:func:`oracle_lambda_limits`). This independently anchors the
  generalized classifier created in F-0.
* **Stubs (raise NotImplementedError):** the per-section nominal
  flexural strength oracles ``mn_F6 / mn_F7 / mn_F8 / mn_F9 / mn_F10 /
  mn_F11 / mn_F12``. Phases F-2 … F-7 fill these in (the existing
  ``_chapterF_aisc_oracle.py`` already covers F2/F3/F4/F5 bit-exactly
  and is unchanged).

Every constant is written as a literal from the printed spec /
``docs/design_notes/_chapterF_citation_reference.md``, intentionally
*not* shared with the library, so a typo in either implementation
surfaces as a disagreement.

References
----------
AISC 360-22, Specification for Structural Steel Buildings:
  * Table B4.1b (Cases 10/11 flange, 15/16 web, ~17/19 HSS, 20 round
    HSS) + §F9.4 / §F10.3 stem / leg breakpoints.
  * §F6 Eq. F6-1..F6-4   (minor-axis I & channel)
  * §F7 Eq. F7-1..F7-13  (square / rectangular HSS & box)
  * §F8 Eq. F8-1..F8-4   (round HSS / pipe)
  * §F9 Eq. F9-1..F9-19  (tees & double angles)
  * §F10 Eq. F10-1..F10-8 (single angles)
  * §F11 Eq. F11-1..F11-5 (rectangular bars & rounds)
  * §F12 Eq. F12-1..F12-4 (unsymmetrical shapes)
See ``docs/design_notes/_chapterF_citation_reference.md`` for
per-equation provenance and the ENGINEER-CONFIRM list.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Table B4.1b flexure lambda_p / lambda_r oracle (independent re-derivation)
#
# Coefficients transcribed from _chapterF_citation_reference.md Part 2.
# These are duplicated here (NOT imported from apeSteel) on purpose.
# ---------------------------------------------------------------------------


def _kc(h_tw: float) -> float:
    """Table B4.1b note [c]: kc = 4/sqrt(h/tw), 0.35 <= kc <= 0.76."""
    return min(0.76, max(0.35, 4.0 / math.sqrt(h_tw)))


@dataclass(frozen=True)
class LambdaLimits:
    """Oracle Table B4.1b limits for one plate element."""

    lambda_p: float
    lambda_r: float
    classification: str  # "compact" | "non_compact" | "slender"


def _classify(lam: float, lam_p: float, lam_r: float) -> str:
    if lam <= lam_p:
        return "compact"
    if lam <= lam_r:
        return "non_compact"
    return "slender"


def oracle_i_channel_flange(
    lam_f: float,
    Fy: float,
    E: float,
    *,
    construction: str,
    h_tw: float,
) -> LambdaLimits:
    """Table B4.1b Case 10 (rolled) / Case 11 (welded) - I/channel flange.

    ``lambda_pf = 0.38 sqrt(E/Fy)``; Case 10
    ``lambda_rf = 1.0 sqrt(E/Fy)``; Case 11
    ``lambda_rf = 0.95 sqrt(kc E / (0.7 Fy))``.
    """
    s = math.sqrt(E / Fy)
    lam_p = 0.38 * s
    if construction == "rolled":
        lam_r = 1.00 * s
    elif construction == "welded":
        lam_r = 0.95 * math.sqrt(_kc(h_tw) * E / (0.7 * Fy))
    else:  # pragma: no cover - test inputs are controlled
        raise ValueError(construction)
    return LambdaLimits(lam_p, lam_r, _classify(lam_f, lam_p, lam_r))


def oracle_ds_web(lam_w: float, Fy: float, E: float) -> LambdaLimits:
    """Table B4.1b Case 15 - doubly-symmetric I/channel web.

    ``lambda_pw = 3.76 sqrt(E/Fy)``, ``lambda_rw = 5.70 sqrt(E/Fy)``.
    """
    s = math.sqrt(E / Fy)
    lam_p, lam_r = 3.76 * s, 5.70 * s
    return LambdaLimits(lam_p, lam_r, _classify(lam_w, lam_p, lam_r))


def oracle_ss_web_case16(
    lam_w: float,
    hc: float,
    hp: float,
    Mp: float,
    My: float,
    Fy: float,
    E: float,
) -> LambdaLimits:
    """Table B4.1b Case 16 - singly-symmetric I web.

    ``lambda_pw = (hc/hp) sqrt(E/Fy) / (0.54 Mp/My - 0.09)^2 <=
    lambda_rw``, ``lambda_rw = 5.70 sqrt(E/Fy)``.
    """
    s = math.sqrt(E / Fy)
    lam_r = 5.70 * s
    den = 0.54 * (Mp / My) - 0.09
    lam_p = min((hc / hp) * s / den**2, lam_r) if den > 0.0 else lam_r
    return LambdaLimits(lam_p, lam_r, _classify(lam_w, lam_p, lam_r))


def oracle_hss_flange(lam: float, Fy: float, E: float) -> LambdaLimits:
    """Rect/sq HSS flange in flexure: lp = 1.12 sqrt(E/Fy), lr = 1.40 sqrt(E/Fy)."""
    s = math.sqrt(E / Fy)
    lam_p, lam_r = 1.12 * s, 1.40 * s
    return LambdaLimits(lam_p, lam_r, _classify(lam, lam_p, lam_r))


def oracle_hss_web(lam: float, Fy: float, E: float) -> LambdaLimits:
    """Rect/sq HSS web in flexure: lp = 2.42 sqrt(E/Fy), lr = 5.70 sqrt(E/Fy)."""
    s = math.sqrt(E / Fy)
    lam_p, lam_r = 2.42 * s, 5.70 * s
    return LambdaLimits(lam_p, lam_r, _classify(lam, lam_p, lam_r))


def oracle_round_hss(D_t: float, Fy: float, E: float) -> LambdaLimits:
    """Round HSS in flexure, Case 20: lp = 0.07 E/Fy, lr = 0.31 E/Fy.

    Note these are ratios of ``E/Fy`` (not ``sqrt(E/Fy)``).
    """
    r = E / Fy
    lam_p, lam_r = 0.07 * r, 0.31 * r
    return LambdaLimits(lam_p, lam_r, _classify(D_t, lam_p, lam_r))


def oracle_tee_stem(d_tw: float, Fy: float, E: float) -> LambdaLimits:
    """Tee stem (§F9.4 breakpoints): lp = 0.84 sqrt(E/Fy), lr = 1.52 sqrt(E/Fy)."""
    s = math.sqrt(E / Fy)
    lam_p, lam_r = 0.84 * s, 1.52 * s
    return LambdaLimits(lam_p, lam_r, _classify(d_tw, lam_p, lam_r))


def oracle_angle_leg(b_t: float, Fy: float, E: float) -> LambdaLimits:
    """Angle leg (§F10.3 breakpoints): lp = 0.54 sqrt(E/Fy), lr = 0.91 sqrt(E/Fy)."""
    s = math.sqrt(E / Fy)
    lam_p, lam_r = 0.54 * s, 0.91 * s
    return LambdaLimits(lam_p, lam_r, _classify(b_t, lam_p, lam_r))


def oracle_lambda_limits(
    section_kind: str,
    Fy: float,
    E: float,
    *,
    construction: str = "welded",
    flange_lam: float = 0.0,
    web_lam: float = 0.0,
    hc: float = 0.0,
    hp: float = 0.0,
    Mp: float = 0.0,
    My: float = 0.0,
    hss_flange_lam: float = 0.0,
    hss_web_lam: float = 0.0,
    round_D_t: float = 0.0,
    tee_stem_lam: float = 0.0,
    angle_leg_lam: float = 0.0,
) -> dict[str, LambdaLimits]:
    """Independent Table B4.1b oracle, dispatched by ``section_kind``.

    Returns a mapping ``element name -> LambdaLimits``. Mirrors the
    generalized
    :func:`apeSteel.classification.flexural_compactness.classify_flexural_compactness`
    dispatch so the classifier can be anchored bit-for-bit at
    ``rel_tol`` per element. Bars / unsymmetric return an empty mapping
    (no B4.1b local-buckling limit state).
    """
    out: dict[str, LambdaLimits] = {}
    if section_kind in ("doubly_symmetric_I", "singly_symmetric_I", "channel"):
        out["flange"] = oracle_i_channel_flange(
            flange_lam, Fy, E, construction=construction, h_tw=web_lam
        )
        if section_kind == "singly_symmetric_I" and hp > 0.0:
            out["web"] = oracle_ss_web_case16(web_lam, hc, hp, Mp, My, Fy, E)
        else:
            out["web"] = oracle_ds_web(web_lam, Fy, E)
    elif section_kind == "rectangular_HSS":
        out["flange"] = oracle_hss_flange(hss_flange_lam, Fy, E)
        out["web"] = oracle_hss_web(hss_web_lam, Fy, E)
    elif section_kind == "round_HSS":
        out["wall"] = oracle_round_hss(round_D_t, Fy, E)
    elif section_kind == "tee":
        out["flange"] = oracle_i_channel_flange(
            flange_lam, Fy, E, construction="rolled", h_tw=web_lam or 1.0
        )
        out["stem"] = oracle_tee_stem(tee_stem_lam, Fy, E)
    elif section_kind in ("single_angle", "double_angle"):
        out["leg"] = oracle_angle_leg(angle_leg_lam, Fy, E)
    elif section_kind in ("rectangular_bar", "round_bar", "unsymmetric"):
        pass
    else:  # pragma: no cover - controlled test inputs
        raise ValueError(section_kind)
    return out


# ---------------------------------------------------------------------------
# Per-section Mn oracle properties + result type (filled by F-2 .. F-7)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FullOracleProps:
    """Plain-float section properties for the full-chapter Mn oracles.

    Phases F-2 … F-7 extend / consume this. Only the fields a given §F
    section needs are populated by that phase's golden test; the rest
    stay at their defaults. All values are in apeSteel base units
    (N-mm-tonne-s).
    """

    Fy: float
    E: float
    # gross / both axes
    Sx: float = 0.0
    Zx: float = 0.0
    Sy: float = 0.0
    Zy: float = 0.0
    Ag: float = 0.0
    d: float = 0.0
    # LTB constants
    ry: float = 0.0
    rts: float = 0.0
    ho: float = 0.0
    J: float = 0.0
    Iy: float = 0.0
    Cw: float = 0.0
    # slenderness ratios
    lam_f: float = 0.0  # flange bf/2tf
    lam_w: float = 0.0  # web h/tw (or hc/tw for SS)
    hss_lam_f: float = 0.0  # HSS flat-width b/t
    hss_lam_w: float = 0.0  # HSS flat-width h/t
    D_t: float = 0.0  # round HSS / pipe
    d_tw: float = 0.0  # tee stem
    b_t: float = 0.0  # angle leg
    # SS / tee
    Sxc: float = 0.0
    Sxt: float = 0.0
    hc: float = 0.0
    hp: float = 0.0
    bfc: float = 0.0
    tfc: float = 0.0
    # round HSS / pipe
    diameter_D: float = 0.0
    wall_t: float = 0.0
    # single angle principal axes
    Iw: float = 0.0
    Iz: float = 0.0
    rz: float = 0.0
    Sc: float = 0.0  # elastic modulus to the toe in compression
    equal_leg: bool = True
    geometric_axis: bool = False
    # §F11 rectangular bar
    bar_b: float = 0.0
    bar_t: float = 0.0
    # §F12 unsymmetric
    Smin: float = 0.0


@dataclass(frozen=True)
class FullOracleResult:
    Mn: float
    governing: str


def mn_F6(p: FullOracleProps, Lb: float, Cb: float, construction: str) -> FullOracleResult:
    """AISC 360-22 §F6 - I-shapes & channels, minor axis. **Phase F-4.**"""
    raise NotImplementedError("Phase F-4")


def mn_F7(p: FullOracleProps, Lb: float, Cb: float) -> FullOracleResult:
    """AISC 360-22 §F7 - square / rectangular HSS & box. **Phase F-3.**"""
    raise NotImplementedError("Phase F-3")


def mn_F8(p: FullOracleProps) -> FullOracleResult:
    """AISC 360-22 §F8 - round HSS / pipe (no LTB). **Phase F-2.**"""
    raise NotImplementedError("Phase F-2")


def mn_F9(p: FullOracleProps, Lb: float, Cb: float, stem_in_compression: bool) -> FullOracleResult:
    """AISC 360-22 §F9 - tees & double angles in plane of symmetry. **Phase F-5.**"""
    raise NotImplementedError("Phase F-5")


def mn_F10(p: FullOracleProps, Lb: float, Cb: float) -> FullOracleResult:
    """AISC 360-22 §F10 - single angles. **Phase F-6.**"""
    raise NotImplementedError("Phase F-6")


def mn_F11(p: FullOracleProps, Lb: float, Cb: float, is_round: bool) -> FullOracleResult:
    """AISC 360-22 §F11 - rectangular bars & rounds. **Phase F-7.**"""
    raise NotImplementedError("Phase F-7")


def mn_F12(p: FullOracleProps, Fcr_ltb: float, Fcr_lb: float) -> FullOracleResult:
    """AISC 360-22 §F12 - unsymmetrical shapes (elastic Fn*Smin). **Phase F-7.**"""
    raise NotImplementedError("Phase F-7")

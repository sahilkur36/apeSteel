"""AISC 360-22 §F11 (rectangular bars & rounds) + §F12 (unsymmetrical).

Two pure calculators close Chapter F:

``compute_flexural_strength_F11_bar``
    §F11 "Rectangular Bars and Rounds" (spec_chapterF.txt printed
    16.1-71).  Lower of yielding (plastic moment) and, for a
    rectangular bar bent about its major axis, lateral-torsional
    buckling:

    * **Yielding** - rectangular bar Eq. F11-1
      ``Mn = Mp = Fy*Z <= 1.5*Fy*Sx``; round Eq. F11-2
      ``Mn = Mp = Fy*Z <= 1.6*Fy*Sx``.
    * **Lateral-torsional buckling** (rectangular bar about its major
      axis only).  Let ``L_d_t2 = Lb*d/t^2`` (``d`` = depth in the
      bending plane, ``t`` = bar width).  §F11.2(a): LTB does **not**
      apply when ``L_d_t2 <= 0.08*E/Fy`` (also never for a round or a
      rectangular bar bent about its minor axis).  §F11.2(b)
      ``0.08*E/Fy < L_d_t2 <= 1.9*E/Fy`` -> inelastic Eq. F11-3
      ``Mn = Cb*[1.52 - 0.274*L_d_t2*(Fy/E)]*My <= Mp``.  §F11.2(c)
      ``L_d_t2 > 1.9*E/Fy`` -> elastic Eq. F11-4 ``Mn = Fcr*Sx <= Mp``
      with Eq. F11-5 ``Fcr = 1.9*E*Cb / L_d_t2``.

``compute_flexural_strength_F12_unsymmetric``
    §F12 "Unsymmetrical Shapes" (spec_chapterF.txt printed
    16.1-71/72), the elastic catch-all for any unsymmetrical shape
    except single angles.  Eq. F12-1 ``Mn = Fn*Smin`` with
    ``Fn = min(`` Eq. F12-2 yielding ``Fy``, Eq. F12-3 LTB
    ``Fcr_LTB <= Fy``, Eq. F12-4 local buckling ``Fcr_LB <= Fy`` ``)``
    over the controlling extreme-fibre elastic modulus
    ``Smin = min(extreme_fibre_moduli)``.

    **Analysis-basis boundary (documented per design note 10).**  §F12
    Eq. F12-3 / F12-4 define ``Fcr`` as the lateral-torsional /
    local-buckling stress "as determined by analysis" - the spec does
    *not* give a closed form for a general unsymmetrical shape.  This
    calculator therefore takes the LTB and local-buckling ``Fcr`` as
    **caller-supplied stresses**, exactly the precedent §H3.3 set for
    its caller-supplied torsional stress.  When the caller does not
    supply one (``None``), that buckling limit state is treated as
    non-governing (``Fcr -> Fy``), so §F12 degenerates to the pure
    yield-moment ``Fy*Smin`` - the conservative floor.  The §F12 User
    Note's Z-shape guidance ("take ``Fcr`` as 0.5 ``Fcr`` of a channel
    with the same flange and web properties") is exactly such an
    externally-determined stress and is the intended way to populate
    ``critical_stress_LTB_Fcr``.

``phi_b = 0.90`` / ``Omega_b = 1.67`` (AISC 360-22 §F1), shared with
the rest of Chapter F via :mod:`apeSteel.flexure._common`.

Bars are compact by inspection (no Table B4.1b local-buckling limit
state); the F-0 generalized classifier
:func:`apeSteel.classification.classify_flexural_compactness` returns an
empty plate-element tuple for ``rectangular_bar`` / ``round_bar`` /
``unsymmetric``.  It is still invoked here so §F11/§F12 and the
classifier cannot disagree on that (the classification is informational
for these families - design note 10 §4).

Layering: this module is in the ``flexure`` layer; it imports only from
``sections`` (:class:`FlexuralSectionProperties`), ``classification``
(:func:`classify_flexural_compactness`), and ``core``.  It is **not**
wired into any facade / ``Element`` here - that is Phase F-8.

References
----------
.. [1] AISC 360-22 §F11 "Rectangular Bars and Rounds", Eq. F11-1 -
       F11-5, p. 16.1-71; §F12 "Unsymmetrical Shapes", Eq. F12-1 -
       F12-4, pp. 16.1-71 - 16.1-72.  American Institute of Steel
       Construction, 2022.  Equation forms and page transcribed
       verbatim from
       ``docs/design_notes/_aisc_src_extract/spec_chapterF.txt``.
.. [2] AISC Manual v15.1 Vol.1, Design Examples F.12 (rectangular bar,
       Manual p. F-62..F-64, PDF p.209-211) and F.13 (round bar,
       Manual p. F-65, PDF p.212).  EDITION DELTA: the v15.1 Manual is
       360-16-based and prints the Eq. F11-1 rectangular-bar yield cap
       as ``1.6*Fy*Sx``; AISC **360-22** §F11 (the staged
       ``spec_chapterF.txt`` printed 16.1-71) tightened it to
       ``1.5*Fy*Sx``.  This module follows the 360-22 spec extract
       (design note 10 §1 / §9: the spec extract is the authority; the
       Manual anchor is taken on edition-independent quantities only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification.flexural_compactness import classify_flexural_compactness
from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.flexure._common import (
    CITATIONS_AISC_360_CHAPTER_F,
    OMEGA_FLEXURE_ASD,
    PHI_FLEXURE_LRFD,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.flexural_properties import BendingAxis, FlexuralSectionProperties

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 §F11 / §F12 (spec_chapterF.txt printed
# 16.1-71/72).  Every magic number is named + cited so the provenance
# is traceable at the call site (mirrors the F2 / F4 / F8 constant
# style).
# ---------------------------------------------------------------------------

#: AISC 360-22 Eq. F11-1 rectangular-bar yield cap: Mp = Fy*Z but not
#: more than 1.5*Fy*Sx (spec_chapterF.txt printed 16.1-71).  NOTE the
#: 360-22 value is 1.5; the 360-16-based AISC Manual v15.1 Ex. F.12
#: prints 1.6 - documented edition delta (design note 10 §1/§9; the
#: staged spec extract is the authority).
_EQ_F11_1_RECT_BAR_YIELD_CAP_COEFF: float = 1.5

#: AISC 360-22 Eq. F11-2 round-bar yield cap: Mp = Fy*Z but not more
#: than 1.6*Fy*Sx (spec_chapterF.txt printed 16.1-71).
_EQ_F11_2_ROUND_BAR_YIELD_CAP_COEFF: float = 1.6

#: AISC 360-22 §F11.2(a)/(b) lower LTB slenderness gate coefficient:
#: LTB does not apply while ``Lb*d/t^2 <= 0.08*E/Fy``; the inelastic
#: branch (Eq. F11-3) starts above it (spec_chapterF.txt 16.1-71).
_F11_LTB_GATE_LOWER_COEFF: float = 0.08

#: AISC 360-22 §F11.2(b)/(c) upper LTB slenderness gate coefficient:
#: the inelastic branch (Eq. F11-3) applies for
#: ``0.08*E/Fy < Lb*d/t^2 <= 1.9*E/Fy``; above ``1.9*E/Fy`` the
#: elastic branch (Eq. F11-4 / F11-5) applies (spec_chapterF.txt
#: 16.1-71).
_F11_LTB_GATE_UPPER_COEFF: float = 1.9

#: AISC 360-22 Eq. F11-3 inelastic-LTB lead constant:
#: ``Mn = Cb*(1.52 - 0.274*(Lb*d/t^2)*(Fy/E))*My <= Mp``
#: (spec_chapterF.txt printed 16.1-71).
_EQ_F11_3_A: float = 1.52
#: AISC 360-22 Eq. F11-3 inelastic-LTB slenderness coefficient (see
#: ``_EQ_F11_3_A``).
_EQ_F11_3_B: float = 0.274

#: AISC 360-22 Eq. F11-5 elastic-LTB critical-stress coefficient:
#: ``Fcr = 1.9*E*Cb / (Lb*d/t^2)`` (spec_chapterF.txt printed
#: 16.1-71).
_EQ_F11_5_FCR_COEFF: float = 1.9


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF11Report(Report):
    """AISC 360-22 §F11 flexural-strength result for a bar / round.

    All moments are in apeSteel base units (N*mm); ``Lb``/``d``/``t``
    in mm; stresses in MPa.

    Attributes
    ----------
    is_round : bool
        ``True`` for a round bar (Eq. F11-2 cap, no LTB), ``False`` for
        a rectangular bar (Eq. F11-1 cap).
    bending_axis : str
        ``"major"`` or ``"minor"`` (rectangular bar).  LTB applies only
        for a rectangular bar bent about its major axis.
    plastic_moment_Mp : float
        ``Mp``, the Eq. F11-1 / F11-2 yield plateau **after** the
        ``1.5*Fy*Sx`` (rect) / ``1.6*Fy*Sx`` (round) cap (N*mm).
    yield_moment_My : float
        ``My = Fy*Sx`` (N*mm); used by the Eq. F11-3 inelastic-LTB
        branch and reported for trace.
    uncapped_Fy_Z : float
        ``Fy*Z`` *before* the §F11 yield cap (N*mm); reported so the
        cap's activity is introspectable.
    yield_cap_coefficient : float
        The active §F11 yield-cap coefficient (1.5 rect / 1.6 round).
    yield_cap_value : float
        ``coeff*Fy*Sx``, the cap ceiling itself (N*mm).
    ltb_slenderness_Lb_d_t2 : float
        ``Lb*d/t^2`` (dimensionless); the §F11.2 LTB regime variable.
        ``0.0`` when LTB cannot apply (round, or no ``Lb`` supplied).
    ltb_gate_lower : float
        ``0.08*E/Fy`` - the §F11.2(a)/(b) LTB activation threshold.
    ltb_gate_upper : float
        ``1.9*E/Fy`` - the §F11.2(b)/(c) inelastic/elastic split.
    lateral_torsional_applies : bool
        Whether the LTB limit state was evaluated at all.
    critical_stress_Fcr : float
        Eq. F11-5 ``Fcr`` (MPa); non-zero only on the elastic-LTB
        branch (Eq. F11-4).
    nominal_flexural_strength_Mn : float
        Final ``Mn`` per the governing §F11 limit state (N*mm).
        Mirrors :attr:`Report.nominal_strength`.
    """

    is_round: bool = False
    bending_axis: str = "major"
    plastic_moment_Mp: float = 0.0
    yield_moment_My: float = 0.0
    uncapped_Fy_Z: float = 0.0
    yield_cap_coefficient: float = 0.0
    yield_cap_value: float = 0.0
    ltb_slenderness_Lb_d_t2: float = 0.0
    ltb_gate_lower: float = 0.0
    ltb_gate_upper: float = 0.0
    lateral_torsional_applies: bool = False
    critical_stress_Fcr: float = 0.0
    nominal_flexural_strength_Mn: float = 0.0


@dataclass(frozen=True, slots=True)
class FlexureF12Report(Report):
    """AISC 360-22 §F12 flexural-strength result for an unsymmetrical shape.

    All moments are in apeSteel base units (N*mm); stresses in MPa.

    Attributes
    ----------
    minimum_elastic_modulus_Smin : float
        ``Smin = min(extreme_fibre_moduli)`` (mm^3), Eq. F12-1.
    yield_stress_Fy : float
        Eq. F12-2 ``Fn = Fy`` (MPa).
    critical_stress_LTB_Fcr : float
        Eq. F12-3 caller-supplied lateral-torsional-buckling stress,
        already clamped to ``<= Fy`` (MPa).  Equals ``Fy`` when the
        caller supplied no LTB stress (limit state non-governing).
    critical_stress_LB_Fcr : float
        Eq. F12-4 caller-supplied local-buckling stress, clamped to
        ``<= Fy`` (MPa).  Equals ``Fy`` when none was supplied.
    nominal_stress_Fn : float
        ``Fn = min(Fy, Fcr_LTB, Fcr_LB)`` (MPa), the governing §F12
        stress.
    nominal_flexural_strength_Mn : float
        ``Mn = Fn*Smin`` (N*mm), Eq. F12-1.  Mirrors
        :attr:`Report.nominal_strength`.
    """

    minimum_elastic_modulus_Smin: float = 0.0
    yield_stress_Fy: float = 0.0
    critical_stress_LTB_Fcr: float = 0.0
    critical_stress_LB_Fcr: float = 0.0
    nominal_stress_Fn: float = 0.0
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Equation-set citations
# ---------------------------------------------------------------------------
_CITATIONS_F11: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    # §F11 body - equation numbers + page verbatim from
    # spec_chapterF.txt (§F11 @ printed 16.1-71).
    AISCClauseReference("AISC 360-22", "F11", None, "16.1-71"),
    AISCClauseReference("AISC 360-22", "F11.1", "F11-1", "16.1-71"),
    AISCClauseReference("AISC 360-22", "F11.1", "F11-2", "16.1-71"),
    AISCClauseReference("AISC 360-22", "F11.2", "F11-3", "16.1-71"),
    AISCClauseReference("AISC 360-22", "F11.2", "F11-4", "16.1-71"),
    AISCClauseReference("AISC 360-22", "F11.2", "F11-5", "16.1-71"),
)

_CITATIONS_F12: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    # §F12 body - equation numbers + page verbatim from
    # spec_chapterF.txt (§F12 @ printed 16.1-71/72).
    AISCClauseReference("AISC 360-22", "F12", "F12-1", "16.1-71"),
    AISCClauseReference("AISC 360-22", "F12.1", "F12-2", "16.1-72"),
    AISCClauseReference("AISC 360-22", "F12.2", "F12-3", "16.1-72"),
    AISCClauseReference("AISC 360-22", "F12.3", "F12-4", "16.1-72"),
)


# ---------------------------------------------------------------------------
# §F11 helpers (decomposed so the public calculator stays flat -
# PLR0912/PLR0915 by structure, never by suppression)
# ---------------------------------------------------------------------------
def _f11_yield_plateau(
    *,
    Fy: float,
    Z: float,
    Sx: float,
    is_round: bool,
) -> tuple[float, float, float, float]:
    """Return ``(Mp, uncapped_Fy_Z, cap_coeff, cap_value)`` per §F11.1.

    Eq. F11-1 (rectangular bar) ``Mp = Fy*Z <= 1.5*Fy*Sx``; Eq. F11-2
    (round) ``Mp = Fy*Z <= 1.6*Fy*Sx``.  ``Mp`` is the capped plateau.
    """
    uncapped_fy_z: float = Fy * Z
    cap_coeff: float = (
        _EQ_F11_2_ROUND_BAR_YIELD_CAP_COEFF if is_round else _EQ_F11_1_RECT_BAR_YIELD_CAP_COEFF
    )
    cap_value: float = cap_coeff * Fy * Sx
    mp: float = min(uncapped_fy_z, cap_value)
    return mp, uncapped_fy_z, cap_coeff, cap_value


def _f11_ltb_branch(
    *,
    Fy: float,
    E: float,
    Sx: float,
    My: float,
    Mp: float,
    Cb: float,
    l_d_t2: float,
    gate_upper: float,
) -> tuple[str, float, float]:
    """Return ``(limit_state, Mn, Fcr)`` for the §F11.2 LTB regimes.

    Assumes the caller has already established that LTB *can* apply
    (rectangular bar, major axis, ``l_d_t2 > gate_lower``) - so only
    the §F11.2(b)/(c) inelastic-vs-elastic split (``gate_upper``)
    remains to be made here.

    * ``gate_lower < l_d_t2 <= gate_upper`` -> Eq. F11-3 inelastic
      ``Mn = Cb*(1.52 - 0.274*l_d_t2*Fy/E)*My <= Mp``.
    * ``l_d_t2 > gate_upper`` -> Eq. F11-5 ``Fcr = 1.9*E*Cb/l_d_t2``,
      Eq. F11-4 ``Mn = Fcr*Sx <= Mp``.
    """
    if l_d_t2 <= gate_upper:
        # Eq. F11-3 - inelastic LTB.
        mn_unbounded: float = Cb * (_EQ_F11_3_A - _EQ_F11_3_B * l_d_t2 * (Fy / E)) * My
        return "inelastic_LTB", min(mn_unbounded, Mp), 0.0
    # Eq. F11-5 / F11-4 - elastic LTB.
    fcr: float = _EQ_F11_5_FCR_COEFF * E * Cb / l_d_t2
    return "elastic_LTB", min(fcr * Sx, Mp), fcr


def compute_flexural_strength_F11_bar(
    section_properties_or_fsp: FlexuralSectionProperties,
    material: SteelMaterial,
    *,
    laterally_unbraced_length_Lb: float | None = None,
    lateral_torsional_modification_Cb: float = 1.0,
    bending_axis: BendingAxis = "major",
) -> FlexureF11Report:
    """Return ``Mn`` per AISC 360-22 §F11 for a rectangular bar / round.

    Lower of yielding (plastic moment) and lateral-torsional buckling
    (the latter only for a rectangular bar bent about its major axis).

    * Yielding: Eq. F11-1 rect ``Mn = Mp = Fy*Z <= 1.5*Fy*Sx``;
      Eq. F11-2 round ``Mn = Mp = Fy*Z <= 1.6*Fy*Sx``.
    * LTB (rect, major axis only): with ``L_d_t2 = Lb*d/t^2`` -
      §F11.2(a) does not apply if ``L_d_t2 <= 0.08*E/Fy``; §F11.2(b)
      inelastic Eq. F11-3 if ``0.08*E/Fy < L_d_t2 <= 1.9*E/Fy``;
      §F11.2(c) elastic Eq. F11-4 / F11-5 if ``L_d_t2 > 1.9*E/Fy``.

    The Table B4.1b classification is obtained from the F-0 generalized
    classifier (it returns no plate elements for a bar - compact by
    inspection); §F11 has no local-buckling limit state.

    Parameters
    ----------
    section_properties_or_fsp : FlexuralSectionProperties
        A ``rectangular_bar`` or ``round_bar`` snapshot, as produced by
        :meth:`RectangularBar.compute_section_properties` /
        :meth:`RoundBar.compute_section_properties`.  Reads
        ``plastic_modulus_Zx``, ``elastic_modulus_Sx`` and
        ``overall_depth_d`` for the major axis;
        ``plastic_modulus_Zy`` / ``elastic_modulus_Sy`` for the minor
        axis (rectangular bar).  ``t`` (the §F11.2 LTB bar width
        perpendicular to the bending plane) is recovered exactly from
        the gross area as ``Ag / d`` (no fillet), avoiding a separate
        width field on the shared frozen model; for a rectangular bar
        ``Ag = b*d`` so ``Ag/d`` is exactly ``b``.
    material : SteelMaterial
        Reads ``Fy`` and ``E`` only.
    laterally_unbraced_length_Lb : float or None, optional
        ``Lb`` (mm).  Required to evaluate the rectangular-bar
        major-axis LTB limit state; if ``None`` the LTB check is
        skipped (yielding governs) - appropriate for a round, a
        minor-axis rectangular bar, or a continuously braced bar.
    lateral_torsional_modification_Cb : float, optional
        ``Cb`` (Eq. F1-1).  Default ``1.0`` (conservative; the value
        AISC Manual v15.1 Ex. F.12 / F.13 use).
    bending_axis : {"major", "minor"}, optional
        Geometric bending axis of a rectangular bar.  LTB applies only
        for ``"major"``; ``"minor"`` (and any round) is yielding-only
        per §F11.2(a).  Default ``"major"``.

    Returns
    -------
    FlexureF11Report
        Frozen dataclass with every §F11 intermediate exposed.

    Raises
    ------
    ValueError
        If ``section_kind`` is not ``"rectangular_bar"`` /
        ``"round_bar"``; if a non-positive ``Lb`` is supplied; or if
        ``bending_axis`` is given as ``"minor"`` for a round bar
        (axisymmetric - the distinction is meaningless).
    """
    fsp: FlexuralSectionProperties = section_properties_or_fsp
    if fsp.section_kind not in ("rectangular_bar", "round_bar"):
        msg = (
            f"§F11 applies only to rectangular bars / rounds; got section_kind={fsp.section_kind!r}"
        )
        raise ValueError(msg)
    is_round: bool = fsp.section_kind == "round_bar"
    if is_round and bending_axis != "major":
        msg = f"a round bar is axisymmetric; bending_axis must be 'major', got {bending_axis!r}"
        raise ValueError(msg)
    if laterally_unbraced_length_Lb is not None and laterally_unbraced_length_Lb <= 0.0:
        msg = f"laterally_unbraced_length_Lb must be positive, got {laterally_unbraced_length_Lb!r}"
        raise ValueError(msg)

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E

    # Axis-specific section moduli.  §F11.1 caps both bars on Sx (the
    # spec writes "Sx" for the cap of a bar bent about either axis -
    # spec_chapterF.txt 16.1-71); use the modulus of the active axis.
    if bending_axis == "major":
        z_axis: float = fsp.plastic_modulus_Zx
        s_axis: float = fsp.elastic_modulus_Sx
    else:
        z_axis = fsp.plastic_modulus_Zy
        s_axis = fsp.elastic_modulus_Sy

    # Invoke the F-0 classifier so §F11 and the classifier cannot
    # disagree that a bar carries no Table B4.1b local-buckling limit
    # state (informational for this family - design note 10 §4).
    classification_report = classify_flexural_compactness(material, section_kind=fsp.section_kind)
    if classification_report.plate_elements:  # pragma: no cover - classifier invariant
        msg = (
            f"{fsp.section_kind!r} must have no plate elements (compact by "
            f"inspection); classifier returned "
            f"{len(classification_report.plate_elements)}"
        )
        raise ValueError(msg)

    Mp, uncapped_fy_z, cap_coeff, cap_value = _f11_yield_plateau(
        Fy=Fy, Z=z_axis, Sx=s_axis, is_round=is_round
    )
    My: float = Fy * s_axis  # elastic yield moment (Eq. F11-3 input / trace)

    # --- LTB applicability (§F11.2(a)) -------------------------------
    # LTB applies ONLY to a rectangular bar bent about its major axis,
    # and only when Lb is supplied so Lb*d/t^2 can be formed.
    gate_lower: float = _F11_LTB_GATE_LOWER_COEFF * (E / Fy)
    gate_upper: float = _F11_LTB_GATE_UPPER_COEFF * (E / Fy)

    governing_limit_state: str = "yielding"
    Mn: float = Mp
    Fcr: float = 0.0
    l_d_t2: float = 0.0
    ltb_evaluated: bool = False

    # Narrow on ``Lb is not None`` inline so the type-checker
    # statically proves ``lb`` is a plain float - no ``type: ignore``.
    # (LTB applies only to a rectangular bar bent about its major
    # axis, §F11.2(a).)
    if (not is_round) and bending_axis == "major" and laterally_unbraced_length_Lb is not None:
        lb: float = laterally_unbraced_length_Lb
        d: float = fsp.overall_depth_d
        # Bar width perpendicular to the major-axis bending plane.
        # For a rectangular bar Ag = b*d, so t = Ag/d = b exactly
        # (no fillet); this avoids carrying a separate width field on
        # the shared frozen model.
        t: float = fsp.gross_area_Ag / d
        l_d_t2 = lb * d / t**2

        if l_d_t2 > gate_lower:
            ltb_evaluated = True
            ltb_ls, mn_ltb, fcr_ltb = _f11_ltb_branch(
                Fy=Fy,
                E=E,
                Sx=s_axis,
                My=My,
                Mp=Mp,
                Cb=lateral_torsional_modification_Cb,
                l_d_t2=l_d_t2,
                gate_upper=gate_upper,
            )
            # §F11 lead paragraph: Mn is the LOWER of yielding and LTB.
            if mn_ltb < Mn:
                governing_limit_state = ltb_ls
                Mn = mn_ltb
                Fcr = fcr_ltb

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF11Report(
        cited_clauses=_CITATIONS_F11,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        is_round=is_round,
        bending_axis=bending_axis,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
        uncapped_Fy_Z=uncapped_fy_z,
        yield_cap_coefficient=cap_coeff,
        yield_cap_value=cap_value,
        ltb_slenderness_Lb_d_t2=l_d_t2,
        ltb_gate_lower=gate_lower,
        ltb_gate_upper=gate_upper,
        lateral_torsional_applies=ltb_evaluated,
        critical_stress_Fcr=Fcr,
        nominal_flexural_strength_Mn=Mn,
    )


def compute_flexural_strength_F12_unsymmetric(
    section_properties_or_fsp: FlexuralSectionProperties,
    material: SteelMaterial,
    *,
    lateral_torsional_buckling_stress_Fcr: float | None = None,
    local_buckling_stress_Fcr: float | None = None,
) -> FlexureF12Report:
    """Return ``Mn`` per AISC 360-22 §F12 for an unsymmetrical shape.

    Eq. F12-1 ``Mn = Fn*Smin`` with
    ``Fn = min(`` Eq. F12-2 ``Fy``, Eq. F12-3 ``Fcr_LTB <= Fy``,
    Eq. F12-4 ``Fcr_LB <= Fy`` ``)`` and
    ``Smin = min(extreme_fibre_moduli)``.

    §F12 is the elastic catch-all for *any* unsymmetrical shape except
    single angles.  Eq. F12-3 / F12-4 define ``Fcr`` as the buckling
    stress "as determined by analysis" - the spec gives no closed form
    for a general unsymmetrical shape - so those two stresses are
    **caller-supplied**, mirroring the §H3.3 caller-supplied-stress
    precedent (design note 10).  A ``None`` stress means that limit
    state does not govern (it is treated as ``Fy``), so §F12
    degenerates to the conservative yield-moment floor ``Fy*Smin``.
    The §F12 User Note's Z-shape rule ("``Fcr`` = 0.5 ``Fcr`` of a
    channel with the same flange and web properties") is exactly such
    an externally-determined LTB stress.

    Parameters
    ----------
    section_properties_or_fsp : FlexuralSectionProperties
        Any snapshot carrying a non-empty ``extreme_fibre_moduli``
        tuple (``Smin = min(...)``, Eq. F12-1).  A
        ``section_kind == "unsymmetric"`` snapshot is the intended
        input, but §F12 reads only ``extreme_fibre_moduli``, so any
        kind that populates it is accepted (the elastic catch-all is
        deliberately section-agnostic).
    material : SteelMaterial
        Reads ``Fy`` only.
    lateral_torsional_buckling_stress_Fcr : float or None, optional
        Eq. F12-3 ``Fcr`` (MPa), determined by analysis.  Clamped to
        ``<= Fy`` internally.  ``None`` -> LTB non-governing.
    local_buckling_stress_Fcr : float or None, optional
        Eq. F12-4 ``Fcr`` (MPa), determined by analysis.  Clamped to
        ``<= Fy`` internally.  ``None`` -> local buckling
        non-governing.

    Returns
    -------
    FlexureF12Report
        Frozen dataclass with every §F12 intermediate exposed.

    Raises
    ------
    ValueError
        If ``extreme_fibre_moduli`` is empty (cannot form ``Smin``);
        or if any supplied ``Fcr`` is non-positive.
    """
    fsp: FlexuralSectionProperties = section_properties_or_fsp
    moduli: tuple[float, ...] = fsp.extreme_fibre_moduli
    if not moduli:
        msg = (
            "§F12 needs at least one extreme-fibre elastic modulus "
            "(extreme_fibre_moduli is empty); cannot form Smin (Eq. F12-1)"
        )
        raise ValueError(msg)
    if any(m <= 0.0 for m in moduli):
        msg = f"all extreme_fibre_moduli must be positive, got {moduli!r}"
        raise ValueError(msg)

    Fy: float = material.yield_stress_Fy

    if (
        lateral_torsional_buckling_stress_Fcr is not None
        and lateral_torsional_buckling_stress_Fcr <= 0.0
    ):
        msg = (
            f"lateral_torsional_buckling_stress_Fcr must be positive, "
            f"got {lateral_torsional_buckling_stress_Fcr!r}"
        )
        raise ValueError(msg)
    if local_buckling_stress_Fcr is not None and local_buckling_stress_Fcr <= 0.0:
        msg = f"local_buckling_stress_Fcr must be positive, got {local_buckling_stress_Fcr!r}"
        raise ValueError(msg)

    S_min: float = min(moduli)

    # Eq. F12-2 yielding: Fn = Fy.
    fn_yield: float = Fy
    # Eq. F12-3 LTB: Fn = Fcr <= Fy (caller-supplied; absent ->
    # non-governing, i.e. clamp to Fy).
    fcr_ltb: float = (
        min(lateral_torsional_buckling_stress_Fcr, Fy)
        if lateral_torsional_buckling_stress_Fcr is not None
        else Fy
    )
    # Eq. F12-4 local buckling: Fn = Fcr <= Fy (same convention).
    fcr_lb: float = (
        min(local_buckling_stress_Fcr, Fy) if local_buckling_stress_Fcr is not None else Fy
    )

    Fn: float = min(fn_yield, fcr_ltb, fcr_lb)
    Mn: float = Fn * S_min  # Eq. F12-1

    # Identify which Eq. F12-2/3/4 source set Fn (ties resolve to the
    # earliest spec limit state: yielding, then LTB, then LB).
    if Fn >= fn_yield:
        governing_limit_state = "yielding"
    elif Fn == fcr_ltb:
        governing_limit_state = "elastic_LTB"
    else:
        governing_limit_state = "flange_local_buckling"

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF12Report(
        cited_clauses=_CITATIONS_F12,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        minimum_elastic_modulus_Smin=S_min,
        yield_stress_Fy=Fy,
        critical_stress_LTB_Fcr=fcr_ltb,
        critical_stress_LB_Fcr=fcr_lb,
        nominal_stress_Fn=Fn,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF11Report",
    "FlexureF12Report",
    "compute_flexural_strength_F11_bar",
    "compute_flexural_strength_F12_unsymmetric",
]

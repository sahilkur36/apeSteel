"""AISC 360-22 Chapter E facade - nominal compressive strength.

Orchestrates the §E2/E3/E4/E5/E7 primitives into a single frozen
:class:`CompressionStrengthReport`, exactly as ``F2_compact_doubly_
symmetric`` etc. orchestrate the Chapter-F primitives.

Sequence (AISC-correct ordering):

1. §E2 - effective lengths ``Lcx, Lcy, Lcz`` and ``Lc/r`` per axis.
2. §E3 - flexural-buckling ``Fcr`` about x and about y.
3. §E4 - torsional / flexural-torsional ``Fcr`` (always evaluated;
   for doubly-symmetric W it may still govern, as in the source
   spreadsheet's ``MIN(C66,C76,C86)``).
4. §E5 - for a single angle whose §E5 conditions hold, the flexural
   term is replaced by §E3 on the §E5 *modified* slenderness and §E4 is
   not separately required.
5. Governing ``Fcr`` = the smallest of the applicable modes.
6. §E7 - reduce ``Ag`` to ``Ae`` *at the governing* ``Fcr``
   (Eq. E7-1 uses the governing stress), then ``Pn = Fcr * Ae``.

``phi_c = 0.90``, ``Omega_c = 1.67``.

References
----------
.. [1] AISC 360-22 Chapter E, pp. 16.1-37 - 16.1-43.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.compression._common import (
    CITATIONS_AISC_360_CHAPTER_E,
    OMEGA_COMPRESSION_ASD,
    PHI_COMPRESSION_LRFD,
    BucklingRegime,
    CompressionLimitState,
)
from apeSteel.compression.built_up_E6 import (
    KI_BACK_TO_BACK_ANGLES,
    ConnectorType,
    compute_modified_slenderness_E6,
)
from apeSteel.compression.effective_length_E2 import (
    compute_effective_length_Lc,
    compute_member_slenderness_Lc_over_r,
    is_within_slenderness_advisory,
)
from apeSteel.compression.flexural_buckling_E3 import (
    compute_flexural_buckling_critical_stress_E3,
    compute_nominal_compressive_strength_Pn,
)
from apeSteel.compression.single_angle_E5 import (
    SingleAngleE5Case,
    compute_modified_slenderness_E5,
)
from apeSteel.compression.slender_elements_E7 import resolve_effective_area
from apeSteel.compression.torsional_flexural_E4 import compute_E4_critical_stress
from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.compression_properties import CompressionSectionProperties


@dataclass(frozen=True, slots=True)
class CompressionStrengthReport(Report):
    """AISC 360-22 Chapter E nominal compressive strength.

    All stresses MPa, lengths mm, areas mm^2, ``Pn`` in N.
    ``nominal_strength`` (from :class:`Report`) carries ``Pn``.
    """

    section_kind: str = ""
    # --- §E2 ---
    effective_length_x_Lcx: float = 0.0
    effective_length_y_Lcy: float = 0.0
    effective_length_torsional_Lcz: float = 0.0
    slenderness_x_Lc_over_rx: float = 0.0
    slenderness_y_Lc_over_ry: float = 0.0
    governing_slenderness_Lc_over_r: float = 0.0
    within_slenderness_advisory_200: bool = True
    # --- §E3 flexural buckling ---
    elastic_buckling_stress_Fe_x: float = 0.0
    critical_stress_Fcr_x: float = 0.0
    regime_x: BucklingRegime = "inelastic"
    elastic_buckling_stress_Fe_y: float = 0.0
    critical_stress_Fcr_y: float = 0.0
    regime_y: BucklingRegime = "inelastic"
    # --- §E4 torsional / flexural-torsional ---
    e4_applicable: bool = False
    elastic_buckling_stress_Fe_E4: float = 0.0
    critical_stress_Fcr_E4: float = 0.0
    regime_E4: BucklingRegime = "inelastic"
    # --- §E5 single angle ---
    used_E5_modified_slenderness: bool = False
    modified_slenderness_E5: float = 0.0
    # --- §E7 slender elements ---
    gross_area_Ag: float = 0.0
    effective_area_Ae: float = 0.0
    section_has_slender_element: bool = False
    # --- Governing ---
    governing_critical_stress_Fcr: float = 0.0
    governing_compression_limit_state: CompressionLimitState = "flexural_buckling"
    nominal_compressive_strength_Pn: float = 0.0


_CITATIONS_CHAPTER_E: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_E,
    AISCClauseReference("AISC 360-22", "E2", None, "16.1-37"),
    AISCClauseReference("AISC 360-22", "E3", "E3-1", "16.1-37"),
    AISCClauseReference("AISC 360-22", "E3", "E3-2", "16.1-38"),
    AISCClauseReference("AISC 360-22", "E3", "E3-3", "16.1-38"),
    AISCClauseReference("AISC 360-22", "E3", "E3-4", "16.1-38"),
    AISCClauseReference("AISC 360-22", "E4", "E4-2", "16.1-39"),
    AISCClauseReference("AISC 360-22", "E4", "E4-3", "16.1-39"),
    AISCClauseReference("AISC 360-22", "E4", "E4-4", "16.1-40"),
    AISCClauseReference("AISC 360-22", "E5", "E5-1", "16.1-41"),
    AISCClauseReference("AISC 360-22", "E7", "E7-1", "16.1-42"),
)


def compute_compression_strength(
    section_properties: CompressionSectionProperties,
    material: SteelMaterial,
    effective_length_x_Lcx: float,
    effective_length_y_Lcy: float,
    effective_length_torsional_Lcz: float,
    *,
    single_angle_E5_case: SingleAngleE5Case | None = None,
    single_angle_E5_length_L: float | None = None,
    builtup_connector_spacing_a: float | None = None,
    builtup_connector_type: ConnectorType = "snug_bolted",
    evaluate_E4: bool = True,
) -> CompressionStrengthReport:
    """Return the AISC 360-22 Chapter-E nominal compressive strength.

    Parameters
    ----------
    section_properties : CompressionSectionProperties
    material : SteelMaterial
        Reads ``Fy``, ``E``, ``G``.
    effective_length_x_Lcx, effective_length_y_Lcy : float
        Effective lengths for flexural buckling about x and y (mm).
    effective_length_torsional_Lcz : float
        Effective length for torsion/FT (mm).
    single_angle_E5_case : {"a", "b"} or None
        If given (and the section is a single angle), the §E5 modified
        slenderness replaces the flexural term and §E4 is skipped.
    single_angle_E5_length_L : float or None
        The actual member length ``L`` (mm) for the §E5 ``L/rx`` (E5
        uses ``L``, not ``K L``).  Required when ``single_angle_E5_case``
        is given.
    evaluate_E4 : bool
        Evaluate §E4 and include it in the governing min (default True;
        ignored when §E5 governs).

    Returns
    -------
    CompressionStrengthReport
    """
    fy: float = material.yield_stress_Fy
    e_mod: float = material.elastic_modulus_E
    g_mod: float = material.shear_modulus_G
    rx: float = section_properties.radius_of_gyration_x_rx
    ry: float = section_properties.radius_of_gyration_y_ry

    # Closed HSS are torsionally stiff: AISC routes them through §E3
    # only (§E4 torsional / FT is not a governing limit state).
    if section_properties.section_kind in ("rectangular_HSS", "round_HSS"):
        evaluate_E4 = False

    lc_over_rx: float = compute_member_slenderness_Lc_over_r(effective_length_x_Lcx, rx)
    lc_over_ry: float = compute_member_slenderness_Lc_over_r(effective_length_y_Lcy, ry)

    # §E6 built-up modified slenderness about the built-up (y) axis.
    # Applied consistently to §E3-y and (via an equivalent Lcy) to the
    # §E4-3 Fey, so both modes see the same (Lc/r)m.
    lcy_for_e4: float = effective_length_y_Lcy
    if (
        builtup_connector_spacing_a is not None
        and section_properties.section_kind == "double_angle"
        and section_properties.component_min_radius_of_gyration_ri > 0.0
    ):
        lc_over_ry = compute_modified_slenderness_E6(
            builtup_slenderness_Lc_over_r_o=lc_over_ry,
            connector_spacing_a=builtup_connector_spacing_a,
            component_min_radius_of_gyration_ri=section_properties.component_min_radius_of_gyration_ri,
            connector_type=builtup_connector_type,
            Ki=KI_BACK_TO_BACK_ANGLES,
        )
        lcy_for_e4 = lc_over_ry * ry

    e3x = compute_flexural_buckling_critical_stress_E3(fy, e_mod, lc_over_rx)
    e3y = compute_flexural_buckling_critical_stress_E3(fy, e_mod, lc_over_ry)

    # --- governing flexural / FT critical stress ---
    used_e5: bool = False
    modified_slenderness: float = 0.0
    e4_applicable: bool = False
    fe_e4: float = 0.0
    fcr_e4: float = 0.0
    regime_e4: BucklingRegime = "inelastic"

    if single_angle_E5_case is not None and section_properties.section_kind == "single_angle":
        if single_angle_E5_length_L is None:
            raise ValueError(
                "single_angle_E5_length_L is required when single_angle_E5_case is given"
            )
        used_e5 = True
        # rx = radius about the geometric axis parallel to the connected
        # leg; for an equal-leg angle rx == ry (the geometric axes).
        modified_slenderness = compute_modified_slenderness_E5(
            geometric_slenderness_L_over_rx=single_angle_E5_length_L / rx,
            case=single_angle_E5_case,
        )
        e5_stress = compute_flexural_buckling_critical_stress_E3(fy, e_mod, modified_slenderness)
        governing_fcr: float = e5_stress.critical_stress_Fcr
        governing_state: CompressionLimitState = "single_angle_flexural"
        governing_slenderness: float = modified_slenderness
    else:
        flexural_min_fcr: float = min(e3x.critical_stress_Fcr, e3y.critical_stress_Fcr)
        governing_fcr = flexural_min_fcr
        governing_state = "flexural_buckling"
        governing_slenderness = (
            lc_over_rx if e3x.critical_stress_Fcr <= e3y.critical_stress_Fcr else lc_over_ry
        )
        if evaluate_E4:
            e4_applicable = True
            e4 = compute_E4_critical_stress(
                section_properties=section_properties,
                yield_stress_Fy=fy,
                elastic_modulus_E=e_mod,
                shear_modulus_G=g_mod,
                effective_length_x_Lcx=effective_length_x_Lcx,
                effective_length_y_Lcy=lcy_for_e4,
                effective_length_torsional_Lcz=effective_length_torsional_Lcz,
            )
            fe_e4 = e4.elastic_buckling_stress_Fe
            fcr_e4 = e4.critical_stress_Fcr
            regime_e4 = e4.regime
            if fcr_e4 < governing_fcr:
                governing_fcr = fcr_e4
                governing_state = (
                    "torsional_buckling"
                    if section_properties.symmetry == "doubly_symmetric"
                    else "flexural_torsional_buckling"
                )

    # --- §E7 effective area at the governing Fcr ---
    ea = resolve_effective_area(
        section_properties=section_properties,
        yield_stress_Fy=fy,
        elastic_modulus_E=e_mod,
        critical_stress_Fcr=governing_fcr,
    )

    pn: float = compute_nominal_compressive_strength_Pn(
        critical_stress_Fcr=governing_fcr,
        effective_area_Ae=ea.effective_area_Ae,
    )
    phi_pn: float = PHI_COMPRESSION_LRFD * pn
    pn_over_omega: float = pn / OMEGA_COMPRESSION_ASD

    return CompressionStrengthReport(
        cited_clauses=_CITATIONS_CHAPTER_E,
        governing_limit_state=governing_state,
        phi_LRFD=PHI_COMPRESSION_LRFD,
        omega_ASD=OMEGA_COMPRESSION_ASD,
        nominal_strength=pn,
        phi_strength_LRFD=phi_pn,
        omega_strength_ASD=pn_over_omega,
        section_kind=section_properties.section_kind,
        effective_length_x_Lcx=effective_length_x_Lcx,
        effective_length_y_Lcy=effective_length_y_Lcy,
        effective_length_torsional_Lcz=effective_length_torsional_Lcz,
        slenderness_x_Lc_over_rx=lc_over_rx,
        slenderness_y_Lc_over_ry=lc_over_ry,
        governing_slenderness_Lc_over_r=governing_slenderness,
        within_slenderness_advisory_200=is_within_slenderness_advisory(max(lc_over_rx, lc_over_ry)),
        elastic_buckling_stress_Fe_x=e3x.elastic_buckling_stress_Fe,
        critical_stress_Fcr_x=e3x.critical_stress_Fcr,
        regime_x=e3x.regime,
        elastic_buckling_stress_Fe_y=e3y.elastic_buckling_stress_Fe,
        critical_stress_Fcr_y=e3y.critical_stress_Fcr,
        regime_y=e3y.regime,
        e4_applicable=e4_applicable,
        elastic_buckling_stress_Fe_E4=fe_e4,
        critical_stress_Fcr_E4=fcr_e4,
        regime_E4=regime_e4,
        used_E5_modified_slenderness=used_e5,
        modified_slenderness_E5=modified_slenderness,
        gross_area_Ag=ea.gross_area_Ag,
        effective_area_Ae=ea.effective_area_Ae,
        section_has_slender_element=ea.section_has_slender_element,
        governing_critical_stress_Fcr=governing_fcr,
        governing_compression_limit_state=governing_state,
        nominal_compressive_strength_Pn=pn,
    )


def compute_compression_strength_from_K_L(
    section_properties: CompressionSectionProperties,
    material: SteelMaterial,
    effective_length_factor_Kx: float,
    unbraced_length_Lx: float,
    effective_length_factor_Ky: float,
    unbraced_length_Ly: float,
    effective_length_factor_Kz: float,
    unbraced_length_Lz: float,
    *,
    single_angle_E5_case: SingleAngleE5Case | None = None,
    evaluate_E4: bool = True,
) -> CompressionStrengthReport:
    """``K, L`` convenience wrapper (the spreadsheet's input form).

    Computes ``Lc = K L`` per axis via §E2, then delegates to
    :func:`compute_compression_strength`.  For §E5, the actual length
    ``Lz`` (un-factored) is passed as the §E5 ``L``.
    """
    return compute_compression_strength(
        section_properties=section_properties,
        material=material,
        effective_length_x_Lcx=compute_effective_length_Lc(
            effective_length_factor_Kx, unbraced_length_Lx
        ),
        effective_length_y_Lcy=compute_effective_length_Lc(
            effective_length_factor_Ky, unbraced_length_Ly
        ),
        effective_length_torsional_Lcz=compute_effective_length_Lc(
            effective_length_factor_Kz, unbraced_length_Lz
        ),
        single_angle_E5_case=single_angle_E5_case,
        single_angle_E5_length_L=unbraced_length_Lz,
        evaluate_E4=evaluate_E4,
    )


__all__ = [
    "CompressionStrengthReport",
    "compute_compression_strength",
    "compute_compression_strength_from_K_L",
]

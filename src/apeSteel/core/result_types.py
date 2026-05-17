"""Shared result-type primitives for apeSteel calculators.

Every calculator in apeSteel (flexure, shear, classification, serviceability,
seismic) returns a frozen dataclass that subclasses :class:`Report`. The base
:class:`Report` carries the universal payload:

* :attr:`Report.cited_clauses` — a tuple of :class:`AISCClauseReference`
  records pinning the AISC specification, section, equation, and page that
  the calculator implements.
* :attr:`Report.governing_limit_state` — a short string label naming the
  controlling failure mode (e.g. ``"yielding"``, ``"inelastic_LTB"``,
  ``"web_elastic_buckling"``).
* :attr:`Report.phi_LRFD` / :attr:`Report.omega_ASD` — AISC strength
  factors. The pair is always carried even when the calculator was invoked
  in only one of the two design philosophies, because downstream
  documentation typically wants both.
* :attr:`Report.nominal_strength` — the nominal strength in base units
  (``N``, ``N·mm``, ``N·mm``, ...).
* :attr:`Report.phi_strength_LRFD` / :attr:`Report.omega_strength_ASD` —
  the design strengths in base units, ready to be divided by a display
  unit constant.

Subclasses add the AISC-symbol-suffixed intermediate quantities specific
to their calculation (``limiting_length_plastic_Lp``,
``web_shear_strength_coefficient_Cv1``, …) so a user can introspect every
step of the derivation without re-running the math.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# AISC clause reference
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AISCClauseReference:
    """A pointer back to a paragraph or equation in an AISC document.

    Attributes
    ----------
    specification : str
        The AISC document, e.g. ``"AISC 360-22"``, ``"AISC 341-22"``,
        ``"AISC 358-22"``.
    section : str
        The numbered section, e.g. ``"F2.2"`` or ``"Table B4.1b"``.
    equation : str or None
        The equation number when the citation is to a specific formula,
        e.g. ``"F2-5"``. ``None`` when the citation is to a paragraph
        rather than a numbered equation.
    page : str or None
        Page number in the Steel Construction Manual (e.g.
        ``"16.1-49"``), if known. ``None`` when not available.

    Notes
    -----
    The class is intentionally immutable so that a report's citation
    list cannot be mutated after construction. Cite-by-value semantics
    mean any cached document object can be reused freely.

    Examples
    --------
    >>> AISCClauseReference("AISC 360-22", "F2.2", "F2-5", "16.1-49")
    AISCClauseReference(specification='AISC 360-22', section='F2.2',
                        equation='F2-5', page='16.1-49')
    """

    specification: str
    section: str
    equation: str | None = None
    page: str | None = None

    def short(self) -> str:
        """Compact human-readable string, e.g. ``'AISC 360-22 §F2.2 Eq. F2-5'``."""
        parts: list[str] = [self.specification, "§" + self.section]
        if self.equation is not None:
            parts.append("Eq. " + self.equation)
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Report base
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Report:
    """Base class for every calculator result in apeSteel.

    All attributes are stored in apeSteel's canonical
    ``N-mm-tonne-s`` base units. See
    :mod:`apeSteel.core.units` and ``docs/UNITS_AND_CONVENTIONS.md`` for
    the full convention.

    Subclasses are expected to:

    1. Be decorated with ``@dataclass(frozen=True, slots=True)``.
    2. Add their AISC-symbol-suffixed intermediate quantities as
       additional attributes.
    3. Override :meth:`format` if their default rendering needs more than
       the base fields.

    Attributes
    ----------
    cited_clauses : tuple of AISCClauseReference
        AISC specifications, sections, equations, and pages this report
        cites. Default empty tuple — every real calculator must populate
        it.
    governing_limit_state : str
        Short snake_case label of the controlling failure mode.
    phi_LRFD : float
        AISC LRFD strength reduction factor used to compute
        :attr:`phi_strength_LRFD`. Typically in ``(0, 1]``.
    omega_ASD : float
        AISC ASD safety factor used to compute
        :attr:`omega_strength_ASD`. Typically ``> 1``.
    nominal_strength : float
        Nominal strength in apeSteel base units. The physical meaning
        (force, moment, etc.) depends on the calculator.
    phi_strength_LRFD : float
        ``phi_LRFD * nominal_strength`` in base units.
    omega_strength_ASD : float
        ``nominal_strength / omega_ASD`` in base units.

    Notes
    -----
    The base :class:`Report` is itself a usable dataclass, but a
    calculator should always return a concrete subclass so that
    introspection tooling (the formatter, JSON exporter, etc.) can
    surface the intermediate quantities.
    """

    cited_clauses: tuple[AISCClauseReference, ...] = field(default_factory=tuple)
    governing_limit_state: str = ""
    phi_LRFD: float = 1.0
    omega_ASD: float = 1.0
    nominal_strength: float = 0.0
    phi_strength_LRFD: float = 0.0
    omega_strength_ASD: float = 0.0

    def format(self) -> str:
        """Render a one-paragraph summary suitable for ``print``.

        Returns
        -------
        str
            Multi-line, human-readable text. Subclasses override to add
            their own intermediate quantities.
        """
        cite_lines: str = "".join("\n    " + reference.short() for reference in self.cited_clauses)
        return (
            f"{type(self).__name__}\n"
            f"  governing limit state : {self.governing_limit_state!r}\n"
            f"  nominal strength       : {self.nominal_strength}\n"
            f"  phi (LRFD)             : {self.phi_LRFD}\n"
            f"  omega (ASD)            : {self.omega_ASD}\n"
            f"  phi * Rn (LRFD)        : {self.phi_strength_LRFD}\n"
            f"  Rn / omega (ASD)       : {self.omega_strength_ASD}\n"
            f"  citations             :{cite_lines or ' (none)'}"
        )

    def __str__(self) -> str:  # pragma: no cover - thin pass-through
        return self.format()


__all__ = ["AISCClauseReference", "Report"]

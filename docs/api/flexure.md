# Flexure

AISC 360-22 Chapter F, end-to-end. One module per clause (§F2-§F12)
plus shared primitives (`Lp`, `Lr`, `Mp`, `Mcr`, `Cb`, `Rpc`/`Rpt`,
`Rpg`) and the capacity-curve helpers.

Members are ordered by source — clauses appear in section order (§F2
first, §F12 last); each clause exports one `compute_flexural_strength_*`
entry point and a `FlexureF*Report` frozen dataclass.

::: apeSteel.flexure

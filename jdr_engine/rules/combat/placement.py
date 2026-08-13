# jdr_engine/rules/combat/placement.py
"""Placement initial des combattants sur la grille — lot 8."""
from __future__ import annotations

from jdr_engine.domain.combat.combat_grid import CombatGrid
from jdr_engine.domain.combat.grid_position import GridPosition


class GridTooSmallError(Exception):
    """La grille ne peut pas accueillir tous les combattants."""


def default_combatant_placements(
    initiative_order: tuple[str, ...],
    grid: CombatGrid,
    *,
    spacing: int = 1,
) -> dict[str, GridPosition]:
    """
    Ligne horizontale déterministe — y au centre, x croissant selon l'initiative.

    ``spacing`` = cases entre deux combattants (minimum 1).
    """
    if spacing < 1:
        raise ValueError("spacing doit être >= 1.")
    y = grid.height // 2
    x = 1
    placements: dict[str, GridPosition] = {}
    for combatant_id in initiative_order:
        if not grid.contains(x, y):
            raise GridTooSmallError(
                f"Grille {grid.width}×{grid.height} insuffisante pour "
                f"{len(initiative_order)} combattant(s)."
            )
        placements[combatant_id] = GridPosition(x=x, y=y)
        x += spacing
    return placements

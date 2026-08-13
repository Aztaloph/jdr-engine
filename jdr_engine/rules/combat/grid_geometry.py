# jdr_engine/rules/combat/grid_geometry.py
"""
Géométrie grille combat — distance Chebyshev × 5 ft (variante mouvement SRD 5.1 2014).

Pas de pathfinding ni d'obstacles (lot terrain).
"""
from __future__ import annotations

from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.domain.combat.grid_position import GridPosition

FEET_PER_CELL = 5


def grid_distance_ft(a: GridPosition, b: GridPosition) -> int:
    """Distance en pieds entre deux cases (Chebyshev × 5 ft — conforme SRD)."""
    delta_x = abs(a.x - b.x)
    delta_y = abs(a.y - b.y)
    return max(delta_x, delta_y) * FEET_PER_CELL


def movement_cost_ft(origin: GridPosition, destination: GridPosition) -> int:
    """Coût d'un saut direct case départ → case arrivée (lot 8)."""
    return grid_distance_ft(origin, destination)


def in_range(origin: GridPosition, target: GridPosition, range_ft: int) -> bool:
    """``True`` si ``target`` est à portée de ``origin`` (distance sans obstacle)."""
    return grid_distance_ft(origin, target) <= range_ft


def is_cell_free(
    state: CombatState,
    x: int,
    y: int,
    *,
    ignore_combatant_id: str | None = None,
) -> bool:
    """``True`` si la case est libre (aucun combattant actif ne l'occupe)."""
    for combatant_id, combatant in state.combatants.items():
        if combatant_id == ignore_combatant_id:
            continue
        if not combatant.is_active:
            continue
        if combatant.position is None:
            continue
        if combatant.position.x == x and combatant.position.y == y:
            return False
    return True

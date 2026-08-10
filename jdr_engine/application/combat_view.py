# jdr_engine/application/combat_view.py
"""Contexte viewer pour la sérialisation combat (DTO API)."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.combat.castable_spells import list_combat_castable_spell_ids


def resolve_viewer_context(
    state: CombatState,
    viewer_character_id: str,
    character_repository: SqliteCharacterRepository,
) -> dict[str, Any] | None:
    """
    Bloc ``viewer`` pour ``combat_state_to_dict`` — ``None`` si absent du combat.

    ``castable_spells`` : sorts overlay lançables maintenant par le viewer
    (tour propre + budget + fiche).
    """
    combatant_id: str | None = None
    combatant = None
    for cid, candidate in state.combatants.items():
        if candidate.character_id == viewer_character_id:
            combatant_id = cid
            combatant = candidate
            break

    if combatant_id is None or combatant is None:
        return {
            "character_id": viewer_character_id,
            "combatant_id": None,
            "castable_spells": [],
        }

    character = character_repository.get_by_id(viewer_character_id)
    castable: list[str] = []
    if character is not None:
        castable = list_combat_castable_spell_ids(state, combatant, character)

    return {
        "character_id": viewer_character_id,
        "combatant_id": combatant_id,
        "castable_spells": castable,
    }

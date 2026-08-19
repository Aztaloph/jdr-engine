"""Dérivation grille et placements depuis un snapshot scène — lot Sc."""

from __future__ import annotations

from typing import Any

from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.domain.combat.grid_position import GridPosition


def grid_dimensions_from_snapshot(snapshot: dict[str, Any]) -> tuple[int, int]:
    grid = snapshot["grid"]
    return int(grid["width"]), int(grid["height"])


def list_player_spawns(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Spawns joueur triés par ``spawn.index`` croissant."""
    spawns: list[dict[str, Any]] = []
    for obj in snapshot.get("objects") or []:
        if obj.get("kind") != "spawn":
            continue
        spawn = obj.get("spawn")
        if not isinstance(spawn, dict):
            continue
        if spawn.get("role") != "player":
            continue
        spawns.append(obj)
    spawns.sort(key=lambda item: int(item["spawn"]["index"]))
    return spawns


def spawn_anchor_position(spawn_obj: dict[str, Any]) -> GridPosition:
    return GridPosition(x=int(spawn_obj["x"]), y=int(spawn_obj["y"]))


def build_spawn_placements(
    snapshot: dict[str, Any],
    character_ids: list[str],
    combatants: dict[str, Combatant],
) -> dict[str, GridPosition]:
    """
    Placements partiels : ``character_ids[i]`` → spawn joueur d'index ``i``.

    Les combattants sans spawn disponible sont absents du dict (défaut moteur).
    """
    char_to_combatant = {
        combatant.character_id: combatant_id
        for combatant_id, combatant in combatants.items()
        if combatant.character_id
    }
    spawns = list_player_spawns(snapshot)
    partial: dict[str, GridPosition] = {}
    for index, character_id in enumerate(character_ids):
        if index >= len(spawns):
            break
        combatant_id = char_to_combatant.get(character_id)
        if combatant_id is None:
            continue
        partial[combatant_id] = spawn_anchor_position(spawns[index])
    return partial

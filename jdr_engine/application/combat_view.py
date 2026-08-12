# jdr_engine/application/combat_view.py
"""Contexte viewer pour la sérialisation combat (DTO API)."""
from __future__ import annotations

from typing import Any

from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.domain.character.ability_scores import DEFAULT_ABILITY_IDS
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.application.dto.output_serializers import spellcasting_view_to_dict
from jdr_engine.rules.combat.castable_spells import (
    list_combat_castable_reaction_spell_ids,
    list_combat_castable_spell_ids,
)
from jdr_engine.rules.derived_stats import ABILITY_FULL_LABELS_FR
from jdr_engine.rules.spellcasting.prepared_choice import is_prepared_rechoice_pending


def resolve_viewer_context(
    state: CombatState,
    viewer_character_id: str,
    character_repository: SqliteCharacterRepository,
    engine,
    *,
    locale: str = "fr",
) -> dict[str, Any] | None:
    """
    Bloc ``viewer`` pour ``combat_state_to_dict`` — ``None`` si absent du combat.

    ``castable_spells`` : sorts overlay lançables maintenant par le viewer
    (tour propre + budget + fiche).
    ``castable_reaction_spells`` : réactions overlay (ex. ``shield``), hors tour propre.
    ``spellcasting`` : emplacements et listes dérivées de la fiche (``null`` si non-lanceur).
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
            "castable_reaction_spells": [],
            "spellcasting": None,
        }

    character = character_repository.get_by_id(viewer_character_id)
    castable: list[str] = []
    castable_reaction: list[str] = []
    spellcasting: dict[str, Any] | None = None
    if character is not None:
        castable = list_combat_castable_spell_ids(
            state,
            combatant,
            character,
            engine,
            locale=locale,
        )
        castable_reaction = list_combat_castable_reaction_spell_ids(
            state,
            combatant,
            character,
        )
        sheet = build_character_sheet(character, engine, locale=locale)
        if sheet.spellcasting is not None:
            spellcasting = spellcasting_view_to_dict(
                sheet.spellcasting,
                prepared_rechoice_pending=is_prepared_rechoice_pending(character),
            )

    return {
        "character_id": viewer_character_id,
        "combatant_id": combatant_id,
        "castable_spells": castable,
        "castable_reaction_spells": castable_reaction,
        "spellcasting": spellcasting,
    }


def _ability_labels_fr() -> dict[str, str]:
    return {
        ability_id: ABILITY_FULL_LABELS_FR.get(ability_id, ability_id.upper())
        for ability_id in DEFAULT_ABILITY_IDS
    }


def resolve_combatant_ability_snapshots(
    state: CombatState,
    character_repository: SqliteCharacterRepository,
    engine,
    *,
    viewer: str | None,
    locale: str = "fr",
) -> dict[str, dict[str, Any]]:
    """
    Scores et modificateurs de caractéristiques par ``combatant_id``.

    Même règle de visibilité que PV/CA : vue MJ (``viewer`` absent) ou propre
    combattant du viewer ; rien pour les autres en vue joueur.
    """
    labels = _ability_labels_fr()
    snapshots: dict[str, dict[str, Any]] = {}
    for combatant_id, combatant in state.combatants.items():
        is_own = viewer is not None and combatant.character_id == viewer
        is_dm_view = viewer is None
        if not (is_dm_view or is_own):
            continue
        character = character_repository.get_by_id(combatant.character_id)
        if character is None:
            continue
        sheet = build_character_sheet(character, engine, locale=locale)
        snapshots[combatant_id] = {
            "ability_scores": dict(sheet.ability_scores),
            "ability_modifiers": dict(sheet.ability_modifiers),
            "ability_labels": labels,
        }
    return snapshots

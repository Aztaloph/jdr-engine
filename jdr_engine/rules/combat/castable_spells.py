# jdr_engine/rules/combat/castable_spells.py
"""Sorts overlay combat lançables maintenant — filtre registre ADR-006."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.action_budget import ActionKind
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.rules.combat.overlay_cast import OVERLAY_CAST_REGISTRY
from jdr_engine.rules.combat.spell_resolution import (
    load_combat_spell,
    spell_combat_action_kind,
)
from jdr_engine.rules.engine import RuleEngine
from jdr_engine.rules.spellcasting.cast import SpellCastError
from jdr_engine.rules.spellcasting.slots import get_max_spell_slots
from jdr_engine.rules.spellcasting.state import (
    list_spell_autocomplete_ids,
    spell_is_available,
)


def _current_turn_combatant_id(state: CombatState) -> str | None:
    order = state.initiative_order
    if not order:
        return None
    idx = state.turn_index
    if idx < 0 or idx >= len(order):
        return None
    return order[idx]


def _budget_allows(budget, kind: ActionKind) -> bool:
    if kind == "action":
        return budget.has_action
    if kind == "bonus_action":
        return budget.has_bonus_action
    if kind == "reaction":
        return budget.has_reaction
    return budget.has_movement


def _list_overlay_spell_ids(
    state: CombatState,
    combatant: Combatant,
    character: Character,
    *,
    action_kind: ActionKind | None = None,
    expose_in_castable: bool | None = None,
) -> list[str]:
    if state.status != "active" or not combatant.is_active:
        return []

    budget = combatant.action_budget
    if budget is None:
        return []

    current_id = _current_turn_combatant_id(state)
    is_own_turn = current_id == combatant.combatant_id

    castable: list[str] = []
    for spell_id, spec in OVERLAY_CAST_REGISTRY.items():
        if action_kind is not None and spec.action_kind != action_kind:
            continue
        if expose_in_castable is not None and spec.expose_in_castable != expose_in_castable:
            continue
        if spec.require_own_turn and not is_own_turn:
            continue
        if not spec.require_own_turn and is_own_turn:
            continue
        if not spell_is_available(character, spell_id):
            continue
        if not _budget_allows(budget, spec.action_kind):
            continue
        castable.append(spell_id)

    return castable


def _max_castable_spell_level(class_id: str, character_level: int) -> int:
    """Niveau de sort le plus élevé lançable (table d'emplacements SRD)."""
    max_slots = get_max_spell_slots(class_id, character_level)
    if not max_slots:
        return 0
    return max(max_slots)


def _list_resolved_combat_spell_ids(
    state: CombatState,
    combatant: Combatant,
    character: Character,
    engine: RuleEngine,
    *,
    action_kind: ActionKind,
    locale: str = "fr",
) -> list[str]:
    """Attaques / sauvegardes combat (hors registre overlay ADR-006)."""
    if state.status != "active" or not combatant.is_active:
        return []

    budget = combatant.action_budget
    if budget is None or not _budget_allows(budget, action_kind):
        return []

    current_id = _current_turn_combatant_id(state)
    if current_id != combatant.combatant_id:
        return []

    max_spell_level = _max_castable_spell_level(character.class_id, character.level)
    castable: list[str] = []
    for spell_id in list_spell_autocomplete_ids(character):
        if spell_id in OVERLAY_CAST_REGISTRY:
            continue
        if not spell_is_available(character, spell_id):
            continue
        try:
            spell = load_combat_spell(engine, spell_id, locale=locale)
        except SpellCastError:
            continue
        if spell.effect_type not in ("spell_attack", "saving_throw"):
            continue
        if spell_combat_action_kind(spell, locale=locale) != action_kind:
            continue
        if spell.spell_level > max_spell_level:
            continue
        castable.append(spell_id)
    return castable


def list_combat_castable_spell_ids(
    state: CombatState,
    combatant: Combatant,
    character: Character,
    engine: RuleEngine,
    *,
    locale: str = "fr",
) -> list[str]:
    """
    Sorts lançables immédiatement au tour propre — **action** standard.

    Overlay : registre ADR-006 (``action``) ; résolus : attaque/sauvegarde action.
    """
    overlay = _list_overlay_spell_ids(
        state,
        combatant,
        character,
        action_kind="action",
        expose_in_castable=True,
    )
    resolved = _list_resolved_combat_spell_ids(
        state,
        combatant,
        character,
        engine,
        action_kind="action",
        locale=locale,
    )
    return list(dict.fromkeys(overlay + resolved))


def list_combat_castable_bonus_spell_ids(
    state: CombatState,
    combatant: Combatant,
    character: Character,
    engine: RuleEngine,
    *,
    locale: str = "fr",
) -> list[str]:
    """Sorts lançables au tour propre — **action bonus** (overlay + résolus)."""
    overlay = _list_overlay_spell_ids(
        state,
        combatant,
        character,
        action_kind="bonus_action",
        expose_in_castable=True,
    )
    resolved = _list_resolved_combat_spell_ids(
        state,
        combatant,
        character,
        engine,
        action_kind="bonus_action",
        locale=locale,
    )
    return list(dict.fromkeys(overlay + resolved))


def list_combat_castable_reaction_spell_ids(
    state: CombatState,
    combatant: Combatant,
    character: Character,
) -> list[str]:
    """Sorts overlay en réaction (ex. ``shield``) — hors tour propre du combattant."""
    return _list_overlay_spell_ids(
        state,
        combatant,
        character,
        action_kind="reaction",
    )

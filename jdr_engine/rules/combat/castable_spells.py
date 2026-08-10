# jdr_engine/rules/combat/castable_spells.py
"""Sorts overlay combat lançables maintenant — filtre registre ADR-006."""
from __future__ import annotations

from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.action_budget import ActionKind
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.rules.combat.overlay_cast import OVERLAY_CAST_REGISTRY
from jdr_engine.rules.spellcasting.state import spell_is_available


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


def list_combat_castable_spell_ids(
    state: CombatState,
    combatant: Combatant,
    character: Character,
) -> list[str]:
    """
    Sorts overlay du registre que ``combatant`` peut lancer immédiatement.

    Conditions : combat ``active``, combattant actif, tour propre (sauf réaction
    — non exposée tant que ``expose_in_castable`` est faux), sort disponible sur
    la fiche, budget d'action suffisant.
    """
    if state.status != "active" or not combatant.is_active:
        return []

    budget = combatant.action_budget
    if budget is None:
        return []

    current_id = _current_turn_combatant_id(state)
    is_own_turn = current_id == combatant.combatant_id

    castable: list[str] = []
    for spell_id, spec in OVERLAY_CAST_REGISTRY.items():
        if not spec.expose_in_castable:
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

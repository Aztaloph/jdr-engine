# jdr_engine/application/combat_journal.py
"""Formatage du journal combat pour l'API (lot 7 web)."""
from __future__ import annotations

from typing import Any, Literal

from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.persistence.combat_log_repository import CombatLogEntry

JournalKind = Literal["attack", "spell", "system"]


def _name(state: CombatState, combatant_id: str | None) -> str:
    if not combatant_id:
        return "—"
    combatant = state.combatants.get(combatant_id)
    return combatant.display_name if combatant else combatant_id


def format_combat_log_entry(
    entry: CombatLogEntry,
    state: CombatState,
) -> dict[str, Any]:
    """Transforme une ligne brute en entrée affichable (summary + detail)."""
    payload = entry.payload
    event_type = entry.event_type

    if event_type == "AttackRollResolved":
        attacker = _name(state, payload.get("attacker_id"))
        target = _name(state, payload.get("target_id"))
        total = payload.get("attack_total")
        ac = payload.get("target_ac")
        if payload.get("automatic_miss"):
            summary = f"{attacker} manque automatiquement {target}"
        elif payload.get("hit"):
            crit = " (critique)" if payload.get("critical") else ""
            summary = f"{attacker} touche {target}{crit} ({total} vs CA {ac})"
        else:
            summary = f"{attacker} manque {target} ({total} vs CA {ac})"
        return _row(entry, "attack", summary, f"d20={payload.get('kept_d20')}")

    if event_type == "DamageDealt":
        target = _name(state, payload.get("target_id"))
        source = _name(state, payload.get("source_id"))
        damage = payload.get("damage")
        hp_before = payload.get("hp_before")
        hp_after = payload.get("hp_after")
        summary = f"{target} subit {damage} dégâts"
        detail = (
            f"Source : {source} · {payload.get('dice_notation', '')} · "
            f"PV {hp_before}→{hp_after}"
        )
        return _row(entry, "attack", summary, detail.strip())

    if event_type == "SpellCast":
        caster = _name(state, payload.get("caster_id"))
        spell = payload.get("spell_name") or payload.get("spell_id")
        targets = payload.get("target_ids") or []
        if targets:
            target_names = ", ".join(_name(state, tid) for tid in targets)
            summary = f"{caster} lance {spell} sur {target_names}"
        else:
            summary = f"{caster} lance {spell}"
        return _row(entry, "spell", summary, str(payload.get("effect_type", "")))

    if event_type == "SavingThrowResolved":
        target = _name(state, payload.get("target_id"))
        spell_id = payload.get("spell_id", "sort")
        succeeded = payload.get("succeeded")
        outcome = "réussit" if succeeded else "échoue"
        summary = f"{target} {outcome} sa sauvegarde ({spell_id})"
        detail = (
            f"DD {payload.get('save_dc')} · jet {payload.get('save_total')} · "
            f"dégâts {payload.get('damage_applied')}"
        )
        return _row(entry, "spell", summary, detail)

    if event_type == "TurnStarted":
        name = _name(state, payload.get("combatant_id"))
        return _row(entry, "system", f"Tour de {name}", f"Round {payload.get('round_number', '—')}")

    if event_type == "RoundStarted":
        return _row(
            entry,
            "system",
            f"Début du round {payload.get('round_number', '—')}",
            "",
        )

    if event_type == "CombatStarted":
        return _row(entry, "system", "Combat démarré", "")

    if event_type == "CombatEnded":
        return _row(entry, "system", "Combat terminé", "")

    if event_type == "ConcentrationBroken":
        target = _name(state, payload.get("combatant_id"))
        spell = payload.get("spell_name") or payload.get("spell_id")
        return _row(entry, "system", f"{target} perd la concentration ({spell})", "")

    if event_type == "ConditionApplied":
        target = _name(state, payload.get("combatant_id"))
        cond = payload.get("condition_id")
        return _row(entry, "system", f"{cond} appliqué à {target}", "")

    if event_type == "ConditionRemoved":
        target = _name(state, payload.get("combatant_id"))
        cond = payload.get("condition_id")
        return _row(entry, "system", f"{cond} retiré de {target}", "")

    if event_type == "ActionConsumed":
        actor = _name(state, payload.get("combatant_id"))
        kind = str(payload.get("action_kind", "action"))
        labels = {
            "action": "Action consommée",
            "bonus_action": "Action bonus consommée",
            "reaction": "Réaction consommée",
            "movement": "Déplacement consommé",
        }
        summary = f"{actor} — {labels.get(kind, kind)}"
        return _row(entry, "system", summary, kind)

    return _row(entry, "system", event_type, "")


def format_combat_log(
    entries: list[CombatLogEntry],
    state: CombatState,
) -> list[dict[str, Any]]:
    """Journal complet, ordre anti-chronologique (plus récent en premier)."""
    formatted = [format_combat_log_entry(entry, state) for entry in entries]
    formatted.reverse()
    return formatted


def _row(
    entry: CombatLogEntry,
    kind: JournalKind,
    summary: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "log_id": entry.log_id,
        "kind": kind,
        "summary": summary,
        "detail": detail,
        "event_type": entry.event_type,
        "created_at": entry.created_at,
    }

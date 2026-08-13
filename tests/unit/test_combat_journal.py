# tests/unit/test_combat_journal.py
"""Formatage journal combat — lot 7 web."""
from __future__ import annotations

import unittest

from jdr_engine.application.combat_journal import format_combat_log_entry
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.persistence.combat_log_repository import CombatLogEntry


def _state() -> CombatState:
    return CombatState(
        schema_version=2,
        ruleset_id="dnd5e",
        round_number=1,
        turn_index=0,
        initiative_order=("a1", "b2"),
        combatants={
            "a1": Combatant(
                combatant_id="a1",
                display_name="Alice",
                kind="player_character",
                character_id="char_a",
                hp_current=20,
                hp_max=20,
                ac=14,
            ),
            "b2": Combatant(
                combatant_id="b2",
                display_name="Bob",
                kind="player_character",
                character_id="char_b",
                hp_current=10,
                hp_max=18,
                ac=12,
            ),
        },
        status="active",
        started_at="2026-08-12T12:00:00+00:00",
        combat_id="1",
    )


class TestCombatJournal(unittest.TestCase):
    def test_spell_cast_summary(self) -> None:
        entry = CombatLogEntry(
            log_id=1,
            combat_id=1,
            event_type="SpellCast",
            payload={
                "caster_id": "a1",
                "spell_id": "magic_missile",
                "spell_name": "Projectile magique",
                "effect_type": "spell_attack",
                "target_ids": ["b2"],
            },
            created_at="2026-08-12T12:00:00+00:00",
        )
        row = format_combat_log_entry(entry, _state())
        self.assertEqual(row["kind"], "spell")
        self.assertIn("Alice", row["summary"])
        self.assertIn("Bob", row["summary"])

    def test_action_consumed_bonus_action_label(self) -> None:
        entry = CombatLogEntry(
            log_id=2,
            combat_id=1,
            event_type="ActionConsumed",
            payload={
                "combatant_id": "a1",
                "action_kind": "bonus_action",
            },
            created_at="2026-08-12T12:00:01+00:00",
        )
        row = format_combat_log_entry(entry, _state())
        self.assertIn("Action bonus consommée", row["summary"])
        self.assertEqual(row["detail"], "bonus_action")


if __name__ == "__main__":
    unittest.main()

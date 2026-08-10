# tests/unit/test_combat_castable_spells.py
"""Lot B4-web (b) — ``castable_spells`` viewer (registre overlay)."""
from __future__ import annotations

import unittest

from jdr_engine.application.combat_view import resolve_viewer_context
from jdr_engine.application.dto.output_serializers import combat_state_to_dict
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.action_budget import ActionBudget, fresh_action_budget
from jdr_engine.domain.combat.combat_state import COMBAT_STATE_VERSION, CombatState
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.rules.combat.castable_spells import list_combat_castable_spell_ids


def _ranger_character(*, char_id: str = "ranger_char") -> Character:
    return Character(
        id=char_id,
        owner_id="111",
        guild_id="guild1",
        name="Rodeur",
        race_id="human",
        class_id="ranger",
        level=2,
        ability_scores=AbilityScores(
            scores={
                "str": 12,
                "dex": 16,
                "con": 12,
                "int": 10,
                "wis": 14,
                "cha": 10,
            }
        ),
        hp_current=24,
        hp_max=24,
        choices={
            "spellcasting": {
                "spells_known": ["hunters_mark"],
                "slots_used": {},
            }
        },
    )


def _cleric_character(*, char_id: str = "cleric_char") -> Character:
    return Character(
        id=char_id,
        owner_id="113",
        guild_id="guild1",
        name="Clerc",
        race_id="human",
        class_id="cleric",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 10,
                "dex": 10,
                "con": 12,
                "int": 10,
                "wis": 16,
                "cha": 10,
            }
        ),
        hp_current=22,
        hp_max=22,
        choices={
            "spellcasting": {
                "cantrips_known": ["sacred_flame"],
                "spells_prepared": ["bless", "cure_wounds"],
                "slots_used": {},
            }
        },
    )


class TestListCombatCastableSpellIds(unittest.TestCase):
    def _state(
        self,
        *,
        turn_index: int = 0,
        ranger_budget: ActionBudget | None = None,
        cleric_budget: ActionBudget | None = None,
    ) -> tuple[CombatState, Combatant, Combatant]:
        ranger = Combatant(
            combatant_id="rng11111",
            display_name="Rodeur",
            kind="player_character",
            character_id="ranger_char",
            hp_current=24,
            hp_max=24,
            ac=14,
            is_active=True,
            initiative_total=18,
        ).with_action_budget(ranger_budget or fresh_action_budget())
        cleric = Combatant(
            combatant_id="clr22222",
            display_name="Clerc",
            kind="player_character",
            character_id="cleric_char",
            hp_current=22,
            hp_max=22,
            ac=16,
            is_active=True,
            initiative_total=12,
        ).with_action_budget(cleric_budget or fresh_action_budget())
        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id="dnd5e",
            round_number=1,
            turn_index=turn_index,
            initiative_order=("rng11111", "clr22222"),
            combatants={"rng11111": ranger, "clr22222": cleric},
            status="active",
            started_at="2026-08-10T00:00:00+00:00",
        )
        return state, ranger, cleric

    def test_ranger_on_own_turn_with_bonus_action(self) -> None:
        state, ranger, _ = self._state()
        char = _ranger_character()
        self.assertEqual(
            list_combat_castable_spell_ids(state, ranger, char),
            ["hunters_mark"],
        )

    def test_ranger_not_on_turn_returns_empty(self) -> None:
        state, ranger, _ = self._state(turn_index=1)
        char = _ranger_character()
        self.assertEqual(list_combat_castable_spell_ids(state, ranger, char), [])

    def test_ranger_without_bonus_action_returns_empty(self) -> None:
        budget = ActionBudget(
            has_action=True,
            has_bonus_action=False,
            has_reaction=True,
            has_movement=True,
        )
        state, ranger, _ = self._state(ranger_budget=budget)
        char = _ranger_character()
        self.assertEqual(list_combat_castable_spell_ids(state, ranger, char), [])

    def test_cleric_bless_on_own_turn(self) -> None:
        state, _, cleric = self._state(turn_index=1)
        char = _cleric_character()
        self.assertEqual(
            list_combat_castable_spell_ids(state, cleric, char),
            ["bless"],
        )

    def test_preparing_combat_returns_empty(self) -> None:
        state, ranger, _ = self._state()
        state = CombatState(
            schema_version=state.schema_version,
            ruleset_id=state.ruleset_id,
            round_number=state.round_number,
            turn_index=state.turn_index,
            initiative_order=state.initiative_order,
            combatants=state.combatants,
            status="preparing",
            started_at=None,
        )
        char = _ranger_character()
        self.assertEqual(list_combat_castable_spell_ids(state, ranger, char), [])


class TestCombatStateViewerDto(unittest.TestCase):
    def test_viewer_block_includes_castable_spells(self) -> None:
        state, ranger, _ = TestListCombatCastableSpellIds()._state()
        viewer_context = {
            "character_id": "ranger_char",
            "combatant_id": ranger.combatant_id,
            "castable_spells": ["hunters_mark"],
        }
        data = combat_state_to_dict(
            state,
            viewer="ranger_char",
            viewer_context=viewer_context,
        )
        self.assertIn("viewer", data)
        self.assertEqual(data["viewer"]["castable_spells"], ["hunters_mark"])
        self.assertEqual(data["viewer"]["combatant_id"], "rng11111")

    def test_dm_view_omits_viewer_block(self) -> None:
        state, _, _ = TestListCombatCastableSpellIds()._state()
        data = combat_state_to_dict(state, viewer=None)
        self.assertNotIn("viewer", data)


class TestResolveViewerContext(unittest.TestCase):
    class _Repo:
        def __init__(self, characters: dict[str, Character]) -> None:
            self._characters = characters

        def get_by_id(self, character_id: str) -> Character | None:
            return self._characters.get(character_id)

    def test_resolve_viewer_context_castable(self) -> None:
        state, ranger, _ = TestListCombatCastableSpellIds()._state()
        repo = self._Repo({"ranger_char": _ranger_character()})
        ctx = resolve_viewer_context(state, "ranger_char", repo)
        assert ctx is not None
        self.assertEqual(ctx["castable_spells"], ["hunters_mark"])
        self.assertEqual(ctx["combatant_id"], ranger.combatant_id)

    def test_unknown_viewer_in_combat_returns_empty_castable(self) -> None:
        state, _, _ = TestListCombatCastableSpellIds()._state()
        repo = self._Repo({})
        ctx = resolve_viewer_context(state, "unknown_char", repo)
        assert ctx is not None
        self.assertIsNone(ctx["combatant_id"])
        self.assertEqual(ctx["castable_spells"], [])


if __name__ == "__main__":
    unittest.main()

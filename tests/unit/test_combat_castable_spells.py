# tests/unit/test_combat_castable_spells.py
"""Lot B4-web (b) — ``castable_spells`` viewer (registre overlay)."""
from __future__ import annotations

import unittest
from pathlib import Path

from jdr_engine.application.combat_view import resolve_viewer_context
from jdr_engine.application.dto.output_serializers import combat_state_to_dict
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.action_budget import ActionBudget, fresh_action_budget
from jdr_engine.domain.combat.combat_state import COMBAT_STATE_VERSION, CombatState
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.castable_spells import (
    list_combat_castable_bonus_spell_ids,
    list_combat_castable_reaction_spell_ids,
    list_combat_castable_spell_ids,
)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


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


def _wizard_character(
    *,
    char_id: str = "wizard_char",
    prepared: list[str] | None = None,
) -> Character:
    return Character(
        id=char_id,
        owner_id="114",
        guild_id="guild1",
        name="Magicien",
        race_id="human",
        class_id="wizard",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 8,
                "dex": 14,
                "con": 12,
                "int": 16,
                "wis": 10,
                "cha": 10,
            }
        ),
        hp_current=20,
        hp_max=20,
        choices={
            "spellcasting": {
                "cantrips_known": ["fire_bolt"],
                "spells_prepared": prepared if prepared is not None else ["shield"],
                "slots_used": {},
            }
        },
    )


class TestListCombatCastableSpellIds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _engine()

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

    def _wizard_state(self, *, turn_index: int = 1) -> tuple[CombatState, Combatant]:
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
        ).with_action_budget(fresh_action_budget())
        wizard = Combatant(
            combatant_id="wiz33333",
            display_name="Magicien",
            kind="player_character",
            character_id="wizard_char",
            hp_current=20,
            hp_max=20,
            ac=12,
            is_active=True,
            initiative_total=6,
        ).with_action_budget(fresh_action_budget())
        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id="dnd5e",
            round_number=1,
            turn_index=turn_index,
            initiative_order=("rng11111", "wiz33333"),
            combatants={"rng11111": ranger, "wiz33333": wizard},
            status="active",
            started_at="2026-08-10T00:00:00+00:00",
        )
        return state, wizard

    def test_ranger_on_own_turn_with_bonus_action(self) -> None:
        state, ranger, _ = self._state()
        char = _ranger_character()
        self.assertEqual(
            list_combat_castable_spell_ids(state, ranger, char, self.engine),
            [],
        )
        self.assertEqual(
            list_combat_castable_bonus_spell_ids(state, ranger, char, self.engine),
            ["hunters_mark"],
        )

    def test_ranger_not_on_turn_returns_empty(self) -> None:
        state, ranger, _ = self._state(turn_index=1)
        char = _ranger_character()
        self.assertEqual(
            list_combat_castable_spell_ids(state, ranger, char, self.engine),
            [],
        )
        self.assertEqual(
            list_combat_castable_bonus_spell_ids(state, ranger, char, self.engine),
            [],
        )

    def test_ranger_without_bonus_action_returns_empty(self) -> None:
        budget = ActionBudget(
            has_action=True,
            has_bonus_action=False,
            has_reaction=True,
            has_movement=True,
        )
        state, ranger, _ = self._state(ranger_budget=budget)
        char = _ranger_character()
        self.assertEqual(
            list_combat_castable_spell_ids(state, ranger, char, self.engine),
            [],
        )
        self.assertEqual(
            list_combat_castable_bonus_spell_ids(state, ranger, char, self.engine),
            [],
        )

    def test_cleric_bless_on_own_turn(self) -> None:
        state, _, cleric = self._state(turn_index=1)
        char = _cleric_character()
        castable = list_combat_castable_spell_ids(state, cleric, char, self.engine)
        self.assertEqual(castable, ["bless", "sacred_flame", "cure_wounds"])
        self.assertEqual(
            list_combat_castable_bonus_spell_ids(state, cleric, char, self.engine),
            [],
        )

    def test_cleric_spiritual_weapon_in_bonus_list(self) -> None:
        state, _, cleric = self._state(turn_index=1)
        char = Character(
            id="cleric_sw",
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
                    "spells_prepared": ["bless", "spiritual_weapon"],
                    "slots_used": {},
                }
            },
        )
        action_spells = list_combat_castable_spell_ids(
            state, cleric, char, self.engine
        )
        bonus_spells = list_combat_castable_bonus_spell_ids(
            state, cleric, char, self.engine
        )
        self.assertIn("bless", action_spells)
        self.assertIn("sacred_flame", action_spells)
        self.assertNotIn("spiritual_weapon", action_spells)
        self.assertEqual(bonus_spells, ["spiritual_weapon"])

    def test_wizard_includes_resolved_spells_on_own_turn(self) -> None:
        state, wizard = self._wizard_state(turn_index=1)
        char = _wizard_character(prepared=["magic_missile", "shield"])
        castable = list_combat_castable_spell_ids(
            state,
            wizard,
            char,
            self.engine,
        )
        self.assertIn("fire_bolt", castable)
        self.assertIn("magic_missile", castable)
        self.assertNotIn("shield", castable)

    def test_wizard_scorching_ray_when_prepared_even_if_slots_exhausted(self) -> None:
        state, wizard = self._wizard_state(turn_index=1)
        char = _wizard_character(
            prepared=["magic_missile", "scorching_ray"],
        )
        char = Character(
            id=char.id,
            owner_id=char.owner_id,
            guild_id=char.guild_id,
            name=char.name,
            race_id=char.race_id,
            class_id=char.class_id,
            level=char.level,
            ability_scores=char.ability_scores,
            hp_current=char.hp_current,
            hp_max=char.hp_max,
            choices={
                "spellcasting": {
                    "cantrips_known": ["fire_bolt"],
                    "spells_prepared": ["magic_missile", "scorching_ray"],
                    "slots_used": {"1": 4, "2": 2},
                }
            },
        )
        castable = list_combat_castable_spell_ids(
            state,
            wizard,
            char,
            self.engine,
        )
        self.assertIn("scorching_ray", castable)
        self.assertIn("magic_missile", castable)

    def test_wizard_level_2_hides_scorching_ray(self) -> None:
        state, wizard = self._wizard_state(turn_index=1)
        char = Character(
            id="wiz_lv2",
            owner_id="114",
            guild_id="guild1",
            name="Magicien",
            race_id="human",
            class_id="wizard",
            level=2,
            ability_scores=AbilityScores(
                scores={
                    "str": 8,
                    "dex": 14,
                    "con": 12,
                    "int": 16,
                    "wis": 10,
                    "cha": 10,
                }
            ),
            hp_current=20,
            hp_max=20,
            choices={
                "spellcasting": {
                    "cantrips_known": ["fire_bolt"],
                    "spells_prepared": ["magic_missile", "scorching_ray"],
                    "slots_used": {},
                }
            },
        )
        castable = list_combat_castable_spell_ids(
            state,
            wizard,
            char,
            self.engine,
        )
        self.assertIn("magic_missile", castable)
        self.assertNotIn("scorching_ray", castable)

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
        self.assertEqual(
            list_combat_castable_spell_ids(state, ranger, char, self.engine),
            [],
        )


class TestListCombatCastableReactionSpellIds(unittest.TestCase):
    def _state(
        self,
        *,
        turn_index: int = 0,
        wizard_budget: ActionBudget | None = None,
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
        ).with_action_budget(fresh_action_budget())
        wizard = Combatant(
            combatant_id="wiz33333",
            display_name="Magicien",
            kind="player_character",
            character_id="wizard_char",
            hp_current=20,
            hp_max=20,
            ac=12,
            is_active=True,
            initiative_total=6,
        ).with_action_budget(wizard_budget or fresh_action_budget())
        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id="dnd5e",
            round_number=1,
            turn_index=turn_index,
            initiative_order=("rng11111", "wiz33333"),
            combatants={"rng11111": ranger, "wiz33333": wizard},
            status="active",
            started_at="2026-08-10T00:00:00+00:00",
        )
        return state, ranger, wizard

    def test_shield_off_own_turn_with_reaction(self) -> None:
        state, _, wizard = self._state(turn_index=0)
        char = _wizard_character()
        self.assertEqual(
            list_combat_castable_reaction_spell_ids(state, wizard, char),
            ["shield"],
        )

    def test_shield_on_own_turn_returns_empty(self) -> None:
        state, _, wizard = self._state(turn_index=1)
        char = _wizard_character()
        self.assertEqual(
            list_combat_castable_reaction_spell_ids(state, wizard, char),
            [],
        )

    def test_shield_without_reaction_budget_returns_empty(self) -> None:
        budget = ActionBudget(
            has_action=True,
            has_bonus_action=True,
            has_reaction=False,
            has_movement=True,
        )
        state, _, wizard = self._state(turn_index=0, wizard_budget=budget)
        char = _wizard_character()
        self.assertEqual(
            list_combat_castable_reaction_spell_ids(state, wizard, char),
            [],
        )


class TestCombatStateViewerDto(unittest.TestCase):
    def test_viewer_block_includes_castable_spells(self) -> None:
        state, ranger, _ = TestListCombatCastableSpellIds()._state()
        viewer_context = {
            "character_id": "ranger_char",
            "combatant_id": ranger.combatant_id,
            "castable_spells": [],
            "castable_bonus_spells": ["hunters_mark"],
            "castable_reaction_spells": [],
            "spellcasting": None,
        }
        data = combat_state_to_dict(
            state,
            viewer="ranger_char",
            viewer_context=viewer_context,
        )
        self.assertIn("viewer", data)
        self.assertEqual(data["viewer"]["castable_bonus_spells"], ["hunters_mark"])
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

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _engine()

    def test_resolve_viewer_context_castable(self) -> None:
        state, ranger, _ = TestListCombatCastableSpellIds()._state()
        repo = self._Repo({"ranger_char": _ranger_character()})
        ctx = resolve_viewer_context(
            state,
            "ranger_char",
            repo,
            self.engine,
        )
        assert ctx is not None
        self.assertEqual(ctx["castable_spells"], [])
        self.assertEqual(ctx["castable_bonus_spells"], ["hunters_mark"])
        self.assertEqual(ctx["castable_reaction_spells"], [])
        self.assertEqual(ctx["combatant_id"], ranger.combatant_id)
        self.assertIsNotNone(ctx["spellcasting"])

    def test_resolve_viewer_context_reaction_spell(self) -> None:
        state, _, wizard = TestListCombatCastableReactionSpellIds()._state()
        repo = self._Repo({"wizard_char": _wizard_character()})
        ctx = resolve_viewer_context(
            state,
            "wizard_char",
            repo,
            self.engine,
        )
        assert ctx is not None
        self.assertEqual(ctx["castable_spells"], [])
        self.assertEqual(ctx["castable_reaction_spells"], ["shield"])
        sc = ctx["spellcasting"]
        assert sc is not None
        self.assertIn("slots_max", sc)
        self.assertIn("slots_remaining", sc)

    def test_resolve_viewer_context_wizard_own_turn_lists_attack_spells(self) -> None:
        state, wizard = TestListCombatCastableSpellIds()._wizard_state(turn_index=1)
        repo = self._Repo(
            {
                "wizard_char": _wizard_character(
                    prepared=["magic_missile", "shield"],
                )
            }
        )
        ctx = resolve_viewer_context(state, "wizard_char", repo, self.engine)
        assert ctx is not None
        self.assertIn("fire_bolt", ctx["castable_spells"])
        self.assertIn("magic_missile", ctx["castable_spells"])
        self.assertEqual(ctx["castable_reaction_spells"], [])
        self.assertEqual(ctx["combatant_id"], wizard.combatant_id)

    def test_unknown_viewer_in_combat_returns_empty_castable(self) -> None:
        state, _, _ = TestListCombatCastableSpellIds()._state()
        repo = self._Repo({})
        ctx = resolve_viewer_context(state, "unknown_char", repo, self.engine)
        assert ctx is not None
        self.assertIsNone(ctx["combatant_id"])
        self.assertEqual(ctx["castable_spells"], [])
        self.assertEqual(ctx["castable_reaction_spells"], [])
        self.assertIsNone(ctx["spellcasting"])


if __name__ == "__main__":
    unittest.main()

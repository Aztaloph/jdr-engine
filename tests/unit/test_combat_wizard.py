# tests/unit/test_combat_wizard.py
"""Lot 7 — parcours mage en combat (cantrip, save, auto-hit, multi, réaction)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import DomainEvent, EventBus
from jdr_engine.core.events.combat_events import SpellCast
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.action_budget import ActionBudgetExhaustedError
from jdr_engine.game.combat_manager import CombatManager, NotCombatantTurnError
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.castable_spells import (
    list_combat_castable_reaction_spell_ids,
    list_combat_castable_spell_ids,
)


class RandSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, a: int, b: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


class InitiativeSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("InitiativeSequence épuisé")
        return self._values.pop(0)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _wizard(*, name: str = "Mage") -> Character:
    return Character(
        owner_id="111",
        guild_id="guild1",
        name=name,
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
                "spells_prepared": [
                    "burning_hands",
                    "magic_missile",
                    "shield",
                    "scorching_ray",
                ],
                "slots_used": {},
            }
        },
    )


def _target(*, name: str = "Cible", hp: int = 30) -> Character:
    return Character(
        owner_id="112",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="fighter",
        level=3,
        ability_scores=AbilityScores(
            scores={
                "str": 16,
                "dex": 10,
                "con": 14,
                "int": 8,
                "wis": 10,
                "cha": 10,
            }
        ),
        hp_current=hp,
        hp_max=hp,
        choices={},
    )


class TestCombatWizard(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe(SpellCast, self.events.append)
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.wizard = _wizard(name="Alice")
        self.target = _target(name="Bob")
        for char in (self.wizard, self.target):
            self.char_repo.save(char)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_two(self) -> tuple[int, dict[str, str]]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.wizard.id, self.target.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([14, 8])
        )
        id_map = {c.character_id: cid for cid, c in state.combatants.items()}
        return int(state.combat_id), id_map

    def test_castable_spells_on_own_turn(self) -> None:
        combat_id, ids = self._active_two()
        state = self.manager.load_combat(combat_id)
        wizard_c = state.combatants[ids[self.wizard.id]]
        castable = list_combat_castable_spell_ids(
            state, wizard_c, self.wizard, self.engine
        )
        self.assertEqual(
            castable,
            ["fire_bolt", "burning_hands", "magic_missile", "scorching_ray"],
        )
        self.assertEqual(
            list_combat_castable_reaction_spell_ids(
                state, wizard_c, self.wizard
            ),
            [],
        )

    def test_shield_only_off_turn(self) -> None:
        combat_id, ids = self._active_two()
        wizard_id = ids[self.wizard.id]
        state = self.manager.load_combat(combat_id)
        wizard_c = state.combatants[wizard_id]
        self.assertEqual(
            list_combat_castable_reaction_spell_ids(
                state, wizard_c, self.wizard
            ),
            [],
        )
        with self.assertRaises(NotCombatantTurnError):
            self.manager.cast_spell(
                combat_id,
                wizard_id,
                "shield",
                [],
            )

        self.manager.advance_turn(combat_id)
        state = self.manager.load_combat(combat_id)
        wizard_c = state.combatants[wizard_id]
        self.assertEqual(
            list_combat_castable_reaction_spell_ids(
                state, wizard_c, self.wizard
            ),
            ["shield"],
        )

    def test_fire_bolt_via_cast_spell(self) -> None:
        combat_id, ids = self._active_two()
        caster_id = ids[self.wizard.id]
        target_id = ids[self.target.id]
        hp_before = self.manager.load_combat(combat_id).combatants[target_id].hp_current

        state = self.manager.cast_spell(
            combat_id,
            caster_id,
            "fire_bolt",
            [target_id],
            rng=RandSequence([17, 6]),
        )
        self.assertLess(state.combatants[target_id].hp_current, hp_before)
        budget = state.combatants[caster_id].action_budget
        assert budget is not None
        self.assertFalse(budget.has_action)

    def test_burning_hands_half_damage_via_cast_spell(self) -> None:
        combat_id, ids = self._active_two()
        caster_id = ids[self.wizard.id]
        target_id = ids[self.target.id]
        hp_before = self.manager.load_combat(combat_id).combatants[target_id].hp_current

        state = self.manager.cast_spell(
            combat_id,
            caster_id,
            "burning_hands",
            [target_id],
            rng=RandSequence([4, 5, 6, 14]),
        )
        # save réussie → moitié de 15 = 7
        self.assertEqual(state.combatants[target_id].hp_current, hp_before - 7)

    def test_second_action_spell_rejected_after_fire_bolt(self) -> None:
        combat_id, ids = self._active_two()
        caster_id = ids[self.wizard.id]
        target_id = ids[self.target.id]

        self.manager.cast_spell(
            combat_id,
            caster_id,
            "fire_bolt",
            [target_id],
            rng=RandSequence([17, 4]),
        )
        with self.assertRaises(ActionBudgetExhaustedError):
            self.manager.cast_spell(
                combat_id,
                caster_id,
                "magic_missile",
                [target_id],
                rng=RandSequence([2, 3, 4]),
            )

    def test_shield_off_turn_consumes_reaction(self) -> None:
        combat_id, ids = self._active_two()
        wizard_id = ids[self.wizard.id]
        self.manager.advance_turn(combat_id)

        state = self.manager.cast_spell(
            combat_id,
            wizard_id,
            "shield",
            [],
        )
        budget = state.combatants[wizard_id].action_budget
        assert budget is not None
        self.assertFalse(budget.has_reaction)
        self.assertTrue(
            any(
                effect.effect_id == "shielded" and effect.target_id == wizard_id
                for effect in state.active_effects
            )
        )


if __name__ == "__main__":
    unittest.main()

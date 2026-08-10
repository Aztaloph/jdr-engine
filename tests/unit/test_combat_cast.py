# tests/unit/test_combat_cast.py
"""Lot B4-web (a) — dispatch unifié ``CombatManager.cast_spell``."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.core.events import EventBus
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.spellcasting.cast import SpellCastError


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


def _ranger(*, name: str = "Rodeur") -> Character:
    return Character(
        owner_id="111",
        guild_id="guild1",
        name=name,
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


def _wizard(*, name: str = "Mage") -> Character:
    return Character(
        owner_id="112",
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
                "spells_prepared": ["magic_missile"],
                "slots_used": {},
            }
        },
    )


class TestCombatCastDispatch(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.engine = _engine()
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.ranger = _ranger()
        self.wizard = _wizard()
        self.char_repo.save(self.ranger)
        self.char_repo.save(self.wizard)
        self.manager = CombatManager(
            EventBus(),
            self.combat_repo,
            self.char_repo,
            self.engine,
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _active_fight(self) -> tuple[int, str, str]:
        state = self.manager.create_combat(
            "guild1", "channel1", [self.ranger.id, self.wizard.id]
        )
        state = self.manager.activate_combat(
            int(state.combat_id), rng=InitiativeSequence([18, 6])
        )
        ranger_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.ranger.id
        )
        wizard_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.wizard.id
        )
        return int(state.combat_id), ranger_id, wizard_id

    def test_cast_spell_hunters_mark_via_dispatch(self) -> None:
        combat_id, ranger_id, wizard_id = self._active_fight()
        state = self.manager.cast_spell(
            combat_id,
            ranger_id,
            "hunters_mark",
            [wizard_id],
        )
        self.assertTrue(
            any(
                effect.effect_id == "hunters_mark" and effect.target_id == wizard_id
                for effect in state.active_effects
            )
        )

    def test_cast_spell_rejects_wrong_target_count(self) -> None:
        combat_id, ranger_id, wizard_id = self._active_fight()
        with self.assertRaises(SpellCastError):
            self.manager.cast_spell(
                combat_id,
                ranger_id,
                "hunters_mark",
                [wizard_id, ranger_id],
            )

    def test_cast_spell_rejects_unsupported_slot_level(self) -> None:
        combat_id, ranger_id, wizard_id = self._active_fight()
        with self.assertRaises(SpellCastError):
            self.manager.cast_spell(
                combat_id,
                ranger_id,
                "hunters_mark",
                [wizard_id],
                slot_level=2,
            )


if __name__ == "__main__":
    unittest.main()

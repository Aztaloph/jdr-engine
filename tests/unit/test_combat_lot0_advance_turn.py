# tests/unit/test_combat_lot0_advance_turn.py
"""Lot 0 piste client Web — horloge round, join actif, sérialisation viewer."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jdr_engine.application.dto.output_serializers import combat_state_to_dict
from jdr_engine.core.events import EventBus
from jdr_engine.core.events.combat_events import (
    CombatantJoined,
    RoundStarted,
    TurnStarted,
)
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.game.combat_manager import CombatManager
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.initiative import (
    insert_combatant_into_initiative_order,
    next_active_turn_index,
)


class SequenceRng:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("SequenceRng épuisé")
        return self._values.pop(0)


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _fighter(*, char_id: str, name: str, dex: int = 12) -> Character:
    return Character(
        id=char_id,
        owner_id="1",
        guild_id="guild1",
        name=name,
        race_id="human",
        class_id="fighter",
        level=1,
        ability_scores=AbilityScores(
            scores={
                "str": 16,
                "dex": dex,
                "con": 14,
                "int": 10,
                "wis": 10,
                "cha": 8,
            }
        ),
        hp_current=12,
        hp_max=12,
    )


class TestInsertInitiativeOrder(unittest.TestCase):
    def test_insert_before_current_preserves_turn_combatant(self) -> None:
        order = ("b", "a")
        totals = {"a": 10, "b": 15}
        new_order = insert_combatant_into_initiative_order(
            order,
            "c",
            20,
            initiative_totals=totals,
        )
        self.assertEqual(new_order, ("c", "b", "a"))
        self.assertEqual(new_order.index("b"), 1)


class TestAdvanceTurnDomain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.events: list = []
        self.bus = EventBus()
        self.bus.subscribe(TurnStarted, lambda e: self.events.append(e))
        self.bus.subscribe(RoundStarted, lambda e: self.events.append(e))
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        self.alice = _fighter(char_id="lot0_alice", name="Alice", dex=16)
        self.bob = _fighter(char_id="lot0_bob", name="Bob", dex=10)
        self.carol = _fighter(char_id="lot0_carol", name="Carol", dex=14)
        for char in (self.alice, self.bob, self.carol):
            self.char_repo.save(char)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _activate_two(self, *, rng: SequenceRng) -> tuple[int, str, str]:
        state = self.manager.create_combat(
            "guild1",
            "channel1",
            [self.alice.id, self.bob.id],
        )
        combat_id = int(state.combat_id)
        state = self.manager.activate_combat(combat_id, rng=rng)
        first = state.initiative_order[state.turn_index]
        second = next(
            cid for cid in state.initiative_order if cid != first
        )
        return combat_id, first, second

    def test_advance_simple_within_round(self) -> None:
        combat_id, first, second = self._activate_two(rng=SequenceRng([18, 8]))
        state = self.manager.advance_turn(combat_id)
        self.assertEqual(state.initiative_order[state.turn_index], second)
        self.assertEqual(state.round_number, 1)

    def test_advance_wrap_increments_round(self) -> None:
        combat_id, first, _second = self._activate_two(rng=SequenceRng([12, 8]))
        self.manager.advance_turn(combat_id)
        state = self.manager.advance_turn(combat_id)
        self.assertEqual(state.round_number, 2)
        self.assertEqual(state.turn_index, 0)
        self.assertEqual(state.initiative_order[state.turn_index], first)
        self.assertEqual(len([e for e in self.events if isinstance(e, RoundStarted)]), 1)

    def test_advance_skips_inactive_combatant(self) -> None:
        combat_id, first, second = self._activate_two(rng=SequenceRng([14, 14]))
        self.manager.apply_damage(
            combat_id,
            first,
            damage_amount=99,
        )
        state = self.manager.advance_turn(combat_id)
        self.assertEqual(state.initiative_order[state.turn_index], second)

    def test_join_before_current_turn_keeps_same_combatant(self) -> None:
        combat_id, first, _second = self._activate_two(rng=SequenceRng([10, 8]))
        before_index = self.manager.load_combat(combat_id).turn_index
        before_id = self.manager.load_combat(combat_id).initiative_order[
            before_index
        ]
        joined = self.manager.add_combatant(
            combat_id,
            self.carol.id,
            rng=SequenceRng([20]),
        )
        self.assertEqual(
            joined.initiative_order[joined.turn_index],
            before_id,
        )
        self.assertIn(self.carol.id, [c.character_id for c in joined.combatants.values()])

    def test_join_after_current_plays_later_same_round(self) -> None:
        combat_id, first, second = self._activate_two(rng=SequenceRng([18, 6]))
        self.manager.advance_turn(combat_id)
        state = self.manager.load_combat(combat_id)
        self.assertEqual(state.initiative_order[state.turn_index], second)
        joined = self.manager.add_combatant(
            combat_id,
            self.carol.id,
            rng=SequenceRng([7]),
        )
        carol_id = next(
            cid
            for cid, c in joined.combatants.items()
            if c.character_id == self.carol.id
        )
        self.assertEqual(joined.initiative_order[joined.turn_index], second)
        order = joined.initiative_order
        self.assertLess(order.index(carol_id), order.index(second))

    def test_join_publishes_combatant_joined(self) -> None:
        combat_id, _first, _second = self._activate_two(rng=SequenceRng([10, 8]))
        self.bus.subscribe(CombatantJoined, lambda e: self.events.append(e))
        self.manager.add_combatant(combat_id, self.carol.id, rng=SequenceRng([12]))
        joined_events = [e for e in self.events if isinstance(e, CombatantJoined)]
        self.assertEqual(len(joined_events), 1)
        self.assertEqual(joined_events[0].character_id, self.carol.id)

    def test_round_trip_persistence(self) -> None:
        combat_id, _first, _second = self._activate_two(rng=SequenceRng([16, 7]))
        self.manager.advance_turn(combat_id)
        snapshot = self.combat_repo.get_by_id(combat_id)
        assert snapshot is not None
        expected = (
            snapshot.state.round_number,
            snapshot.state.turn_index,
            snapshot.state.initiative_order,
        )
        loaded = self.manager.load_combat(combat_id)
        self.assertEqual(
            (loaded.round_number, loaded.turn_index, loaded.initiative_order),
            expected,
        )


class TestCombatStateViewerDto(unittest.TestCase):
    def test_viewer_dm_sees_all_hp_and_budget(self) -> None:
        from jdr_engine.domain.combat.action_budget import fresh_action_budget
        from jdr_engine.domain.combat.combat_state import COMBAT_STATE_VERSION, CombatState
        from jdr_engine.domain.combat.combatant import Combatant

        alice = Combatant(
            combatant_id="aaa11111",
            display_name="Alice",
            kind="player_character",
            character_id="char_alice",
            hp_current=10,
            hp_max=12,
            ac=16,
            is_active=True,
            initiative_total=15,
        ).with_action_budget(fresh_action_budget())
        bob = Combatant(
            combatant_id="bbb22222",
            display_name="Bob",
            kind="player_character",
            character_id="char_bob",
            hp_current=8,
            hp_max=12,
            ac=14,
            is_active=True,
            initiative_total=10,
        ).with_action_budget(fresh_action_budget())
        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id="dnd5e",
            round_number=1,
            turn_index=0,
            initiative_order=("aaa11111", "bbb22222"),
            combatants={"aaa11111": alice, "bbb22222": bob},
            status="active",
            started_at="2026-08-08T00:00:00+00:00",
        )
        dm_view = combat_state_to_dict(state, viewer=None)
        alice_dm = dm_view["combatants"]["aaa11111"]
        bob_dm = dm_view["combatants"]["bbb22222"]
        self.assertIn("hp_current", alice_dm)
        self.assertIn("action_budget", alice_dm)
        self.assertIn("hp_current", bob_dm)
        self.assertIn("action_budget", bob_dm)

    def test_viewer_player_hides_other_private_fields(self) -> None:
        from jdr_engine.domain.combat.action_budget import fresh_action_budget
        from jdr_engine.domain.combat.combat_state import COMBAT_STATE_VERSION, CombatState
        from jdr_engine.domain.combat.combatant import Combatant

        alice = Combatant(
            combatant_id="aaa11111",
            display_name="Alice",
            kind="player_character",
            character_id="char_alice",
            hp_current=10,
            hp_max=12,
            ac=16,
            is_active=True,
            initiative_total=15,
        ).with_action_budget(fresh_action_budget())
        bob = Combatant(
            combatant_id="bbb22222",
            display_name="Bob",
            kind="player_character",
            character_id="char_bob",
            hp_current=8,
            hp_max=12,
            ac=14,
            is_active=True,
            initiative_total=10,
        ).with_action_budget(fresh_action_budget())
        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id="dnd5e",
            round_number=1,
            turn_index=0,
            initiative_order=("aaa11111", "bbb22222"),
            combatants={"aaa11111": alice, "bbb22222": bob},
            status="active",
            started_at="2026-08-08T00:00:00+00:00",
        )
        player_view = combat_state_to_dict(state, viewer="char_alice")
        self.assertIn("hp_current", player_view["combatants"]["aaa11111"])
        self.assertIn("action_budget", player_view["combatants"]["aaa11111"])
        bob_view = player_view["combatants"]["bbb22222"]
        self.assertNotIn("hp_current", bob_view)
        self.assertNotIn("action_budget", bob_view)
        self.assertEqual(bob_view["display_name"], "Bob")
        self.assertEqual(bob_view["initiative_total"], 10)

    def test_combat_state_dto_ability_snapshots_respect_viewer(self) -> None:
        from jdr_engine.domain.combat.action_budget import fresh_action_budget
        from jdr_engine.domain.combat.combat_state import COMBAT_STATE_VERSION, CombatState
        from jdr_engine.domain.combat.combatant import Combatant

        alice = Combatant(
            combatant_id="aaa11111",
            display_name="Alice",
            kind="player_character",
            character_id="char_alice",
            hp_current=10,
            hp_max=12,
            ac=16,
            is_active=True,
            initiative_total=15,
        ).with_action_budget(fresh_action_budget())
        bob = Combatant(
            combatant_id="bbb22222",
            display_name="Bob",
            kind="player_character",
            character_id="char_bob",
            hp_current=8,
            hp_max=12,
            ac=14,
            is_active=True,
            initiative_total=10,
        ).with_action_budget(fresh_action_budget())
        state = CombatState(
            schema_version=COMBAT_STATE_VERSION,
            ruleset_id="dnd5e",
            round_number=1,
            turn_index=0,
            initiative_order=("aaa11111", "bbb22222"),
            combatants={"aaa11111": alice, "bbb22222": bob},
            status="active",
            started_at="2026-08-08T00:00:00+00:00",
        )
        labels = {"str": "Force", "dex": "Dextérité", "con": "Constitution",
                  "int": "Intelligence", "wis": "Sagesse", "cha": "Charisme"}
        alice_ab = {
            "ability_scores": {"str": 16, "dex": 14, "con": 12, "int": 10, "wis": 10, "cha": 8},
            "ability_modifiers": {"str": 3, "dex": 2, "con": 1, "int": 0, "wis": 0, "cha": -1},
            "ability_labels": labels,
        }
        bob_ab = {
            "ability_scores": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "ability_modifiers": {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            "ability_labels": labels,
        }
        snapshots = {"aaa11111": alice_ab, "bbb22222": bob_ab}
        dm_view = combat_state_to_dict(
            state,
            combatant_ability_snapshots=snapshots,
        )
        self.assertEqual(dm_view["combatants"]["aaa11111"]["ability_scores"]["str"], 16)
        self.assertEqual(dm_view["combatants"]["bbb22222"]["ability_modifiers"]["dex"], 0)

        player_view = combat_state_to_dict(
            state,
            viewer="char_alice",
            combatant_ability_snapshots={"aaa11111": alice_ab},
        )
        self.assertIn("ability_scores", player_view["combatants"]["aaa11111"])
        self.assertNotIn("ability_scores", player_view["combatants"]["bbb22222"])


class TestNextActiveTurnIndex(unittest.TestCase):
    def test_no_active_returns_none(self) -> None:
        order = ("a", "b")

        def inactive(_cid: str) -> bool:
            return False

        self.assertIsNone(
            next_active_turn_index(order, 0, is_active=inactive)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

# tests/unit/test_combat_geometry.py
"""Lot 8 — géométrie de combat (grille, mouvement, portée)."""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jdr_engine.core.events import EventBus
from jdr_engine.domain.combat.action_budget import ActionBudgetExhaustedError
from jdr_engine.domain.combat.combat_grid import CombatGrid
from jdr_engine.domain.combat.combat_state import (
    COMBAT_STATE_VERSION,
    CombatState,
    CombatStateVersionError,
)
from jdr_engine.domain.combat.combatant import Combatant
from jdr_engine.domain.combat.grid_position import GridPosition
from jdr_engine.game.combat_manager import (
    CellOccupiedError,
    CombatManager,
    InvalidPositionError,
    NotCombatantTurnError,
    OutOfRangeError,
)
from jdr_engine.persistence.combat_repository import SqliteCombatRepository
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.grid_geometry import (
    grid_distance_ft,
    in_range,
    movement_cost_ft,
)
from jdr_engine.rules.combat.placement import default_combatant_placements


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


class TestGridGeometry(unittest.TestCase):
    def test_chebyshev_distance_srd(self):
        origin = GridPosition(0, 0)
        self.assertEqual(grid_distance_ft(origin, GridPosition(0, 0)), 0)
        self.assertEqual(grid_distance_ft(origin, GridPosition(1, 0)), 5)
        self.assertEqual(grid_distance_ft(origin, GridPosition(1, 1)), 5)
        self.assertEqual(grid_distance_ft(origin, GridPosition(2, 1)), 10)

    def test_in_range(self):
        a = GridPosition(0, 0)
        b = GridPosition(1, 0)
        self.assertTrue(in_range(a, b, 5))
        self.assertFalse(in_range(a, b, 0))

    def test_movement_cost_equals_distance(self):
        a = GridPosition(1, 1)
        b = GridPosition(3, 1)
        self.assertEqual(movement_cost_ft(a, b), grid_distance_ft(a, b))


class TestCombatStateVersion(unittest.TestCase):
    def test_version_3_required(self):
        self.assertEqual(COMBAT_STATE_VERSION, 3)

    def test_blob_v2_rejected(self):
        data = {
            "schema_version": 2,
            "ruleset_id": "dnd5e",
            "round_number": 1,
            "turn_index": 0,
            "initiative_order": [],
            "combatants": {},
            "started_at": None,
            "ended_at": None,
            "active_effects": [],
        }
        with self.assertRaises(CombatStateVersionError):
            CombatState.from_dict(data, sql_status="preparing")


class TestCombatManagerGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.char_repo = SqliteCharacterRepository(self.db_path)
        self.combat_repo = SqliteCombatRepository(self.db_path)
        self.bus = EventBus()
        self.manager = CombatManager(
            self.bus,
            self.combat_repo,
            self.char_repo,
            self.engine,
        )
        from jdr_engine.domain.character.ability_scores import AbilityScores
        from jdr_engine.domain.character.character import Character

        self.fighter_a = Character(
            owner_id="1",
            guild_id="g1",
            name="Alpha",
            race_id="human",
            class_id="fighter",
            level=1,
            ability_scores=AbilityScores(
                scores={
                    "str": 16,
                    "dex": 12,
                    "con": 14,
                    "int": 10,
                    "wis": 10,
                    "cha": 8,
                }
            ),
            hp_current=12,
            hp_max=12,
        )
        self.fighter_b = Character(
            owner_id="2",
            guild_id="g1",
            name="Beta",
            race_id="human",
            class_id="fighter",
            level=1,
            ability_scores=AbilityScores(
                scores={
                    "str": 16,
                    "dex": 10,
                    "con": 14,
                    "int": 10,
                    "wis": 10,
                    "cha": 8,
                }
            ),
            hp_current=12,
            hp_max=12,
        )
        self.char_repo.save(self.fighter_a)
        self.char_repo.save(self.fighter_b)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _activate_two_fighters(self, *, rng=None):
        state = self.manager.create_combat(
            "g1",
            "ch1",
            [self.fighter_a.id, self.fighter_b.id],
        )
        combat_id = int(state.combat_id)
        return self.manager.activate_combat(combat_id, rng=rng), combat_id

    def test_activate_assigns_grid_and_positions(self):
        state, _combat_id = self._activate_two_fighters(
            rng=lambda: 10,
        )
        self.assertIsNotNone(state.grid)
        assert state.grid is not None
        self.assertEqual(state.grid.width, 20)
        self.assertEqual(state.grid.height, 20)
        for combatant in state.combatants.values():
            self.assertIsNotNone(combatant.position)

    def test_move_consumes_partial_movement(self):
        state, combat_id = self._activate_two_fighters(rng=lambda: 10)
        current_id = state.initiative_order[state.turn_index]
        current = state.combatants[current_id]
        assert current.position is not None
        start_ft = current.action_budget.movement_remaining_ft
        dest_x = current.position.x
        dest_y = current.position.y + 1

        moved = self.manager.move_combatant(
            combat_id, current_id, dest_x, dest_y
        )
        updated = moved.combatants[current_id]
        assert updated.action_budget is not None
        self.assertEqual(
            updated.action_budget.movement_remaining_ft,
            start_ft - 5,
        )
        self.assertEqual(updated.position, GridPosition(dest_x, dest_y))

    def test_move_rejects_out_of_turn(self):
        _state, combat_id = self._activate_two_fighters(rng=lambda: 10)
        state = self.manager.load_combat(combat_id)
        current_id = state.initiative_order[state.turn_index]
        other_id = next(
            cid for cid in state.initiative_order if cid != current_id
        )
        other = state.combatants[other_id]
        assert other.position is not None
        with self.assertRaises(NotCombatantTurnError):
            self.manager.move_combatant(
                combat_id, other_id, other.position.x, other.position.y
            )

    def test_move_rejects_occupied_cell(self):
        state, combat_id = self._activate_two_fighters(rng=lambda: 10)
        current_id = state.initiative_order[state.turn_index]
        other_id = next(
            cid for cid in state.initiative_order if cid != current_id
        )
        other = state.combatants[other_id]
        assert other.position is not None
        with self.assertRaises(CellOccupiedError):
            self.manager.move_combatant(
                combat_id,
                current_id,
                other.position.x,
                other.position.y,
            )

    def test_melee_attack_out_of_range(self):
        state, combat_id = self._activate_two_fighters(rng=lambda: 10)
        attacker_id = state.initiative_order[state.turn_index]
        target_id = next(
            cid for cid in state.initiative_order if cid != attacker_id
        )
        target = state.combatants[target_id]
        assert target.position is not None
        far = GridPosition(x=target.position.x + 4, y=target.position.y)
        state.combatants[attacker_id] = state.combatants[
            attacker_id
        ].with_position(far)
        self.manager._persist(state)

        from jdr_engine.dice.d20 import D20RollRequest

        request = D20RollRequest(
            roll_type="attack",
            ability="str",
            melee_weapon=True,
            ranged_weapon=False,
        )
        with self.assertRaises(OutOfRangeError):
            self.manager.resolve_attack_roll(
                combat_id,
                attacker_id,
                target_id,
                request,
                max_range_ft=5,
            )

    def test_default_placements_respect_grid(self):
        grid = CombatGrid(width=10, height=10)
        order = ("a", "b", "c")
        placements = default_combatant_placements(order, grid)
        self.assertEqual(len(placements), 3)
        for pos in placements.values():
            self.assertTrue(grid.contains(pos.x, pos.y))


class TestLegacyBlobCompat(unittest.TestCase):
    """Blobs v2 ouverts — clôture auto pour débloquer le lobby (lot 8)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCombatRepository(self.db_path)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_list_open_closes_incompatible_blob(self):
        import sqlite3

        legacy_blob = json.dumps(
            {
                "schema_version": 2,
                "ruleset_id": "dnd5e",
                "round_number": 0,
                "turn_index": 0,
                "initiative_order": [],
                "combatants": {},
                "started_at": None,
                "ended_at": None,
                "active_effects": [],
            }
        )
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO combats (guild_id, channel_id, status, state_json, updated_at)
            VALUES ('api', 'legacy-ch', 'preparing', ?, datetime('now'))
            """,
            (legacy_blob,),
        )
        conn.commit()
        conn.close()

        self.assertEqual(self.repo.list_open(), [])

        conn = sqlite3.connect(self.db_path)
        status = conn.execute(
            "SELECT status FROM combats WHERE channel_id = 'legacy-ch'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(status, "ended")


if __name__ == "__main__":
    unittest.main()

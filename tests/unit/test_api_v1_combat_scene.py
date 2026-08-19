# tests/unit/test_api_v1_combat_scene.py
"""Lot Sc — pont scène → combat (BRIEF_JALON_S.md §9.3)."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.api.app import create_app
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine
from jdr_engine.rules.combat.placement import default_combatant_placements
from jdr_engine.domain.combat.combat_grid import CombatGrid

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "scenes" / "fixtures"


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


class InitiativeSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self) -> int:
        if not self._values:
            raise RuntimeError("InitiativeSequence épuisé")
        return self._values.pop(0)


def _spawn_scene(*, width: int = 12, height: int = 8) -> dict:
    return {
        "schema_version": 1,
        "name": "Arène spawns test",
        "grid": {"width": width, "height": height, "enabled": True},
        "objects": [
            {
                "id": "spawn-p0",
                "kind": "spawn",
                "x": 2,
                "y": 3,
                "width": 1,
                "height": 1,
                "quarter_turns": 0,
                "asset_id": None,
                "spawn": {"role": "player", "index": 0},
            },
            {
                "id": "spawn-p1",
                "kind": "spawn",
                "x": 8,
                "y": 5,
                "width": 1,
                "height": 1,
                "quarter_turns": 0,
                "asset_id": None,
                "spawn": {"role": "player", "index": 1},
            },
        ],
        "lights": [],
    }


class TestApiV1CombatScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="sc_alice", name="Alice", dex=14)
        self.bob = _fighter(char_id="sc_bob", name="Bob", dex=12)
        self.carol = _fighter(char_id="sc_carol", name="Carol", dex=10)
        for char in (self.alice, self.bob, self.carol):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([18, 10, 14]),
            )
        )
        self.taverne = json.loads(
            (FIXTURES / "test-sd-taverne.json").read_text(encoding="utf-8")
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _create_scene(self, document: dict) -> str:
        response = self.client.post("/v1/scenes", json=document)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def _create_combat(
        self,
        *,
        character_ids: list[str],
        scene_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        body: dict = {"character_ids": character_ids}
        if scene_id is not None:
            body["scene_id"] = scene_id
        if channel_id is not None:
            body["channel_id"] = channel_id
        response = self.client.post("/v1/combats", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_t1_create_with_scene_id_persists_snapshot(self) -> None:
        scene_id = self._create_scene(self.taverne)
        payload = self._create_combat(
            character_ids=[self.alice.id, self.bob.id],
            scene_id=scene_id,
            channel_id="scene-t1",
        )
        self.assertEqual(payload["scene_id"], scene_id)
        self.assertIn("scene_snapshot", payload)
        self.assertEqual(payload["scene_snapshot"]["name"], "Taverne test Sd")
        self.assertEqual(payload["scene_snapshot"]["grid"]["width"], 16)

        fetched = self.client.get(f"/v1/combats/{payload['combat_id']}").json()
        self.assertEqual(fetched["scene_snapshot"]["grid"]["height"], 10)

    def test_t2_activate_uses_snapshot_grid_not_default(self) -> None:
        scene_id = self._create_scene(self.taverne)
        created = self._create_combat(
            character_ids=[self.alice.id, self.bob.id],
            scene_id=scene_id,
            channel_id="scene-t2",
        )
        activated = self.client.post(
            f"/v1/combats/{created['combat_id']}/activate"
        )
        self.assertEqual(activated.status_code, 200, activated.text)
        grid = activated.json()["grid"]
        self.assertEqual(grid["width"], 16)
        self.assertEqual(grid["height"], 10)
        self.assertNotEqual(grid["width"], 20)

    def test_t3_two_characters_two_player_spawns(self) -> None:
        scene_id = self._create_scene(_spawn_scene())
        created = self._create_combat(
            character_ids=[self.alice.id, self.bob.id],
            scene_id=scene_id,
            channel_id="scene-t3",
        )
        activated = self.client.post(
            f"/v1/combats/{created['combat_id']}/activate"
        ).json()
        by_character = {
            combatant["character_id"]: combatant
            for combatant in activated["combatants"].values()
        }
        self.assertEqual(by_character[self.alice.id]["position"], {"x": 2, "y": 3})
        self.assertEqual(by_character[self.bob.id]["position"], {"x": 8, "y": 5})

    def test_t4_surplus_character_uses_default_placement(self) -> None:
        scene_id = self._create_scene(_spawn_scene())
        created = self._create_combat(
            character_ids=[self.alice.id, self.bob.id, self.carol.id],
            scene_id=scene_id,
            channel_id="scene-t4",
        )
        activated = self.client.post(
            f"/v1/combats/{created['combat_id']}/activate"
        ).json()
        by_character = {
            combatant["character_id"]: combatant
            for combatant in activated["combatants"].values()
        }
        self.assertEqual(by_character[self.alice.id]["position"], {"x": 2, "y": 3})
        self.assertEqual(by_character[self.bob.id]["position"], {"x": 8, "y": 5})

        grid = CombatGrid(width=12, height=8)
        defaults = default_combatant_placements(
            tuple(activated["initiative_order"]),
            grid,
        )
        char_to_combatant = {
            combatant["character_id"]: combatant_id
            for combatant_id, combatant in activated["combatants"].items()
        }
        carol_id = char_to_combatant[self.carol.id]
        expected = defaults[carol_id]
        actual = by_character[self.carol.id]["position"]
        self.assertEqual(actual, {"x": expected.x, "y": expected.y})
        self.assertNotIn(actual, ({"x": 2, "y": 3}, {"x": 8, "y": 5}))

    def test_t5_edit_source_scene_does_not_change_combat_snapshot(self) -> None:
        scene_id = self._create_scene(self.taverne)
        created = self._create_combat(
            character_ids=[self.alice.id, self.bob.id],
            scene_id=scene_id,
            channel_id="scene-t5",
        )
        original_snapshot = copy.deepcopy(created["scene_snapshot"])

        mutated = copy.deepcopy(self.taverne)
        mutated["name"] = "Taverne mutée"
        mutated["grid"]["width"] = 30
        mutated["grid"]["height"] = 30
        put = self.client.put(f"/v1/scenes/{scene_id}", json=mutated)
        self.assertEqual(put.status_code, 200, put.text)

        fetched = self.client.get(f"/v1/combats/{created['combat_id']}").json()
        self.assertEqual(fetched["scene_snapshot"], original_snapshot)

        activated = self.client.post(
            f"/v1/combats/{created['combat_id']}/activate"
        ).json()
        self.assertEqual(activated["grid"]["width"], 16)
        self.assertEqual(activated["grid"]["height"], 10)


if __name__ == "__main__":
    unittest.main()

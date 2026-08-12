# tests/unit/test_api_v1_prepared_spells.py
"""Lot 7 — API re-préparation sorts (clerc, druide, paladin, magicien)."""
from __future__ import annotations

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
from jdr_engine.rules.rest import apply_long_rest
from jdr_engine.rules.spellcasting.prepared_choice import (
    get_player_prepared_quota,
    get_prepared_spell_pool,
    mark_prepared_rechoice_pending,
)
from jdr_engine.rules.spellcasting.state import get_spells_prepared_list


def _api_error(response) -> dict:
    payload = response.json()
    assert "error" in payload, payload
    return payload["error"]


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _cleric(*, char_id: str = "prep_cleric") -> Character:
    return Character(
        id=char_id,
        owner_id="1",
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
            "specialization": "life",
            "spellcasting": {
                "cantrips_known": ["sacred_flame"],
                "spells_prepared": ["bless", "cure_wounds"],
                "domain_spells": ["bless", "cure_wounds", "spiritual_weapon"],
                "slots_used": {},
            }
        },
    )


def _fighter(*, char_id: str = "prep_fighter") -> Character:
    return Character(
        id=char_id,
        owner_id="2",
        guild_id="guild1",
        name="Guerrier",
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


def _wizard(*, char_id: str = "prep_wizard") -> Character:
    return Character(
        id=char_id,
        owner_id="3",
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
                "spellbook": [
                    "magic_missile",
                    "shield",
                    "burning_hands",
                    "detect_magic",
                    "mage_armor",
                    "scorching_ray",
                ],
                "spells_prepared": ["magic_missile", "shield"],
                "slots_used": {},
            }
        },
    )


class TestApiV1PreparedSpells(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = _engine()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.cleric = _cleric()
        self.wizard = _wizard()
        self.fighter = _fighter()
        self.repo.save(self.cleric)
        self.repo.save(self.wizard)
        self.repo.save(self.fighter)
        self.client = TestClient(
            create_app(engine=self.engine, db_path=self.db_path)
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_get_fighter_not_eligible(self) -> None:
        response = self.client.get(
            f"/v1/characters/{self.fighter.id}/prepared-spells"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["eligible"])
        self.assertFalse(data["prepared_rechoice_pending"])

    def test_get_cleric_without_pending(self) -> None:
        response = self.client.get(
            f"/v1/characters/{self.cleric.id}/prepared-spells"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["eligible"])
        self.assertFalse(data["prepared_rechoice_pending"])
        self.assertIn("quota", data)
        self.assertIn("pool", data)
        self.assertEqual(data["quota"], 2)
        self.assertEqual(data["srd_quota"], 6)
        self.assertEqual(set(data["pool"]), {"inflict_wounds", "detect_magic"})
        self.assertNotIn("bless", data["pool"])
        self.assertIsNotNone(data.get("pool_capped_notice"))

    def test_long_rest_then_prepare_cleric_capped_pool(self) -> None:
        char = self.repo.get_by_id(self.cleric.id)
        assert char is not None
        updated, _rest = apply_long_rest(char, self.engine)
        self.repo.save(updated)

        pending_get = self.client.get(
            f"/v1/characters/{self.cleric.id}/prepared-spells"
        )
        self.assertEqual(pending_get.status_code, 200)
        data = pending_get.json()
        self.assertTrue(data["prepared_rechoice_pending"])
        self.assertEqual(data["quota"], 2)
        selection = data["pool"]

        put = self.client.put(
            f"/v1/characters/{self.cleric.id}/prepared-spells",
            json={"spell_ids": selection},
        )
        self.assertEqual(put.status_code, 200, put.text)
        self.assertFalse(put.json()["prepared_rechoice_pending"])
        self.assertEqual(put.json()["spells_prepared"], selection)

    def test_put_without_pending_rejected(self) -> None:
        response = self.client.put(
            f"/v1/characters/{self.cleric.id}/prepared-spells",
            json={"spell_ids": ["bless"]},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(_api_error(response)["code"], "PREPARED_CHOICE_REJECTED")

    def test_long_rest_then_prepare_spells(self) -> None:
        char = self.repo.get_by_id(self.wizard.id)
        assert char is not None
        updated, _rest = apply_long_rest(char, self.engine)
        self.repo.save(updated)

        pending_get = self.client.get(
            f"/v1/characters/{self.wizard.id}/prepared-spells"
        )
        self.assertEqual(pending_get.status_code, 200)
        self.assertTrue(pending_get.json()["prepared_rechoice_pending"])

        quota = get_player_prepared_quota(updated, engine=self.engine)
        pool = list(get_prepared_spell_pool(updated, engine=self.engine))
        self.assertGreaterEqual(len(pool), quota)
        selection = pool[:quota]

        put = self.client.put(
            f"/v1/characters/{self.wizard.id}/prepared-spells",
            json={"spell_ids": selection},
        )
        self.assertEqual(put.status_code, 200)
        body = put.json()
        self.assertFalse(body["prepared_rechoice_pending"])
        self.assertEqual(body["spells_prepared"], selection)

        reloaded = self.repo.get_by_id(self.wizard.id)
        assert reloaded is not None
        self.assertEqual(get_spells_prepared_list(reloaded), selection)

    def test_viewer_spellcasting_exposes_pending_flag(self) -> None:
        char = self.repo.get_by_id(self.cleric.id)
        assert char is not None
        char = mark_prepared_rechoice_pending(char, pending=True)
        self.repo.save(char)

        create = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.cleric.id, self.fighter.id],
                "channel_id": "prep-viewer",
            },
        )
        combat_id = create.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")

        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.cleric.id},
        )
        self.assertEqual(response.status_code, 200)
        sc = response.json()["viewer"]["spellcasting"]
        self.assertIsNotNone(sc)
        self.assertTrue(sc["prepared_rechoice_pending"])


if __name__ == "__main__":
    unittest.main()

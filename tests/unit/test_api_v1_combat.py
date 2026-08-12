# tests/unit/test_api_v1_combat.py
"""Lot API v1 — cycle de vie combat, invariant lobby, parcours E2E §5.1."""
from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.api.app import create_app
from interfaces.api.combat_scope import (
    GENERATED_CHANNEL_ID_PREFIX,
    resolve_create_scope,
)
from jdr_engine.application.combat_service import CombatService
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


def _api_error(response) -> dict:
    payload = response.json()
    assert "error" in payload, payload
    return payload["error"]


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


class RandSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, low: int, high: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


class TestCombatScope(unittest.TestCase):
    def test_generated_channel_id_uses_prefix(self):
        _guild, channel = resolve_create_scope(guild_id=None, channel_id=None)
        self.assertTrue(channel.startswith(GENERATED_CHANNEL_ID_PREFIX))

    def test_client_channel_id_unchanged(self):
        _guild, channel = resolve_create_scope(
            guild_id=None,
            channel_id="session-alpha",
        )
        self.assertEqual(channel, "session-alpha")

    def test_generated_id_does_not_collide_with_client_prefix_choice(self):
        client_channel = f"{GENERATED_CHANNEL_ID_PREFIX}manual"
        _guild, generated = resolve_create_scope(guild_id=None, channel_id=None)
        self.assertNotEqual(client_channel, generated)


class TestApiV1CombatLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="cmb_alice", name="Alice")
        self.bob = _fighter(char_id="cmb_bob", name="Bob")
        self.carol = _fighter(char_id="cmb_carol", name="Carol")
        for char in (self.alice, self.bob, self.carol):
            self.repo.save(char)
        self.client = TestClient(
            create_app(engine=self.engine, db_path=self.db_path)
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _count_combats(self) -> int:
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM combats").fetchone()[0]
        conn.close()
        return int(count)

    def _count_open_combats(self) -> int:
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM combats WHERE status IN ('preparing', 'active')"
        ).fetchone()[0]
        conn.close()
        return int(count)

    def _create_combat(
        self,
        character_ids: list[str],
        *,
        channel_id: str | None = "test-channel",
    ):
        body: dict = {"character_ids": character_ids}
        if channel_id is not None:
            body["channel_id"] = channel_id
        return self.client.post("/v1/combats", json=body)

    def test_create_get_activate_close_happy_path(self):
        created = self._create_combat([self.alice.id, self.bob.id])
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]
        self.assertEqual(created.json()["status"], "preparing")
        self.assertEqual(len(created.json()["combatants"]), 2)

        fetched = self.client.get(f"/v1/combats/{combat_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["combat_id"], combat_id)

        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["status"], "active")
        self.assertEqual(len(activated.json()["initiative_order"]), 2)

        closed = self.client.post(f"/v1/combats/{combat_id}/close")
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "ended")

    def test_list_open_combats_excludes_closed(self):
        created = self._create_combat([self.alice.id, self.bob.id])
        combat_id = created.json()["combat_id"]
        listed = self.client.get("/v1/combats/open")
        self.assertEqual(listed.status_code, 200)
        open_ids = [entry["combat_id"] for entry in listed.json()["combats"]]
        self.assertIn(combat_id, open_ids)
        self.client.post(f"/v1/combats/{combat_id}/close")
        after = self.client.get("/v1/combats/open")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json()["combats"], [])

    def test_characters_reusable_after_close(self):
        """Test explicite commit 3 — clôture libère les personnages pour un nouveau lobby."""
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="lobby-a",
        )
        self.assertEqual(first.status_code, 200)
        combat_id_1 = first.json()["combat_id"]

        close = self.client.post(f"/v1/combats/{combat_id_1}/close")
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.json()["status"], "ended")

        second = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="lobby-b",
        )
        self.assertEqual(second.status_code, 200)
        combat_id_2 = second.json()["combat_id"]
        self.assertNotEqual(combat_id_1, combat_id_2)
        self.assertEqual(second.json()["status"], "preparing")
        self.assertEqual(len(second.json()["combatants"]), 2)

    def test_character_already_in_combat_rejects_entire_body(self):
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="engaged",
        )
        self.assertEqual(first.status_code, 200)
        combats_before = self._count_combats()
        open_before = self._count_open_combats()

        response = self._create_combat(
            [self.bob.id, self.carol.id],
            channel_id="new-lobby",
        )
        self.assertEqual(response.status_code, 409)
        err = _api_error(response)
        self.assertEqual(err["code"], "CHARACTER_ALREADY_IN_COMBAT")
        self.assertEqual(err["details"]["character_id"], self.bob.id)
        self.assertEqual(self._count_combats(), combats_before)
        self.assertEqual(self._count_open_combats(), open_before)

    def test_unknown_character_rejects_without_creating_combat(self):
        combats_before = self._count_combats()
        response = self._create_combat([self.alice.id, "inconnu"])
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_api_error(response)["code"], "CHARACTER_NOT_FOUND")
        self.assertEqual(self._count_combats(), combats_before)

    def test_activate_insufficient_combatants(self):
        created = self._create_combat([self.alice.id], channel_id="solo")
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]
        response = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            _api_error(response)["code"],
            "INSUFFICIENT_COMBATANTS",
        )

    def test_combat_not_found(self):
        response = self.client.get("/v1/combats/99999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_api_error(response)["code"], "COMBAT_NOT_FOUND")

    def test_open_combat_exists_same_channel(self):
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id="shared-scope",
        )
        self.assertEqual(first.status_code, 200)
        second = self._create_combat(
            [self.carol.id],
            channel_id="shared-scope",
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(_api_error(second)["code"], "OPEN_COMBAT_EXISTS")

    def test_generated_channel_id_allows_parallel_combats(self):
        first = self._create_combat(
            [self.alice.id, self.bob.id],
            channel_id=None,
        )
        second = self._create_combat(
            [self.carol.id],
            channel_id=None,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(
            first.json()["combat_id"],
            second.json()["combat_id"],
        )

        conn = sqlite3.connect(self.db_path)
        channels = [
            row[0]
            for row in conn.execute(
                "SELECT channel_id FROM combats ORDER BY id"
            ).fetchall()
        ]
        conn.close()
        self.assertEqual(len(channels), 2)
        for channel in channels:
            self.assertTrue(channel.startswith(GENERATED_CHANNEL_ID_PREFIX))
        self.assertNotEqual(channels[0], channels[1])


class TestApiV1CombatE2E(unittest.TestCase):
    """Parcours contractuel §5.1 — bout en bout."""

    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="e2e_alice", name="Alice", dex=14)
        self.bob = _fighter(char_id="e2e_bob", name="Bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([15, 8]),
                combat_attack_rng=RandSequence([14, 5]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_contract_parcours_7_etapes(self):
        # 1. Fiche initiale — Alice consulte sa fiche ; Bob entre au combat à 12 PV
        sheet_before = self.client.get(f"/v1/characters/{self.alice.id}/sheet")
        self.assertEqual(sheet_before.status_code, 200)
        self.assertNotIn("active_effects", sheet_before.json())
        self.assertEqual(sheet_before.json()["hp_current"], 12)

        bob_sheet_before = self.client.get(f"/v1/characters/{self.bob.id}/sheet")
        self.assertEqual(bob_sheet_before.status_code, 200)
        bob_hp_before = bob_sheet_before.json()["hp_current"]
        sqlite_bob_before = copy.deepcopy(self.repo.get_by_id(self.bob.id))

        # 2. Créer le lobby — Alice et Bob s'engagent dans la rencontre
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "e2e-parcours",
            },
        )
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]

        # 3. Activer — initiative lancée, le tour commence
        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["status"], "active")
        active_id = activated.json()["initiative_order"][
            activated.json()["turn_index"]
        ]
        target_id = next(
            cid
            for cid in activated.json()["combatants"]
            if cid != active_id
        )

        # 4. Attaque — Alice frappe Bob à l'épée longue ; jet et dégâts en une réponse
        attack = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(attack.status_code, 200)
        payload = attack.json()
        self.assertTrue(payload["attack"]["outcome"]["hit"])
        damage = payload["damage"]
        self.assertIsNotNone(damage)
        damage_total = damage["total"]
        self.assertEqual(payload["target"]["combatant_id"], target_id)
        self.assertEqual(damage["hp_before"], bob_hp_before)
        self.assertEqual(damage["hp_after"], bob_hp_before - damage_total)
        self.assertEqual(payload["target"]["hp_current"], bob_hp_before - damage_total)

        # 5. État rencontre — l'overlay combat raconte la même chose que la réponse
        combat = self.client.get(f"/v1/combats/{combat_id}")
        self.assertEqual(combat.status_code, 200)
        self.assertEqual(combat.json()["status"], "active")
        target_in_combat = combat.json()["combatants"][target_id]
        self.assertEqual(target_in_combat["hp_current"], payload["target"]["hp_current"])
        self.assertEqual(target_in_combat["hp_current"], bob_hp_before - damage_total)

        # 6. Fiche fusionnée de Bob — PV affichés = PV initiaux − dégâts annoncés
        sheet_merged = self.client.get(f"/v1/characters/{self.bob.id}/sheet")
        self.assertEqual(sheet_merged.status_code, 200)
        self.assertIn("active_effects", sheet_merged.json())
        self.assertIsInstance(sheet_merged.json()["active_effects"], list)
        self.assertEqual(
            sheet_merged.json()["hp_current"],
            bob_hp_before - damage_total,
        )
        # ADR-005 : la fiche SQLite de Bob n'a pas bougé pendant le combat
        sqlite_bob_mid = self.repo.get_by_id(self.bob.id)
        assert sqlite_bob_before is not None and sqlite_bob_mid is not None
        self.assertEqual(sqlite_bob_mid.hp_current, sqlite_bob_before.hp_current)
        self.assertEqual(sqlite_bob_mid.to_dict(), sqlite_bob_before.to_dict())

        # 7. Clôture — fin de rencontre ; sync PV fiche puis retour à la fiche normale
        closed = self.client.post(f"/v1/combats/{combat_id}/close")
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "ended")

        sheet_after = self.client.get(f"/v1/characters/{self.bob.id}/sheet")
        self.assertNotIn("active_effects", sheet_after.json())
        self.assertEqual(
            sheet_after.json()["hp_current"],
            bob_hp_before - damage_total,
        )
        self.assertEqual(
            self.repo.get_by_id(self.bob.id).hp_current,
            bob_hp_before - damage_total,
        )


class TestApiV1AttackAndMergedSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="atk_alice", name="Alice", dex=16)
        self.bob = _fighter(char_id="atk_bob", name="Bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.combat_service = CombatService.from_db_path(
            self.db_path,
            self.engine,
            register_auto_save_handler=False,
        )
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([18, 6]),
                combat_attack_rng=RandSequence([12, 4]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_attack_in_preparing_combat_rejected(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "preparing-only",
            },
        )
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]
        attacker_id, target_id = list(created.json()["combatants"])

        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            json={
                "attacker_id": attacker_id,
                "target_id": target_id,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(_api_error(response)["code"], "COMBAT_STATUS_INVALID")

    def test_attack_legacy_body_fields_rejected(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "legacy-body",
            },
        )
        combat_id = created.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")
        activated = self.client.get(f"/v1/combats/{combat_id}").json()
        active_id = activated["initiative_order"][activated["turn_index"]]
        target_id = next(
            cid for cid in activated["combatants"] if cid != active_id
        )

        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "weapon_id": "longsword",
                "melee_weapon": True,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(_api_error(response)["code"], "VALIDATION_ERROR")

    def test_attack_unknown_weapon_returns_weapon_unknown_code(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "unknown-weapon",
            },
        )
        combat_id = created.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")
        activated = self.client.get(f"/v1/combats/{combat_id}").json()
        active_id = activated["initiative_order"][activated["turn_index"]]
        target_id = next(
            cid for cid in activated["combatants"] if cid != active_id
        )

        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "weapon_id": "greatsword",
            },
        )
        self.assertEqual(response.status_code, 422)
        err = _api_error(response)
        self.assertEqual(err["code"], "WEAPON_UNKNOWN")
        self.assertEqual(err["details"]["weapon_id"], "greatsword")

    def test_attack_miss_damage_null(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "attack-miss",
            },
        )
        combat_id = created.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")
        activated = self.client.get(f"/v1/combats/{combat_id}").json()
        active_id = activated["initiative_order"][activated["turn_index"]]
        target_id = next(
            cid for cid in activated["combatants"] if cid != active_id
        )
        target_hp_before = activated["combatants"][target_id]["hp_current"]

        client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([18, 6]),
                combat_attack_rng=RandSequence([1]),
            )
        )
        response = client.post(
            f"/v1/combats/{combat_id}/attack",
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["attack"]["outcome"]["hit"])
        self.assertIsNone(payload["damage"])
        self.assertEqual(payload["target"]["hp_current"], target_hp_before)
        client.close()

    def test_attack_does_not_persist_character_sheet(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "persist-check",
            },
        )
        combat_id = created.json()["combat_id"]
        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        active_id = activated.json()["initiative_order"][
            activated.json()["turn_index"]
        ]
        target_id = next(
            cid for cid in activated.json()["combatants"] if cid != active_id
        )

        before = copy.deepcopy(self.repo.get_by_id(self.alice.id))
        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["damage"])
        after = self.repo.get_by_id(self.alice.id)
        assert before is not None and after is not None
        self.assertEqual(after.hp_current, before.hp_current)
        self.assertEqual(after.to_dict(), before.to_dict())

    def test_merged_sheet_hp_overlay_without_sqlite_write(self):
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "merged-hp",
            },
        )
        combat_id = created.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")
        state = self.combat_service.load_combat(combat_id)
        bob_combatant_id = next(
            cid
            for cid, c in state.combatants.items()
            if c.character_id == self.bob.id
        )
        sqlite_hp_before = self.repo.get_by_id(self.bob.id).hp_current

        self.combat_service.apply_damage(
            combat_id,
            bob_combatant_id,
            damage_amount=5,
        )

        sheet = self.client.get(f"/v1/characters/{self.bob.id}/sheet")
        self.assertEqual(sheet.status_code, 200)
        self.assertEqual(sheet.json()["hp_current"], sqlite_hp_before - 5)
        self.assertEqual(
            self.repo.get_by_id(self.bob.id).hp_current,
            sqlite_hp_before,
        )

    def test_attack_viewer_hides_other_target_hp(self) -> None:
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "attack-viewer",
            },
        )
        combat_id = created.json()["combat_id"]
        activated = self.client.post(f"/v1/combats/{combat_id}/activate").json()
        active_id = activated["initiative_order"][activated["turn_index"]]
        target_id = next(
            cid for cid in activated["combatants"] if cid != active_id
        )
        attacker_char = activated["combatants"][active_id]["character_id"]
        target_char = activated["combatants"][target_id]["character_id"]
        self.assertNotEqual(attacker_char, target_char)

        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            params={"viewer": attacker_char},
            json={
                "attacker_id": active_id,
                "target_id": target_id,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("hp_current", payload["target"])
        self.assertNotIn("hp_max", payload["target"])
        if payload["damage"] is not None:
            self.assertNotIn("hp_before", payload["damage"])
            self.assertNotIn("hp_after", payload["damage"])
            self.assertIn("damage_dealt", payload["damage"])


class TestApiV1AdvanceTurn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="adv_alice", name="Alice", dex=16)
        self.bob = _fighter(char_id="adv_bob", name="Bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([18, 6]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _active_combat_id(self) -> int:
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "advance-turn",
            },
        )
        combat_id = created.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")
        return combat_id

    def test_advance_turn_advances_and_returns_state(self) -> None:
        combat_id = self._active_combat_id()
        before = self.client.get(f"/v1/combats/{combat_id}").json()
        response = self.client.post(f"/v1/combats/{combat_id}/advance-turn")
        self.assertEqual(response.status_code, 200)
        after = response.json()
        self.assertNotEqual(after["turn_index"], before["turn_index"])

    def test_advance_turn_viewer_player_hides_other_hp(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.post(
            f"/v1/combats/{combat_id}/advance-turn",
            params={"viewer": self.alice.id},
        )
        self.assertEqual(response.status_code, 200)
        combatants = response.json()["combatants"]
        alice_cid = next(
            cid
            for cid, c in combatants.items()
            if c["character_id"] == self.alice.id
        )
        bob_cid = next(
            cid
            for cid, c in combatants.items()
            if c["character_id"] == self.bob.id
        )
        self.assertIn("hp_current", combatants[alice_cid])
        self.assertNotIn("hp_current", combatants[bob_cid])

    def test_advance_turn_preparing_combat_rejected(self) -> None:
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "preparing-adv",
            },
        )
        combat_id = created.json()["combat_id"]
        response = self.client.post(f"/v1/combats/{combat_id}/advance-turn")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(_api_error(response)["code"], "COMBAT_STATUS_INVALID")

    def test_advance_turn_unknown_combat_404(self) -> None:
        response = self.client.post("/v1/combats/99999/advance-turn")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_api_error(response)["code"], "COMBAT_NOT_FOUND")


class TestApiV1CombatRead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="read_alice", name="Alice", dex=16)
        self.bob = _fighter(char_id="read_bob", name="Bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([18, 6]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _active_combat_id(self) -> int:
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.alice.id, self.bob.id],
                "channel_id": "combat-read",
            },
        )
        combat_id = created.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_id}/activate")
        return combat_id

    def _combatant_ids_by_character(
        self,
        combatants: dict,
        character_id: str,
    ) -> str:
        return next(
            cid
            for cid, c in combatants.items()
            if c["character_id"] == character_id
        )

    def test_get_combat_without_viewer_shows_all_hp(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.get(f"/v1/combats/{combat_id}")
        self.assertEqual(response.status_code, 200)
        combatants = response.json()["combatants"]
        for cid in combatants:
            self.assertIn("hp_current", combatants[cid])

    def test_get_combat_with_viewer_hides_other_hp(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.alice.id},
        )
        self.assertEqual(response.status_code, 200)
        combatants = response.json()["combatants"]
        alice_cid = self._combatant_ids_by_character(combatants, self.alice.id)
        bob_cid = self._combatant_ids_by_character(combatants, self.bob.id)
        self.assertIn("hp_current", combatants[alice_cid])
        self.assertNotIn("hp_current", combatants[bob_cid])

    def test_get_combat_includes_abilities_dm_view(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.get(f"/v1/combats/{combat_id}")
        self.assertEqual(response.status_code, 200)
        for combatant in response.json()["combatants"].values():
            self.assertIn("ability_scores", combatant)
            self.assertIn("ability_modifiers", combatant)
            self.assertIn("ability_labels", combatant)
            self.assertGreaterEqual(combatant["ability_scores"]["str"], 16)
            self.assertGreaterEqual(combatant["ability_modifiers"]["str"], 3)

    def test_get_combat_viewer_own_abilities_only(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.alice.id},
        )
        self.assertEqual(response.status_code, 200)
        combatants = response.json()["combatants"]
        alice_cid = self._combatant_ids_by_character(combatants, self.alice.id)
        bob_cid = self._combatant_ids_by_character(combatants, self.bob.id)
        self.assertIn("ability_scores", combatants[alice_cid])
        self.assertEqual(combatants[alice_cid]["ability_modifiers"]["str"], 3)
        self.assertNotIn("ability_scores", combatants[bob_cid])

    def test_get_and_advance_turn_viewer_parity(self) -> None:
        combat_id = self._active_combat_id()
        get_view = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.alice.id},
        ).json()
        adv_view = self.client.post(
            f"/v1/combats/{combat_id}/advance-turn",
            params={"viewer": self.alice.id},
        ).json()
        alice_cid = self._combatant_ids_by_character(
            get_view["combatants"],
            self.alice.id,
        )
        bob_cid = self._combatant_ids_by_character(
            get_view["combatants"],
            self.bob.id,
        )
        for label, payload in (("GET", get_view), ("advance-turn", adv_view)):
            with self.subTest(route=label):
                combatants = payload["combatants"]
                self.assertIn("hp_current", combatants[alice_cid])
                self.assertNotIn("hp_current", combatants[bob_cid])

    def test_get_empty_viewer_is_dm_view(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": "   "},
        )
        self.assertEqual(response.status_code, 200)
        combatants = response.json()["combatants"]
        for cid in combatants:
            self.assertIn("hp_current", combatants[cid])

    def test_get_unknown_viewer_404(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": "nobody_here"},
        )
        self.assertEqual(response.status_code, 404)
        err = _api_error(response)
        self.assertEqual(err["code"], "VIEWER_NOT_IN_COMBAT")
        self.assertEqual(err["details"]["character_id"], "nobody_here")

    def test_advance_turn_unknown_viewer_404(self) -> None:
        combat_id = self._active_combat_id()
        response = self.client.post(
            f"/v1/combats/{combat_id}/advance-turn",
            params={"viewer": "nobody_here"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_api_error(response)["code"], "VIEWER_NOT_IN_COMBAT")


def _ranger(*, char_id: str, name: str = "Rodeur") -> Character:
    return Character(
        id=char_id,
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


def _cleric(*, char_id: str, name: str = "Clerc") -> Character:
    return Character(
        id=char_id,
        owner_id="113",
        guild_id="guild1",
        name=name,
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
                "spells_prepared": ["bless", "burning_hands", "cure_wounds"],
                "slots_used": {},
            }
        },
    )


class TestApiV1CombatCast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.ranger = _ranger(char_id="cast_ranger", name="Alice")
        self.cleric = _cleric(char_id="cast_cleric", name="Bob")
        self.wizard = Character(
            id="cast_wizard",
            owner_id="112",
            guild_id="guild1",
            name="Charlie",
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
                    "spells_prepared": ["magic_missile", "shield"],
                    "slots_used": {},
                }
            },
        )
        for char in (self.ranger, self.cleric, self.wizard):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_initiative_rng=InitiativeSequence([18, 14, 6]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _create_and_activate(self, channel_id: str = "cast-test") -> dict:
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [
                    self.ranger.id,
                    self.cleric.id,
                    self.wizard.id,
                ],
                "channel_id": channel_id,
            },
        )
        self.assertEqual(created.status_code, 200)
        payload = created.json()
        combat_id = payload["combat_id"]
        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(activated.status_code, 200)
        return activated.json()

    def _combatant_for_character(self, state: dict, character_id: str) -> str:
        for combatant_id, block in state["combatants"].items():
            if block["character_id"] == character_id:
                return combatant_id
        raise AssertionError(f"combattant absent pour {character_id}")

    def test_cast_hunters_mark_returns_combat_state(self) -> None:
        state = self._create_and_activate()
        combat_id = state["combat_id"]
        ranger_id = self._combatant_for_character(state, self.ranger.id)
        wizard_id = self._combatant_for_character(state, self.wizard.id)

        response = self.client.post(
            f"/v1/combats/{combat_id}/cast",
            json={
                "caster_id": ranger_id,
                "spell_id": "hunters_mark",
                "target_ids": [wizard_id],
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "active")
        self.assertTrue(
            any(
                effect["effect_id"] == "hunters_mark"
                and effect["target_id"] == wizard_id
                for effect in data["active_effects"]
            )
        )

    def test_cast_bless_multi_target(self) -> None:
        state = self._create_and_activate(channel_id="cast-bless")
        combat_id = state["combat_id"]
        cleric_id = self._combatant_for_character(state, self.cleric.id)
        ranger_id = self._combatant_for_character(state, self.ranger.id)
        wizard_id = self._combatant_for_character(state, self.wizard.id)

        # Le clerc n'est pas forcément en tête — avancer jusqu'à son tour.
        while state["combatants"][state["initiative_order"][state["turn_index"]]][
            "character_id"
        ] != self.cleric.id:
            advance = self.client.post(f"/v1/combats/{combat_id}/advance-turn")
            self.assertEqual(advance.status_code, 200)
            state = advance.json()

        response = self.client.post(
            f"/v1/combats/{combat_id}/cast",
            json={
                "caster_id": cleric_id,
                "spell_id": "bless",
                "target_ids": [ranger_id, wizard_id],
            },
        )
        self.assertEqual(response.status_code, 200)
        blessed_targets = {
            effect["target_id"]
            for effect in response.json()["active_effects"]
            if effect["effect_id"] == "blessed"
        }
        self.assertEqual(blessed_targets, {ranger_id, wizard_id})

    def test_cast_preparing_combat_rejected(self) -> None:
        created = self.client.post(
            "/v1/combats",
            json={
                "character_ids": [self.ranger.id, self.wizard.id],
                "channel_id": "cast-preparing",
            },
        )
        combat_id = created.json()["combat_id"]
        ranger_id, wizard_id = list(created.json()["combatants"])

        response = self.client.post(
            f"/v1/combats/{combat_id}/cast",
            json={
                "caster_id": ranger_id,
                "spell_id": "hunters_mark",
                "target_ids": [wizard_id],
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(_api_error(response)["code"], "COMBAT_STATUS_INVALID")

    def test_cast_invalid_target_count_rejected(self) -> None:
        state = self._create_and_activate(channel_id="cast-invalid-targets")
        combat_id = state["combat_id"]
        ranger_id = self._combatant_for_character(state, self.ranger.id)
        wizard_id = self._combatant_for_character(state, self.wizard.id)

        response = self.client.post(
            f"/v1/combats/{combat_id}/cast",
            json={
                "caster_id": ranger_id,
                "spell_id": "hunters_mark",
                "target_ids": [wizard_id, ranger_id],
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(_api_error(response)["code"], "SPELL_CAST_REJECTED")

    def test_cast_unknown_combatant_404(self) -> None:
        state = self._create_and_activate(channel_id="cast-unknown-combatant")
        combat_id = state["combat_id"]
        wizard_id = self._combatant_for_character(state, self.wizard.id)

        response = self.client.post(
            f"/v1/combats/{combat_id}/cast",
            json={
                "caster_id": "ghost_combatant",
                "spell_id": "hunters_mark",
                "target_ids": [wizard_id],
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_api_error(response)["code"], "COMBATANT_NOT_FOUND")

    def test_get_combat_viewer_includes_castable_spells(self) -> None:
        state = self._create_and_activate(channel_id="cast-viewer-dto")
        combat_id = state["combat_id"]

        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.ranger.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("viewer", data)
        self.assertEqual(data["viewer"]["character_id"], self.ranger.id)
        self.assertIn("hunters_mark", data["viewer"]["castable_spells"])

    def test_get_combat_viewer_empty_when_not_own_turn(self) -> None:
        state = self._create_and_activate(channel_id="cast-viewer-turn")
        combat_id = state["combat_id"]
        cleric_id = self._combatant_for_character(state, self.cleric.id)

        while state["combatants"][state["initiative_order"][state["turn_index"]]][
            "character_id"
        ] != self.cleric.id:
            advance = self.client.post(f"/v1/combats/{combat_id}/advance-turn")
            self.assertEqual(advance.status_code, 200)
            state = advance.json()

        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.ranger.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["viewer"]["castable_spells"], [])

    def test_get_combat_viewer_includes_reaction_spells_off_turn(self) -> None:
        state = self._create_and_activate(channel_id="cast-viewer-shield")
        combat_id = state["combat_id"]

        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.wizard.id},
        )
        self.assertEqual(response.status_code, 200)
        viewer = response.json()["viewer"]
        self.assertEqual(viewer["castable_spells"], [])
        self.assertIn("shield", viewer["castable_reaction_spells"])

    def test_get_combat_viewer_includes_spell_slots(self) -> None:
        state = self._create_and_activate(channel_id="cast-viewer-slots")
        combat_id = state["combat_id"]

        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.wizard.id},
        )
        self.assertEqual(response.status_code, 200)
        sc = response.json()["viewer"]["spellcasting"]
        self.assertIsNotNone(sc)
        self.assertIn("1", sc["slots_max"])
        self.assertIn("1", sc["slots_remaining"])
        self.assertGreater(sc["slots_max"]["1"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

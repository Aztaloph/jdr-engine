# tests/unit/test_api_v1_auth.py
"""Lot B1 auth — sessions, garde-fous API (BRIEF_LOT_B1_AUTH.md T1–T12)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from interfaces.api.app import create_app
from interfaces.api.combat_ws import WS_AUTH_REQUIRED
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


def _fighter(*, char_id: str, name: str, owner_id: str, dex: int = 12) -> Character:
    return Character(
        id=char_id,
        owner_id=owner_id,
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


class TestApiV1Auth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="auth_alice", name="Alice", owner_id="owner_alice", dex=16)
        self.bob = _fighter(char_id="auth_bob", name="Bob", owner_id="owner_bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                auth_enabled=True,
                combat_initiative_rng=InitiativeSequence([15, 10, 12, 8]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _login(self, user_id: str, role: str) -> str:
        response = self.client.post(
            "/v1/auth/dev-login",
            json={"user_id": user_id, "role": role},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    def _headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _create_active_combat(self, gm_token: str) -> int:
        create = self.client.post(
            "/v1/combats",
            json={"character_ids": [self.alice.id, self.bob.id]},
            headers=self._headers(gm_token),
        )
        self.assertEqual(create.status_code, 200, create.text)
        combat_id = int(create.json()["combat_id"])
        activate = self.client.post(
            f"/v1/combats/{combat_id}/activate",
            headers=self._headers(gm_token),
        )
        self.assertEqual(activate.status_code, 200, activate.text)
        return combat_id

    def _combatant_id(self, payload: dict, character_id: str) -> str:
        for cid, combatant in payload["combatants"].items():
            if combatant["character_id"] == character_id:
                return cid
        raise AssertionError(f"combattant absent pour {character_id}")

    def test_t1_attack_without_token_401(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        state = self.client.get(
            f"/v1/combats/{combat_id}",
            headers=self._headers(gm_token),
        ).json()
        alice_cid = self._combatant_id(state, self.alice.id)
        bob_cid = self._combatant_id(state, self.bob.id)
        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            params={"viewer": self.alice.id},
            json={
                "attacker_id": alice_cid,
                "target_id": bob_cid,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(_api_error(response)["code"], "AUTH_REQUIRED")

    def test_t2_player_cannot_attack_as_other_combatant(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        state = self.client.get(
            f"/v1/combats/{combat_id}",
            headers=self._headers(gm_token),
        ).json()
        alice_cid = self._combatant_id(state, self.alice.id)
        bob_cid = self._combatant_id(state, self.bob.id)
        alice_token = self._login(self.alice.owner_id, "player")
        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            params={"viewer": self.alice.id},
            headers=self._headers(alice_token),
            json={
                "attacker_id": bob_cid,
                "target_id": alice_cid,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(_api_error(response)["code"], "COMBATANT_NOT_OWNED")

    def test_t3_player_viewer_not_allowed(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        alice_token = self._login(self.alice.owner_id, "player")
        response = self.client.get(
            f"/v1/combats/{combat_id}",
            params={"viewer": self.bob.id},
            headers=self._headers(alice_token),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(_api_error(response)["code"], "VIEWER_NOT_ALLOWED")

    def test_t4_player_legitimate_attack(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        state = self.client.get(
            f"/v1/combats/{combat_id}",
            headers=self._headers(gm_token),
        ).json()
        alice_cid = self._combatant_id(state, self.alice.id)
        bob_cid = self._combatant_id(state, self.bob.id)
        if state["current_combatant_id"] != alice_cid:
            advance = self.client.post(
                f"/v1/combats/{combat_id}/advance-turn",
                headers=self._headers(gm_token),
            )
            self.assertEqual(advance.status_code, 200, advance.text)
            state = advance.json()
        alice_token = self._login(self.alice.owner_id, "player")
        response = self.client.post(
            f"/v1/combats/{combat_id}/attack",
            params={"viewer": self.alice.id},
            headers=self._headers(alice_token),
            json={
                "attacker_id": alice_cid,
                "target_id": bob_cid,
                "weapon_id": "longsword",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_t5_player_advance_turn_forbidden(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        alice_token = self._login(self.alice.owner_id, "player")
        response = self.client.post(
            f"/v1/combats/{combat_id}/advance-turn",
            params={"viewer": self.alice.id},
            headers=self._headers(alice_token),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(_api_error(response)["code"], "GM_REQUIRED")

    def test_t6_gm_table_actions(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        advance = self.client.post(
            f"/v1/combats/{combat_id}/advance-turn",
            headers=self._headers(gm_token),
        )
        self.assertEqual(advance.status_code, 200, advance.text)
        close = self.client.post(
            f"/v1/combats/{combat_id}/close",
            headers=self._headers(gm_token),
        )
        self.assertEqual(close.status_code, 200, close.text)

    def test_t7_player_character_list_filtered(self) -> None:
        gm_token = self._login("gm1", "gm")
        gm_list = self.client.get("/v1/characters", headers=self._headers(gm_token))
        self.assertEqual(gm_list.status_code, 200)
        self.assertEqual(len(gm_list.json()["characters"]), 2)
        alice_token = self._login(self.alice.owner_id, "player")
        player_list = self.client.get(
            "/v1/characters",
            headers=self._headers(alice_token),
        )
        self.assertEqual(player_list.status_code, 200)
        ids = {row["character_id"] for row in player_list.json()["characters"]}
        self.assertEqual(ids, {self.alice.id})

    def test_t8_ws_without_token_closes_4401(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        with self.client.websocket_connect(
            f"/v1/combats/{combat_id}/ws?viewer={self.alice.id}",
        ) as ws:
            with self.assertRaises(WebSocketDisconnect) as ctx:
                ws.receive_text()
            self.assertEqual(ctx.exception.code, WS_AUTH_REQUIRED)

    def test_t9_ws_player_viewer_connected(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        alice_token = self._login(self.alice.owner_id, "player")
        with self.client.websocket_connect(
            f"/v1/combats/{combat_id}/ws"
            f"?token={alice_token}&viewer={self.alice.id}",
        ) as ws:
            message = ws.receive_json()
            self.assertEqual(message["type"], "connected")

    def test_t10_auth_off_unchanged(self) -> None:
        client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                auth_enabled=False,
                combat_initiative_rng=InitiativeSequence([15, 10]),
            )
        )
        create = client.post(
            "/v1/combats",
            json={"character_ids": [self.alice.id, self.bob.id]},
        )
        self.assertEqual(create.status_code, 200, create.text)

    def test_t11_player_sync_own_combatant(self) -> None:
        gm_token = self._login("gm1", "gm")
        combat_id = self._create_active_combat(gm_token)
        state = self.client.get(
            f"/v1/combats/{combat_id}",
            headers=self._headers(gm_token),
        ).json()
        alice_cid = self._combatant_id(state, self.alice.id)
        alice_token = self._login(self.alice.owner_id, "player")
        response = self.client.post(
            f"/v1/combats/{combat_id}/sync-combatant",
            params={"viewer": self.alice.id},
            headers=self._headers(alice_token),
            json={"combatant_id": alice_cid},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_t12_player_long_rest_own_character(self) -> None:
        alice_token = self._login(self.alice.owner_id, "player")
        response = self.client.post(
            f"/v1/characters/{self.alice.id}/long-rest",
            headers=self._headers(alice_token),
        )
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()

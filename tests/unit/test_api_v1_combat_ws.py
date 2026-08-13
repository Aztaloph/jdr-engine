# tests/unit/test_api_v1_combat_ws.py
"""Lot 6c — WebSocket combat v1 (CONTRAT_WS.md §6.4 T1–T7)."""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from interfaces.api.app import create_app
from interfaces.api.combat_ws import WS_COMBAT_NOT_FOUND
from jdr_engine.domain.character.ability_scores import AbilityScores
from jdr_engine.domain.character.character import Character
from jdr_engine.persistence.database import init_database
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)
from jdr_engine.rules import RuleEngine


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


class RandSequence:
    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def __call__(self, low: int, high: int) -> int:
        if not self._values:
            raise RuntimeError("RandSequence épuisé")
        return self._values.pop(0)


class TestApiV1CombatWebSocket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.repo = SqliteCharacterRepository(self.db_path)
        self.alice = _fighter(char_id="ws_alice", name="Alice", dex=16)
        self.bob = _fighter(char_id="ws_bob", name="Bob", dex=10)
        for char in (self.alice, self.bob):
            self.repo.save(char)
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                combat_attack_rng=RandSequence([14, 5]),
            )
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _create_and_activate(self) -> tuple[int, dict]:
        created = self.client.post(
            "/v1/combats",
            json={"character_ids": [self.alice.id, self.bob.id]},
        )
        self.assertEqual(created.status_code, 200)
        combat_id = created.json()["combat_id"]
        activated = self.client.post(f"/v1/combats/{combat_id}/activate")
        self.assertEqual(activated.status_code, 200)
        return combat_id, activated.json()

    def _ws_url(self, combat_id: int, viewer: str | None = None) -> str:
        if viewer:
            return f"/v1/combats/{combat_id}/ws?viewer={viewer}"
        return f"/v1/combats/{combat_id}/ws"

    def test_t1_connect_existing_combat_receives_connected(self):
        combat_id, _body = self._create_and_activate()
        with self.client.websocket_connect(self._ws_url(combat_id)) as ws:
            msg = ws.receive_json()
        self.assertEqual(msg["type"], "connected")
        self.assertEqual(msg["combat_id"], combat_id)
        self.assertIn("timestamp", msg)
        self.assertIsNone(msg["payload"]["viewer"])

    def test_t2_move_broadcasts_position_changed(self):
        combat_id, body = self._create_and_activate()
        current_id = body["current_combatant_id"]
        pos = body["combatants"][current_id]["position"]
        with self.client.websocket_connect(self._ws_url(combat_id)) as ws:
            connected = ws.receive_json()
            self.assertEqual(connected["type"], "connected")
            moved = self.client.post(
                f"/v1/combats/{combat_id}/move",
                json={
                    "combatant_id": current_id,
                    "x": pos["x"],
                    "y": pos["y"] + 1,
                },
            )
            self.assertEqual(moved.status_code, 200, moved.text)
            event = ws.receive_json()
        self.assertEqual(event["type"], "position_changed")
        self.assertEqual(event["combat_id"], combat_id)
        self.assertEqual(event["payload"]["combatant_id"], current_id)
        self.assertEqual(event["payload"]["to"], {"x": pos["x"], "y": pos["y"] + 1})

    def test_t3_attack_broadcasts_combat_state_invalidated(self):
        combat_id, body = self._create_and_activate()
        attacker_id = body["current_combatant_id"]
        target_id = next(
            cid for cid in body["initiative_order"] if cid != attacker_id
        )
        with self.client.websocket_connect(self._ws_url(combat_id)) as ws:
            self.assertEqual(ws.receive_json()["type"], "connected")
            attack = self.client.post(
                f"/v1/combats/{combat_id}/attack",
                json={
                    "attacker_id": attacker_id,
                    "target_id": target_id,
                    "weapon_id": "longsword",
                },
            )
            self.assertEqual(attack.status_code, 200, attack.text)
            seen_invalidated = False
            for _ in range(6):
                event = ws.receive_json()
                if event["type"] == "combat_state_invalidated":
                    seen_invalidated = True
                    self.assertEqual(event["combat_id"], combat_id)
                    self.assertIsInstance(event["payload"]["source_event"], str)
                    break
            self.assertTrue(seen_invalidated)

    def test_t4_close_sends_combat_ended_and_closes_1000(self):
        combat_id, _body = self._create_and_activate()
        with self.client.websocket_connect(self._ws_url(combat_id)) as ws:
            self.assertEqual(ws.receive_json()["type"], "connected")
            closed = self.client.post(f"/v1/combats/{combat_id}/close")
            self.assertEqual(closed.status_code, 200)
            event = ws.receive_json()
            self.assertEqual(event["type"], "combat_ended")
            self.assertEqual(event["payload"]["reason"], "closed")
            with self.assertRaises(WebSocketDisconnect) as ctx:
                ws.receive_text()
            self.assertEqual(ctx.exception.code, 1000)

    def test_t5_missing_combat_closes_4404(self):
        with self.client.websocket_connect("/v1/combats/99999/ws") as ws:
            with self.assertRaises(WebSocketDisconnect) as ctx:
                ws.receive_text()
            self.assertEqual(ctx.exception.code, WS_COMBAT_NOT_FOUND)

    def test_t6_two_connections_same_combat_both_receive_broadcast(self):
        combat_id, body = self._create_and_activate()
        current_id = body["current_combatant_id"]
        pos = body["combatants"][current_id]["position"]
        with self.client.websocket_connect(self._ws_url(combat_id)) as ws1:
            with self.client.websocket_connect(self._ws_url(combat_id)) as ws2:
                self.assertEqual(ws1.receive_json()["type"], "connected")
                self.assertEqual(ws2.receive_json()["type"], "connected")
                moved = self.client.post(
                    f"/v1/combats/{combat_id}/move",
                    json={
                        "combatant_id": current_id,
                        "x": pos["x"],
                        "y": pos["y"] + 1,
                    },
                )
                self.assertEqual(moved.status_code, 200, moved.text)
                event1 = ws1.receive_json()
                event2 = ws2.receive_json()
        self.assertEqual(event1, event2)
        self.assertEqual(event1["type"], "position_changed")

    def test_t7_isolated_combat_id_no_cross_leak(self):
        created_a = self.client.post(
            "/v1/combats",
            json={"character_ids": [self.alice.id, self.bob.id]},
        )
        self.assertEqual(created_a.status_code, 200)
        combat_a = created_a.json()["combat_id"]
        self.client.post(f"/v1/combats/{combat_a}/activate")

        carol = _fighter(char_id="ws_carol", name="Carol", dex=12)
        dave = _fighter(char_id="ws_dave", name="Dave", dex=8)
        self.repo.save(carol)
        self.repo.save(dave)
        created_b = self.client.post(
            "/v1/combats",
            json={"character_ids": [carol.id, dave.id]},
        )
        self.assertEqual(created_b.status_code, 200)
        combat_b = created_b.json()["combat_id"]
        activated_b = self.client.post(f"/v1/combats/{combat_b}/activate")
        self.assertEqual(activated_b.status_code, 200)
        body_b = activated_b.json()
        current_b = body_b["current_combatant_id"]
        pos_b = body_b["combatants"][current_b]["position"]

        with self.client.websocket_connect(self._ws_url(combat_a)) as ws_a:
            self.assertEqual(ws_a.receive_json()["type"], "connected")
            moved = self.client.post(
                f"/v1/combats/{combat_b}/move",
                json={
                    "combatant_id": current_b,
                    "x": pos_b["x"],
                    "y": pos_b["y"] + 1,
                },
            )
            self.assertEqual(moved.status_code, 200, moved.text)

            leak = threading.Event()
            leaked: list[dict] = []

            def _reader() -> None:
                try:
                    leaked.append(ws_a.receive_json())
                    leak.set()
                except Exception:
                    pass

            reader = threading.Thread(target=_reader, daemon=True)
            reader.start()
            leak.wait(timeout=0.5)
            self.assertFalse(leak.is_set(), msg=f"message leak: {leaked}")

    def test_connected_echoes_viewer_query(self):
        combat_id, _body = self._create_and_activate()
        with self.client.websocket_connect(
            self._ws_url(combat_id, viewer=self.alice.id)
        ) as ws:
            msg = ws.receive_json()
        self.assertEqual(msg["payload"]["viewer"], self.alice.id)


if __name__ == "__main__":
    unittest.main()

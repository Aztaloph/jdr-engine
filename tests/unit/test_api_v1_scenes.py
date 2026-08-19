# tests/unit/test_api_v1_scenes.py
"""Lot Sb — CRUD API scènes (BRIEF_JALON_S.md §9.2)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.api.app import create_app
from jdr_engine.persistence.database import init_database
from jdr_engine.rules import RuleEngine

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "scenes" / "fixtures"


def _api_error(response) -> dict:
    payload = response.json()
    assert "error" in payload, payload
    return payload["error"]


def _engine() -> RuleEngine:
    if not Path("compendium/dnd5e").is_dir():
        raise unittest.SkipTest("compendium absent")
    return RuleEngine.load("dnd5e", validate=True, strict=True)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestApiV1Scenes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _engine()

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = init_database(Path(self._tmpdir.name) / "bot.db")
        self.client = TestClient(
            create_app(
                engine=self.engine,
                db_path=self.db_path,
                auth_enabled=True,
            )
        )
        self.fixture = _load_fixture("test-sd-taverne.json")

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

    def test_t1_post_scene_gm(self) -> None:
        token = self._login("gm_scenes", "gm")
        response = self.client.post(
            "/v1/scenes",
            json=self.fixture,
            headers=self._headers(token),
        )
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertIn("id", payload)
        self.assertEqual(payload["owner_id"], "gm_scenes")
        self.assertEqual(payload["scene"]["name"], self.fixture["name"])

    def test_t2_post_scene_player_forbidden(self) -> None:
        token = self._login("player_scenes", "player")
        response = self.client.post(
            "/v1/scenes",
            json=self.fixture,
            headers=self._headers(token),
        )
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(_api_error(response)["code"], "GM_REQUIRED")

    def test_t3_get_round_trip_identical(self) -> None:
        gm_token = self._login("gm_roundtrip", "gm")
        create = self.client.post(
            "/v1/scenes",
            json=self.fixture,
            headers=self._headers(gm_token),
        )
        self.assertEqual(create.status_code, 201, create.text)
        scene_id = create.json()["id"]
        player_token = self._login("player_read", "player")
        get_response = self.client.get(
            f"/v1/scenes/{scene_id}",
            headers=self._headers(player_token),
        )
        self.assertEqual(get_response.status_code, 200, get_response.text)
        self.assertEqual(get_response.json()["scene"], create.json()["scene"])

        update = self.client.put(
            f"/v1/scenes/{scene_id}",
            json=_load_fixture("test-se-dungeon.json"),
            headers=self._headers(gm_token),
        )
        self.assertEqual(update.status_code, 200, update.text)
        again = self.client.get(
            f"/v1/scenes/{scene_id}",
            headers=self._headers(gm_token),
        )
        self.assertEqual(again.json()["scene"], update.json()["scene"])

    def test_t4_export_autonomous_blob(self) -> None:
        gm_token = self._login("gm_export", "gm")
        create = self.client.post(
            "/v1/scenes",
            json=_load_fixture("test-se-dungeon.json"),
            headers=self._headers(gm_token),
        )
        scene_id = create.json()["id"]
        export = self.client.get(
            f"/v1/scenes/{scene_id}/export",
            headers=self._headers(gm_token),
        )
        self.assertEqual(export.status_code, 200, export.text)
        blob = export.json()
        self.assertEqual(blob, create.json()["scene"])
        self.assertEqual(blob["schema_version"], 1)
        self.assertNotIn("owner_id", blob)

    def test_list_scenes_requires_auth_when_enabled(self) -> None:
        response = self.client.get("/v1/scenes")
        self.assertEqual(response.status_code, 401, response.text)

    def test_invalid_scene_rejected(self) -> None:
        gm_token = self._login("gm_invalid", "gm")
        bad = dict(self.fixture)
        bad["objects"][0]["kind"] = "barrel"
        response = self.client.post(
            "/v1/scenes",
            json=bad,
            headers=self._headers(gm_token),
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(_api_error(response)["code"], "SCENE_INVALID")

    def test_delete_scene(self) -> None:
        gm_token = self._login("gm_delete", "gm")
        create = self.client.post(
            "/v1/scenes",
            json=self.fixture,
            headers=self._headers(gm_token),
        )
        scene_id = create.json()["id"]
        delete = self.client.delete(
            f"/v1/scenes/{scene_id}",
            headers=self._headers(gm_token),
        )
        self.assertEqual(delete.status_code, 200, delete.text)
        missing = self.client.get(
            f"/v1/scenes/{scene_id}",
            headers=self._headers(gm_token),
        )
        self.assertEqual(missing.status_code, 404, missing.text)


if __name__ == "__main__":
    unittest.main()

# tests/unit/test_scenes_format.py
"""Lot Sa — format scene.json v1."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from interfaces.scenes.footprint import effective_footprint
from interfaces.scenes.validate import parse_scene_document, validate_scene_document

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "scenes" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestScenesFormat(unittest.TestCase):
    def test_t1_fixture_valide(self) -> None:
        for path in FIXTURES.glob("*.json"):
            with self.subTest(path=path.name):
                report = validate_scene_document(_load(path.name))
                self.assertTrue(report.ok, report.issues)

    def test_t2_kind_inconnu(self) -> None:
        data = _load("test-sd-taverne.json")
        data["objects"][0]["kind"] = "barrel"
        report = validate_scene_document(data)
        self.assertFalse(report.ok)
        codes = [issue.code for issue in report.issues]
        self.assertIn("INVALID_KIND", codes)

    def test_t3_objet_hors_grille(self) -> None:
        data = _load("test-sd-taverne.json")
        data["objects"].append(
            {
                "id": "overflow",
                "kind": "torch",
                "x": 15,
                "y": 9,
                "width": 2,
                "height": 2,
                "quarter_turns": 0,
                "asset_id": None,
            }
        )
        report = validate_scene_document(data)
        self.assertFalse(report.ok)
        codes = [issue.code for issue in report.issues]
        self.assertIn("OUT_OF_GRID", codes)

    def test_t4_quarter_turns_impair_echange_emprise(self) -> None:
        self.assertEqual(effective_footprint(2, 1, 0), (2, 1))
        self.assertEqual(effective_footprint(2, 1, 1), (1, 2))
        self.assertEqual(effective_footprint(2, 3, 3), (3, 2))

        data = _load("test-se-dungeon.json")
        wall = next(obj for obj in data["objects"] if obj["id"] == "wall-rotated")
        self.assertEqual(wall["quarter_turns"], 1)
        report = validate_scene_document(data)
        self.assertTrue(report.ok, report.issues)

    def test_t5_round_trip(self) -> None:
        original = _load("test-se-dungeon.json")
        canonical = parse_scene_document(original)
        again = parse_scene_document(copy.deepcopy(canonical))
        self.assertEqual(canonical, again)

    def test_chemin_absolu_interdit(self) -> None:
        data = _load("test-sd-taverne.json")
        data["objects"][0]["asset_id"] = r"C:\assets\wall.png"
        report = validate_scene_document(data)
        self.assertFalse(report.ok)
        codes = [issue.code for issue in report.issues]
        self.assertIn("ABSOLUTE_PATH", codes)


if __name__ == "__main__":
    unittest.main()

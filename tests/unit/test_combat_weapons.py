# tests/unit/test_combat_weapons.py
"""Lot 2 API — résolution ``weapon_id`` compendium (liste fermée §10.5)."""
from __future__ import annotations

import unittest

from jdr_engine.rules.combat.weapons import UnknownWeaponError, resolve_weapon


class TestResolveWeapon(unittest.TestCase):
    def test_longsword_melee_notation(self) -> None:
        profile = resolve_weapon("longsword")
        self.assertEqual(profile.weapon_id, "longsword")
        self.assertEqual(profile.damage_dice, "1d8")
        self.assertTrue(profile.melee_weapon)
        self.assertFalse(profile.ranged_weapon)
        self.assertFalse(profile.finesse_weapon)

    def test_shortsword_finesse_melee(self) -> None:
        profile = resolve_weapon("ShortSword")
        self.assertEqual(profile.weapon_id, "shortsword")
        self.assertEqual(profile.damage_dice, "1d6")
        self.assertTrue(profile.melee_weapon)
        self.assertFalse(profile.ranged_weapon)
        self.assertTrue(profile.finesse_weapon)

    def test_shortbow_ranged(self) -> None:
        profile = resolve_weapon(" shortbow ")
        self.assertEqual(profile.weapon_id, "shortbow")
        self.assertEqual(profile.damage_dice, "1d6")
        self.assertFalse(profile.melee_weapon)
        self.assertTrue(profile.ranged_weapon)

    def test_longbow_ranged(self) -> None:
        profile = resolve_weapon("longbow")
        self.assertEqual(profile.damage_dice, "1d8")
        self.assertFalse(profile.melee_weapon)
        self.assertTrue(profile.ranged_weapon)

    def test_unknown_weapon_raises_explicit_error(self) -> None:
        with self.assertRaises(UnknownWeaponError) as ctx:
            resolve_weapon("greatsword")
        exc = ctx.exception
        self.assertEqual(exc.weapon_id, "greatsword")
        self.assertEqual(exc.code, "WEAPON_UNKNOWN")
        self.assertIn("greatsword", str(exc))

    def test_empty_weapon_id_raises(self) -> None:
        with self.assertRaises(UnknownWeaponError) as ctx:
            resolve_weapon("   ")
        self.assertEqual(ctx.exception.weapon_id, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

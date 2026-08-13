# jdr_engine/rules/combat/weapons.py
"""
Résolution d'arme par id compendium — lot 2 API.

Dette §10.5 CONTRAT : liste fermée transitoire tant que le catalogue
``compendium/…/weapons/`` n'existe pas. Ce module deviendra un adaptateur
compendium ; la table interne disparaîtra à ce moment-là.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "UnknownWeaponError",
    "WeaponProfile",
    "resolve_weapon",
    "weapon_attack_range_ft",
]


class UnknownWeaponError(Exception):
    """Arme inconnue — mappée ``WEAPON_UNKNOWN`` côté API (contrat §3.3, commit 3)."""

    code = "WEAPON_UNKNOWN"

    def __init__(self, weapon_id: str) -> None:
        self.weapon_id = str(weapon_id).strip()
        super().__init__(f"Arme inconnue : {self.weapon_id!r}.")


@dataclass(frozen=True)
class WeaponProfile:
    """Propriétés combat dérivées d'une arme (notation + contexte de jet)."""

    weapon_id: str
    damage_dice: str
    melee_weapon: bool
    ranged_weapon: bool
    finesse_weapon: bool = False
    normal_range_ft: int = 5


def weapon_attack_range_ft(profile: WeaponProfile) -> int:
    """Portée normale en pieds pour une attaque (mêlée 5 ft, distance ``normal_range_ft``)."""
    if profile.ranged_weapon and not profile.melee_weapon:
        return profile.normal_range_ft
    return 5


_WEAPONS_BY_ID: dict[str, WeaponProfile] = {
    "longsword": WeaponProfile(
        weapon_id="longsword",
        damage_dice="1d8",
        melee_weapon=True,
        ranged_weapon=False,
    ),
    "shortsword": WeaponProfile(
        weapon_id="shortsword",
        damage_dice="1d6",
        melee_weapon=True,
        ranged_weapon=False,
        finesse_weapon=True,
    ),
    "shortbow": WeaponProfile(
        weapon_id="shortbow",
        damage_dice="1d6",
        melee_weapon=False,
        ranged_weapon=True,
        normal_range_ft=80,
    ),
    "longbow": WeaponProfile(
        weapon_id="longbow",
        damage_dice="1d8",
        melee_weapon=False,
        ranged_weapon=True,
        normal_range_ft=150,
    ),
}


def resolve_weapon(weapon_id: str) -> WeaponProfile:
    """
    Résout un ``weapon_id`` compendium en notation de dégâts et propriétés de jet.

    Lève ``UnknownWeaponError`` si l'id est absent ou vide — jamais ``KeyError``.
    """
    normalized = str(weapon_id).strip().lower()
    if not normalized:
        raise UnknownWeaponError(weapon_id)
    profile = _WEAPONS_BY_ID.get(normalized)
    if profile is None:
        raise UnknownWeaponError(weapon_id)
    return profile

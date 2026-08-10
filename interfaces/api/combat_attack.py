# interfaces/api/combat_attack.py
"""Construction requête jet d'attaque API → ``D20RollRequest`` moteur."""
from __future__ import annotations

from jdr_engine.dice.d20 import D20RollRequest
from jdr_engine.domain.character.character import Character
from jdr_engine.rules.calculator import build_character_sheet
from jdr_engine.rules.combat.weapons import WeaponProfile
from jdr_engine.rules.engine import RuleEngine


def _attack_ability(weapon: WeaponProfile) -> str:
    return "dex" if weapon.ranged_weapon else "str"


def build_weapon_attack_request(
    character: Character,
    engine: RuleEngine,
    weapon: WeaponProfile,
    locale: str = "fr",
) -> D20RollRequest:
    """
    Dérive le contexte de jet d'attaque depuis la fiche et le profil d'arme.

    Modificateurs et maîtrise viennent du moteur (pas saisis librement par le client).
    """
    sheet = build_character_sheet(character, engine, locale=locale)
    ability = _attack_ability(weapon)
    ability_modifier = sheet.ability_modifiers[ability]
    is_proficient = bool(sheet.weapon_proficiencies)
    return D20RollRequest(
        roll_type="attack",
        ability_modifier=ability_modifier,
        proficiency_bonus=sheet.proficiency_bonus,
        is_proficient=is_proficient,
        ability=ability,
        melee_weapon=weapon.melee_weapon,
        ranged_weapon=weapon.ranged_weapon,
        finesse_weapon=weapon.finesse_weapon,
    )


def build_weapon_damage_notation(
    character: Character,
    engine: RuleEngine,
    weapon: WeaponProfile,
    locale: str = "fr",
) -> str:
    """Notation de dégâts arme + modificateur de caractéristique (fiche moteur)."""
    sheet = build_character_sheet(character, engine, locale=locale)
    modifier = sheet.ability_modifiers[_attack_ability(weapon)]
    dice = weapon.damage_dice
    if modifier == 0:
        return dice
    if modifier > 0:
        return f"{dice}+{modifier}"
    return f"{dice}{modifier}"

# jdr_engine/rules/combat/spell_ranges.py
"""
Portées mécaniques transitoires des sorts curated — lot 8.

Dette : remplacer par ``range_ft`` structuré dans le compendium YAML.
Source : libellés ``mechanics.range.en`` des 42 sorts SRD curated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SpellRangeKind = Literal["self", "touch", "feet"]

MELEE_TOUCH_RANGE_FT = 5


@dataclass(frozen=True)
class SpellRangeSpec:
    kind: SpellRangeKind
    feet: int = 0


_SPELL_RANGES: dict[str, SpellRangeSpec] = {
    "armor_of_agathys": SpellRangeSpec("self"),
    "banishment": SpellRangeSpec("feet", 60),
    "bless": SpellRangeSpec("feet", 30),
    "burning_hands": SpellRangeSpec("feet", 15),
    "chromatic_orb": SpellRangeSpec("feet", 90),
    "counterspell": SpellRangeSpec("feet", 60),
    "cure_wounds": SpellRangeSpec("touch"),
    "darkness": SpellRangeSpec("feet", 60),
    "detect_magic": SpellRangeSpec("self"),
    "dimension_door": SpellRangeSpec("feet", 500),
    "dispel_magic": SpellRangeSpec("feet", 120),
    "druidcraft": SpellRangeSpec("feet", 30),
    "eldritch_blast": SpellRangeSpec("feet", 120),
    "entangle": SpellRangeSpec("feet", 90),
    "faerie_fire": SpellRangeSpec("feet", 60),
    "fire_bolt": SpellRangeSpec("feet", 120),
    "fireball": SpellRangeSpec("feet", 120),
    "flaming_sphere": SpellRangeSpec("feet", 60),
    "fly": SpellRangeSpec("touch"),
    "guidance": SpellRangeSpec("touch"),
    "haste": SpellRangeSpec("feet", 30),
    "healing_word": SpellRangeSpec("feet", 60),
    "hellish_rebuke": SpellRangeSpec("feet", 60),
    "hex": SpellRangeSpec("feet", 90),
    "hunters_mark": SpellRangeSpec("feet", 90),
    "ice_storm": SpellRangeSpec("feet", 300),
    "inflict_wounds": SpellRangeSpec("touch"),
    "light": SpellRangeSpec("touch"),
    "lightning_bolt": SpellRangeSpec("feet", 100),
    "mage_armor": SpellRangeSpec("touch"),
    "mage_hand": SpellRangeSpec("feet", 30),
    "magic_missile": SpellRangeSpec("feet", 120),
    "polymorph": SpellRangeSpec("feet", 60),
    "prestidigitation": SpellRangeSpec("feet", 10),
    "produce_flame": SpellRangeSpec("self"),
    "ray_of_frost": SpellRangeSpec("feet", 60),
    "sacred_flame": SpellRangeSpec("feet", 60),
    "scorching_ray": SpellRangeSpec("feet", 120),
    "shield": SpellRangeSpec("self"),
    "spiritual_weapon": SpellRangeSpec("feet", 60),
    "thaumaturgy": SpellRangeSpec("feet", 30),
    "vicious_mockery": SpellRangeSpec("feet", 60),
}


class UnknownSpellRangeError(Exception):
    """Sort absent de la table transitoire."""

    def __init__(self, spell_id: str) -> None:
        self.spell_id = spell_id
        super().__init__(f"Portée combat inconnue pour le sort {spell_id!r}.")


def resolve_spell_range(spell_id: str) -> SpellRangeSpec:
    """Résout la portée mécanique d'un sort curated."""
    normalized = str(spell_id).strip().lower()
    spec = _SPELL_RANGES.get(normalized)
    if spec is None:
        raise UnknownSpellRangeError(spell_id)
    return spec


def spell_range_ft_for_target(
    spec: SpellRangeSpec,
    *,
    caster_id: str,
    target_id: str,
) -> int | None:
    """
    Portée en pieds applicable à une paire lanceur/cible.

    ``None`` si le sort est auto (self) et la cible est le lanceur — pas de check distance.
    Lève ``ValueError`` si self-only et cible différente.
    """
    if spec.kind == "self":
        if caster_id != target_id:
            raise ValueError("Ce sort ne cible que le lanceur.")
        return None
    if spec.kind == "touch":
        return MELEE_TOUCH_RANGE_FT
    return spec.feet

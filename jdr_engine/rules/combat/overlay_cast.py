# jdr_engine/rules/combat/overlay_cast.py
"""Registre des sorts overlay combat — bornes de cibles pour ``cast_spell``."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayCastSpec:
    """Nombre de cibles attendu pour un sort overlay en combat."""

    min_targets: int
    max_targets: int


OVERLAY_CAST_REGISTRY: dict[str, OverlayCastSpec] = {
    "hunters_mark": OverlayCastSpec(1, 1),
    "hex": OverlayCastSpec(1, 1),
    "bless": OverlayCastSpec(1, 3),
    "shield": OverlayCastSpec(0, 0),
}

# Sorts acceptant ``slot_level`` en combat (vide tant que le scaling n'est pas câblé).
UPCAST_COMBAT_SPELLS: frozenset[str] = frozenset()

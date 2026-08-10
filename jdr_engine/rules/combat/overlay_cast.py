# jdr_engine/rules/combat/overlay_cast.py
"""Registre des sorts overlay combat — bornes de cibles pour ``cast_spell``."""
from __future__ import annotations

from dataclasses import dataclass

from jdr_engine.domain.combat.action_budget import ActionKind


@dataclass(frozen=True)
class OverlayCastSpec:
    """Métadonnées d'un sort overlay lançable via ``cast_spell``."""

    min_targets: int
    max_targets: int
    action_kind: ActionKind
    require_own_turn: bool = True
    expose_in_castable: bool = True


OVERLAY_CAST_REGISTRY: dict[str, OverlayCastSpec] = {
    "hunters_mark": OverlayCastSpec(1, 1, "bonus_action"),
    "hex": OverlayCastSpec(1, 1, "action"),
    "bless": OverlayCastSpec(1, 3, "action"),
    "shield": OverlayCastSpec(
        0,
        0,
        "reaction",
        require_own_turn=False,
        expose_in_castable=False,
    ),
}

# Sorts acceptant ``slot_level`` en combat (vide tant que le scaling n'est pas câblé).
UPCAST_COMBAT_SPELLS: frozenset[str] = frozenset()

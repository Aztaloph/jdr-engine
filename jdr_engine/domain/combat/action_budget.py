# jdr_engine/domain/combat/action_budget.py
"""Budget d'actions par tour — lot C4 (SRD 5.1 2014), mouvement en pieds (lot 8)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

ActionKind = Literal["action", "bonus_action", "reaction", "movement"]

_FIELD_BY_KIND: dict[str, str] = {
    "action": "has_action",
    "bonus_action": "has_bonus_action",
    "reaction": "has_reaction",
}


class ActionBudgetExhaustedError(Exception):
    """Composante du budget déjà consommée pour le tour courant."""


@dataclass(frozen=True)
class ActionBudget:
    """Action, action bonus, réaction (booléens) ; mouvement en pieds restants."""

    has_action: bool = True
    has_bonus_action: bool = True
    has_reaction: bool = True
    movement_remaining_ft: int = 0

    def consume(self, kind: ActionKind) -> ActionBudget:
        """Consomme action / bonus / réaction ; le mouvement passe par ``consume_movement_ft``."""
        if kind == "movement":
            raise ValueError(
                "Utiliser consume_movement_ft pour le mouvement."
            )
        field = _FIELD_BY_KIND[kind]
        if not getattr(self, field):
            raise ActionBudgetExhaustedError(
                f"Budget épuisé pour {kind!r}."
            )
        return replace(self, **{field: False})

    def consume_movement_ft(self, cost_ft: int) -> ActionBudget:
        """Déduit ``cost_ft`` du mouvement restant."""
        if cost_ft <= 0:
            raise ValueError("cost_ft doit être strictement positif.")
        if cost_ft > self.movement_remaining_ft:
            raise ActionBudgetExhaustedError(
                f"Mouvement insuffisant : {cost_ft} ft requis, "
                f"{self.movement_remaining_ft} ft restants."
            )
        return replace(
            self,
            movement_remaining_ft=self.movement_remaining_ft - cost_ft,
        )

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "has_action": self.has_action,
            "has_bonus_action": self.has_bonus_action,
            "has_reaction": self.has_reaction,
            "movement_remaining_ft": self.movement_remaining_ft,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionBudget:
        return cls(
            has_action=bool(data.get("has_action", True)),
            has_bonus_action=bool(data.get("has_bonus_action", True)),
            has_reaction=bool(data.get("has_reaction", True)),
            movement_remaining_ft=int(data.get("movement_remaining_ft", 0)),
        )


def fresh_action_budget(*, movement_speed_ft: int) -> ActionBudget:
    """Budget complet — réinitialisé au ``TurnStarted`` du combattant."""
    return ActionBudget(movement_remaining_ft=movement_speed_ft)

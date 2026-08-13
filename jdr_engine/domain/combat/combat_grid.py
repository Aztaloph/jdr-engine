# jdr_engine/domain/combat/combat_grid.py
"""Dimensions de la grille tactique — persistées dans l'état de combat (lot 8)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CombatGrid:
    """Grille rectangulaire ; bornes inclusives ``[0, width-1]`` × ``[0, height-1]``."""

    width: int
    height: int

    def contains(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def to_dict(self) -> dict[str, int]:
        return {"width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CombatGrid:
        return cls(width=int(data["width"]), height=int(data["height"]))

# jdr_engine/domain/combat/grid_position.py
"""Position discrète sur grille de combat — lot 8 (1 case = 5 ft SRD)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GridPosition:
    """Coordonnées entières en cases (origine coin supérieur gauche)."""

    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GridPosition:
        return cls(x=int(data["x"]), y=int(data["y"]))

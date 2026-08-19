"""Constantes format scene.json v1 — jalon S."""

from __future__ import annotations

SCHEMA_VERSION = 1

GRID_MAX_CELLS = 50

SPAWN_ROLES = frozenset({"player", "enemy"})

SCENE_KINDS = frozenset(
    {
        "background",
        "floor",
        "wall",
        "door",
        "table",
        "chest",
        "torch",
        "npc",
        "spawn",
    }
)

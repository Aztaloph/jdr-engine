"""Format scene.json v1 — jalon S (contenu, hors moteur D&D)."""

from interfaces.scenes.constants import GRID_MAX_CELLS, SCHEMA_VERSION, SCENE_KINDS
from interfaces.scenes.footprint import effective_footprint
from interfaces.scenes.validate import (
    SceneValidationError,
    SceneValidationReport,
    parse_scene_document,
    validate_scene_document,
)

__all__ = [
    "GRID_MAX_CELLS",
    "SCHEMA_VERSION",
    "SCENE_KINDS",
    "SceneValidationError",
    "SceneValidationReport",
    "effective_footprint",
    "parse_scene_document",
    "validate_scene_document",
]

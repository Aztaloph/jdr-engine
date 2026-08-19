"""Validation structurelle scene.json v1 — jalon S."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from interfaces.scenes.constants import (
    GRID_MAX_CELLS,
    SCHEMA_VERSION,
    SCENE_KINDS,
    SPAWN_ROLES,
)
from interfaces.scenes.footprint import effective_footprint

_ABSOLUTE_PATH_RE = re.compile(
    r"(?:^[A-Za-z]:[/\\])|(?:^file://)|(?:^/Users/)|(?:^/home/)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SceneValidationIssue:
    level: str  # "error" | "warning"
    code: str
    message: str
    ref: str | None = None


@dataclass
class SceneValidationReport:
    issues: list[SceneValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == "error")


class SceneValidationError(ValueError):
    """Document scène invalide."""

    def __init__(self, report: SceneValidationReport) -> None:
        self.report = report
        first = next(
            (issue for issue in report.issues if issue.level == "error"),
            None,
        )
        message = first.message if first else "Document scène invalide."
        super().__init__(message)


def _issue(
    code: str,
    message: str,
    *,
    ref: str | None = None,
    level: str = "error",
) -> SceneValidationIssue:
    return SceneValidationIssue(level=level, code=code, message=message, ref=ref)


def _scan_forbidden_paths(value: Any, ref: str, report: SceneValidationReport) -> None:
    if isinstance(value, str):
        if _ABSOLUTE_PATH_RE.search(value.strip()):
            report.issues.append(
                _issue(
                    "ABSOLUTE_PATH",
                    f"Chemin absolu interdit : {value!r}",
                    ref=ref,
                )
            )
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            _scan_forbidden_paths(nested, f"{ref}.{key}", report)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_forbidden_paths(nested, f"{ref}[{index}]", report)


def _require_int(
    data: dict[str, Any],
    key: str,
    *,
    ref: str,
    report: SceneValidationReport,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if key not in data:
        report.issues.append(_issue("MISSING_FIELD", f"Champ obligatoire absent : {key}", ref=ref))
        return None
    raw = data[key]
    if isinstance(raw, bool) or not isinstance(raw, int):
        report.issues.append(
            _issue("INVALID_TYPE", f"{key} doit être un entier", ref=f"{ref}.{key}")
        )
        return None
    if minimum is not None and raw < minimum:
        report.issues.append(
            _issue(
                "OUT_OF_RANGE",
                f"{key} doit être ≥ {minimum} (reçu {raw})",
                ref=f"{ref}.{key}",
            )
        )
        return None
    if maximum is not None and raw > maximum:
        report.issues.append(
            _issue(
                "OUT_OF_RANGE",
                f"{key} doit être ≤ {maximum} (reçu {raw})",
                ref=f"{ref}.{key}",
            )
        )
        return None
    return raw


def _validate_object(
    raw: Any,
    *,
    index: int,
    grid_width: int,
    grid_height: int,
    seen_ids: set[str],
    report: SceneValidationReport,
) -> dict[str, Any] | None:
    ref = f"objects[{index}]"
    object_ok = True
    if not isinstance(raw, dict):
        report.issues.append(_issue("INVALID_TYPE", "Objet scène doit être un objet", ref=ref))
        return None

    def _fail() -> None:
        nonlocal object_ok
        object_ok = False

    obj_id = raw.get("id")
    if not isinstance(obj_id, str) or not obj_id.strip():
        report.issues.append(_issue("INVALID_ID", "id obligatoire (string non vide)", ref=f"{ref}.id"))
        _fail()
        obj_id = None
    elif obj_id in seen_ids:
        report.issues.append(
            _issue("DUPLICATE_ID", f"Identifiant dupliqué : {obj_id!r}", ref=f"{ref}.id")
        )
        _fail()
    else:
        seen_ids.add(obj_id)

    kind = raw.get("kind")
    if not isinstance(kind, str) or kind not in SCENE_KINDS:
        report.issues.append(
            _issue(
                "INVALID_KIND",
                f"kind inconnu : {kind!r} (enum v1 : {sorted(SCENE_KINDS)})",
                ref=f"{ref}.kind",
            )
        )
        _fail()
        kind = None

    x = _require_int(raw, "x", ref=ref, report=report, minimum=0)
    y = _require_int(raw, "y", ref=ref, report=report, minimum=0)
    if "width" in raw:
        width = _require_int(raw, "width", ref=ref, report=report, minimum=1)
        if width is None:
            _fail()
    else:
        width = 1
    if "height" in raw:
        height = _require_int(raw, "height", ref=ref, report=report, minimum=1)
        if height is None:
            _fail()
    else:
        height = 1
    if "quarter_turns" in raw:
        quarter_turns = _require_int(
            raw, "quarter_turns", ref=ref, report=report, minimum=0, maximum=3
        )
        if quarter_turns is None:
            _fail()
    else:
        quarter_turns = 0
    if x is None or y is None:
        _fail()

    asset_id = raw.get("asset_id", None)
    if asset_id is not None and not isinstance(asset_id, str):
        report.issues.append(
            _issue("INVALID_TYPE", "asset_id doit être string ou null", ref=f"{ref}.asset_id")
        )
        asset_id = None

    door = raw.get("door", None)
    spawn = raw.get("spawn", None)

    if kind == "door":
        if door is None:
            report.issues.append(
                _issue("MISSING_DOOR", "kind door exige door.target_scene_id", ref=f"{ref}.door")
            )
        elif not isinstance(door, dict):
            report.issues.append(_issue("INVALID_TYPE", "door doit être un objet", ref=f"{ref}.door"))
        else:
            target = door.get("target_scene_id")
            if not isinstance(target, str) or not target.strip():
                report.issues.append(
                    _issue(
                        "INVALID_DOOR",
                        "door.target_scene_id obligatoire (string non vide)",
                        ref=f"{ref}.door.target_scene_id",
                    )
                )
    elif door is not None:
        report.issues.append(
            _issue("UNEXPECTED_DOOR", "door autorisé uniquement si kind=door", ref=f"{ref}.door")
        )

    if kind == "spawn":
        if spawn is None:
            report.issues.append(
                _issue("MISSING_SPAWN", "kind spawn exige spawn.role et spawn.index", ref=f"{ref}.spawn")
            )
        elif not isinstance(spawn, dict):
            report.issues.append(_issue("INVALID_TYPE", "spawn doit être un objet", ref=f"{ref}.spawn"))
        else:
            role = spawn.get("role")
            if role not in SPAWN_ROLES:
                report.issues.append(
                    _issue(
                        "INVALID_SPAWN_ROLE",
                        f"spawn.role invalide : {role!r}",
                        ref=f"{ref}.spawn.role",
                    )
                )
            _require_int(spawn, "index", ref=f"{ref}.spawn", report=report, minimum=0)
    elif spawn is not None:
        report.issues.append(
            _issue("UNEXPECTED_SPAWN", "spawn autorisé uniquement si kind=spawn", ref=f"{ref}.spawn")
        )

    if (
        object_ok
        and x is not None
        and y is not None
        and width is not None
        and height is not None
        and quarter_turns is not None
    ):
        eff_w, eff_h = effective_footprint(width, height, quarter_turns)
        if x + eff_w > grid_width or y + eff_h > grid_height:
            report.issues.append(
                _issue(
                    "OUT_OF_GRID",
                    f"Emprise effective {eff_w}×{eff_h} à ({x},{y}) déborde la grille "
                    f"{grid_width}×{grid_height}",
                    ref=ref,
                )
            )
            _fail()

    if not object_ok:
        return None

    normalized: dict[str, Any] = {
        "id": obj_id,
        "kind": kind,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "quarter_turns": quarter_turns if quarter_turns is not None else 0,
        "asset_id": asset_id,
        "door": None,
        "spawn": None,
    }
    if kind == "door" and isinstance(door, dict):
        normalized["door"] = {"target_scene_id": str(door["target_scene_id"]).strip()}
    if kind == "spawn" and isinstance(spawn, dict):
        normalized["spawn"] = {
            "role": spawn["role"],
            "index": int(spawn["index"]),
        }
    return normalized


def _validate_light(raw: Any, *, index: int, report: SceneValidationReport) -> dict[str, Any] | None:
    ref = f"lights[{index}]"
    if not isinstance(raw, dict):
        report.issues.append(_issue("INVALID_TYPE", "Entrée lights doit être un objet", ref=ref))
        return None
    x = _require_int(raw, "x", ref=ref, report=report, minimum=0)
    y = _require_int(raw, "y", ref=ref, report=report, minimum=0)
    radius = _require_int(raw, "radius_cells", ref=ref, report=report, minimum=0)
    color = raw.get("color")
    if not isinstance(color, str) or not color.strip():
        report.issues.append(
            _issue("INVALID_LIGHT", "lights.color obligatoire (string)", ref=f"{ref}.color")
        )
    if not report.ok:
        return None
    return {
        "x": x,
        "y": y,
        "radius_cells": radius,
        "color": str(color).strip(),
    }


def validate_scene_document(data: Any) -> SceneValidationReport:
    """Valide un document scène v1 ; ne lève pas d'exception."""
    report = SceneValidationReport()
    if not isinstance(data, dict):
        report.issues.append(_issue("INVALID_ROOT", "Racine scene.json doit être un objet"))
        return report

    _scan_forbidden_paths(data, "root", report)

    version = _require_int(data, "schema_version", ref="root", report=report)
    if version is not None and version != SCHEMA_VERSION:
        report.issues.append(
            _issue(
                "UNSUPPORTED_VERSION",
                f"schema_version {version} non supporté (attendu {SCHEMA_VERSION})",
                ref="schema_version",
            )
        )

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        report.issues.append(_issue("INVALID_NAME", "name obligatoire (string non vide)", ref="name"))

    grid_raw = data.get("grid")
    if not isinstance(grid_raw, dict):
        report.issues.append(_issue("INVALID_GRID", "grid obligatoire (objet)", ref="grid"))
        return report

    grid_width = _require_int(
        grid_raw,
        "width",
        ref="grid",
        report=report,
        minimum=1,
        maximum=GRID_MAX_CELLS,
    )
    grid_height = _require_int(
        grid_raw,
        "height",
        ref="grid",
        report=report,
        minimum=1,
        maximum=GRID_MAX_CELLS,
    )
    enabled = grid_raw.get("enabled", True)
    if not isinstance(enabled, bool):
        report.issues.append(
            _issue("INVALID_TYPE", "grid.enabled doit être un booléen", ref="grid.enabled")
        )
        enabled = True

    if grid_width is None or grid_height is None:
        return report

    objects_raw = data.get("objects")
    if objects_raw is None:
        objects_raw = []
    if not isinstance(objects_raw, list):
        report.issues.append(_issue("INVALID_TYPE", "objects doit être un tableau", ref="objects"))
        return report

    lights_raw = data.get("lights")
    if lights_raw is None:
        lights_raw = []
    if not isinstance(lights_raw, list):
        report.issues.append(_issue("INVALID_TYPE", "lights doit être un tableau", ref="lights"))
        return report

    if not report.ok:
        return report

    seen_ids: set[str] = set()
    for index, raw_obj in enumerate(objects_raw):
        _validate_object(
            raw_obj,
            index=index,
            grid_width=grid_width,
            grid_height=grid_height,
            seen_ids=seen_ids,
            report=report,
        )

    for index, raw_light in enumerate(lights_raw):
        _validate_light(raw_light, index=index, report=report)

    return report


def _canonicalize_scene(data: dict[str, Any]) -> dict[str, Any]:
    """Forme canonique — appeler uniquement après validation OK."""
    grid_raw = data["grid"]
    objects_raw = data.get("objects", [])
    lights_raw = data.get("lights", [])

    grid_width = int(grid_raw["width"])
    grid_height = int(grid_raw["height"])
    seen_ids: set[str] = set()
    objects: list[dict[str, Any]] = []
    empty_report = SceneValidationReport()
    for index, raw_obj in enumerate(objects_raw):
        normalized = _validate_object(
            raw_obj,
            index=index,
            grid_width=grid_width,
            grid_height=grid_height,
            seen_ids=seen_ids,
            report=empty_report,
        )
        assert normalized is not None
        objects.append(normalized)

    lights: list[dict[str, Any]] = []
    for index, raw_light in enumerate(lights_raw):
        normalized = _validate_light(raw_light, index=index, report=empty_report)
        assert normalized is not None
        lights.append(normalized)

    return {
        "schema_version": SCHEMA_VERSION,
        "name": str(data["name"]).strip(),
        "grid": {
            "width": grid_width,
            "height": grid_height,
            "enabled": bool(grid_raw.get("enabled", True)),
        },
        "objects": objects,
        "lights": lights,
    }


def parse_scene_document(data: Any) -> dict[str, Any]:
    """
    Valide et retourne une forme canonique (defaults explicites).

    Lève SceneValidationError si invalide.
    """
    report = validate_scene_document(data)
    if not report.ok:
        raise SceneValidationError(report)
    assert isinstance(data, dict)
    return _canonicalize_scene(data)

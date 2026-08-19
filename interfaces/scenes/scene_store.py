"""Persistance SQLite des scènes — jalon S lot Sb."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jdr_engine.persistence.database import ensure_scenes_schema, get_connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SceneRecord:
    id: str
    owner_id: str
    updated_at: str
    document: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.document.get("name", ""))


@dataclass(frozen=True)
class SceneListEntry:
    id: str
    name: str
    owner_id: str
    updated_at: str
    grid_width: int
    grid_height: int
    grid_enabled: bool
    object_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "updated_at": self.updated_at,
            "grid": {
                "width": self.grid_width,
                "height": self.grid_height,
                "enabled": self.grid_enabled,
            },
            "object_count": self.object_count,
        }


class SqliteSceneStore:
    """Store scènes — une ligne = un document scene.json canonique."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        ensure_scenes_schema(db_path)

    def create(self, *, owner_id: str, document: dict[str, Any]) -> SceneRecord:
        scene_id = uuid.uuid4().hex
        return self._insert(
            scene_id=scene_id,
            owner_id=owner_id,
            document=document,
        )

    def _insert(
        self,
        *,
        scene_id: str,
        owner_id: str,
        document: dict[str, Any],
    ) -> SceneRecord:
        updated_at = _utc_now()
        payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        name = str(document["name"])
        with get_connection(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO scenes (id, name, json, owner_id, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (scene_id, name, payload, owner_id, updated_at),
            )
        return SceneRecord(
            id=scene_id,
            owner_id=owner_id,
            updated_at=updated_at,
            document=document,
        )

    def get(self, scene_id: str) -> SceneRecord | None:
        with get_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT id, name, json, owner_id, updated_at FROM scenes WHERE id = ?",
                (scene_id,),
            ).fetchone()
        if row is None:
            return None
        return SceneRecord(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            updated_at=str(row["updated_at"]),
            document=json.loads(row["json"]),
        )

    def list_all(self) -> list[SceneListEntry]:
        with get_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, name, json, owner_id, updated_at
                FROM scenes
                ORDER BY name COLLATE NOCASE, updated_at DESC
                """
            ).fetchall()
        entries: list[SceneListEntry] = []
        for row in rows:
            document = json.loads(row["json"])
            grid = document.get("grid") or {}
            entries.append(
                SceneListEntry(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    owner_id=str(row["owner_id"]),
                    updated_at=str(row["updated_at"]),
                    grid_width=int(grid.get("width", 0)),
                    grid_height=int(grid.get("height", 0)),
                    grid_enabled=bool(grid.get("enabled", True)),
                    object_count=len(document.get("objects") or []),
                )
            )
        return entries

    def update(self, scene_id: str, document: dict[str, Any]) -> SceneRecord | None:
        updated_at = _utc_now()
        payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        name = str(document["name"])
        with get_connection(self._db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE scenes
                SET name = ?, json = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, payload, updated_at, scene_id),
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT owner_id FROM scenes WHERE id = ?",
                (scene_id,),
            ).fetchone()
        assert row is not None
        return SceneRecord(
            id=scene_id,
            owner_id=str(row["owner_id"]),
            updated_at=updated_at,
            document=document,
        )

    def delete(self, scene_id: str) -> bool:
        with get_connection(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
            return cursor.rowcount > 0

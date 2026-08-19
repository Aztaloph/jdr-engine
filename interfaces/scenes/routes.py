"""Routes HTTP /v1/scenes — jalon S lot Sb."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict

from interfaces.api.auth.guards import require_gm, require_session
from interfaces.api.errors import ApiError
from interfaces.scenes.scene_store import SceneRecord, SqliteSceneStore
from interfaces.scenes.validate import SceneValidationError, parse_scene_document


class SceneDocumentBody(BaseModel):
    """Corps POST/PUT — document scene.json v1 (champs libres contrôlés par validateur)."""

    model_config = ConfigDict(extra="allow")


def _record_to_response(record: SceneRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "owner_id": record.owner_id,
        "updated_at": record.updated_at,
        "scene": record.document,
    }


def _resolve_owner_id(session) -> str:
    if session is None:
        return "local"
    return session.user_id


def register_scene_routes(app: FastAPI, *, db_path: Path) -> None:
    store = SqliteSceneStore(db_path)

    @app.get("/v1/scenes")
    def list_scenes(request: Request) -> dict:
        require_session(request)
        return {
            "scenes": [entry.to_dict() for entry in store.list_all()],
        }

    @app.post("/v1/scenes", status_code=201)
    def create_scene(body: SceneDocumentBody, request: Request) -> dict:
        session = require_session(request)
        require_gm(session)
        try:
            document = parse_scene_document(body.model_dump())
        except SceneValidationError as exc:
            raise ApiError(
                422,
                "SCENE_INVALID",
                "Document scène invalide.",
                details={
                    "issues": [
                        {
                            "code": issue.code,
                            "message": issue.message,
                            "ref": issue.ref,
                        }
                        for issue in exc.report.issues
                        if issue.level == "error"
                    ]
                },
            ) from exc
        record = store.create(owner_id=_resolve_owner_id(session), document=document)
        return _record_to_response(record)

    @app.get("/v1/scenes/{scene_id}")
    def get_scene(scene_id: str, request: Request) -> dict:
        require_session(request)
        record = store.get(scene_id)
        if record is None:
            raise ApiError(
                404,
                "SCENE_NOT_FOUND",
                "Scène introuvable.",
                details={"scene_id": scene_id},
            )
        return _record_to_response(record)

    @app.get("/v1/scenes/{scene_id}/export")
    def export_scene(scene_id: str, request: Request) -> dict:
        require_session(request)
        record = store.get(scene_id)
        if record is None:
            raise ApiError(
                404,
                "SCENE_NOT_FOUND",
                "Scène introuvable.",
                details={"scene_id": scene_id},
            )
        return record.document

    @app.put("/v1/scenes/{scene_id}")
    def update_scene(
        scene_id: str,
        body: SceneDocumentBody,
        request: Request,
    ) -> dict:
        session = require_session(request)
        require_gm(session)
        try:
            document = parse_scene_document(body.model_dump())
        except SceneValidationError as exc:
            raise ApiError(
                422,
                "SCENE_INVALID",
                "Document scène invalide.",
                details={
                    "issues": [
                        {
                            "code": issue.code,
                            "message": issue.message,
                            "ref": issue.ref,
                        }
                        for issue in exc.report.issues
                        if issue.level == "error"
                    ]
                },
            ) from exc
        record = store.update(scene_id, document)
        if record is None:
            raise ApiError(
                404,
                "SCENE_NOT_FOUND",
                "Scène introuvable.",
                details={"scene_id": scene_id},
            )
        return _record_to_response(record)

    @app.delete("/v1/scenes/{scene_id}")
    def delete_scene(scene_id: str, request: Request) -> dict:
        session = require_session(request)
        require_gm(session)
        if not store.delete(scene_id):
            raise ApiError(
                404,
                "SCENE_NOT_FOUND",
                "Scène introuvable.",
                details={"scene_id": scene_id},
            )
        return {"scene_id": scene_id, "deleted": True}

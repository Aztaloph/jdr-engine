# interfaces/api/auth/routes.py
"""Routes auth v1 — établissement de session dev."""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from interfaces.api.auth.config import dev_login_allowed
from interfaces.api.auth.guards import extract_bearer_token, require_session
from interfaces.api.auth.models import ApiSessionRole
from interfaces.api.auth.session_store import ApiSessionStore
from interfaces.api.errors import ApiError


class DevLoginRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: Literal["player", "gm"] = "player"


def register_auth_routes(
    app: FastAPI,
    *,
    session_store: ApiSessionStore,
) -> None:
    """Enregistre ``POST /v1/auth/dev-login`` et ``GET /v1/auth/me``."""

    @app.post("/v1/auth/dev-login")
    def dev_login(body: DevLoginRequest) -> dict:
        if not getattr(app.state, "auth_enabled", False):
            raise ApiError(
                403,
                "AUTH_DISABLED",
                "Authentification désactivée sur cette instance.",
            )
        if not dev_login_allowed():
            raise ApiError(
                403,
                "AUTH_DISABLED",
                "Connexion dev désactivée (JDR_AUTH_DEV=0).",
            )
        session = session_store.create(body.user_id.strip(), body.role)
        return {
            "token": session.token,
            "expires_at": session.expires_at,
            "user_id": session.user_id,
            "role": session.role,
        }

    @app.get("/v1/auth/me")
    def auth_me(request: Request) -> dict:
        session = require_session(request)
        if session is None:
            return {"authenticated": False}
        return {
            "authenticated": True,
            "user_id": session.user_id,
            "role": session.role,
            "expires_at": session.expires_at,
        }

    @app.post("/v1/auth/logout")
    def auth_logout(request: Request) -> dict:
        if not getattr(app.state, "auth_enabled", False):
            return {"ok": True}
        token = extract_bearer_token(request)
        if token:
            session_store.delete(token)
        return {"ok": True}

# interfaces/api/auth/guards.py
"""Garde-fous autorisation API — lot B1 auth (couche transport)."""
from __future__ import annotations

from fastapi import Request

from interfaces.api.auth.models import ApiSession
from interfaces.api.errors import ApiError
from jdr_engine.domain.character.character import Character
from jdr_engine.domain.combat.combat_state import CombatState
from jdr_engine.persistence.sqlite_character_repository import (
    SqliteCharacterRepository,
)


def extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    trimmed = parts[1].strip()
    return trimmed if trimmed else None


def auth_enabled(request: Request) -> bool:
    return bool(getattr(request.app.state, "auth_enabled", False))


def require_session(request: Request) -> ApiSession | None:
    """
    Session obligatoire si auth activée.

    Retourne ``None`` si auth désactivée (comportement banc local).
    """
    if not auth_enabled(request):
        return None
    store = request.app.state.session_store
    token = extract_bearer_token(request)
    if token is None:
        raise ApiError(
            401,
            "AUTH_REQUIRED",
            "Authentification requise.",
        )
    session = store.get_valid(token)
    if session is None:
        raise ApiError(
            401,
            "AUTH_INVALID",
            "Session invalide ou expirée.",
        )
    return session


def require_gm(session: ApiSession | None) -> None:
    if session is None:
        return
    if session.role != "gm":
        raise ApiError(
            403,
            "GM_REQUIRED",
            "Action réservée au maître du jeu.",
        )


def assert_character_access(
    session: ApiSession | None,
    character: Character,
) -> None:
    if session is None:
        return
    if session.role == "gm":
        return
    if str(character.owner_id) != session.user_id:
        raise ApiError(
            403,
            "FORBIDDEN",
            "Accès refusé à ce personnage.",
            details={"character_id": character.id},
        )


def assert_combatant_owned(
    session: ApiSession | None,
    state: CombatState,
    combatant_id: str,
    character_repository: SqliteCharacterRepository,
) -> None:
    if session is None:
        return
    if session.role == "gm":
        return
    combatant = state.combatants.get(combatant_id)
    if combatant is None:
        return
    character = character_repository.get_by_id(combatant.character_id)
    if character is None:
        raise ApiError(
            404,
            "CHARACTER_NOT_FOUND",
            "Personnage introuvable.",
            details={"character_id": combatant.character_id},
        )
    if str(character.owner_id) != session.user_id:
        raise ApiError(
            403,
            "COMBATANT_NOT_OWNED",
            "Ce combattant n'appartient pas à votre session.",
            details={"combatant_id": combatant_id},
        )


def assert_viewer_allowed(
    session: ApiSession | None,
    viewer: str | None,
    *,
    state: CombatState | None = None,
    character_repository: SqliteCharacterRepository | None = None,
) -> str | None:
    """Normalise ``viewer`` et vérifie cohérence session."""
    normalized = _normalize_viewer(viewer)
    if session is None:
        return normalized
    if session.role == "gm":
        return normalized
    if normalized is None:
        raise ApiError(
            403,
            "VIEWER_REQUIRED",
            "Vue joueur requise pour ce rôle.",
        )
    if state is not None and character_repository is not None:
        from jdr_engine.application.dto.output_serializers import viewer_combatant_id

        if viewer_combatant_id(state, normalized) is None:
            raise ApiError(
                404,
                "VIEWER_NOT_IN_COMBAT",
                "Le personnage ne participe pas à cette rencontre.",
                details={"character_id": normalized},
            )
        character = character_repository.get_by_id(normalized)
        if character is None:
            raise ApiError(
                404,
                "CHARACTER_NOT_FOUND",
                "Personnage introuvable.",
                details={"character_id": normalized},
            )
        if str(character.owner_id) != session.user_id:
            raise ApiError(
                403,
                "VIEWER_NOT_ALLOWED",
                "Vue non autorisée pour cette session.",
                details={"character_id": normalized},
            )
    else:
        if character_repository is not None:
            character = character_repository.get_by_id(normalized)
            if character is None:
                raise ApiError(
                    404,
                    "CHARACTER_NOT_FOUND",
                    "Personnage introuvable.",
                    details={"character_id": normalized},
                )
            if str(character.owner_id) != session.user_id:
                raise ApiError(
                    403,
                    "VIEWER_NOT_ALLOWED",
                    "Vue non autorisée pour cette session.",
                    details={"character_id": normalized},
                )
    return normalized


def resolve_ws_session(request: Request, token: str | None) -> ApiSession | None:
    if not auth_enabled(request):
        return None
    trimmed = (token or "").strip()
    if not trimmed:
        raise ApiError(
            401,
            "AUTH_REQUIRED",
            "Authentification requise.",
        )
    store = request.app.state.session_store
    session = store.get_valid(trimmed)
    if session is None:
        raise ApiError(
            401,
            "AUTH_INVALID",
            "Session invalide ou expirée.",
        )
    return session


def _normalize_viewer(viewer: str | None) -> str | None:
    if viewer is None:
        return None
    trimmed = viewer.strip()
    return trimmed if trimmed else None

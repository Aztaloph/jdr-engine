# interfaces/api/auth/session_store.py
"""Persistance sessions API — table SQLite ``api_sessions``."""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from interfaces.api.auth.models import ApiSession, ApiSessionRole
from jdr_engine.persistence.database import get_connection

DEFAULT_SESSION_TTL_HOURS = 24


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class ApiSessionStore:
    """Store session opaque — token aléatoire indexé."""

    def __init__(self, db_path: Path, *, ttl_hours: int = DEFAULT_SESSION_TTL_HOURS) -> None:
        self._db_path = db_path
        self._ttl_hours = ttl_hours

    def create(self, user_id: str, role: ApiSessionRole) -> ApiSession:
        token = secrets.token_urlsafe(32)
        now = _utc_now()
        expires = now + timedelta(hours=self._ttl_hours)
        created_at = _iso(now)
        expires_at = _iso(expires)
        with get_connection(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO api_sessions (token, user_id, role, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token, str(user_id), role, expires_at, created_at),
            )
        return ApiSession(
            token=token,
            user_id=str(user_id),
            role=role,
            expires_at=expires_at,
        )

    def get_valid(self, token: str) -> ApiSession | None:
        trimmed = token.strip()
        if not trimmed:
            return None
        with get_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT token, user_id, role, expires_at
                FROM api_sessions
                WHERE token = ?
                """,
                (trimmed,),
            ).fetchone()
            if row is None:
                return None
            expires_at = str(row["expires_at"])
            if _parse_iso(expires_at) <= _utc_now():
                conn.execute("DELETE FROM api_sessions WHERE token = ?", (trimmed,))
                return None
            role = str(row["role"])
            if role not in ("player", "gm"):
                return None
            return ApiSession(
                token=str(row["token"]),
                user_id=str(row["user_id"]),
                role=role,  # type: ignore[arg-type]
                expires_at=expires_at,
            )

    def delete(self, token: str) -> None:
        with get_connection(self._db_path) as conn:
            conn.execute("DELETE FROM api_sessions WHERE token = ?", (token.strip(),))

    def purge_expired(self) -> int:
        now = _iso(_utc_now())
        with get_connection(self._db_path) as conn:
            cur = conn.execute(
                "DELETE FROM api_sessions WHERE expires_at <= ?",
                (now,),
            )
            return int(cur.rowcount)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

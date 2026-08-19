# interfaces/api/auth/models.py
"""Modèle de session API — lot B1 auth."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ApiSessionRole = Literal["player", "gm"]


@dataclass(frozen=True)
class ApiSession:
    """Session authentifiée — ``user_id`` = ``Character.owner_id`` (Discord)."""

    token: str
    user_id: str
    role: ApiSessionRole
    expires_at: str

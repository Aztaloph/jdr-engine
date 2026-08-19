# interfaces/api/auth/config.py
"""Configuration auth API — variable ``JDR_API_AUTH``."""
from __future__ import annotations

import os

ENV_AUTH_ENABLED = "JDR_API_AUTH"
ENV_AUTH_DEV_LOGIN = "JDR_AUTH_DEV"


def resolve_auth_enabled(*, explicit: bool | None = None) -> bool:
    """``True`` si auth requise — défaut ``False`` (banc local / tests existants)."""
    if explicit is not None:
        return explicit
    return os.environ.get(ENV_AUTH_ENABLED, "0").strip() == "1"


def dev_login_allowed() -> bool:
    """``dev-login`` autorisé si auth dev explicitement activée."""
    return os.environ.get(ENV_AUTH_DEV_LOGIN, "1").strip() != "0"

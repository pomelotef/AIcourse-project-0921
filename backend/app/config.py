"""Runtime configuration, read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("LABPULSE_DATABASE_URL", "sqlite:///./labpulse.db")
    # Set to true when served over HTTPS so the session cookie is never sent in clear text.
    cookie_secure: bool = _bool("LABPULSE_COOKIE_SECURE", False)
    session_days: int = int(os.getenv("LABPULSE_SESSION_DAYS", "14"))


settings = Settings()

SESSION_COOKIE = "labpulse_session"

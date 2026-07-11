"""Vaultify application configuration."""

import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _read_bool(name, default=False):
    """Read one boolean environment variable."""
    raw_value = os.environ.get(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class Config:
    """Base configuration for the Vaultify web application."""

    SECRET_KEY = (
        os.environ.get("VAULTIFY_SECRET_KEY")
        or secrets.token_hex(32)
    )

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or f"sqlite:///{BASE_DIR / 'instance' / 'vaultify.db'}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.environ.get(
        "VAULTIFY_UPLOAD_FOLDER",
        str(BASE_DIR / "uploads"),
    )

    MAX_CONTENT_LENGTH = int(
        os.environ.get(
            "VAULTIFY_MAX_UPLOAD_BYTES",
            str(25 * 1024 * 1024),
        )
    )

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _read_bool(
        "VAULTIFY_SECURE_COOKIES",
        default=False,
    )

    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

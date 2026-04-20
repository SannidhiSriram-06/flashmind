import os

import bcrypt
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from app.db import get_db

_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds


def _get_secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if not key:
        if os.environ.get("ENV") == "production":
            raise RuntimeError(
                "SECRET_KEY must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return "dev-only-insecure-change-me"
    return key


def _get_signer() -> TimestampSigner:
    return TimestampSigner(_get_secret_key())


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ── Session token helpers ─────────────────────────────────────────────────────

def create_session_token(user_id: str) -> str:
    return _get_signer().sign(user_id).decode("utf-8")


def verify_session_token(token: str) -> str | None:
    """Return user_id if token is valid and not expired, else None."""
    try:
        user_id_bytes = _get_signer().unsign(token, max_age=_MAX_AGE)
        return user_id_bytes.decode("utf-8")
    except (SignatureExpired, BadSignature):
        return None


# ── Request-level user resolution ─────────────────────────────────────────────

def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


def get_current_user(request: Request) -> dict | None:
    """Read the 'session' cookie and return the user dict, or None."""
    token = request.cookies.get("session")
    if not token:
        return None
    user_id = verify_session_token(token)
    if not user_id:
        return None
    db = get_db()
    user = db.users.find_one({"user_id": user_id})
    if not user:
        return None
    return _clean(user)

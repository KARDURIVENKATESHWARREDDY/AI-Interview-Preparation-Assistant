"""User authentication with hashed passwords stored in JSON."""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

USERS_FILE = Path(__file__).resolve().parent.parent / "data" / "users.json"
_ITERATIONS = 120_000

DEFAULT_USERS = {
    "demo": "demo123",
    "admin": "admin123",
}


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _ITERATIONS,
    )
    return digest.hex()


def _load_raw() -> dict:
    if not USERS_FILE.exists():
        return {}
    with USERS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _save_raw(users: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def ensure_default_users() -> None:
    """Create default demo accounts if no user file exists."""
    if USERS_FILE.exists():
        return
    users = {}
    for username, password in DEFAULT_USERS.items():
        salt = secrets.token_hex(16)
        users[username] = {
            "salt": salt,
            "password_hash": _hash_password(password, salt),
        }
    _save_raw(users)


def authenticate(username: str, password: str) -> bool:
    """Return True only if username exists and password matches."""
    ensure_default_users()
    username = (username or "").strip().lower()
    password = password or ""
    if not username or not password:
        return False

    users = _load_raw()
    record = users.get(username)
    if not record:
        return False

    expected = record.get("password_hash", "")
    salt = record.get("salt", "")
    return secrets.compare_digest(_hash_password(password, salt), expected)


def register_user(username: str, password: str) -> tuple[bool, str]:
    """Register a new user. Returns (success, message)."""
    ensure_default_users()
    username = (username or "").strip().lower()
    password = password or ""

    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    users = _load_raw()
    if username in users:
        return False, "Username already taken."

    salt = secrets.token_hex(16)
    users[username] = {
        "salt": salt,
        "password_hash": _hash_password(password, salt),
    }
    _save_raw(users)
    return True, "Account created. You can sign in now."


def list_usernames() -> list[str]:
    ensure_default_users()
    return sorted(_load_raw().keys())

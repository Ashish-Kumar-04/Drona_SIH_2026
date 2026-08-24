"""
Password hashing (bcrypt) and JWT access-token helpers.

Passwords: new hashes use bcrypt. Legacy accounts created before this module used
unsalted SHA-256; verify_password transparently accepts those and signals that the
stored hash should be upgraded to bcrypt on the next successful login.
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt

from app.core.config import settings

# bcrypt only considers the first 72 bytes of a password; truncate defensively so a
# very long password never raises instead of hashing.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns a 60-char '$2b$...' string."""
    pw_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def _legacy_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> Tuple[bool, bool]:
    """
    Verify a password against a stored hash.

    Returns (is_valid, needs_rehash). needs_rehash is True when the stored hash is a
    legacy SHA-256 digest that verified correctly and should be upgraded to bcrypt.
    """
    if not stored_hash:
        return False, False

    # bcrypt hashes start with $2a$ / $2b$ / $2y$
    if stored_hash.startswith("$2"):
        try:
            pw_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
            return bcrypt.checkpw(pw_bytes, stored_hash.encode("utf-8")), False
        except (ValueError, TypeError):
            return False, False

    # Legacy unsalted SHA-256 (64 hex chars). Constant-time compare, then flag for upgrade.
    is_valid = hmac.compare_digest(_legacy_sha256(password), stored_hash)
    return is_valid, is_valid


def create_access_token(subject: str, typ: str = "athlete", expires_hours: Optional[int] = None) -> str:
    """Create a signed JWT for the given subject id. typ is 'athlete' or 'official'."""
    hours = expires_hours if expires_hours is not None else settings.JWT_EXPIRE_HOURS
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "typ": typ,
        "iat": now,
        "exp": now + timedelta(hours=hours),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns the claims dict, or None if invalid/expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

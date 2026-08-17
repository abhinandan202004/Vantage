"""
Password hashing (PBKDF2-SHA256, via Python's built-in hashlib — no
`bcrypt` dependency, which needs a C extension) and JWT tokens (via
PyJWT — pure Python, no `cryptography` dependency for the HS256
algorithm used here). Deliberately avoiding native-compiled
dependencies, consistent with this project's approach elsewhere
(pgvector, psycopg2 → psycopg, etc.) given how much Windows build-tool
friction we've already hit.

PBKDF2 iteration count: OWASP's 2023 guidance recommends 600,000+
iterations for PBKDF2-HMAC-SHA256. Using that as the default.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 32


def hash_password(password: str) -> tuple[str, str]:
    """
    Returns (password_hash_hex, salt_hex). Store both — verification
    needs the salt that was used.
    """
    salt = secrets.token_hex(SALT_BYTES)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return hashed.hex(), salt


def verify_password(password: str, stored_hash_hex: str, salt_hex: str) -> bool:
    """
    Recomputes the hash with the given salt and compares against the
    stored hash using a constant-time comparison (hmac.compare_digest)
    to avoid leaking timing information about how much of the hash
    matched — a standard precaution for auth code, not just a nice-to-have.
    """
    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(candidate_hash.hex(), stored_hash_hex)


def create_access_token(user_id: int) -> str:
    """Returns a signed JWT encoding the user's id, expiring after settings.jwt_expire_minutes."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> int:
    """
    Returns the user_id encoded in a valid, non-expired token.
    Raises jwt.PyJWTError (or a subclass — ExpiredSignatureError,
    InvalidTokenError, etc.) for any invalid/expired/tampered token —
    callers should catch that broadly rather than each subclass
    individually unless they need to distinguish the reason.
    """
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    return int(payload["sub"])

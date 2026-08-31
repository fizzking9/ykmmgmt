"""Password hashing and JWT helpers for authentication."""

import datetime as dt

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    """Raised when a JWT is invalid, expired, or of the wrong type."""


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(password, password_hash)


def _create_token(user_id: int, token_type: str, expires_delta: dt.timedelta) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(user_id: int) -> str:
    return _create_token(
        user_id,
        ACCESS_TOKEN_TYPE,
        dt.timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        user_id,
        REFRESH_TOKEN_TYPE,
        dt.timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: str) -> int:
    """Decode a JWT and return the user id it was issued for.

    Raises :class:`TokenError` on invalid/expired tokens or a type mismatch.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as e:
        raise TokenError(str(e)) from e
    if payload.get("type") != expected_type:
        raise TokenError("unexpected token type")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError) as e:
        raise TokenError("invalid subject") from e

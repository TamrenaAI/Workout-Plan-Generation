"""
This backend's own session tokens (JWT), issued after a Google ID token has
been verified. The mobile app never sends its Google ID token on every
request — it exchanges it once at /auth/google for one of these, then sends
this as `Authorization: Bearer <token>` on every subsequent call. Keeps
every other route's auth check independent of Google's token format/expiry
(Google ID tokens are short-lived; ours are a separate, longer-lived
mobile-session concern).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET


class InvalidSessionToken(Exception):
    pass


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the user_id (a Mongo ObjectId's string form) encoded in the
    token. Raises InvalidSessionToken on expiry, tampering, or malformed
    input."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidSessionToken(str(exc)) from exc

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise InvalidSessionToken("Token has no subject.")
    return user_id

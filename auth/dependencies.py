"""
FastAPI dependency that protects a route behind a valid session token.
Usage: `def route(user: dict = Depends(get_current_user)): ...`
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.models import get_user_by_id
from auth.tokens import InvalidSessionToken, decode_access_token

_bearer_scheme = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> dict:
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidSessionToken as exc:
        raise HTTPException(401, f"Invalid or expired session: {exc}") from exc

    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(401, "User no longer exists.")
    return user

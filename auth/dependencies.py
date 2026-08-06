"""
FastAPI dependency that protects a route behind a valid session token.
Usage: `def route(user: dict = Depends(get_current_user)): ...`

This service no longer owns user identity (see
docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md) — a separate
BFF repo verifies Google Sign-In, issues the JWT, and owns the `users`
collection. This dependency only verifies the token's signature/expiry
(against the same shared JWT_SECRET the BFF signs with) and trusts the
`sub` claim as the user_id directly — no local Mongo lookup, no "does this
user still exist" check (that's the BFF's concern now).
"""

from typing import Optional

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.tokens import InvalidSessionToken, decode_access_token

_bearer_scheme = HTTPBearer()
_optional_bearer_scheme = HTTPBearer(auto_error=False)


def _resolve_user(raw_token: str) -> dict:
    try:
        user_id = decode_access_token(raw_token)
    except InvalidSessionToken as exc:
        raise HTTPException(401, f"Invalid or expired session: {exc}") from exc
    return {"id": user_id}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> dict:
    return _resolve_user(credentials.credentials)


def get_current_user_for_stream(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer_scheme),
) -> dict:
    """Same session-token check as get_current_user, but also accepts the
    token as a `?token=` query param — only for SSE routes. The browser's
    native EventSource API cannot send an Authorization header at all, so
    an SSE endpoint has no way to receive a Bearer token except via the
    URL. Not used by any non-SSE route; those keep header-only auth."""
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        raise HTTPException(401, "Missing authentication token.")
    return _resolve_user(raw_token)

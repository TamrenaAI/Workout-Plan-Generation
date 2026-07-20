"""
POST /auth/google — mobile app sends the ID token it got from a native
Google Sign-In; we verify it against Google, create the user record on
first sign-in, and return this backend's own session JWT.

GET /auth/me — returns the signed-in user's profile. Protected by
auth.dependencies.get_current_user, the same dependency every other
account-scoped route will use going forward.

POST /auth/dev-login — same idea as /auth/google but with NO Google
verification at all; mints a session for a fixed test account. Only exists
when config.ALLOW_DEV_LOGIN is set (see config.py for why this is safe by
default). Exists because every other endpoint requires a real token, and
without this there is literally no way to reach any screen past login in
web preview or Expo Go, where the real native Google Sign-In can't run.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user
from auth.google_oauth import InvalidGoogleToken, verify_google_id_token
from auth.models import get_or_create_user_by_google
from auth.tokens import create_access_token
from config import ALLOW_DEV_LOGIN

DEV_USER_SUB = "dev-test-user"
DEV_USER_EMAIL = "dev@tamreena.local"

router = APIRouter()


class GoogleSignInRequest(BaseModel):
    id_token: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None
    picture_url: str | None
    created_at: str


@router.post("/auth/google", response_model=SessionResponse)
async def sign_in_with_google(body: GoogleSignInRequest):
    try:
        claims = verify_google_id_token(body.id_token)
    except InvalidGoogleToken as exc:
        raise HTTPException(401, f"Google sign-in failed: {exc}") from exc

    user = get_or_create_user_by_google(
        sub=claims["sub"],
        email=claims["email"],
        name=claims.get("name"),
        picture_url=claims.get("picture"),
    )
    access_token = create_access_token(user_id=user["id"])
    return SessionResponse(access_token=access_token, user=_public_user(user))


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return _public_user(user)


@router.post("/auth/dev-login", response_model=SessionResponse)
async def dev_login():
    if not ALLOW_DEV_LOGIN:
        # 404, not 403 — a disabled dev-login route shouldn't even confirm
        # it exists to something probing the API.
        raise HTTPException(404, "Not found.")

    user = get_or_create_user_by_google(
        sub=DEV_USER_SUB,
        email=DEV_USER_EMAIL,
        name="Dev Tester",
        picture_url=None,
    )
    access_token = create_access_token(user_id=user["id"])
    return SessionResponse(access_token=access_token, user=_public_user(user))


def _public_user(user: dict) -> dict:
    """Strips internal-only fields (google_sub should never round-trip to
    a client) before returning a user over the API. created_at is kept —
    the mobile Home screen uses it for "days since starting"."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture_url": user["picture_url"],
        "created_at": user["created_at"],
    }

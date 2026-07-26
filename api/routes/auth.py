"""
Authentication routes for local development and testing.
Provides /auth/dev-login endpoint to auto-mint session JWT tokens.
"""

from fastapi import APIRouter
from auth.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Fixed Mongo ObjectId string for local development user
DEV_USER_ID = "65f1a2b3c4d5e6f7a8b9c0d1"


@router.api_route("/dev-login", methods=["GET", "POST"])
async def dev_login():
    """Generates a valid JWT session token for local testing and web app UI."""
    token = create_access_token(user_id=DEV_USER_ID)
    return {
        "token": token,
        "user_id": DEV_USER_ID,
        "message": "Dev authentication token generated successfully",
    }

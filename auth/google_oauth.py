"""
Verifies Google ID tokens the mobile app hands us after a native Google
Sign-In. This is the ONLY thing that establishes trust — never accept a
client-asserted email/sub without this verification, or anyone could POST
an arbitrary "I am this user" payload to /auth/google.
"""

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from config import GOOGLE_OAUTH_CLIENT_ID

_google_request = google_requests.Request()


class InvalidGoogleToken(Exception):
    pass


def verify_google_id_token(token: str) -> dict:
    """Verifies signature, expiry, and audience (must match our own OAuth
    client ID) against Google's public keys. Returns the token's claims
    (sub, email, name, picture, email_verified, ...) on success.

    Raises InvalidGoogleToken on any failure — expired, wrong audience,
    tampered signature, or malformed input. Callers should treat this as a
    401, not a 500: an invalid token is an expected outcome, not a bug.
    """
    if not GOOGLE_OAUTH_CLIENT_ID:
        raise InvalidGoogleToken("GOOGLE_OAUTH_CLIENT_ID is not configured on this server.")
    try:
        claims = id_token.verify_oauth2_token(token, _google_request, GOOGLE_OAUTH_CLIENT_ID)
    except ValueError as exc:
        raise InvalidGoogleToken(str(exc)) from exc

    if not claims.get("email_verified", False):
        raise InvalidGoogleToken("Google account email is not verified.")

    return claims

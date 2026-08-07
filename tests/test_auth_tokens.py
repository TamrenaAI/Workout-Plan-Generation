"""
Tests for auth/tokens.py — the JWT issuance/verification this backend uses
for its own mobile session tokens (separate from the short-lived Google ID
token, which is only ever exchanged once at POST /auth/google).

JWT_SECRET is monkeypatched rather than read from .env, so this test
doesn't depend on a developer's local secret being configured.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import tokens
from auth.tokens import InvalidSessionToken


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def test_round_trip_returns_same_user_id():
    user_id = str(uuid.uuid4())
    token = tokens.create_access_token(user_id=user_id)
    assert tokens.decode_access_token(token) == user_id


def test_tampered_token_is_rejected():
    token = tokens.create_access_token(user_id=str(uuid.uuid4()))
    # Flip a character in the payload segment (not the very last character
    # of the signature) — the last base64 character before padding can
    # encode as few as 2 meaningful bits depending on byte-length
    # alignment, so occasionally flipping it doesn't change the decoded
    # bytes at all and the tamper is a no-op. A middle character always
    # changes the decoded payload, guaranteeing the signature won't match.
    mid = len(token) // 2
    tampered = token[:mid] + ("A" if token[mid] != "A" else "B") + token[mid + 1:]
    with pytest.raises(InvalidSessionToken):
        tokens.decode_access_token(tampered)


def test_expired_token_is_rejected():
    now = datetime.now(timezone.utc)
    expired_payload = {"sub": "7", "iat": now - timedelta(days=2), "exp": now - timedelta(days=1)}
    expired_token = jwt.encode(expired_payload, tokens.JWT_SECRET, algorithm=tokens.JWT_ALGORITHM)
    with pytest.raises(InvalidSessionToken):
        tokens.decode_access_token(expired_token)


def test_token_signed_with_wrong_secret_is_rejected():
    now = datetime.now(timezone.utc)
    payload = {"sub": "5", "iat": now, "exp": now + timedelta(minutes=5)}
    wrong_secret_token = jwt.encode(payload, "a-different-secret", algorithm=tokens.JWT_ALGORITHM)
    with pytest.raises(InvalidSessionToken):
        tokens.decode_access_token(wrong_secret_token)

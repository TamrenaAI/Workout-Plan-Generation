"""
Tests for auth/tokens.py — the JWT issuance/verification this backend uses
for its own mobile session tokens (separate from the short-lived Google ID
token, which is only ever exchanged once at POST /auth/google).

JWT_SECRET is monkeypatched rather than read from .env, so this test
doesn't depend on a developer's local secret being configured.
"""

import os
import sys
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
    token = tokens.create_access_token(user_id=42)
    assert tokens.decode_access_token(token) == 42


def test_tampered_token_is_rejected():
    token = tokens.create_access_token(user_id=1)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
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

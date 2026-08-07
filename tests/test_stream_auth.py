"""
Tests for GET /generate-plan/stream/{session_id}'s auth dependency
(auth.dependencies.get_current_user_for_stream). The browser's native
EventSource API can't send an Authorization header, so this route accepts
the session token as a `?token=` query param too, in addition to the
header every other route requires. A bogus/missing token must still 401;
a valid token via either channel must pass auth (verified by getting a 404
"unknown session" instead of a 401 "unauthenticated" for a session_id that
doesn't exist — that 404 only happens after auth succeeds).
"""

import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import tokens


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def _dev_token() -> str:
    return tokens.create_access_token(user_id=str(uuid.uuid4()))


def test_stream_accepts_token_via_authorization_header():
    import api.main as m

    client = TestClient(m.app)
    token = _dev_token()

    r = client.get(
        "/generate-plan/stream/does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Auth passed (not 401) — falls through to the ownership/existence check.
    assert r.status_code == 404


def test_stream_accepts_token_via_query_param():
    import api.main as m

    client = TestClient(m.app)
    token = _dev_token()

    r = client.get(f"/generate-plan/stream/does-not-exist?token={token}")
    assert r.status_code == 404


def test_stream_rejects_missing_token():
    import api.main as m

    client = TestClient(m.app)

    r = client.get("/generate-plan/stream/does-not-exist")
    assert r.status_code == 401


def test_stream_rejects_invalid_token_from_query_param():
    import api.main as m

    client = TestClient(m.app)

    r = client.get("/generate-plan/stream/does-not-exist?token=not-a-real-token")
    assert r.status_code == 401


def test_header_takes_precedence_when_both_present_and_query_is_invalid():
    import api.main as m

    client = TestClient(m.app)
    token = _dev_token()

    r = client.get(
        "/generate-plan/stream/does-not-exist?token=garbage",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404

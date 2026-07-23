"""
Tests for POST /auth/dev-login — must be a real 404 (route effectively
doesn't exist) when config.ALLOW_DEV_LOGIN is unset, and must only work
when a test explicitly opts in. This is the one auth endpoint with no
credential check at all, so its off-by-default behavior matters more than
usual.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routes import auth as auth_routes
from auth import tokens


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def test_disabled_by_default(monkeypatch):
    import api.main as m

    # Explicitly set false rather than relying on the ambient environment —
    # a developer's local .env may well have ALLOW_DEV_LOGIN=true set for
    # their own convenience (as this project's does), which must not make
    # this test pass for the wrong reason.
    monkeypatch.setattr(auth_routes, "ALLOW_DEV_LOGIN", False)

    client = TestClient(m.app)
    r = client.post("/auth/dev-login")
    assert r.status_code == 404


def test_works_when_explicitly_enabled(monkeypatch):
    import api.main as m

    monkeypatch.setattr(auth_routes, "ALLOW_DEV_LOGIN", True)

    client = TestClient(m.app)
    r = client.post("/auth/dev-login")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "dev@tamreena.local"
    assert body["access_token"]

    # GET /auth/me with the returned token should resolve to the same user.
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "dev@tamreena.local"


def test_repeated_calls_reuse_the_same_account(monkeypatch):
    import api.main as m

    monkeypatch.setattr(auth_routes, "ALLOW_DEV_LOGIN", True)

    client = TestClient(m.app)
    first = client.post("/auth/dev-login").json()
    second = client.post("/auth/dev-login").json()
    assert first["user"]["id"] == second["user"]["id"]

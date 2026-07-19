"""
Tests for auth/ownership.py — the plan_sessions table answering "does user
X own session Y", used by GET /sessions and the SSE stream endpoint so
users can't read each other's generated plans (session_ids are UUIDs, not
secrets, so ownership has to be checked server-side, not assumed from
knowing the id).

DB_PATH is monkeypatched to a temp SQLite file so these tests never touch
the real data/tamreena.db.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(ownership, "DB_PATH", tmp_path / "test_ownership.db")
    ownership.init_db()


def test_owner_can_be_verified():
    ownership.create_session("session-a", user_id=1, goal="hypertrophy")
    assert ownership.user_owns_session("session-a", user_id=1) is True


def test_non_owner_is_rejected():
    ownership.create_session("session-a", user_id=1, goal="hypertrophy")
    assert ownership.user_owns_session("session-a", user_id=2) is False


def test_unknown_session_is_rejected():
    assert ownership.user_owns_session("does-not-exist", user_id=1) is False


def test_list_sessions_for_user_returns_only_their_own():
    ownership.create_session("s1", user_id=1, goal="strength")
    ownership.create_session("s2", user_id=1, goal="fat_loss")
    ownership.create_session("s3", user_id=2, goal="hypertrophy")

    sessions = ownership.list_sessions_for_user(1)
    assert {s["session_id"] for s in sessions} == {"s1", "s2"}


def test_sessions_endpoint_requires_auth():
    import api.main as m

    client = TestClient(m.app)
    r = client.get("/sessions")
    assert r.status_code == 401

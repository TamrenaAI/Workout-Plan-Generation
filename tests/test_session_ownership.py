"""
Tests for auth/ownership.py — the plan_sessions collection answering "does
user X own session Y", used by GET /sessions and the SSE stream endpoint so
users can't read each other's generated plans (session_ids are UUIDs, not
secrets, so ownership has to be checked server-side, not assumed from
knowing the id).

Mongo access is mongomock'd per-test — see tests/conftest.py's mongo_db
fixture (autouse).
"""

import os
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership


def _uid() -> str:
    return str(uuid.uuid4())


def test_owner_can_be_verified():
    user_id = _uid()
    ownership.create_session("session-a", user_id=user_id, goal="hypertrophy")
    assert ownership.user_owns_session("session-a", user_id=user_id) is True


def test_non_owner_is_rejected():
    ownership.create_session("session-a", user_id=_uid(), goal="hypertrophy")
    assert ownership.user_owns_session("session-a", user_id=_uid()) is False


def test_unknown_session_is_rejected():
    assert ownership.user_owns_session("does-not-exist", user_id=_uid()) is False


def test_list_sessions_for_user_returns_only_their_own():
    user1, user2 = _uid(), _uid()
    ownership.create_session("s1", user_id=user1, goal="strength")
    ownership.create_session("s2", user_id=user1, goal="fat_loss")
    ownership.create_session("s3", user_id=user2, goal="hypertrophy")

    sessions = ownership.list_sessions_for_user(user1)
    assert {s["session_id"] for s in sessions} == {"s1", "s2"}


def test_session_status_defaults_to_generating_and_can_be_updated():
    session_id = "session-status"
    ownership.create_session(session_id, user_id=_uid(), goal="hypertrophy")
    assert ownership.get_session(session_id)["status"] == "generating"

    ownership.update_session_status(session_id, "ready")
    assert ownership.get_session(session_id)["status"] == "ready"

    ownership.update_session_status(session_id, "failed", error="boom")
    session = ownership.get_session(session_id)
    assert session["status"] == "failed"
    assert session["error"] == "boom"


def test_sessions_endpoint_requires_auth():
    import api.main as m

    client = TestClient(m.app)
    r = client.get("/sessions")
    assert r.status_code == 401

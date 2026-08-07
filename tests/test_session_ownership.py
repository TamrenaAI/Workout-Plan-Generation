"""
Tests for auth/ownership.py — the plan_sessions collection answering "does
user X own session Y", used by GET /sessions and the SSE stream endpoint so
users can't read each other's generated plans (session_ids are UUIDs, not
secrets, so ownership has to be checked server-side, not assumed from
knowing the id).

DynamoDB access is moto-mocked per-test — see tests/conftest.py's
dynamo_tables fixture (autouse).
"""

import os
import sys
import uuid
from decimal import Decimal

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


def test_get_session_intake_ints_are_not_decimal():
    """Regression test: boto3 always deserializes DynamoDB's Number type as
    Decimal, including for values nested inside a map attribute like
    `intake` (days_per_week, age, ...). If get_session() ever hands back a
    Decimal here, api/routes/plan.py's monthly-review same_goal=true path
    passes it straight into pipeline/monthly_progress.py::_adherence, where
    `days_per_week * weeks_elapsed` (a float) raises TypeError. Asserting
    equality alone (Decimal(3) == 3) would NOT catch a regression here —
    the type itself must be checked."""
    session_id = _uid()
    intake = {"days_per_week": 3, "age": 30, "experience": "beginner"}
    ownership.create_session(session_id, user_id=_uid(), goal="hypertrophy", intake=intake)

    session = ownership.get_session(session_id)
    assert session["intake"]["days_per_week"] == 3
    assert isinstance(session["intake"]["days_per_week"], int)
    assert not isinstance(session["intake"]["days_per_week"], Decimal)
    assert isinstance(session["intake"]["age"], int)
    assert not isinstance(session["intake"]["age"], Decimal)


def test_list_sessions_for_user_intake_ints_are_not_decimal():
    """Same regression as above, via list_sessions_for_user's read path
    (used by GET /sessions), which builds its own _serialize call separate
    from get_session's."""
    user_id = _uid()
    ownership.create_session("s-intake-list", user_id=user_id, goal="hypertrophy",
                              intake={"days_per_week": 5, "age": 22})

    sessions = ownership.list_sessions_for_user(user_id)
    assert len(sessions) == 1
    assert isinstance(sessions[0]["intake"]["days_per_week"], int)
    assert not isinstance(sessions[0]["intake"]["days_per_week"], Decimal)


def test_sessions_endpoint_requires_auth():
    import api.main as m

    client = TestClient(m.app)
    r = client.get("/sessions")
    assert r.status_code == 401

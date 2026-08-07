"""
Tests for monthly-review eligibility computation (auth/ownership.py):
a session becomes eligible 30 days after creation, only once its plan has
finished generating, and only until a review has already been created for it.

DynamoDB access is moto'd per-test — see tests/conftest.py's dynamo_tables
fixture (autouse).
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership
from tools.dynamo import get_plan_sessions_table

_SAMPLE_INTAKE = {
    "goal": "hypertrophy", "days_per_week": 4, "experience": "beginner",
    "session_duration": "60min", "injuries": None, "priority": None,
    "age": None, "sleep_quality": None, "job_type": None, "current_program": None,
}


def _make_user(sub: str) -> dict:
    # This service no longer owns `users` (see
    # docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md) — a
    # fresh uuid4 is all any test needs, since every route here only
    # ever reads the id. `sub` is kept as a parameter purely so call sites
    # stay readable (e.g. `_make_user("cv-owner")`); it's not used for
    # deduplication anymore, each call already produces a distinct id.
    return {"id": str(uuid.uuid4())}


def _backdate_and_ready(session_id: str, days: int):
    get_plan_sessions_table().update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET #s = :status, created_at = :created_at",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": "ready",
            ":created_at": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(),
        },
    )


def test_create_session_persists_intake_and_previous_session_id():
    owner = _make_user("elig-create")
    ownership.create_session("s0", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE, previous_session_id="prev-0")

    doc = ownership.get_session("s0")
    assert doc["intake"] == _SAMPLE_INTAKE
    assert doc["previous_session_id"] == "prev-0"


def test_session_not_eligible_before_30_days():
    owner = _make_user("elig-1")
    ownership.create_session("s1", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("s1", days=10)

    sessions = ownership.list_sessions_for_user(owner["id"])
    assert sessions[0]["eligible_for_review"] is False


def test_session_eligible_after_30_days_and_ready():
    owner = _make_user("elig-2")
    ownership.create_session("s2", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("s2", days=31)

    sessions = ownership.list_sessions_for_user(owner["id"])
    assert sessions[0]["eligible_for_review"] is True


def test_session_not_eligible_if_still_generating():
    owner = _make_user("elig-3")
    ownership.create_session("s3", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    get_plan_sessions_table().update_item(
        Key={"session_id": "s3"},
        UpdateExpression="SET created_at = :created_at",
        ExpressionAttributeValues={
            ":created_at": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
        },
    )
    # status is left at "generating" — never marked ready

    sessions = ownership.list_sessions_for_user(owner["id"])
    assert sessions[0]["eligible_for_review"] is False


def test_session_not_eligible_once_already_reviewed():
    owner = _make_user("elig-4")
    ownership.create_session("s4", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("s4", days=31)
    ownership.create_session("s4-review", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE, previous_session_id="s4")

    sessions = ownership.list_sessions_for_user(owner["id"])
    s4 = next(s for s in sessions if s["session_id"] == "s4")
    assert s4["eligible_for_review"] is False


def test_get_session_reports_eligibility_same_as_list():
    owner = _make_user("elig-5")
    ownership.create_session("s5", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("s5", days=31)

    doc = ownership.get_session("s5")
    assert doc["eligible_for_review"] is True


def test_get_session_created_at_is_timezone_aware():
    # Regression test: _serialize used to return doc["created_at"] (the raw,
    # possibly-naive value) instead of the normalized tz-aware local
    # variable it computed for the eligibility check. A naive datetime
    # here would make any caller doing
    # `datetime.now(timezone.utc) - get_session(...)["created_at"]`
    # (e.g. pipeline/monthly_progress.py's _adherence) raise TypeError.
    owner = _make_user("elig-6")
    ownership.create_session("s6", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)

    doc = ownership.get_session("s6")
    assert doc["created_at"].tzinfo is not None

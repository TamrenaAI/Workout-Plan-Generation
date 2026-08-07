"""
Tests for pipeline/workout_feedback.py (recording feedback + deciding
whether an adjustment is needed) and the read side in tools/memory.py.
Does not exercise agents/plan_adjuster.py itself — that requires a live
LLM call, same scoping as the rest of this test suite.

DynamoDB access is moto-mocked per-test — see tests/conftest.py's
dynamo_tables fixture (autouse). workout_feedback itself lives in DynamoDB
(see tools/dynamo.py's get_workout_feedback_table) — plan.md/feedback.json-style
session files still live under SESSION_DIR (unaffected by this migration),
hence the SESSION_DIR monkeypatch below.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership
from auth import tokens
from auth.tokens import create_access_token
from pipeline import workout_feedback
from tools import memory as tools_memory


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(tools_memory, "SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def _make_user(sub: str) -> dict:
    # This service no longer owns `users` (see
    # docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md) — a
    # fresh uuid is all any test needs, since every route here only
    # ever reads the id. `sub` is kept as a parameter purely so call sites
    # stay readable (e.g. `_make_user("cv-owner")`); it's not used for
    # deduplication anymore, each call already produces a distinct id.
    return {"id": str(uuid.uuid4())}


def test_needs_adjustment_false_when_everything_just_right():
    exercises = [
        {"name": "Bench Press", "completed": True, "difficulty": "just_right", "pain": False},
        {"name": "Incline Press", "completed": True, "difficulty": "just_right", "pain": False},
    ]
    assert workout_feedback.needs_adjustment(exercises) is False


@pytest.mark.parametrize("exercises", [
    [{"name": "Bench Press", "difficulty": "too_hard", "pain": False}],
    [{"name": "Bench Press", "difficulty": "too_easy", "pain": False}],
    [{"name": "Bench Press", "difficulty": "just_right", "pain": True}],
])
def test_needs_adjustment_true_when_flagged(exercises):
    assert workout_feedback.needs_adjustment(exercises) is True


def test_record_feedback_accumulates_submissions_and_is_readable_via_memory_tool():
    user = _make_user("feedback-user")
    session_id = "session-1"
    workout_feedback.record_feedback(
        user["id"], session_id, "Day 1", [{"name": "Bench Press", "difficulty": "too_hard", "pain": False}], True,
    )
    workout_feedback.record_feedback(
        user["id"], session_id, "Day 2", [{"name": "Squat", "difficulty": "just_right", "pain": False}], False,
    )

    raw = tools_memory.read_workout_feedback.invoke({"session_id": session_id})
    submissions = json.loads(raw)
    assert len(submissions) == 2
    assert submissions[0]["day_label"] == "Day 1"
    assert submissions[1]["day_label"] == "Day 2"


def test_read_workout_feedback_before_any_submission():
    raw = tools_memory.read_workout_feedback.invoke({"session_id": "never-submitted"})
    assert raw == "(no feedback submitted yet for this session)"


def test_feedback_endpoint_requires_ownership():
    import api.main as m

    owner = _make_user("owner-sub")
    other = _make_user("other-sub")

    session_id = "someone-elses-session"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = create_access_token(user_id=other["id"])

    r = client.post(
        f"/workouts/{session_id}/feedback",
        json={"day_label": "Day 1", "exercises": [{"name": "Bench Press"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_record_and_read_exercise_adjustments_scoped_by_since():
    session_id = "session-adj"
    since = datetime.now(timezone.utc) - timedelta(seconds=1)

    tools_memory.record_exercise_adjustment.invoke({
        "session_id": session_id,
        "day_label": "Day 1",
        "exercise_name": "Overhead Press",
        "reason": "Shoulder pain reported on pressing movement.",
        "new_exercise_name": "Machine Shoulder Press",
    })
    tools_memory.record_exercise_adjustment.invoke({
        "session_id": session_id,
        "day_label": "Day 1",
        "exercise_name": "Squat",
        "reason": "Felt too easy at prescribed volume.",
        "sets": 4,
    })

    adjustments = tools_memory.read_exercise_adjustments(session_id, "Day 1", since=since)
    assert len(adjustments) == 2
    assert adjustments[0]["exercise_name"] == "Overhead Press"
    assert adjustments[0]["new_exercise_name"] == "Machine Shoulder Press"
    assert adjustments[1]["exercise_name"] == "Squat"
    assert adjustments[1]["sets"] == 4
    assert adjustments[1]["new_exercise_name"] is None


def test_read_exercise_adjustments_excludes_entries_before_since():
    session_id = "session-adj-2"
    tools_memory.record_exercise_adjustment.invoke({
        "session_id": session_id,
        "day_label": "Day 1",
        "exercise_name": "Bench Press",
        "reason": "Prior adjustment run.",
        "sets": 3,
    })

    later = datetime.now(timezone.utc) + timedelta(seconds=1)
    adjustments = tools_memory.read_exercise_adjustments(session_id, "Day 1", since=later)
    assert adjustments == []


def test_feedback_endpoint_no_adjustment_path_skips_llm_call():
    import api.main as m

    owner = _make_user("solo-owner")
    session_id = "own-session"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = create_access_token(user_id=owner["id"])

    r = client.post(
        f"/workouts/{session_id}/feedback",
        json={"day_label": "Day 1", "exercises": [{"name": "Bench Press", "difficulty": "just_right", "pain": False}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["adjustment_triggered"] is False
    assert body["summary"] is None

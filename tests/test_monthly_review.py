"""
Tests for POST /plan/{session_id}/monthly-review and
GET /progress/{session_id}/report — the validation-only paths reachable
without invoking the InBody VLM pipeline or any LLM agent, matching this
suite's existing convention (see tests/test_workout_feedback.py's module
docstring) of never exercising real LLM calls in tests.

Mongo access is mongomock'd per-test — see tests/conftest.py's mongo_db
fixture (autouse).
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bson import ObjectId
from auth import ownership
from auth import tokens
from pipeline import monthly_progress
from tools.inbody import InBodyFlags, InBodyRawExtraction, InBodyResult, SegmentalReading
from tools.mongo import get_db

_SAMPLE_INTAKE = {
    "goal": "hypertrophy", "days_per_week": 4, "experience": "beginner",
    "session_duration": "60min", "injuries": None, "priority": None,
    "age": None, "sleep_quality": None, "job_type": None, "current_program": None,
}


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    import tools.memory as tools_memory
    monkeypatch.setattr(tools_memory, "SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def _make_user(sub: str) -> dict:
    # This service no longer owns `users` (see
    # docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md) — a
    # fresh ObjectId is all any test needs, since every route here only
    # ever reads the id. `sub` is kept as a parameter purely so call sites
    # stay readable (e.g. `_make_user("cv-owner")`); it's not used for
    # deduplication anymore, each call already produces a distinct id.
    return {"id": str(ObjectId())}


def _backdate_and_ready(session_id: str, days: int):
    get_db().plan_sessions.update_one(
        {"_id": session_id},
        {"$set": {"status": "ready", "created_at": datetime.now(timezone.utc) - timedelta(days=days)}},
    )


def _post_review(client, session_id, token, **form):
    data = {"same_goal": "true"}
    data.update(form)
    return client.post(
        f"/plan/{session_id}/monthly-review",
        data=data,
        files={"inbody_file": ("scan.jpg", b"fake-bytes", "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )


# --- POST /plan/{session_id}/monthly-review -----------------------------------

def test_monthly_review_requires_ownership():
    import api.main as m

    owner = _make_user("mr-owner")
    other = _make_user("mr-other")
    ownership.create_session("mr-s1", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("mr-s1", days=31)

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=other["id"])
    r = _post_review(client, "mr-s1", token)
    assert r.status_code == 404


def test_monthly_review_rejects_ineligible_session():
    import api.main as m

    owner = _make_user("mr-owner2")
    ownership.create_session("mr-s2", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("mr-s2", days=5)  # too recent

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = _post_review(client, "mr-s2", token)
    assert r.status_code == 422


def test_monthly_review_same_goal_requires_stored_intake():
    import api.main as m

    owner = _make_user("mr-owner3")
    ownership.create_session("mr-s3", owner["id"], "hypertrophy")  # no intake — legacy-style session
    _backdate_and_ready("mr-s3", days=31)

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = _post_review(client, "mr-s3", token, same_goal="true")
    assert r.status_code == 422


def test_monthly_review_changed_goal_validates_days_per_week():
    import api.main as m

    owner = _make_user("mr-owner4")
    ownership.create_session("mr-s4", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("mr-s4", days=31)

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = _post_review(
        client, "mr-s4", token,
        same_goal="false", days_per_week="10", experience="beginner",
        session_duration="60min", goal="strength",
    )
    assert r.status_code == 422


def test_monthly_review_changed_goal_requires_goal_field():
    import api.main as m

    owner = _make_user("mr-owner5")
    ownership.create_session("mr-s5", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("mr-s5", days=31)

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = _post_review(
        client, "mr-s5", token,
        same_goal="false", days_per_week="4", experience="beginner", session_duration="60min",
    )
    assert r.status_code == 422


def _make_inbody_result() -> InBodyResult:
    seg = SegmentalReading(value=3.0, unit="kg", percent_of_ideal=100.0)
    raw = InBodyRawExtraction(
        gender="male",
        weight=80.0,
        weight_unit="kg",
        skeletal_muscle_mass=30.0,
        smm_unit="kg",
        body_fat_percent=20.0,
        right_arm=seg,
        left_arm=seg,
        trunk=seg,
        right_leg=seg,
        left_leg=seg,
    )
    flags = InBodyFlags(
        arm_asymmetry=False, arm_diff_grams=50.0,
        leg_asymmetry=False, leg_diff_grams=50.0,
        elevated_bf=False, trunk_underdeveloped=False,
    )
    return InBodyResult(raw=raw, flags=flags)


def test_monthly_review_marks_session_failed_on_summary_error(monkeypatch):
    import api.routes.plan as plan_route

    owner = _make_user("mr-owner6")
    ownership.create_session("mr-s6", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    _backdate_and_ready("mr-s6", days=31)

    monkeypatch.setattr(plan_route, "run_inbody_pipeline_from_bytes", lambda *a, **kw: _make_inbody_result())

    def _boom(*args, **kwargs):
        raise RuntimeError("agent blew up")

    monkeypatch.setattr(plan_route, "build_monthly_summary", _boom)

    import api.main as m

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = _post_review(client, "mr-s6", token)
    assert r.status_code == 500

    new_sessions = list(get_db().plan_sessions.find({"previous_session_id": "mr-s6"}))
    assert len(new_sessions) == 1
    doc = new_sessions[0]
    assert doc["status"] == "failed"
    assert doc.get("error")


# --- GET /progress/{session_id}/report ----------------------------------------

def test_get_report_requires_ownership():
    import api.main as m

    owner = _make_user("rep-owner")
    other = _make_user("rep-other")
    ownership.create_session("rep-s1", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=other["id"])
    r = client.get("/progress/rep-s1/report", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_get_report_404_when_no_report_yet():
    import api.main as m

    owner = _make_user("rep-owner2")
    ownership.create_session("rep-s2", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get("/progress/rep-s2/report", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_get_report_returns_stored_report():
    import api.main as m

    owner = _make_user("rep-owner3")
    ownership.create_session("rep-old", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    ownership.create_session("rep-new", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE, previous_session_id="rep-old")
    monthly_progress.record_progress_report(owner["id"], "rep-old", "rep-new", {"adherence": {}}, "Solid month.")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get("/progress/rep-new/report", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["narrative"] == "Solid month."
    assert body["old_session_id"] == "rep-old"

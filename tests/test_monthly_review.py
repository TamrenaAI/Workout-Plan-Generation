"""
Tests for POST /plan/{session_id}/monthly-review and
GET /progress/{session_id}/report — the validation-only paths reachable
without invoking the InBody VLM pipeline or any LLM agent, matching this
suite's existing convention (see tests/test_workout_feedback.py's module
docstring) of never exercising real LLM calls in tests.

plan_sessions, corrective_results, and progress_reports all live on
DynamoDB (moto'd per-test — see tests/conftest.py's dynamo_tables fixture).
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership
from auth import tokens
from pipeline import monthly_progress
from tools.inbody import InBodyFlags, InBodyRawExtraction, InBodyResult, SegmentalReading
from tools.dynamo import get_plan_sessions_table

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

    resp = get_plan_sessions_table().query(
        IndexName="previous-session-index",
        KeyConditionExpression="previous_session_id = :sid",
        ExpressionAttributeValues={":sid": "mr-s6"},
    )
    new_sessions = resp["Items"]
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


def test_record_progress_report_survives_nested_floats():
    """Regression test for the TypeError: Float types are not supported bug
    that record_progress_report's _floats_to_decimal() helper fixes. summary
    here is shaped like build_monthly_summary's real output, with real
    Python floats nested at every level _floats_to_decimal has to recurse
    into: top-level (adherence_rate), one level deep (rep_quality.accuracy/
    avg_score), two levels deep (rep_quality.per_exercise's dict-of-dicts),
    and inbody_delta's deltas. put_item must not raise, and the round-tripped
    value must come back as a native float (not a Decimal) because this test
    goes through the real GET /progress/{id}/report endpoint, whose JSON
    response encoding is what actually converts Decimal back to float —
    calling get_progress_report() directly would still hand back Decimals
    straight from boto3's DynamoDB resource, which wouldn't exercise that
    conversion at all."""
    import api.main as m

    owner = _make_user("rep-owner4")
    ownership.create_session("rep-old2", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE)
    ownership.create_session("rep-new2", owner["id"], "hypertrophy", intake=_SAMPLE_INTAKE, previous_session_id="rep-old2")

    summary = {
        "adherence": {"sessions_submitted": 8, "sessions_expected": 12, "adherence_rate": 0.6667},
        "rep_quality": {
            "total_reps": 120, "good_reps": 100, "bad_reps": 20,
            "accuracy": 0.8333, "avg_score": 87.25,
            "per_exercise": {
                "Squat": {"good": 60, "bad": 10, "accuracy": 0.8571, "avg_score": 88.5},
                "Bench Press": {"good": 40, "bad": 10, "accuracy": 0.8, "avg_score": 85.0},
            },
            "top_form_errors": [{"error_type": "knee_valgus", "count": 3}],
        },
        "subjective_flags": {"Squat": {"too_hard": 1, "too_easy": 0, "pain": 0}},
        "inbody_delta": {
            "skeletal_muscle_mass_kg": 1.5, "body_fat_percent": -1.5,
            "arm_asymmetry_resolved": True, "leg_asymmetry_resolved": False,
            "trunk_underdeveloped_resolved": False,
        },
    }

    # (1) & (2): must not raise TypeError: Float types are not supported.
    monthly_progress.record_progress_report(owner["id"], "rep-old2", "rep-new2", summary, "Great month overall.")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get("/progress/rep-new2/report", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()

    got_summary = body["summary"]
    assert got_summary == summary
    # Confirm specific nested floats round-tripped as native floats, not Decimals.
    assert got_summary["adherence"]["adherence_rate"] == pytest.approx(0.6667)
    assert isinstance(got_summary["adherence"]["adherence_rate"], float)
    assert got_summary["rep_quality"]["avg_score"] == pytest.approx(87.25)
    assert isinstance(got_summary["rep_quality"]["avg_score"], float)
    assert got_summary["rep_quality"]["per_exercise"]["Squat"]["avg_score"] == pytest.approx(88.5)
    assert isinstance(got_summary["rep_quality"]["per_exercise"]["Squat"]["avg_score"], float)
    assert got_summary["inbody_delta"]["skeletal_muscle_mass_kg"] == pytest.approx(1.5)
    assert isinstance(got_summary["inbody_delta"]["skeletal_muscle_mass_kg"], float)

    # Also confirm record_progress_report's direct write path (get_progress_report,
    # not the API) round-trips without raising, per the reviewer's requested check —
    # values here come back as Decimal (boto3's native DynamoDB numeric type), which
    # is why the float-typing assertions above go through the API's JSON encoding.
    direct = monthly_progress.get_progress_report("rep-new2")
    assert direct is not None
    assert float(direct["summary"]["rep_quality"]["avg_score"]) == pytest.approx(87.25)

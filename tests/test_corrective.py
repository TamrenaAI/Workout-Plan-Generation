"""
Tests for api/routes/corrective.py — ingestion of the CV correction
system's native per-exercise JSON export (see Hack_Squat_20260723_000913.json,
repo root, for a real sample this schema is modeled on).

corrective_results lives in DynamoDB (moto'd per-test — see
tests/conftest.py's dynamo_tables fixture).
"""

import os
import sys
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership
from auth.tokens import create_access_token
from tools.dynamo import get_corrective_results_table


def _make_user(sub: str) -> dict:
    # This service no longer owns `users` (see
    # docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md) — a
    # fresh uuid4 is all any test needs, since every route here only
    # ever reads the id. `sub` is kept as a parameter purely so call sites
    # stay readable (e.g. `_make_user("cv-owner")`); it's not used for
    # deduplication anymore, each call already produces a distinct id.
    return {"id": str(uuid.uuid4())}


def _cv_payload(**overrides) -> dict:
    payload = {
        "session": {"recorded_at": "2026-07-22T21:09:13.970653+00:00"},
        "exercise": {"name": "Hack Squat"},
        "summary": {
            "total_reps": 4,
            "good_reps": 2,
            "bad_reps": 2,
            "accuracy": 50.0,
            "average_rep_duration": 3.47,
            "fastest_rep": 2.68,
            "slowest_rep": 4.2,
            "total_workout_duration": 24.72,
            "common_errors": {"knee_unlocked": 3},
            "most_common_error": "knee_unlocked",
            "score": 85.0,
        },
    }
    payload.update(overrides)
    return payload


def test_corrective_endpoint_requires_ownership():
    import api.main as m

    owner = _make_user("cv-owner")
    other = _make_user("cv-other")
    session_id = "someone-elses-session"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = create_access_token(user_id=other["id"])

    r = client.post(
        f"/workouts/{session_id}/corrective-results",
        json=_cv_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_corrective_endpoint_accepts_real_cv_json_shape_and_stores_it():
    import api.main as m

    owner = _make_user("cv-solo-owner")
    session_id = "cv-own-session"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = create_access_token(user_id=owner["id"])

    r = client.post(
        f"/workouts/{session_id}/corrective-results",
        json=_cv_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"recorded": 1}

    resp = get_corrective_results_table().query(
        IndexName="session-index",
        KeyConditionExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": session_id},
    )
    items = resp["Items"]
    assert len(items) == 1
    doc = items[0]
    assert doc["exercise_name"] == "Hack Squat"
    assert doc["total_reps"] == 4
    assert doc["good_reps"] == 2
    assert doc["bad_reps"] == 2
    assert float(doc["accuracy"]) == 50.0
    assert float(doc["score"]) == 85.0
    assert doc["common_errors"] == {"knee_unlocked": 3}
    assert doc["most_common_error"] == "knee_unlocked"
    assert float(doc["average_rep_duration"]) == 3.47
    assert float(doc["fastest_rep"]) == 2.68
    assert float(doc["slowest_rep"]) == 4.2
    assert float(doc["total_workout_duration"]) == 24.72
    expected = datetime.fromisoformat("2026-07-22T21:09:13.970653+00:00")
    actual = datetime.fromisoformat(doc["recorded_at"])
    assert abs((actual - expected).total_seconds()) < 0.001


def test_corrective_endpoint_rejects_impossible_rep_counts():
    import api.main as m

    owner = _make_user("cv-bad-counts-owner")
    session_id = "cv-bad-counts-session"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = create_access_token(user_id=owner["id"])

    bad_summary = _cv_payload()
    bad_summary["summary"]["good_reps"] = 3
    bad_summary["summary"]["bad_reps"] = 3
    bad_summary["summary"]["total_reps"] = 4  # 3 + 3 > 4

    r = client.post(
        f"/workouts/{session_id}/corrective-results",
        json=bad_summary,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_corrective_endpoint_ignores_unknown_fields_from_full_cv_export():
    import api.main as m

    owner = _make_user("cv-full-export-owner")
    session_id = "cv-full-export-session"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = create_access_token(user_id=owner["id"])

    full_payload = _cv_payload(
        rules=[{"name": "knee_unlocked", "type": "angle", "severity": "warning"}],
        history=[{"number": 1, "good": False, "evaluations": []}],
        stats={"rules": [], "scores": {"best": 100.0, "worst": 80.0, "std_dev": 8.66}},
    )

    r = client.post(
        f"/workouts/{session_id}/corrective-results",
        json=full_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

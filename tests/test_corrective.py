"""
Tests for api/routes/corrective.py — ingestion of the CV correction
system's native per-exercise JSON export (see Hack_Squat_20260723_000913.json,
repo root, for a real sample this schema is modeled on).

Mongo access is mongomock'd per-test — see tests/conftest.py's mongo_db
fixture (autouse).
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import models as auth_models
from auth import ownership
from auth.tokens import create_access_token
from tools.mongo import get_db


def _make_user(sub: str) -> dict:
    return auth_models.get_or_create_user_by_google(sub=sub, email=f"{sub}@example.com", name=sub, picture_url=None)


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

    doc = get_db().corrective_results.find_one({"session_id": session_id})
    assert doc is not None
    assert doc["exercise_name"] == "Hack Squat"
    assert doc["total_reps"] == 4
    assert doc["good_reps"] == 2
    assert doc["bad_reps"] == 2
    assert doc["accuracy"] == 50.0
    assert doc["score"] == 85.0
    assert doc["common_errors"] == {"knee_unlocked": 3}
    assert doc["most_common_error"] == "knee_unlocked"
    assert doc["average_rep_duration"] == 3.47
    assert doc["fastest_rep"] == 2.68
    assert doc["slowest_rep"] == 4.2
    assert doc["total_workout_duration"] == 24.72
    assert doc["recorded_at"].isoformat() == "2026-07-22T21:09:13.970653+00:00"


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

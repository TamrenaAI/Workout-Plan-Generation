"""
Tests for GET /exercises/lookup (api/routes/exercises.py) — the fuzzy-match
lookup endpoint. GET /exercises itself is covered by test_exercises_list.py;
this endpoint had no test coverage before this task.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth.dependencies import get_current_user
from tools.dynamo import get_exercises_table

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    original_override = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-id"}
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_override)


def _make_doc(name, target_muscle, gif_path="gifs/test.gif"):
    return {
        "exercise_id": str(uuid.uuid4()),
        "name": name,
        "target_muscle": target_muscle,
        "equipment": "barbell",
        "image_path": "images/test.jpg",
        "gif_path": gif_path,
    }


def test_lookup_exercise_returns_best_match():
    table = get_exercises_table()
    for doc in [_make_doc("barbell bench press", "chest"), _make_doc("incline dumbbell press", "chest")]:
        table.put_item(Item=doc)
    resp = client.get("/exercises/lookup", params={"name": "Flat Barbell Bench Press"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "barbell bench press"
    assert body["target_muscle"] == "chest"


def test_lookup_exercise_404_below_threshold():
    get_exercises_table().put_item(Item=_make_doc("barbell bench press", "chest"))
    resp = client.get("/exercises/lookup", params={"name": "Face Pull"})
    assert resp.status_code == 404


def test_lookup_exercise_404_when_no_exercises_exist():
    resp = client.get("/exercises/lookup", params={"name": "anything"})
    assert resp.status_code == 404


def test_lookup_exercise_is_case_insensitive():
    get_exercises_table().put_item(Item=_make_doc("Barbell Curl", "biceps"))
    resp = client.get("/exercises/lookup", params={"name": "barbell curl"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Barbell Curl"


def test_lookup_exercise_includes_instructions_and_attribution():
    doc = _make_doc("barbell row", "back")
    doc["instructions"] = "Hinge at hips, pull bar to torso."
    doc["attribution"] = "Example Source"
    get_exercises_table().put_item(Item=doc)
    resp = client.get("/exercises/lookup", params={"name": "barbell row"})
    body = resp.json()
    assert body["instructions"] == "Hinge at hips, pull bar to torso."
    assert body["attribution"] == "Example Source"


def test_lookup_exercise_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.get("/exercises/lookup", params={"name": "anything"})
    assert resp.status_code in (401, 403)

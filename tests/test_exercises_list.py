import uuid

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth.dependencies import get_current_user
from tools.dynamo import get_exercises_table

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    """Override auth dependency for these tests."""
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


def _put_all(docs):
    table = get_exercises_table()
    for doc in docs:
        table.put_item(Item=doc)


def test_list_exercises_default_pagination():
    docs = [_make_doc(f"exercise {i:03d}", "biceps") for i in range(35)]
    _put_all(docs)

    resp = client.get("/exercises")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 0
    assert body["page_size"] == 30
    assert body["total"] == 35
    assert len(body["exercises"]) == 30
    first = body["exercises"][0]
    assert set(first.keys()) == {"name", "target_muscle", "equipment", "image_url", "gif_url"}
    assert first["gif_url"] is None or first["gif_url"].startswith("/media/exercises/")

    resp_page1 = client.get("/exercises", params={"page": 1})
    body_page1 = resp_page1.json()
    assert body_page1["total"] == 35
    assert len(body_page1["exercises"]) == 5


def test_list_exercises_filters_by_muscle():
    _put_all([
        _make_doc("barbell curl", "biceps"),
        _make_doc("hammer curl", "biceps"),
        _make_doc("leg press", "quads"),
    ])

    resp = client.get("/exercises", params={"muscle": "biceps", "page_size": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(e["target_muscle"] == "biceps" for e in body["exercises"])
    names = {e["name"] for e in body["exercises"]}
    assert "leg press" not in names


def test_list_exercises_search_matches_name_case_insensitively():
    _put_all([
        _make_doc("barbell curl", "biceps"),
        _make_doc("hammer curl", "biceps"),
        _make_doc("leg press", "quads"),
    ])

    resp = client.get("/exercises", params={"q": "BARBELL curl", "page_size": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert all("curl" in e["name"].lower() for e in body["exercises"])
    names = {e["name"] for e in body["exercises"]}
    assert "leg press" not in names


def test_list_exercises_page_size_is_capped_at_100():
    docs = [_make_doc(f"exercise {i:03d}", "biceps") for i in range(150)]
    _put_all(docs)

    resp = client.get("/exercises", params={"page_size": 500})
    assert resp.status_code == 200
    assert resp.json()["page_size"] == 100
    assert len(resp.json()["exercises"]) == 100


def test_list_exercises_second_page_returns_different_results():
    docs = [_make_doc(f"exercise {i:03d}", "biceps") for i in range(20)]
    _put_all(docs)

    page0 = client.get("/exercises", params={"page": 0, "page_size": 10}).json()
    page1 = client.get("/exercises", params={"page": 1, "page_size": 10}).json()
    names0 = {e["name"] for e in page0["exercises"]}
    names1 = {e["name"] for e in page1["exercises"]}
    assert names0.isdisjoint(names1)


def test_list_exercises_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.get("/exercises")
    assert resp.status_code in (401, 403)

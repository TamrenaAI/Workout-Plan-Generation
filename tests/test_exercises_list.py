import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from api.main import app
from auth.dependencies import get_current_user
import tools.mongo as mongo_module


@pytest.fixture(autouse=True)
def use_real_mongodb_for_exercises(monkeypatch):
    """Use real MongoDB for these tests instead of mongomock."""
    # Restore real MongoDB client instead of using mongomock
    from config import MONGO_URI
    real_client = MongoClient(MONGO_URI)
    monkeypatch.setattr(mongo_module, "_client", real_client)

    # Override auth dependency only for these tests
    original_override = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-id"}
    yield
    # Restore original overrides after test
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_override)


client = TestClient(app)


def test_list_exercises_default_pagination():
    resp = client.get("/exercises")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 0
    assert body["page_size"] == 30
    assert body["total"] >= 1324
    assert len(body["exercises"]) == 30
    first = body["exercises"][0]
    assert set(first.keys()) == {"name", "target_muscle", "equipment", "image_url", "gif_url"}
    assert first["gif_url"] is None or first["gif_url"].startswith("/media/exercises/")


def test_list_exercises_filters_by_muscle():
    resp = client.get("/exercises", params={"muscle": "biceps", "page_size": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(e["target_muscle"] == "biceps" for e in body["exercises"])


def test_list_exercises_search_matches_name_case_insensitively():
    resp = client.get("/exercises", params={"q": "BARBELL curl", "page_size": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all("curl" in e["name"].lower() for e in body["exercises"])


def test_list_exercises_page_size_is_capped_at_100():
    resp = client.get("/exercises", params={"page_size": 500})
    assert resp.status_code == 200
    assert resp.json()["page_size"] == 100
    assert len(resp.json()["exercises"]) == 100


def test_list_exercises_second_page_returns_different_results():
    page0 = client.get("/exercises", params={"page": 0, "page_size": 10}).json()
    page1 = client.get("/exercises", params={"page": 1, "page_size": 10}).json()
    names0 = {e["name"] for e in page0["exercises"]}
    names1 = {e["name"] for e in page1["exercises"]}
    assert names0.isdisjoint(names1)

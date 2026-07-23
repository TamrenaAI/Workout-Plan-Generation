"""
Tests for GET /sessions/{session_id}/plan — fetching a session's persisted
weekly schedule any time after generation finishes, not just live via the
SSE stream (the gap flagged when the mobile app was wired up: there was no
way to fetch a "current plan" outside of that one-time stream).
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import models as auth_models
from auth import ownership
from auth import tokens
from tools import memory as tools_memory


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(tools_memory, "SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def _make_user(sub: str) -> dict:
    return auth_models.get_or_create_user_by_google(sub=sub, email=f"{sub}@example.com", name=sub, picture_url=None)


def test_returns_404_for_unowned_session():
    import api.main as m

    owner = _make_user("owner")
    other = _make_user("other")
    ownership.create_session("s1", user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=other["id"])
    r = client.get("/sessions/s1/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_pending_when_no_schedule_written_yet():
    import api.main as m

    owner = _make_user("owner2")
    ownership.create_session("s2", user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get("/sessions/s2/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["plan"] is None


def test_ready_when_schedule_has_been_written():
    import api.main as m

    owner = _make_user("owner3")
    session_id = "s3"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")
    tools_memory.write_plan_memory.invoke({
        "session_id": session_id,
        "section_title": "Weekly Schedule",
        "content": "### Day 1 — Push\n| # | Exercise | Sets x Reps | Rest | RPE |\n|---|---|---|---|---|\n| 1 | Bench Press | 4x8 | 2 min | 8 |",
    })

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get(f"/sessions/{session_id}/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "Bench Press" in body["plan"]


def test_requires_auth():
    import api.main as m

    client = TestClient(m.app)
    r = client.get("/sessions/anything/plan")
    assert r.status_code == 401

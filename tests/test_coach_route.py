"""Tests for POST /coach/chat. The service layer is mocked (see Task 3's
test_coach_service.py for real coverage of process_coach_message itself) --
this file only covers the route's auth, request/response shape, and error
handling, same division of labor as tests/test_workout_feedback.py's
route-level tests vs its lower-level tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

import api.routes.coach as coach_route
from api.main import app
from auth.dependencies import get_current_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    original_override = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-id"}
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_override)


def test_coach_chat_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.post("/coach/chat", json={"message": "hello"})
    assert resp.status_code in (401, 403)


def test_coach_chat_returns_agent_reply(monkeypatch):
    async def fake_process(user_id, message, nutrition_plan_snapshot):
        assert user_id == "test-user-id"
        assert message == "does chicken and rice fit my plan?"
        assert nutrition_plan_snapshot == '{"calories": 2200}'
        return "Yes, that fits your remaining macros for today."

    monkeypatch.setattr(coach_route, "process_coach_message", fake_process)

    resp = client.post(
        "/coach/chat",
        json={
            "message": "does chicken and rice fit my plan?",
            "nutrition_plan_snapshot": '{"calories": 2200}',
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"response": "Yes, that fits your remaining macros for today."}


def test_coach_chat_nutrition_snapshot_is_optional(monkeypatch):
    async def fake_process(user_id, message, nutrition_plan_snapshot):
        assert nutrition_plan_snapshot is None
        return "Looks like a solid leg day."

    monkeypatch.setattr(coach_route, "process_coach_message", fake_process)

    resp = client.post("/coach/chat", json={"message": "what's next on leg day?"})
    assert resp.status_code == 200
    assert resp.json() == {"response": "Looks like a solid leg day."}


def test_coach_chat_returns_500_when_agent_fails(monkeypatch):
    async def fake_process(user_id, message, nutrition_plan_snapshot):
        raise RuntimeError("LLM timeout")

    monkeypatch.setattr(coach_route, "process_coach_message", fake_process)

    resp = client.post("/coach/chat", json={"message": "hello"})
    assert resp.status_code == 500


def test_coach_history_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.get("/coach/history")
    assert resp.status_code in (401, 403)


def test_coach_history_returns_empty_list_for_new_user():
    resp = client.get("/coach/history")
    assert resp.status_code == 200
    assert resp.json() == {"messages": []}


def test_coach_history_returns_stored_messages_in_order():
    import uuid
    from datetime import datetime, timedelta, timezone
    from tools.dynamo import get_coach_messages_table

    table = get_coach_messages_table()
    now = datetime.now(timezone.utc)
    table.put_item(Item={
        "message_id": str(uuid.uuid4()),
        "user_id": "test-user-id",
        "role": "user",
        "content": "first question",
        "created_at": now.isoformat(),
    })
    table.put_item(Item={
        "message_id": str(uuid.uuid4()),
        "user_id": "test-user-id",
        "role": "assistant",
        "content": "first reply",
        "created_at": (now + timedelta(seconds=1)).isoformat(),
    })

    resp = client.get("/coach/history")
    assert resp.status_code == 200
    assert resp.json() == {
        "messages": [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first reply"},
        ]
    }


def test_coach_history_is_scoped_to_the_authenticated_user():
    import uuid
    from datetime import datetime, timezone
    from tools.dynamo import get_coach_messages_table

    table = get_coach_messages_table()
    table.put_item(Item={
        "message_id": str(uuid.uuid4()),
        "user_id": "someone-else",
        "role": "user",
        "content": "not yours",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    resp = client.get("/coach/history")
    assert resp.status_code == 200
    assert resp.json() == {"messages": []}

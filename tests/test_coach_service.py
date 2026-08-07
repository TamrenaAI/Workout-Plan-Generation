"""Tests for services/coach_assistant.py. run_coach_turn is mocked (a fake
coroutine) -- no live LLM call, same scoping as the rest of this test
suite. DynamoDB access is moto-mocked per-test (see tests/conftest.py's
autouse dynamo_tables fixture)."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.coach_assistant as coach_assistant
from tools.dynamo import get_coach_messages_table


def _uid() -> str:
    return str(uuid.uuid4())


def test_process_coach_message_persists_both_turns_and_returns_reply(monkeypatch):
    async def _fake_run_coach_turn(user_id, history, message, nutrition_snapshot=None):
        return "Your squat volume looks fine this week."

    monkeypatch.setattr(coach_assistant, "run_coach_turn", _fake_run_coach_turn)

    user_id = _uid()
    reply = asyncio.run(
        coach_assistant.process_coach_message(user_id, "how's my squat volume?", None)
    )

    assert reply == "Your squat volume looks fine this week."
    resp = get_coach_messages_table().query(
        IndexName="user-index",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    saved = sorted(resp["Items"], key=lambda d: (d["created_at"], d["message_id"]))
    assert [d["role"] for d in saved] == ["user", "assistant"]
    assert saved[0]["content"] == "how's my squat volume?"
    assert saved[1]["content"] == "Your squat volume looks fine this week."


def test_process_coach_message_includes_prior_turns_in_the_next_call(monkeypatch):
    replies = iter(["first reply", "second reply"])
    calls = []

    async def _fake_run_coach_turn(user_id, history, message, nutrition_snapshot=None):
        calls.append({"user_id": user_id, "history": history, "message": message})
        return next(replies)

    monkeypatch.setattr(coach_assistant, "run_coach_turn", _fake_run_coach_turn)

    user_id = _uid()
    asyncio.run(coach_assistant.process_coach_message(user_id, "first question", None))
    asyncio.run(coach_assistant.process_coach_message(user_id, "second question", None))

    second_call = calls[1]
    assert second_call["history"] == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first reply"},
    ]
    assert second_call["message"] == "second question"


def test_process_coach_message_is_scoped_per_user(monkeypatch):
    async def _fake_run_coach_turn(user_id, history, message, nutrition_snapshot=None):
        return "reply"

    monkeypatch.setattr(coach_assistant, "run_coach_turn", _fake_run_coach_turn)

    user_a, user_b = _uid(), _uid()
    asyncio.run(coach_assistant.process_coach_message(user_a, "user a's question", None))
    asyncio.run(coach_assistant.process_coach_message(user_b, "user b's question", None))

    resp = get_coach_messages_table().query(
        IndexName="user-index",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_a},
    )
    a_messages = resp["Items"]
    assert len(a_messages) == 2
    assert all(m["user_id"] == user_a for m in a_messages)


def test_process_coach_message_caps_history_at_20_most_recent_in_order(monkeypatch):
    calls = []

    async def _fake_run_coach_turn(user_id, history, message, nutrition_snapshot=None):
        calls.append(history)
        return "noted"

    monkeypatch.setattr(coach_assistant, "run_coach_turn", _fake_run_coach_turn)

    user_id = _uid()
    base_time = datetime.now(timezone.utc)
    table = get_coach_messages_table()
    for i in range(25):
        role = "user" if i % 2 == 0 else "assistant"
        table.put_item(Item={
            "message_id": str(uuid.uuid4()),
            "user_id": user_id,
            "role": role,
            "content": f"message {i}",
            "created_at": (base_time + timedelta(seconds=i)).isoformat(),
        })

    asyncio.run(coach_assistant.process_coach_message(user_id, "new question", None))

    # 20 most recent prior messages passed as history (the new question is a
    # separate argument to run_coach_turn, not part of history)
    history_sent = calls[0]
    assert len(history_sent) == 20
    # The 20 most recent of the 25 inserted are messages 5..24 (chronological order)
    assert history_sent[0] == {"role": "assistant", "content": "message 5"}
    assert history_sent[-1] == {"role": "user", "content": "message 24"}

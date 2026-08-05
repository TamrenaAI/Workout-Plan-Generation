"""Tests for services/coach_assistant.py. The agent itself is mocked (a
fake object with an ainvoke coroutine) -- no live LLM call, same scoping
as the rest of this test suite. Mongo access is mongomock'd per-test (see
tests/conftest.py's autouse mongo_db fixture)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bson import ObjectId

import services.coach_assistant as coach_assistant


def _uid() -> str:
    return str(ObjectId())


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeAgent:
    def __init__(self, reply: str):
        self._reply = reply
        self.last_messages = None

    async def ainvoke(self, payload, config=None):
        self.last_messages = payload["messages"]
        return {"messages": [_FakeMessage(self._reply)]}


def test_process_coach_message_persists_both_turns_and_returns_reply(monkeypatch):
    fake_agent = _FakeAgent("Your squat volume looks fine this week.")
    monkeypatch.setattr(coach_assistant, "build_coach_agent", lambda user_id, snapshot: fake_agent)

    user_id = _uid()
    reply = asyncio.run(
        coach_assistant.process_coach_message(user_id, "how's my squat volume?", None)
    )

    assert reply == "Your squat volume looks fine this week."
    saved = list(
        coach_assistant.get_db().coach_messages.find({"user_id": user_id}).sort("created_at", 1)
    )
    assert [d["role"] for d in saved] == ["user", "assistant"]
    assert saved[0]["content"] == "how's my squat volume?"
    assert saved[1]["content"] == "Your squat volume looks fine this week."


def test_process_coach_message_includes_prior_turns_in_the_next_call(monkeypatch):
    replies = iter(["first reply", "second reply"])
    agents_built = []

    def _build(user_id, snapshot):
        agent = _FakeAgent(next(replies))
        agents_built.append(agent)
        return agent

    monkeypatch.setattr(coach_assistant, "build_coach_agent", _build)

    user_id = _uid()
    asyncio.run(coach_assistant.process_coach_message(user_id, "first question", None))
    asyncio.run(coach_assistant.process_coach_message(user_id, "second question", None))

    second_call_messages = agents_built[1].last_messages
    assert second_call_messages[0] == {"role": "user", "content": "first question"}
    assert second_call_messages[1] == {"role": "assistant", "content": "first reply"}
    assert second_call_messages[2] == {"role": "user", "content": "second question"}


def test_process_coach_message_is_scoped_per_user(monkeypatch):
    monkeypatch.setattr(
        coach_assistant, "build_coach_agent", lambda user_id, snapshot: _FakeAgent("reply")
    )

    user_a, user_b = _uid(), _uid()
    asyncio.run(coach_assistant.process_coach_message(user_a, "user a's question", None))
    asyncio.run(coach_assistant.process_coach_message(user_b, "user b's question", None))

    a_messages = list(coach_assistant.get_db().coach_messages.find({"user_id": user_a}))
    assert len(a_messages) == 2
    assert all(m["user_id"] == user_a for m in a_messages)

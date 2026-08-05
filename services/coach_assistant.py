"""
Coach Assistant -- conversational chat grounded in the user's own workout
and nutrition plans. Replaces the earlier keyword-matching stub (part of
the mock "Module 1-7" demo layer under services/) with a real agent call.

Chat history is stored per-user in MongoDB (coach_messages) rather than
in-process memory -- the previous stub's in-memory _history_db didn't
survive a restart and wouldn't work across multiple backend instances.
"""

from datetime import datetime, timezone

from agents.coach import build_coach_agent
from tools.mongo import get_db

__all__ = ["process_coach_message", "get_db"]

_HISTORY_LIMIT = 20


def _load_recent_messages(user_id: str) -> list[dict]:
    """Oldest-first, capped at the most recent _HISTORY_LIMIT turns --
    sorts descending to get the N most recent Mongo documents, then
    reverses back to chronological order for the agent's messages list."""
    docs = list(
        get_db()
        .coach_messages.find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(_HISTORY_LIMIT)
    )
    # Sort by created_at ascending to restore chronological order
    docs.sort(key=lambda d: d["created_at"])
    return [{"role": d["role"], "content": d["content"]} for d in docs]


def _save_message(user_id: str, role: str, content: str) -> None:
    get_db().coach_messages.insert_one({
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc),
    })


async def process_coach_message(
    user_id: str, message: str, nutrition_plan_snapshot: str | None
) -> str:
    history = _load_recent_messages(user_id)
    agent = build_coach_agent(user_id, nutrition_plan_snapshot)
    result = await agent.ainvoke(
        {"messages": history + [{"role": "user", "content": message}]},
        config={"recursion_limit": 50},
    )
    reply = result["messages"][-1].content

    _save_message(user_id, "user", message)
    _save_message(user_id, "assistant", reply)
    return reply

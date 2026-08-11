"""
Coach Assistant -- conversational chat grounded in the user's own workout
and nutrition plans. Chat history is stored per-user in DynamoDB
(`workout_coach_messages`) rather than in-process memory.
"""

import uuid
from datetime import datetime, timezone

from agents.coach import run_coach_turn
from tools.dynamo import get_coach_messages_table

__all__ = ["process_coach_message", "get_coach_messages_table", "load_recent_messages"]

_HISTORY_LIMIT = 20


def load_recent_messages(user_id: str) -> list[dict]:
    """Oldest-first, capped at the most recent _HISTORY_LIMIT turns."""
    resp = get_coach_messages_table().query(
        IndexName="user-index",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
        ScanIndexForward=False,
        Limit=_HISTORY_LIMIT,
    )
    docs = resp["Items"]
    docs.sort(key=lambda d: (d["created_at"], d["message_id"]))
    return [{"role": d["role"], "content": d["content"]} for d in docs]


def _save_message(user_id: str, role: str, content: str, offset_seconds: float = 0.0) -> None:
    now = datetime.now(timezone.utc)
    if offset_seconds:
        from datetime import timedelta
        now = now + timedelta(seconds=offset_seconds)
    get_coach_messages_table().put_item(Item={
        "message_id": str(uuid.uuid4()),
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": now.isoformat(),
    })


async def process_coach_message(
    user_id: str, message: str, nutrition_plan_snapshot: str | None
) -> str:
    history = load_recent_messages(user_id)
    reply = await run_coach_turn(user_id, history, message, nutrition_plan_snapshot)

    _save_message(user_id, "user", message)
    _save_message(user_id, "assistant", reply, offset_seconds=0.001)
    return reply

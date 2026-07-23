"""
Ties a plan-generation session_id to the user who created it. This is the
authorization check behind "can this user see this session's plan/history" —
without it, any authenticated user could read any other user's generated
plan just by guessing/observing a session_id (it's a UUID, not secret).

MongoDB `plan_sessions` collection (same database as everything else, see
tools/mongo.py). The session_id UUID is used directly as the document's
_id rather than introducing a second synthetic key.
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from tools.mongo import get_db


def create_session(session_id: str, user_id: str, goal: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    get_db().plan_sessions.insert_one({
        "_id": session_id,
        "user_id": ObjectId(user_id),
        "goal": goal,
        "status": "generating",
        "error": None,
        "created_at": now,
        "updated_at": now,
    })


def update_session_status(session_id: str, status: str, error: Optional[str] = None) -> None:
    get_db().plan_sessions.update_one(
        {"_id": session_id},
        {"$set": {"status": status, "error": error, "updated_at": datetime.now(timezone.utc)}},
    )


def get_session(session_id: str) -> Optional[dict]:
    doc = get_db().plan_sessions.find_one({"_id": session_id})
    return _serialize(doc) if doc else None


def user_owns_session(session_id: str, user_id: str) -> bool:
    doc = get_db().plan_sessions.find_one({"_id": session_id, "user_id": ObjectId(user_id)})
    return doc is not None


def list_sessions_for_user(user_id: str) -> list[dict]:
    docs = get_db().plan_sessions.find({"user_id": ObjectId(user_id)}).sort("created_at", -1)
    return [_serialize(d) for d in docs]


def _serialize(doc: dict) -> dict:
    return {
        "session_id": doc["_id"],
        "goal": doc.get("goal"),
        "status": doc.get("status"),
        "error": doc.get("error"),
        "created_at": doc["created_at"],
    }

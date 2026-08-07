"""
Ties a plan-generation session_id to the user who created it. This is the
authorization check behind "can this user see this session's plan/history" —
without it, any authenticated user could read any other user's generated
plan just by guessing/observing a session_id (it's a UUID, not secret).

DynamoDB `workout_plan_sessions` table (see tools/dynamo.py), PK
session_id. user_id is an opaque string (the BFF's JWT `sub` claim) — no
bson/ObjectId involved.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from tools.dynamo import get_plan_sessions_table

_REVIEW_ELIGIBLE_AFTER_DAYS = 30


def create_session(
    session_id: str,
    user_id: str,
    goal: Optional[str],
    intake: Optional[dict] = None,
    previous_session_id: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "session_id": session_id,
        "user_id": user_id,
        "goal": goal,
        "intake": intake,
        "status": "generating",
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    if previous_session_id is not None:
        item["previous_session_id"] = previous_session_id
    get_plan_sessions_table().put_item(Item=item)


def update_session_status(session_id: str, status: str, error: Optional[str] = None) -> None:
    get_plan_sessions_table().update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET #s = :status, #e = :error, updated_at = :updated_at",
        ExpressionAttributeNames={"#s": "status", "#e": "error"},
        ExpressionAttributeValues={
            ":status": status,
            ":error": error,
            ":updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def get_session(session_id: str) -> Optional[dict]:
    resp = get_plan_sessions_table().get_item(Key={"session_id": session_id})
    doc = resp.get("Item")
    if not doc:
        return None
    already_reviewed = _has_review(doc["session_id"])
    return _serialize(doc, already_reviewed)


def user_owns_session(session_id: str, user_id: str) -> bool:
    resp = get_plan_sessions_table().get_item(Key={"session_id": session_id})
    doc = resp.get("Item")
    return doc is not None and doc.get("user_id") == user_id


def list_sessions_for_user(user_id: str) -> list[dict]:
    resp = get_plan_sessions_table().query(
        IndexName="user-index",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
        ScanIndexForward=False,
    )
    docs = resp["Items"]
    reviewed_ids = {d["previous_session_id"] for d in docs if d.get("previous_session_id")}
    return [_serialize(d, d["session_id"] in reviewed_ids) for d in docs]


def _has_review(session_id: str) -> bool:
    resp = get_plan_sessions_table().query(
        IndexName="previous-session-index",
        KeyConditionExpression="previous_session_id = :sid",
        ExpressionAttributeValues={":sid": session_id},
        Limit=1,
    )
    return resp["Count"] > 0


def _decimals_to_native(value):
    """DynamoDB's Number type always deserializes to Decimal, including for
    values nested inside a map attribute like `intake` (days_per_week, age,
    ...). Recurse and convert back to plain int/float so callers (e.g.
    pipeline/monthly_progress.py's _adherence, which does
    `days_per_week * weeks_elapsed`) never have to deal with Decimal
    arithmetic — mirror image of _floats_to_decimal in
    pipeline/monthly_progress.py, which does the reverse conversion on write."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _decimals_to_native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decimals_to_native(v) for v in value]
    return value


def _serialize(doc: dict, already_reviewed: bool) -> dict:
    created_at = datetime.fromisoformat(doc["created_at"])

    eligible = (
        doc.get("status") == "ready"
        and not already_reviewed
        and (datetime.now(timezone.utc) - created_at).days >= _REVIEW_ELIGIBLE_AFTER_DAYS
    )
    return {
        "session_id": doc["session_id"],
        "goal": doc.get("goal"),
        "status": doc.get("status"),
        "error": doc.get("error"),
        "created_at": created_at,
        "intake": _decimals_to_native(doc.get("intake")),
        "previous_session_id": doc.get("previous_session_id"),
        "eligible_for_review": eligible,
    }

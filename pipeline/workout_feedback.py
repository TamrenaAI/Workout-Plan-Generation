"""
Post-workout feedback — recorded by the API route right after a user
submits it (POST /workouts/{session_id}/feedback), not by any agent.

DynamoDB `workout_feedback_submissions` table: one item per submission (not
one growing array per session) — this is what makes cross-session training
history actually queryable (e.g. "this user's last 30 days of feedback")
without loading and filtering client-side.

The Plan Adjuster agent reads this back via tools/memory.py's
read_workout_feedback tool, not this module directly — see
docs/CODE_MAP.md's tools/ vs pipeline/ rule: writing here is a pipeline
concern (this file), reading is a tool concern (tools/memory.py), and
tools/ must not import from pipeline/ (the reverse direction is fine, and
already established by pipeline/plan_finalize.py importing from
tools/memory.py).
"""

import uuid
from datetime import datetime, timezone

from tools.dynamo import get_workout_feedback_table


def needs_adjustment(exercises: list[dict]) -> bool:
    """True if any exercise in this submission was flagged too_easy,
    too_hard, or painful — the signal the API route uses to decide whether
    to dispatch the Plan Adjuster agent at all."""
    return any(e.get("pain") or e.get("difficulty") in ("too_easy", "too_hard") for e in exercises)


def record_feedback(user_id: str, session_id: str, day_label: str, exercises: list[dict], adjustment_triggered: bool) -> None:
    get_workout_feedback_table().put_item(Item={
        "feedback_id": str(uuid.uuid4()),
        "user_id": user_id,
        "session_id": session_id,
        "day_label": day_label,
        "exercises": exercises,
        "adjustment_triggered": adjustment_triggered,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })

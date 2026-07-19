"""
Post-workout feedback — recorded by the API route right after a user
submits it (POST /workouts/{session_id}/feedback), not by any agent.
Structured JSON, not appended plan.md prose: this codebase already learned
that lesson once for dispatch progress (see tools/memory.py's
Section 5d rationale) — "did this exercise need adjustment" is exactly the
same kind of question that must not depend on regexing an LLM's prose.

The Plan Adjuster agent reads this back via tools/memory.py's
read_workout_feedback tool, not this module directly — see
docs/CODE_MAP.md's tools/ vs pipeline/ rule: writing here is a pipeline
concern (this file), reading is a tool concern (tools/memory.py), and
tools/ must not import from pipeline/ (the reverse direction is fine, and
already established by pipeline/plan_finalize.py importing from
tools/memory.py).
"""

import json
import os
from datetime import datetime, timezone

from config import SESSION_DIR


def feedback_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, session_id, "feedback.json")


def needs_adjustment(exercises: list[dict]) -> bool:
    """True if any exercise in this submission was flagged too_easy,
    too_hard, or painful — the signal the API route uses to decide whether
    to dispatch the Plan Adjuster agent at all."""
    return any(e.get("pain") or e.get("difficulty") in ("too_easy", "too_hard") for e in exercises)


def record_feedback(session_id: str, day_label: str, exercises: list[dict]) -> None:
    path = feedback_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    submissions = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            submissions = json.load(f)

    submissions.append({
        "day_label": day_label,
        "exercises": exercises,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(submissions, f)

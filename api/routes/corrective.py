"""
POST /workouts/{session_id}/corrective-results — ingestion endpoint for the
external corrective/CV system (a separate repo, called over HTTP, per this
project's convention for coworker-owned agents). Accepts the CV tool's
native per-exercise JSON export directly — one call per exercise
recording, matching how the tool actually produces one file per exercise
(see Hack_Squat_20260723_000913.json, repo root, for a real sample).
Unknown fields (rules/history/stats) are accepted and ignored — Pydantic
drops extra fields by default, so the CV tool's full file can be POSTed
as-is without the caller needing to strip anything.

exercise_name (from exercise.name) is the join key for aggregation
(pipeline/monthly_progress.py) — no exercise_id/day_label/set_number:
the CV tool doesn't know our plan's day/set structure, and nothing yet
gives exercises a stable id to reference (a separate, later workout-plan
restructure).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user
from auth.ownership import user_owns_session
from tools.dynamo import get_corrective_results_table

router = APIRouter()


def _dec(value):
    """DynamoDB's Number type has no native float support — boto3 rejects
    plain floats on put_item and always hands back Decimal on read. Convert
    via str() (not Decimal(float)) to avoid binary floating-point noise."""
    return Decimal(str(value)) if isinstance(value, float) else value


class CVSummary(BaseModel):
    total_reps: int
    good_reps: int
    bad_reps: int
    accuracy: float
    average_rep_duration: float
    fastest_rep: float
    slowest_rep: float
    total_workout_duration: float
    common_errors: dict[str, int] = {}
    most_common_error: Optional[str] = None
    score: float


class CVExercise(BaseModel):
    name: str


class CVSession(BaseModel):
    recorded_at: datetime


class CorrectiveResultPayload(BaseModel):
    session: CVSession
    exercise: CVExercise
    summary: CVSummary


class CorrectiveResultResponse(BaseModel):
    recorded: int


@router.post("/workouts/{session_id}/corrective-results", response_model=CorrectiveResultResponse)
async def submit_corrective_result(
    session_id: str,
    body: CorrectiveResultPayload,
    user: dict = Depends(get_current_user),
):
    if not user_owns_session(session_id, user["id"]):
        raise HTTPException(404, "Unknown session_id.")

    s = body.summary
    if s.good_reps + s.bad_reps > s.total_reps:
        raise HTTPException(422, f"good_reps + bad_reps exceeds total_reps for '{body.exercise.name}'.")

    get_corrective_results_table().put_item(Item={
        "result_id": str(uuid.uuid4()),
        "user_id": user["id"],
        "session_id": session_id,
        "exercise_name": body.exercise.name,
        "total_reps": s.total_reps,
        "good_reps": s.good_reps,
        "bad_reps": s.bad_reps,
        "accuracy": _dec(s.accuracy),
        "score": _dec(s.score),
        "common_errors": s.common_errors,
        "average_rep_duration": _dec(s.average_rep_duration),
        "fastest_rep": _dec(s.fastest_rep),
        "slowest_rep": _dec(s.slowest_rep),
        "total_workout_duration": _dec(s.total_workout_duration),
        "most_common_error": s.most_common_error,
        "recorded_at": body.session.recorded_at.isoformat(),
        "received_at": datetime.now(timezone.utc).isoformat(),
    })

    return CorrectiveResultResponse(recorded=1)

"""
POST /workouts/{session_id}/corrective-results — ingestion endpoint for the
external corrective/CV system (a separate repo, called over HTTP, per this
project's convention for coworker-owned agents). Pure storage scaffolding:
no downstream wiring into any agent yet, and no scoring/validation logic
beyond a loose sanity check — the CV repo's real output contract isn't
defined yet, so exercise_id stays optional (falls back to exercise_name)
until the workout-plan restructure (a separate, later phase) gives
exercises a stable id this system can reference directly.
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user
from auth.ownership import user_owns_session
from tools.mongo import get_db

router = APIRouter()


class FormError(BaseModel):
    rep_index: int
    error_type: str
    confidence: Optional[float] = None


class CorrectiveExerciseResult(BaseModel):
    exercise_id: Optional[str] = None
    exercise_name: str
    day_label: Optional[str] = None
    set_number: Optional[int] = None
    reps_attempted: int
    reps_correct: int
    reps_incorrect: int
    form_errors: list[FormError] = []
    recorded_at: Optional[datetime] = None


class CorrectiveResultsRequest(BaseModel):
    results: list[CorrectiveExerciseResult]


class CorrectiveResultsResponse(BaseModel):
    recorded: int


@router.post("/workouts/{session_id}/corrective-results", response_model=CorrectiveResultsResponse)
async def submit_corrective_results(
    session_id: str,
    body: CorrectiveResultsRequest,
    user: dict = Depends(get_current_user),
):
    if not user_owns_session(session_id, user["id"]):
        raise HTTPException(404, "Unknown session_id.")

    now = datetime.now(timezone.utc)
    docs = []
    for r in body.results:
        if r.reps_correct + r.reps_incorrect > r.reps_attempted:
            raise HTTPException(422, f"reps_correct + reps_incorrect exceeds reps_attempted for '{r.exercise_name}'.")
        docs.append({
            "user_id": ObjectId(user["id"]),
            "session_id": session_id,
            "exercise_id": ObjectId(r.exercise_id) if r.exercise_id else None,
            "exercise_name": r.exercise_name,
            "day_label": r.day_label,
            "set_number": r.set_number,
            "reps_attempted": r.reps_attempted,
            "reps_correct": r.reps_correct,
            "reps_incorrect": r.reps_incorrect,
            "form_errors": [fe.model_dump() for fe in r.form_errors],
            "recorded_at": r.recorded_at or now,
            "received_at": now,
        })

    if docs:
        get_db().corrective_results.insert_many(docs)

    return CorrectiveResultsResponse(recorded=len(docs))

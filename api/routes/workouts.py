"""
POST /workouts/{session_id}/feedback — records per-exercise feedback for a
completed workout day. If any exercise was flagged too_easy, too_hard, or
painful, dispatches the Plan Adjuster agent (agents/plan_adjuster.py) to
revise the plan and returns its summary; otherwise just records the
feedback with no adjustment (no LLM call — nothing to decide).
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.plan_adjuster import build_plan_adjuster
from auth.dependencies import get_current_user
from auth.ownership import user_owns_session
from pipeline.workout_feedback import needs_adjustment, record_feedback
from tools.memory import read_exercise_adjustments

router = APIRouter()


class ExerciseFeedback(BaseModel):
    name: str
    muscle_group: Optional[str] = None
    completed: bool = True
    difficulty: Literal["too_easy", "just_right", "too_hard"] = "just_right"
    pain: bool = False
    note: Optional[str] = None


class WorkoutFeedbackRequest(BaseModel):
    day_label: str
    exercises: list[ExerciseFeedback]


class ExerciseAdjustment(BaseModel):
    exercise_name: str
    new_exercise_name: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[str] = None
    rpe: Optional[int] = None
    reason: str


class WorkoutFeedbackResponse(BaseModel):
    feedback_recorded: bool = True
    adjustment_triggered: bool
    summary: Optional[str] = None
    adjustments: list[ExerciseAdjustment] = []


@router.post("/workouts/{session_id}/feedback", response_model=WorkoutFeedbackResponse)
async def submit_workout_feedback(
    session_id: str,
    body: WorkoutFeedbackRequest,
    user: dict = Depends(get_current_user),
):
    if not user_owns_session(session_id, user["id"]):
        raise HTTPException(404, "Unknown session_id.")

    exercises = [e.model_dump() for e in body.exercises]
    triggers_adjustment = needs_adjustment(exercises)
    record_feedback(user["id"], session_id, body.day_label, exercises, triggers_adjustment)

    if not triggers_adjustment:
        return WorkoutFeedbackResponse(adjustment_triggered=False)

    started_at = datetime.now(timezone.utc)
    summary = await _run_plan_adjuster(session_id, body.day_label)
    adjustments = read_exercise_adjustments(session_id, body.day_label, since=started_at)
    return WorkoutFeedbackResponse(
        adjustment_triggered=True,
        summary=summary,
        adjustments=[ExerciseAdjustment(**a) for a in adjustments],
    )


async def _run_plan_adjuster(session_id: str, day_label: str) -> str:
    adjuster = build_plan_adjuster()
    user_message = f"""SESSION_ID: {session_id}

Feedback was just submitted for {day_label}. Read the plan and the feedback, decide what
needs adjusting, write the adjustment to plan memory, and summarise the change for the user."""

    result = await adjuster.ainvoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"recursion_limit": 50},
    )
    return result["messages"][-1].content

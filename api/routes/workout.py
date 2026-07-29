"""
FastAPI Router for Dynamic Workout Generation & Program Retrieval
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from api.schemas.integration_schemas import OnboardingSurvey
from services.workout_engine import workout_engine

router = APIRouter(prefix="/workout", tags=["workout"])


class WorkoutGenerationRequest(BaseModel):
    user_id: str
    onboarding_survey: OnboardingSurvey
    pain_locations: Optional[List[str]] = []


@router.post("/generate", response_model=Dict[str, Any])
async def generate_workout(request: WorkoutGenerationRequest):
    """Generates a hyper-personalized workout plan tailored to metrics, goals, and safety constraints."""
    try:
        plan = workout_engine.generate_workout_plan(
            user_id=request.user_id,
            survey=request.onboarding_survey,
            injuries_or_pain_locations=request.pain_locations
        )
        return plan
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate workout plan: {str(exc)}")


@router.get("/{session_id}", response_model=Dict[str, Any])
async def get_workout_session(session_id: str):
    """Retrieves a previously generated workout session plan."""
    plan = workout_engine.get_plan(session_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Workout session {session_id} not found.")
    return plan

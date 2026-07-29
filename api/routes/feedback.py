"""
FastAPI Router for Module 5: Daily Feedback & Safety Engine
Processes daily post-workout feedback and returns pain-triggered safety adjustments.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from api.schemas.integration_schemas import DailyFeedbackPayload
from services.feedback_safety import feedback_safety_engine

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/submit", response_model=Dict[str, Any])
async def submit_feedback(payload: DailyFeedbackPayload):
    """Analyzes daily post-workout feedback, checks pain flags, and returns safety adjustments."""
    try:
        return feedback_safety_engine.process_feedback(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to process feedback: {str(exc)}")


@router.get("/{user_id}", response_model=List[Dict[str, Any]])
async def get_feedback_history(user_id: str):
    """Retrieves historical daily feedback entries for a user."""
    return feedback_safety_engine.get_user_feedback_history(user_id)

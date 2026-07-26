"""
FastAPI Router for Module 7: AI Fitness Coach Assistant
Conversational RAG interface grounded in the user's workout history and biometric progression.
"""

from fastapi import APIRouter, HTTPException

from api.schemas.integration_schemas import CoachQueryPayload, CoachResponsePayload
from services.coach_assistant import coach_assistant_engine

router = APIRouter(prefix="/coach", tags=["coach"])


@router.post("/chat", response_model=CoachResponsePayload)
async def coach_chat(payload: CoachQueryPayload):
    """Answers user questions grounded in training history, InBody trends, and movement science."""
    try:
        return coach_assistant_engine.process_query(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Coach assistant failed to respond: {str(exc)}")

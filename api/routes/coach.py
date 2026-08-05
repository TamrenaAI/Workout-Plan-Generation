"""
FastAPI router for the coach chatbot -- conversational Q&A grounded in the
user's own workout and nutrition plans (see agents/coach.py,
services/coach_assistant.py). nutrition_plan_snapshot is supplied by the
tamreena-web BFF, which owns the mapping from user_id to the user's last
nutrition run_id; this service has no way to look that up itself (see
docs/superpowers/specs/2026-08-05-nutrition-workout-coach-chatbot-design.md).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user
from services.coach_assistant import load_recent_messages, process_coach_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach", tags=["coach"])


class CoachChatRequest(BaseModel):
    message: str
    nutrition_plan_snapshot: str | None = None


class CoachChatResponse(BaseModel):
    response: str


class CoachMessage(BaseModel):
    role: str
    content: str


class CoachHistoryResponse(BaseModel):
    messages: list[CoachMessage]


@router.post("/chat", response_model=CoachChatResponse)
async def coach_chat(body: CoachChatRequest, user: dict = Depends(get_current_user)):
    try:
        reply = await process_coach_message(
            user["id"], body.message, body.nutrition_plan_snapshot
        )
    except Exception:
        logger.exception("Coach assistant failed to respond")
        raise HTTPException(status_code=500, detail="Coach assistant failed to respond.")
    return CoachChatResponse(response=reply)


@router.get("/history", response_model=CoachHistoryResponse)
async def coach_history(user: dict = Depends(get_current_user)):
    try:
        messages = load_recent_messages(user["id"])
    except Exception:
        logger.exception("Failed to load coach history")
        raise HTTPException(status_code=500, detail="Failed to load coach history.")
    return CoachHistoryResponse(messages=[CoachMessage(**m) for m in messages])

"""
FastAPI Router for Module 1: InBody OCR & Document Parser
Ingests structured InBody scan + onboarding survey payloads and stores per-user scan history.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from api.schemas.integration_schemas import InBodyOnboardingPayload
from services.inbody_parser import inbody_parser_engine

router = APIRouter(prefix="/inbody", tags=["inbody"])


@router.post("/parse", response_model=Dict[str, Any])
async def parse_inbody(payload: InBodyOnboardingPayload):
    """Validates and stores InBody metrics and onboarding preferences for a user."""
    try:
        return inbody_parser_engine.parse_and_store(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse InBody payload: {str(exc)}")


@router.get("/{user_id}/latest", response_model=Dict[str, Any])
async def get_latest_inbody(user_id: str):
    """Retrieves the most recent InBody scan record for a user."""
    record = inbody_parser_engine.get_latest_metrics(user_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"No InBody scans found for user {user_id}")
    return record

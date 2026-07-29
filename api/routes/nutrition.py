"""
FastAPI Router for Structured Nutrition Plan Generation & Retrieval
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
from api.schemas.integration_schemas import NutritionSurvey, NutritionPlan
from services.nutrition_engine import nutrition_engine

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


class NutritionGenerationRequest(BaseModel):
    survey: NutritionSurvey
    bmr_kcal: Optional[float] = 1820.0
    weight_kg: Optional[float] = 82.5


@router.post("/generate", response_model=NutritionPlan)
async def generate_nutrition(request: NutritionGenerationRequest):
    """Calculates macro distributions and constructs structured Breakfast, Lunch, and Dinner meal architectures."""
    try:
        plan = nutrition_engine.generate_nutrition_plan(
            survey=request.survey,
            bmr_kcal=request.bmr_kcal or 1820.0,
            weight_kg=request.weight_kg or 82.5
        )
        return plan
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate nutrition plan: {str(exc)}")


@router.get("/{user_id}", response_model=NutritionPlan)
async def get_nutrition_plan(user_id: str):
    """Retrieves the active nutrition plan for a user."""
    plan = nutrition_engine.get_user_plan(user_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"No active nutrition plan found for user {user_id}")
    return plan

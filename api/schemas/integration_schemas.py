"""
Shared Data Contracts (Pydantic v2 Schemas)
Strict API contracts for Tamrena-AI Microservices Integration per srs2.md.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# --- INBODY & USER PROFILE SCHEMAS ---
class InBodyMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    scan_date: datetime
    weight_kg: float = Field(..., gt=0)
    skeletal_muscle_mass_kg: float = Field(..., gt=0)
    body_fat_mass_kg: float = Field(..., gt=0)
    body_fat_percentage: float = Field(..., ge=0, le=100)
    visceral_fat_level: int = Field(..., ge=1)
    basal_metabolic_rate_kcal: float = Field(..., gt=0)


class OnboardingSurvey(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: Optional[str] = None
    fitness_goal: str
    experience_level: str
    available_equipment: List[str]
    days_per_week: int = Field(..., ge=1, le=7)
    session_duration_minutes: int
    medical_disclaimers: List[str] = []


class InBodyOnboardingPayload(BaseModel):
    user_id: str
    onboarding_survey: OnboardingSurvey
    inbody_data: InBodyMetrics


# --- CV TELEMETRY SCHEMA (Client-Side MediaPipe Output) ---
class FormFault(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    fault_type: str
    occurrences: int
    rep_numbers: List[int]


class CVTelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: str
    session_id: str
    exercise_id: str
    timestamp: datetime
    good_reps: int = Field(..., ge=0)
    bad_reps: int = Field(..., ge=0)
    total_reps: int = Field(..., ge=0)
    form_faults: List[FormFault] = []
    mean_tempo_seconds: float
    completion_progress_pct: float = Field(..., ge=0, le=100)


# --- DAILY FEEDBACK SCHEMA ---
class ExerciseFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    exercise_id: str
    rating: str
    pain_flag: bool = False
    pain_location: Optional[str] = None
    comment: Optional[str] = None


class DailyFeedbackPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: str
    workout_session_id: str
    date: datetime
    perceived_difficulty: str
    completion_rate: float
    feedback_notes: List[ExerciseFeedback]


# --- NUTRITION SCHEMAS ---
class NutritionSurvey(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: str
    dietary_preference: str
    allergies: List[str] = []
    disliked_foods: List[str] = []
    meals_per_day: int = Field(default=3, ge=1, le=6)
    target_goal: str


class MealOption(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    name: str
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fats_g: float
    ingredients: List[str]
    swap_options: List[str] = []


class DailyMealArchitecture(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    breakfast: MealOption
    lunch: MealOption
    dinner: MealOption
    snacks: Optional[List[MealOption]] = []


class NutritionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: str
    target_calories_kcal: float
    target_protein_g: float
    target_carbs_g: float
    target_fats_g: float
    daily_meals: DailyMealArchitecture
    generated_at: datetime


# --- MONTHLY REVIEW & PROGRESS SCHEMAS ---
class InBodyDelta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    muscle_mass_delta_kg: float
    body_fat_delta_pct: float
    segmental_lean_changes: Optional[Dict[str, float]] = None


class CVFormSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    overall_form_efficiency_pct: float
    primary_form_faults: List[str]
    good_reps_total: int
    bad_reps_total: int


class MonthlyReportSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: str
    report_id: str
    generated_at: datetime
    inbody_deltas: InBodyDelta
    cv_summary: CVFormSummary
    narrative_summary: str
    auto_regulation_adjustments: List[str]


# --- COACH ASSISTANT CHAT SCHEMAS ---
class CoachQueryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: str
    message: str
    session_id: Optional[str] = None


class CoachResponsePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    user_id: str
    response: str
    cited_sources: List[str] = []
    timestamp: datetime

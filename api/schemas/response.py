from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    dependencies: dict[str, str]


class PlanResponse(BaseModel):
    session_id: str
    inbody: dict
    plan: str
    generated_at: str
    session_file: str


class ValidateImageResponse(BaseModel):
    valid: bool
    stage: Optional[str] = None
    issue: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    stage: Optional[str] = None

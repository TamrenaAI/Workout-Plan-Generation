from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    dependencies: dict[str, str]


class GeneratePlanStartResponse(BaseModel):
    """Returned immediately by POST /generate-plan (aliased /plan). The agent
    pipeline then runs in the background — connect to
    GET /generate-plan/stream/{session_id} for live progress and the final
    plan text."""
    session_id: str
    inbody: dict


class ProgressEvent(BaseModel):
    """One SSE message from GET /generate-plan/stream/{session_id}.
    type="progress" events carry `agent` + `label`. The terminal
    type="done" event carries either (`plan`, `generated_at`) on success
    or `error` on failure."""
    type: str
    agent: Optional[str] = None
    label: Optional[str] = None
    plan: Optional[str] = None
    generated_at: Optional[str] = None
    error: Optional[str] = None


class ValidateImageResponse(BaseModel):
    valid: bool
    stage: Optional[str] = None
    issue: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    stage: Optional[str] = None

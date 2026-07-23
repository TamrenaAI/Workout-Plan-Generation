"""
POST /generate-plan — kicks off plan generation.

Runs the InBody image pipeline synchronously (fast: a few seconds), then
launches the agent pipeline as a background asyncio task instead of blocking
the request on it. Returns {session_id, inbody} immediately so the frontend
can start rendering InBody data right away and open the live progress stream.

GET /generate-plan/stream/{session_id} — Server-Sent Events. Streams real
progress events (agents/streaming.py, translating deepagents' astream_events()
output) as the background task runs, ending with a `{"type": "done", ...}`
event carrying the final plan text. A full run dispatches the Exercise
Recommender once per muscle group (5-6 sequential dispatches, more with a
legs_a/legs_b split) plus the Plan Assembler — each a multi-step LLM
conversation of its own — so this can genuinely take several minutes,
not seconds.

/ingest (RAG document ingestion) from tamrena_architecture_2.md Section 12c
is not built — RAG is a hardcoded stub (tools/rag.py) pending the RAG team's
real pipeline.
"""

import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.exercise_recommender import EXERCISE_RECOMMENDER
from agents.plan_assembler import PLAN_ASSEMBLER
from agents.streaming import run_and_stream
from agents.supervisor import build_supervisor
from auth.dependencies import get_current_user, get_current_user_for_stream
from auth.ownership import create_session, list_sessions_for_user, update_session_status, user_owns_session
from config import SESSION_DIR
from pipeline.inbody_history import compare_latest_two, record_scan
from pipeline.plan_finalize import enforce_volume_budget
from services import live_progress
from tools.inbody import check_image_quality, format_inbody_result, pdf_to_image_bytes, run_inbody_pipeline_from_bytes, validate_inbody_scan
from tools.memory import read_weekly_schedule

router = APIRouter()

VALID_EXPERIENCE = {"beginner", "intermediate", "advanced"}
DURATION_PATTERN = re.compile(r"^\d{2,3}min$")
SUPPORTED_CONTENT_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/jfif": "image/jpeg",
    "image/png": "image/png",
    "application/pdf": "application/pdf",
}


async def _read_as_image(file: UploadFile) -> tuple[bytes, str]:
    """Reads an uploaded file and normalizes PDFs to a PNG image. Raises HTTPException on
    an unsupported content type."""
    raw_content_type = file.content_type or ""
    if raw_content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(415, f"Unsupported file type: {raw_content_type}")
    content_type = SUPPORTED_CONTENT_TYPES[raw_content_type]

    file_bytes = await file.read()
    if content_type == "application/pdf":
        file_bytes = await run_in_threadpool(pdf_to_image_bytes, file_bytes)
        content_type = "image/png"
    return file_bytes, content_type


@router.post("/validate-image")
async def validate_image(file: UploadFile = File(...)):
    """Quality + authenticity check only (stages 1-2 of the InBody pipeline) — used by the
    frontend's live camera capture and PDF-upload flows before committing to a full
    (slower, LLM-extraction) /generate-plan call."""
    image_bytes, content_type = await _read_as_image(file)

    quality = await run_in_threadpool(check_image_quality, image_bytes)
    if not quality["pass"]:
        return {"valid": False, "stage": "blur", "issue": quality["issue"]}

    validation = await run_in_threadpool(validate_inbody_scan, image_bytes, content_type)
    if not validation.is_inbody_scan:
        return {
            "valid": False,
            "stage": "authenticity",
            "issue": validation.issue or "This does not appear to be an InBody scan.",
        }

    return {"valid": True, "stage": None, "issue": None}


async def _run_pipeline(session_id: str, user_message: str) -> None:
    """Background task — runs the full Supervisor pipeline, narrating progress
    into services.live_progress as it goes, then publishes the final result."""
    supervisor = build_supervisor(sub_agents=[EXERCISE_RECOMMENDER, PLAN_ASSEMBLER])
    try:
        final_plan = await run_and_stream(supervisor, user_message, session_id)
        # The Plan Assembler is supposed to trim any day over its max_sets
        # budget itself (prompts/plan_assembler.md step 4) but doesn't
        # reliably do so — enforce it deterministically instead of trusting
        # the LLM's own edit.
        enforce_volume_budget(session_id)
        # The Supervisor's own reply above is a free-text re-synthesis of the
        # plan and isn't guaranteed to reproduce every exercise faithfully —
        # prefer the schedule the Plan Assembler actually wrote to memory.
        schedule = read_weekly_schedule(session_id)
        if schedule:
            final_plan = schedule
        update_session_status(session_id, "ready")
        await live_progress.publish_done(session_id, {
            "plan": final_plan,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        update_session_status(session_id, "failed", error=str(exc))
        await live_progress.publish_done(session_id, {"error": str(exc)})


@router.post("/plan")
@router.post("/generate-plan")
async def generate_plan(
    inbody_file: UploadFile = File(...),
    goal: str = Form(...),
    days_per_week: int = Form(...),
    experience: str = Form(...),
    session_duration: str = Form(...),
    injuries: Optional[str] = Form(None),
    priority: Optional[str] = Form(None),
    age: Optional[int] = Form(None),
    sleep_quality: Optional[str] = Form(None),
    job_type: Optional[str] = Form(None),
    current_program: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    if not (2 <= days_per_week <= 6):
        raise HTTPException(422, "days_per_week must be between 2 and 6")
    if experience not in VALID_EXPERIENCE:
        raise HTTPException(422, f"experience must be one of {sorted(VALID_EXPERIENCE)}")
    if not DURATION_PATTERN.match(session_duration):
        raise HTTPException(422, "session_duration must look like '60min'")

    inbody_bytes, content_type = await _read_as_image(inbody_file)

    pipeline_result = await run_in_threadpool(run_inbody_pipeline_from_bytes, inbody_bytes, content_type)
    if isinstance(pipeline_result, dict):
        raise HTTPException(
            422,
            f"InBody scan rejected at [{pipeline_result['stage']}]: {pipeline_result['error']}",
        )
    inbody_text = format_inbody_result(pipeline_result)

    user_query = _build_user_query(
        goal=goal,
        days_per_week=days_per_week,
        experience=experience,
        session_duration=session_duration,
        injuries=injuries,
        priority=priority,
        age=age,
        sleep_quality=sleep_quality,
        job_type=job_type,
        current_program=current_program,
    )

    session_id = str(uuid.uuid4())
    os.makedirs(os.path.join(SESSION_DIR, session_id), exist_ok=True)
    create_session(session_id, user["id"], goal)
    record_scan(user["id"], session_id, pipeline_result)
    comparison = compare_latest_two(user["id"])

    user_message = f"""SESSION_ID: {session_id}

{user_query}

INBODY RAW TEXT:
{inbody_text}
{_format_inbody_comparison(comparison)}
Generate a full personalised workout plan for this user."""

    stream = live_progress.create_stream(session_id)
    stream.task = asyncio.create_task(_run_pipeline(session_id, user_message))

    return {
        "session_id": session_id,
        "inbody": pipeline_result.model_dump(),
    }


@router.get("/generate-plan/stream/{session_id}")
async def stream_plan(session_id: str, user: dict = Depends(get_current_user_for_stream)):
    # 404 (not 403) for a session_id that exists but belongs to someone else —
    # otherwise the response itself would confirm the session_id is valid to
    # whoever's probing it.
    if not user_owns_session(session_id, user["id"]):
        raise HTTPException(404, "Unknown session_id, or this stream already finished.")

    stream = live_progress.get_stream(session_id)
    if not stream:
        raise HTTPException(404, "Unknown session_id, or this stream already finished.")

    async def event_generator():
        try:
            while True:
                event = await stream.queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    return
        finally:
            live_progress.cleanup(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions")
async def list_my_sessions(user: dict = Depends(get_current_user)):
    """Sessions the current user has generated a plan for, most recent
    first. Foundation for the mobile app's Workout History list."""
    return {"sessions": list_sessions_for_user(user["id"])}


class SessionPlanResponse(BaseModel):
    status: Literal["ready", "pending"]
    plan: Optional[str] = None


@router.get("/sessions/{session_id}/plan", response_model=SessionPlanResponse)
async def get_session_plan(session_id: str, user: dict = Depends(get_current_user)):
    """The persisted weekly schedule for a session, fetchable any time after
    generation finishes — not just live during the SSE stream. Reads the
    same source of truth _run_pipeline() already prefers over the
    Supervisor's own free-text reply (tools/memory.py's read_weekly_schedule,
    the last '## Weekly Schedule' section the Plan Assembler actually wrote).

    Known gap: "pending" covers both "still generating" and "generation
    failed before the Assembler wrote a schedule" — plan.md records neither
    a start marker nor a failure marker today, only successful writes, so
    this endpoint can't yet tell those two apart. Live progress (the SSE
    stream) is the only place failure is currently surfaced, and only to a
    client connected at the moment it happens.
    """
    if not user_owns_session(session_id, user["id"]):
        raise HTTPException(404, "Unknown session_id.")

    schedule = read_weekly_schedule(session_id)
    if schedule is None:
        return SessionPlanResponse(status="pending", plan=None)
    return SessionPlanResponse(status="ready", plan=schedule)


def _format_inbody_comparison(comparison: Optional[dict]) -> str:
    """Folds compare_latest_two()'s delta into the Supervisor's own prompt
    text so the agent — not just the Progress screen — sees what changed
    since the user's last scan. Empty string (not a placeholder line) when
    this is the user's first scan, so the prompt doesn't grow a
    "no comparison available" line on every single first-time user."""
    if comparison is None:
        return ""
    d = comparison["delta"]
    resolved = [
        label for label, flag in (
            ("arm asymmetry", d["arm_asymmetry_resolved"]),
            ("leg asymmetry", d["leg_asymmetry_resolved"]),
            ("trunk underdevelopment", d["trunk_underdeveloped_resolved"]),
        )
        if flag
    ]
    resolved_text = f" | Resolved since last scan: {', '.join(resolved)}" if resolved else ""
    return (
        f"\nINBODY CHANGE SINCE LAST SCAN: "
        f"Skeletal muscle mass {d['skeletal_muscle_mass_kg']:+.2f}kg, "
        f"Body fat {d['body_fat_percent']:+.2f}%{resolved_text}\n"
    )


def _build_user_query(**fields) -> str:
    """Formats all form fields into the structured intake text the Supervisor reads."""
    lines = [
        "USER INTAKE FORM",
        "─────────────────────────────────────",
        f"Goal             : {fields['goal']}",
        f"Days per week    : {fields['days_per_week']}",
        f"Experience       : {fields['experience']}",
        f"Session duration : {fields['session_duration']}",
    ]
    if fields.get("injuries"):
        lines.append(f"Injuries/limits  : {fields['injuries']}")
    if fields.get("priority"):
        lines.append(f"Priority focus   : {fields['priority']}")
    if fields.get("age"):
        lines.append(f"Age              : {fields['age']}")
    if fields.get("sleep_quality"):
        lines.append(f"Sleep quality    : {fields['sleep_quality']}")
    if fields.get("job_type"):
        lines.append(f"Job type         : {fields['job_type']}")
    if fields.get("current_program"):
        lines.append(f"Current program  : {fields['current_program']}")
    return "\n".join(lines)

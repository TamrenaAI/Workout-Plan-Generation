"""
FastAPI application entry point.

Run: python main.py  (or: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload)

/health, /validate-image, and /plan (aliased as /generate-plan for the
frontend) are exposed at this stage. /ingest (RAG document ingestion) from
tamrena_architecture_2.md Section 12c is not built — RAG is a hardcoded stub
(tools/rag.py) pending the RAG team's real pipeline.

The frontend/ directory (see FRONTEND.md) is mounted at "/" so that legacy
web app is served from this same process — no CORS needed for it (same
origin). The mobile app's web-preview target (`expo start --web`,
mobile/README) is a DIFFERENT origin (Metro's dev server, a different
port) making cross-origin requests here, which DOES need CORS — the first
time this project has actually needed it. Wide open (`*`) is fine: every
route is protected by Bearer-token auth (not cookies), so CORS here only
controls whether browser JS can read a response, never whether a request
is authorized — a page with no valid token gets 401 regardless of origin.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import (
    auth,
    coach,
    corrective,
    exercises,
    feedback,
    health,
    inbody,
    nutrition,
    plan,
    progress,
    reports,
    telemetry,
    workout,
    workouts,
)
from config import EXERCISE_MEDIA_DIR


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    title="Tamreena AI",
    description="Personalised workout plan generation via multi-agent pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(plan.router, tags=["plan"])
app.include_router(progress.router, tags=["progress"])
app.include_router(workouts.router, tags=["workouts"])
app.include_router(corrective.router, tags=["corrective"])
app.include_router(exercises.router, tags=["exercises"])
app.include_router(inbody.router, tags=["inbody"])
app.include_router(workout.router, tags=["workout"])
app.include_router(nutrition.router, tags=["nutrition"])
app.include_router(telemetry.router, tags=["telemetry"])
app.include_router(feedback.router, tags=["feedback"])
app.include_router(reports.router, tags=["reports"])
app.include_router(coach.router, tags=["coach"])

# Serves the exercise GIFs/thumbnails imported by
# database/exercises_dataset/import.py — gif_url/image_url in
# GET /exercises/lookup responses are paths under this mount.
if EXERCISE_MEDIA_DIR.is_dir():
    app.mount("/media/exercises", StaticFiles(directory=EXERCISE_MEDIA_DIR), name="exercise_media")

# Serves sample InBody images (samples/inbody*.jfif) so the workout-test frontend
# page's "Use sample image" button can attach one without a manual file upload —
# see frontend/src/pages/workout-test.js.
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
if SAMPLES_DIR.is_dir():
    app.mount("/media/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

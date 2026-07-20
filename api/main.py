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

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import auth, health, plan, progress, workouts

app = FastAPI(
    title="Tamreena AI",
    description="Personalised workout plan generation via multi-agent pipeline",
    version="1.0.0",
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

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

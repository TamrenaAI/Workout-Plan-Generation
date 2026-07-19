"""
FastAPI application entry point.

Run: python main.py  (or: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload)

/health, /validate-image, and /plan (aliased as /generate-plan for the
frontend) are exposed at this stage. /ingest (RAG document ingestion) from
tamrena_architecture_2.md Section 12c is not built — RAG is a hardcoded stub
(tools/rag.py) pending the RAG team's real pipeline.

The frontend/ directory (see FRONTEND.md) is mounted at "/" so the whole app
is served from one process — no separate dev server, no CORS needed.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes import auth, health, plan

app = FastAPI(
    title="Tamreena AI",
    description="Personalised workout plan generation via multi-agent pipeline",
    version="1.0.0",
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(plan.router, tags=["plan"])

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

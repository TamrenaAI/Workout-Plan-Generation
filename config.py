"""
Central configuration for Tamreena AI — environment loading and shared paths.

Every module that needs a filesystem path (sessions dir, SQLite db, prompt
files) imports from here instead of re-deriving paths relative to itself.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

SESSION_DIR = BASE_DIR / "sessions"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tamreena.db"
PROMPTS_DIR = BASE_DIR / "prompts"
RAG_DATA_DIR = BASE_DIR / "rag_data"
QDRANT_PATH = RAG_DATA_DIR / "qdrant"
RAG_MODELS_DIR = DATA_DIR / "models"
EXERCISE_MEDIA_DIR = BASE_DIR / "database" / "exercises_dataset" / "media"

SESSION_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── DynamoDB ──────────────────────────────────────────────────────────
# Region/table-naming convention matches tamreena-web/backend/app/config.py
# (workout_users, workout_live_sessions) — this service's own 8 tables,
# one per former Mongo collection.
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
PLAN_SESSIONS_TABLE_NAME = os.getenv("PLAN_SESSIONS_TABLE_NAME", "workout_plan_sessions")
EXERCISES_TABLE_NAME = os.getenv("EXERCISES_TABLE_NAME", "workout_exercises")
INBODY_SCANS_TABLE_NAME = os.getenv("INBODY_SCANS_TABLE_NAME", "workout_inbody_scans")
WORKOUT_FEEDBACK_TABLE_NAME = os.getenv("WORKOUT_FEEDBACK_TABLE_NAME", "workout_feedback_submissions")
CORRECTIVE_RESULTS_TABLE_NAME = os.getenv("CORRECTIVE_RESULTS_TABLE_NAME", "workout_corrective_results")
PROGRESS_REPORTS_TABLE_NAME = os.getenv("PROGRESS_REPORTS_TABLE_NAME", "workout_progress_reports")
PLAN_ADJUSTMENTS_TABLE_NAME = os.getenv("PLAN_ADJUSTMENTS_TABLE_NAME", "workout_plan_adjustments")
COACH_MESSAGES_TABLE_NAME = os.getenv("COACH_MESSAGES_TABLE_NAME", "workout_coach_messages")

# ── Google GenAI / Gemini (Central LLM API) ─────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or os.getenv("MODEL_NAME") or "gemma-4-31b-it"
MODEL_NAME = GEMINI_MODEL

# ── Azure OpenAI (legacy fallback) ───────────────────────────────────
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

# ── ITI Bedrock proxy (legacy fallback) ──────────────────────────────
SBG_API_KEY = os.getenv("SBG_API_KEY")
SBG_MODEL_ID = os.getenv("SBG_MODEL_ID", "us.meta.llama3-3-70b-instruct-v1:0")

# ── Auth ──────────────────────────────────────────────────────────────
# This service no longer owns user identity — Google Sign-In verification,
# JWT issuance, and the `users` collection all moved to a separate BFF repo
# (see docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md).
# JWT_SECRET here MUST match that repo's value exactly: this service only
# verifies tokens signed with it, it no longer mints them.
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days — mobile session, not a web cookie

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")

# ── LangSmith Tracing ────────────────────────────────────────────────
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "tamrena")

os.environ["LANGSMITH_TRACING"] = LANGSMITH_TRACING
os.environ["LANGCHAIN_TRACING_V2"] = LANGSMITH_TRACING
os.environ["LANGSMITH_ENDPOINT"] = LANGSMITH_ENDPOINT
os.environ["LANGCHAIN_ENDPOINT"] = LANGSMITH_ENDPOINT
if LANGSMITH_API_KEY:
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT

# ── Anthropic API Key ────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
if ANTHROPIC_API_KEY:
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY


def load_prompt(name: str) -> str:
    """Read a prompt file from prompts/ by name (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


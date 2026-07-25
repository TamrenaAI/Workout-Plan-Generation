"""
Central configuration for Tamreena AI — environment loading and shared paths.

Every module that needs a filesystem path (sessions dir, SQLite db, prompt
files) imports from here instead of re-deriving paths relative to itself.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

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

# ── MongoDB ───────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "tamreena")

# ── Azure OpenAI (only external LLM API) ─────────────────────────────
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

# ── ITI Bedrock proxy (alternate LLM path, see llm.py's ITIBedrockChat) ──
SBG_API_KEY = os.getenv("SBG_API_KEY")

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


def load_prompt(name: str) -> str:
    """Read a prompt file from prompts/ by name (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")

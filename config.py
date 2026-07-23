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

# ── Auth ──────────────────────────────────────────────────────────────
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days — mobile session, not a web cookie

# Enables POST /auth/dev-login, which mints a real session JWT for a fixed
# test account with NO Google verification — lets the mobile app be tested
# end-to-end (web preview, Expo Go, screens past login) without a native
# Google Sign-In build. Defaults to disabled (the route 404s, not just
# rejects — so it doesn't even confirm it exists) and must be explicitly
# opted into per-environment. NEVER set this true anywhere but a local dev
# machine — it lets anyone with network access to this server sign in as
# that test account with no credential at all.
ALLOW_DEV_LOGIN = os.getenv("ALLOW_DEV_LOGIN", "false").lower() == "true"


def load_prompt(name: str) -> str:
    """Read a prompt file from prompts/ by name (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")

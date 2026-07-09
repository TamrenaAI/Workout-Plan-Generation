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

SESSION_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Azure OpenAI (only external LLM API) ─────────────────────────────
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")


def load_prompt(name: str) -> str:
    """Read a prompt file from prompts/ by name (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")

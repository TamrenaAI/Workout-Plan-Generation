import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    hf_home: str | None = None

    gemini_api_key: str | None = None
    google_api_key: str | None = None
    gemini_model: str | None = None
    model_name: str | None = None
    groq_api_key: str | None = None
    nvidia_api_key: str | None = None
    openrouter_api_key: str | None = None
    iti_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()

# Normalize google_api_key and gemini_api_key
if not settings.google_api_key:
    settings.google_api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not settings.gemini_api_key:
    settings.gemini_api_key = settings.google_api_key
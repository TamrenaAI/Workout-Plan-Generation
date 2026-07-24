from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    hf_home: str | None = None

    google_api_key: str | None = None
    groq_api_key: str | None = None
    nvidia_api_key: str | None = None
    openrouter_api_key: str | None = None
    iti_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
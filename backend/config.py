"""
Sentinel-Agent Configuration
=============================
Centralized environment variable loading using pydantic-settings.
All API keys and runtime settings are loaded here — NEVER hardcoded.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- LLM ---
    gemini_api_key: str = "placeholder"
    gemini_model: str = "gemini-1.5-flash"

    # --- External APIs ---
    openweather_api_key: str = "mock"
    news_api_key: str = "mock"

    # --- Langfuse Observability ---
    langfuse_public_key: str = "pk-lf-placeholder"
    langfuse_secret_key: str = "sk-lf-placeholder"
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Application ---
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # --- Database ---
    db_path: str = "./database/sentinel.db"

    # --- Security ---
    max_react_iterations: int = 10

    # --- CORS ---
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def mock_apis(self) -> bool:
        """Returns True if external API keys are placeholders (use mock data)."""
        return self.openweather_api_key == "mock"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once per process."""
    return Settings()

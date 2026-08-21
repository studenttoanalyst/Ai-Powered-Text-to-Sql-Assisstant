"""Project settings loaded from environment variables via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Configuration for the FMCG AI Sales Assistant."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_MAX_RETRIES: int = 2
    LLM_RETRY_DELAY_SECONDS: float = 1.5
    DB_PATH: str = str(BASE_DIR / "backend" / "data" / "fmcg.db")
    MAX_QUERY_ROWS: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()

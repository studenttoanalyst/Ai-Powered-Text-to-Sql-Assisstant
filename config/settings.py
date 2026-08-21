"""Project settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency in some environments
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Configuration values for the Phase 1 project scaffold."""

    APP_NAME: str = os.getenv("APP_NAME", "AI-Powered Text-to-Sql Assistant")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "uploads.db")
    BASE_DIR: Path = BASE_DIR
    SUPPORTED_FILES: tuple[str, ...] = tuple(
        os.getenv("SUPPORTED_FILES", ".csv,.xlsx").split(",")
    )
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", str(5 * 1024 * 1024)))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


settings = Settings()

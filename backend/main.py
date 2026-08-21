"""FMCG AI Sales Assistant — FastAPI application entrypoint.

Startup: ingest Excel → SQLite → cache schema → init ChatService.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config.settings import Settings
from backend.services.data_loader import DataLoader
from backend.services.schema_generator import SchemaGenerator
from backend.services.schema_manager import SchemaManager
from backend.services.llm_service import LLMService
from backend.services.chat_service import ChatService
from backend.routers import chat, meta
from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.main")

# Paths
BACKEND_DIR = Path(__file__).resolve().parent
SOURCE_FILE = BACKEND_DIR / "data" / "source" / "FMCG_AI_Sales_BI_Demo_Data.xlsx"

# Shared state (populated at startup)
settings = Settings()
schema_manager = SchemaManager(settings.DB_PATH)


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ingest Excel → SQLite → cache schema → init ChatService."""
    logger.info("=== Startup: ingesting FMCG data ===")

    # 1. Load Excel sheets (exclude README)
    loader = DataLoader(excluded_sheets=["readme"])
    dataframes = loader.load_file(SOURCE_FILE)
    logger.info("Loaded %d sheets: %s", len(dataframes), list(dataframes.keys()))

    # 2. Persist to SQLite
    generator = SchemaGenerator(settings.DB_PATH)
    row_counts = generator.persist_tables(dataframes)
    for name, count in row_counts.items():
        logger.info("  → %s: %d rows", name, count)

    # 3. Cache schema
    schema_manager.build_cache()
    logger.info("Schema cached — %d tables ready", len(schema_manager.schema_cache))

    # 4. Initialize ChatService
    chat_ready = False
    try:
        llm_service = LLMService()
        chat_svc = ChatService(
            schema_manager=schema_manager,
            llm_service=llm_service,
            db_path=settings.DB_PATH,
        )
        chat.set_chat_service(chat_svc)
        chat_ready = True
        logger.info("ChatService ready")
    except Exception as exc:
        logger.warning("ChatService init failed (no LLM key?): %s", exc)

    # 5. Inject meta router state
    meta.set_state(schema_manager, chat_ready=chat_ready)

    logger.info("=== Startup complete ===")
    yield
    logger.info("=== Shutdown ===")


# ── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="FMCG AI Sales Assistant",
    description=(
        "AI-powered Text-to-SQL chatbot for FMCG sales data. "
        "Ask natural-language questions and get data-grounded answers."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────

app.include_router(chat.router)
app.include_router(meta.router)

# ── Static Frontend ────────────────────────────────────────
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

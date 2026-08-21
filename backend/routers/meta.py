"""Meta router — GET /api/schema, GET /api/health.

Provides schema inspection and health-check endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import HealthResponse
from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.routers.meta")

router = APIRouter(prefix="/api", tags=["meta"])

# Shared state injected from main.py
_schema_manager = None
_chat_service_ready: bool = False


def set_state(schema_manager, chat_ready: bool = False) -> None:
    """Inject shared state (called from main.py lifespan)."""
    global _schema_manager, _chat_service_ready
    _schema_manager = schema_manager
    _chat_service_ready = chat_ready


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status, loaded tables, and chat readiness.",
)
def health_check() -> HealthResponse:
    """Liveness / readiness check."""
    if _schema_manager is None:
        return HealthResponse(
            status="error",
            tables_loaded=0,
            tables=[],
            chat_ready=False,
        )

    try:
        tables = _schema_manager.get_table_names()
        logger.debug(
            "Health check OK — %d tables loaded, chat_ready=%s.",
            len(tables), _chat_service_ready,
        )
        return HealthResponse(
            status="ok",
            tables_loaded=len(tables),
            tables=tables,
            chat_ready=_chat_service_ready,
        )
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return HealthResponse(
            status="error",
            tables_loaded=0,
            tables=[],
            chat_ready=False,
        )


@router.get(
    "/schema",
    summary="Get database schema",
    description=(
        "Returns the cached schema with table names, column metadata, "
        "and row counts. Useful for debugging and the optional "
        "'About this data' panel in the frontend."
    ),
)
def get_schema() -> dict:
    """Return the cached schema."""
    if _schema_manager is None:
        logger.warning("Schema requested but schema manager is not ready.")
        return {}
    logger.debug("Schema requested — returning cached schema.")
    return _schema_manager.get_schema_dict()

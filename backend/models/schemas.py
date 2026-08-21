"""Pydantic request/response models for the FMCG AI Sales Assistant API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language question about FMCG sales data",
        examples=["What are the total sales in Lahore last month?"],
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session identifier (reserved for future use)",
    )


# ── Response Models ───────────────────────────────────────────


class ChatResponse(BaseModel):
    """Response body for POST /api/chat."""

    answer: str = Field(
        ...,
        description="Natural-language answer grounded in real data",
    )
    sql: str | None = Field(
        default=None,
        description="Generated SQL query (null for meta-questions)",
    )
    columns: list[str] | None = Field(
        default=None,
        description="Column names from the query result",
    )
    rows: list[list] | None = Field(
        default=None,
        description="Query result rows (truncated to MAX_QUERY_ROWS)",
    )
    grounded: bool = Field(
        default=False,
        description="Whether the answer is backed by real SQL query results",
    )
    error: str | None = Field(
        default=None,
        description="Error type if something went wrong (no_matching_data, validation_error, etc.)",
    )


class HealthResponse(BaseModel):
    """Response body for GET /api/health."""

    status: str = Field(..., description="Service status: ok or error")
    tables_loaded: int = Field(default=0, description="Number of tables loaded")
    tables: list[str] = Field(default_factory=list, description="Table names")
    chat_ready: bool = Field(default=False, description="ChatService initialized")


class SchemaResponse(BaseModel):
    """Response body for GET /api/schema — dynamic dict of table info."""
    pass

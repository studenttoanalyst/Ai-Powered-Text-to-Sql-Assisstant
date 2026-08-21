"""Chat router — POST /api/chat.

Processes user questions and returns grounded answers.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ChatRequest, ChatResponse
from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.routers.chat")

router = APIRouter(prefix="/api", tags=["chat"])

# ChatService is injected at startup via app state
_chat_service = None


def set_chat_service(service) -> None:
    """Inject the ChatService instance (called from main.py lifespan)."""
    global _chat_service
    _chat_service = service


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question about FMCG sales data",
    description=(
        "Send a natural-language question and receive a data-grounded answer. "
        "Meta-questions (e.g. 'how many tables') are answered from the cached "
        "schema without any LLM call. Business questions go through the full "
        "Text-to-SQL → validate → execute → answer pipeline."
    ),
)
def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message and return a grounded answer."""
    logger.info(
        "POST /api/chat — message received (%d chars).", len(request.message)
    )

    if _chat_service is None:
        logger.warning("Chat service unavailable — request rejected with 503.")
        raise HTTPException(
            status_code=503,
            detail="Chat service is not ready. Please try again later.",
        )

    try:
        result = _chat_service.handle_message(request.message)
    except Exception:
        logger.exception("Unhandled error while processing chat message.")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing your question.",
        )

    logger.info(
        "POST /api/chat — done (grounded=%s, error=%s).",
        result.get("grounded"), result.get("error"),
    )
    return ChatResponse(**result)

"""LLM service: SQL generation and answer generation via Gemini.

Sends prompts to Gemini and returns cleaned SQL or
natural-language answers.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings
from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.llm_service")


class LLMServiceError(RuntimeError):
    """Raised when the LLM cannot complete a request."""


class LLMService:
    """Send prompts to Gemini and return cleaned SQL or answers."""

    INVALID_SCHEMA_REFERENCE = "INVALID_SCHEMA_REFERENCE"

    # Substrings in error messages that indicate a transient failure
    # worth retrying (Gemini 503 / overload / rate-limit / blips).
    RETRYABLE_ERROR_MARKERS = (
        "503", "500", "429",
        "unavailable", "overloaded", "overload",
        "rate limit", "resource_exhausted",
        "internal error", "deadline exceeded",
        "connection reset", "timed out", "timeout",
    )

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        resolved_key = settings.LLM_API_KEY if api_key is None else api_key
        resolved_model = settings.LLM_MODEL if model is None else model

        if not resolved_key or not str(resolved_key).strip():
            logger.error("LLMService init failed: no API key configured.")
            raise LLMServiceError("A Gemini API key is required.")

        self.api_key = str(resolved_key).strip()
        self.model = resolved_model
        self.max_retries = max(0, int(settings.LLM_MAX_RETRIES))
        self.retry_delay_seconds = max(0.0, float(settings.LLM_RETRY_DELAY_SECONDS))
        logger.info("LLMService initialized (model=%s)", self.model)

        self.answer_prompt_path = (
            Path(__file__).resolve().parent.parent / "prompts" / "answer_generation.txt"
        )

    # ---------------------------------------------------------
    # TEXT -> SQL
    # ---------------------------------------------------------

    def generate_sql(self, prompt: str) -> str:
        """Send a Text-to-SQL prompt to Gemini. Returns cleaned SQL."""
        if not prompt or not str(prompt).strip():
            logger.warning("generate_sql called with an empty prompt.")
            raise LLMServiceError("A valid prompt is required.")

        logger.debug(
            "Sending Text-to-SQL request to Gemini (%d chars).",
            len(str(prompt)),
        )
        response_text = self._generate_with_gemini(str(prompt).strip())
        cleaned_sql = self._clean_sql_response(response_text)

        if not cleaned_sql:
            logger.warning("Gemini returned an empty SQL response.")
            raise LLMServiceError("Gemini returned an empty response.")

        logger.info("Gemini generated SQL successfully.")
        return cleaned_sql

    # ---------------------------------------------------------
    # SQL RESULT -> NATURAL LANGUAGE
    # ---------------------------------------------------------

    def generate_answer(self, question: str, query_result: dict[str, Any]) -> str:
        """Convert an executed SQL result into a natural-language answer."""
        if not question or not str(question).strip():
            return "I couldn't generate an answer because the question was empty."

        if not isinstance(query_result, dict):
            return "I couldn't generate a natural language answer from the SQL result."

        if query_result.get("error_message"):
            return str(query_result["error_message"])

        rows = query_result.get("rows", []) or []
        if not rows:
            logger.info(
                "Query result has no rows — returning fallback answer."
            )
            return "No matching records were found."

        try:
            prompt = self._build_answer_prompt(str(question).strip(), query_result)
            logger.debug(
                "Sending answer-generation request to Gemini (%d chars).",
                len(prompt),
            )
            response_text = self._generate_with_gemini(prompt)
        except LLMServiceError as exc:
            logger.error("Answer generation request failed: %s", exc)
            return "I couldn't generate a natural language answer from the SQL result."

        cleaned_answer = self._clean_answer_response(response_text)
        if not cleaned_answer:
            logger.warning("Gemini returned an empty answer response.")
            return "I couldn't generate a natural language answer from the SQL result."

        logger.info("Gemini generated a natural-language answer.")
        return cleaned_answer

    # ---------------------------------------------------------
    # ANSWER PROMPT
    # ---------------------------------------------------------

    def _build_answer_prompt(self, question: str, query_result: dict[str, Any]) -> str:
        template = self._load_answer_template()
        result_text = self._format_query_result(query_result)
        prompt = template.replace("{{QUESTION}}", question)
        prompt = prompt.replace("{{QUERY_RESULT}}", result_text)
        return prompt

    def _load_answer_template(self) -> str:
        try:
            return self.answer_prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise LLMServiceError(
                f"Answer prompt template not found: {self.answer_prompt_path}"
            ) from exc
        except OSError as exc:
            raise LLMServiceError(f"Unable to read the answer prompt: {exc}") from exc

    def _format_query_result(self, query_result: dict[str, Any]) -> str:
        columns = query_result.get("columns", []) or []
        rows = query_result.get("rows", []) or []

        lines = ["Columns: " + (", ".join(columns) if columns else "none")]

        if rows:
            lines.append(f"Row count: {len(rows)}")
            lines.append("Rows:")
            for row in rows:
                if isinstance(row, dict):
                    row = tuple(row.values())
                lines.append(str(tuple(row)))
        else:
            lines.append("Rows: none")

        return "\n".join(lines)

    # ---------------------------------------------------------
    # GEMINI API
    # ---------------------------------------------------------

    def _generate_with_gemini(self, prompt: str) -> str:
        try:
            from google import genai
        except ImportError as exc:
            raise LLMServiceError(
                "The google-genai package is not installed."
            ) from exc

        attempts = self.max_retries + 1
        last_exc: Exception | None = None
        client = genai.Client(api_key=self.api_key)

        for attempt in range(1, attempts + 1):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
            except Exception as exc:
                last_exc = exc
                if attempt < attempts and self._is_retryable_error(exc):
                    delay = self.retry_delay_seconds * attempt
                    logger.warning(
                        "Gemini request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt, attempts, delay, exc,
                    )
                    time.sleep(delay)
                    continue
                logger.error("Gemini request failed: %s", exc)
                raise LLMServiceError(f"Gemini request failed: {exc}") from exc

            if not hasattr(response, "text") or not response.text:
                logger.warning("Gemini returned an empty response body.")
                raise LLMServiceError("Gemini returned an empty response.")

            return str(response.text)

        # Defensive: loop should always return or raise.
        raise LLMServiceError(
            f"Gemini request failed after {attempts} attempt(s): {last_exc}"
        )

    def _is_retryable_error(self, exc: Exception) -> bool:
        """True if the exception looks like a transient Gemini error (e.g. 503)."""
        message = str(exc).lower()
        return any(marker in message for marker in self.RETRYABLE_ERROR_MARKERS)

    # ---------------------------------------------------------
    # SQL CLEANING
    # ---------------------------------------------------------

    def _clean_sql_response(self, response_text: str) -> str:
        if not response_text:
            return ""

        cleaned = response_text.strip()

        if cleaned.upper() == self.INVALID_SCHEMA_REFERENCE:
            return self.INVALID_SCHEMA_REFERENCE

        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        if cleaned.lower().startswith("sql") and "\n" in cleaned:
            first_line, remaining = cleaned.split("\n", 1)
            if first_line.strip().lower() == "sql":
                cleaned = remaining.strip()

        return cleaned

    def _clean_answer_response(self, response_text: str) -> str:
        if not response_text:
            return ""
        cleaned = response_text.strip()
        cleaned = re.sub(r"```(?:text|markdown)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"```", "", cleaned)
        return cleaned.strip()

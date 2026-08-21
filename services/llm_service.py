"""LLM service for Version 2: SQL generation and answer generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config.settings import settings


class LLMServiceError(RuntimeError):
    """Raised when the LLM cannot complete a request."""


class LLMService:
    """
    Send prompts to Gemini and return cleaned SQL or
    natural-language answers.

    Version 2 supports prompts containing:
    - Multiple tables
    - Multiple columns
    - Primary keys
    - Foreign keys
    - Detected relationships
    - JOIN instructions
    """

    INVALID_SCHEMA_REFERENCE = "INVALID_SCHEMA_REFERENCE"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.7-flash",
    ) -> None:
        resolved_key = (
            settings.GEMINI_API_KEY
            if api_key is None
            else api_key
        )

        if not resolved_key or not str(resolved_key).strip():
            raise LLMServiceError(
                "A Gemini API key is required."
            )

        self.api_key = str(resolved_key).strip()
        self.model = model

        self.answer_prompt_path = (
            Path(__file__).resolve().parents[1]
            / "prompts"
            / "answer_generation.txt"
        )

    # ---------------------------------------------------------
    # TEXT → SQL
    # ---------------------------------------------------------

    def generate_sql(self, prompt: str) -> str:
        """
        Send a Text-to-SQL prompt to Gemini.

        The prompt is expected to already contain the complete
        database schema and the user's question.

        Returns:
            Cleaned SQL or INVALID_SCHEMA_REFERENCE.
        """

        if not prompt or not str(prompt).strip():
            raise LLMServiceError(
                "A valid prompt is required."
            )

        response_text = self._generate_with_gemini(
            str(prompt).strip()
        )

        cleaned_sql = self._clean_sql_response(
            response_text
        )

        if not cleaned_sql:
            raise LLMServiceError(
                "Gemini returned an empty response."
            )

        return cleaned_sql

    # ---------------------------------------------------------
    # SQL RESULT → NATURAL LANGUAGE
    # ---------------------------------------------------------

    def generate_answer(
        self,
        question: str,
        query_result: dict[str, Any],
    ) -> str:
        """
        Convert an executed SQL result into a natural-language answer.
        """

        if not question or not str(question).strip():
            return (
                "I couldn't generate an answer because "
                "the question was empty."
            )

        if not isinstance(query_result, dict):
            return (
                "I couldn't generate a natural language "
                "answer from the SQL result."
            )

        if query_result.get("error_message"):
            return str(query_result["error_message"])

        rows = query_result.get("rows", []) or []

        if not rows:
            return "No matching records were found."

        try:
            prompt = self._build_answer_prompt(
                str(question).strip(),
                query_result,
            )

            response_text = self._generate_with_gemini(
                prompt
            )

        except LLMServiceError:
            return (
                "I couldn't generate a natural language "
                "answer from the SQL result."
            )

        cleaned_answer = self._clean_answer_response(
            response_text
        )

        if not cleaned_answer:
            return (
                "I couldn't generate a natural language "
                "answer from the SQL result."
            )

        return cleaned_answer

    # ---------------------------------------------------------
    # ANSWER PROMPT
    # ---------------------------------------------------------

    def _build_answer_prompt(
        self,
        question: str,
        query_result: dict[str, Any],
    ) -> str:
        """Build the prompt used for result-to-answer generation."""

        template = self._load_answer_template()

        result_text = self._format_query_result(
            query_result
        )

        prompt = template.replace(
            "{{QUESTION}}",
            question,
        )

        prompt = prompt.replace(
            "{{QUERY_RESULT}}",
            result_text,
        )

        return prompt

    def _load_answer_template(self) -> str:
        """Load answer-generation prompt from disk."""

        try:
            return self.answer_prompt_path.read_text(
                encoding="utf-8"
            )

        except FileNotFoundError as exc:
            raise LLMServiceError(
                f"Answer prompt template not found: "
                f"{self.answer_prompt_path}"
            ) from exc

        except OSError as exc:
            raise LLMServiceError(
                f"Unable to read the answer prompt: {exc}"
            ) from exc

    def _format_query_result(
        self,
        query_result: dict[str, Any],
    ) -> str:
        """Convert SQL result into text for the answer prompt."""

        columns = query_result.get(
            "columns",
            [],
        ) or []

        rows = query_result.get(
            "rows",
            [],
        ) or []

        lines = [
            "Columns: "
            + (
                ", ".join(columns)
                if columns
                else "none"
            )
        ]

        if rows:
            lines.append(
                f"Row count: {len(rows)}"
            )

            lines.append("Rows:")

            for row in rows:
                # QueryExecutor returns rows as dicts while some
                # callers pass tuples/lists. Normalize before
                # converting so values are never lost.
                if isinstance(row, dict):
                    row = tuple(row.values())

                lines.append(str(tuple(row)))

        else:
            lines.append("Rows: none")

        return "\n".join(lines)

    # ---------------------------------------------------------
    # GEMINI API
    # ---------------------------------------------------------

    def _generate_with_gemini(
        self,
        prompt: str,
    ) -> str:
        """
        Send a prompt to Gemini and return raw response text.
        """

        try:
            from google import genai

        except ImportError as exc:
            raise LLMServiceError(
                "The google-genai package is not installed."
            ) from exc

        try:
            client = genai.Client(
                api_key=self.api_key
            )

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )

        except Exception as exc:
            raise LLMServiceError(
                f"Gemini request failed: {exc}"
            ) from exc

        if (
            not hasattr(response, "text")
            or not response.text
        ):
            raise LLMServiceError(
                "Gemini returned an empty response."
            )

        return str(response.text)

    # ---------------------------------------------------------
    # SQL CLEANING
    # ---------------------------------------------------------

    def _clean_sql_response(
        self,
        response_text: str,
    ) -> str:
        """
        Clean Gemini's SQL response.

        Removes:
        - Markdown code fences
        - Leading/trailing whitespace
        - Optional 'sql' label
        """

        if not response_text:
            return ""

        cleaned = response_text.strip()

        # Preserve the V2 sentinel exactly.
        if (
            cleaned.upper()
            == self.INVALID_SCHEMA_REFERENCE
        ):
            return self.INVALID_SCHEMA_REFERENCE

        # Remove opening markdown fence.
        cleaned = re.sub(
            r"^```(?:sql)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        # Remove closing markdown fence.
        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = cleaned.strip()

        # Handle:
        #
        # sql
        # SELECT ...
        #
        if (
            cleaned.lower().startswith("sql")
            and "\n" in cleaned
        ):
            first_line, remaining = (
                cleaned.split("\n", 1)
            )

            if first_line.strip().lower() == "sql":
                cleaned = remaining.strip()

        return cleaned

    # ---------------------------------------------------------
    # ANSWER CLEANING
    # ---------------------------------------------------------

    def _clean_answer_response(
        self,
        response_text: str,
    ) -> str:
        """Clean Markdown formatting from an answer."""

        if not response_text:
            return ""

        cleaned = response_text.strip()

        cleaned = re.sub(
            r"```(?:text|markdown)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"```",
            "",
            cleaned,
        )

        return cleaned.strip()
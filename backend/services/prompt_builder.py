"""Prompt builder service.

Builds LLM prompts using the complete relational schema
and the user's natural-language question.
"""

from __future__ import annotations

from pathlib import Path

from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.prompt_builder")


class PromptBuilderError(RuntimeError):
    """Raised when a prompt cannot be built from the template."""


class PromptBuilder:
    """Build Text-to-SQL prompts from schema + question + template."""

    SCHEMA_PLACEHOLDER = "{{SCHEMA}}"
    QUESTION_PLACEHOLDER = "{{QUESTION}}"

    def __init__(self, template_path: str | Path | None = None) -> None:
        self.template_path = Path(
            template_path
            or Path(__file__).resolve().parent.parent
            / "prompts"
            / "text_to_sql.txt"
        )

    def build_prompt(self, schema_text: str, question: str) -> str:
        """Build the final Text-to-SQL prompt."""
        schema = self._validate_input(
            schema_text, "A valid schema is required to build the prompt."
        )
        user_question = self._validate_input(
            question, "A valid question is required to build the prompt."
        )
        template = self._load_template()
        self._validate_template(template)

        prompt = template.replace(self.SCHEMA_PLACEHOLDER, schema)
        prompt = prompt.replace(self.QUESTION_PLACEHOLDER, user_question)
        logger.debug(
            "Built Text-to-SQL prompt (%d chars) for question: %s",
            len(prompt), user_question,
        )
        return prompt

    @staticmethod
    def _validate_input(value: str, error_message: str) -> str:
        if value is None or not str(value).strip():
            raise PromptBuilderError(error_message)
        return str(value).strip()

    def _load_template(self) -> str:
        try:
            return self.template_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            logger.error("Prompt template not found: %s", self.template_path)
            raise PromptBuilderError(
                f"Prompt template not found: {self.template_path}"
            ) from exc
        except OSError as exc:
            logger.error("Unable to read the prompt template: %s", exc)
            raise PromptBuilderError(
                f"Unable to read the prompt template: {exc}"
            ) from exc

    def _validate_template(self, template: str) -> None:
        if self.SCHEMA_PLACEHOLDER not in template:
            logger.error(
                "Prompt template is missing %s placeholder.",
                self.SCHEMA_PLACEHOLDER,
            )
            raise PromptBuilderError(
                f"Prompt template is missing {self.SCHEMA_PLACEHOLDER} placeholder."
            )
        if self.QUESTION_PLACEHOLDER not in template:
            logger.error(
                "Prompt template is missing %s placeholder.",
                self.QUESTION_PLACEHOLDER,
            )
            raise PromptBuilderError(
                f"Prompt template is missing {self.QUESTION_PLACEHOLDER} placeholder."
            )

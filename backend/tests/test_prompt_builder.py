"""Tests for backend.services.prompt_builder.PromptBuilder."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.prompt_builder import PromptBuilder, PromptBuilderError


@pytest.fixture
def template_file(tmp_path: Path) -> Path:
    template = tmp_path / "text_to_sql.txt"
    template.write_text(
        "DATABASE SCHEMA:\n{{SCHEMA}}\n\nUSER QUESTION:\n{{QUESTION}}",
        encoding="utf-8",
    )
    return template


@pytest.fixture
def builder(template_file: Path) -> PromptBuilder:
    return PromptBuilder(template_file)


class TestBuildPrompt:
    def test_replaces_schema_and_question(self, builder: PromptBuilder):
        prompt = builder.build_prompt("TABLE customers", "Show all customers")
        assert "TABLE customers" in prompt
        assert "Show all customers" in prompt
        assert "{{SCHEMA}}" not in prompt
        assert "{{QUESTION}}" not in prompt

    def test_strips_whitespace(self, builder: PromptBuilder):
        prompt = builder.build_prompt("  schema  ", "  question  ")
        assert "schema" in prompt
        assert "question" in prompt


class TestValidation:
    def test_rejects_empty_schema(self, builder: PromptBuilder):
        with pytest.raises(PromptBuilderError, match="valid schema"):
            builder.build_prompt("", "Show customers")

    def test_rejects_empty_question(self, builder: PromptBuilder):
        with pytest.raises(PromptBuilderError, match="valid question"):
            builder.build_prompt("TABLE customers", "")

    def test_rejects_none_schema(self, builder: PromptBuilder):
        with pytest.raises(PromptBuilderError, match="valid schema"):
            builder.build_prompt(None, "Show customers")  # type: ignore

    def test_rejects_missing_schema_placeholder(self, tmp_path: Path):
        template = tmp_path / "bad.txt"
        template.write_text("Q: {{QUESTION}}", encoding="utf-8")
        builder = PromptBuilder(template)
        with pytest.raises(PromptBuilderError, match="SCHEMA"):
            builder.build_prompt("schema", "question")

    def test_rejects_missing_question_placeholder(self, tmp_path: Path):
        template = tmp_path / "bad.txt"
        template.write_text("S: {{SCHEMA}}", encoding="utf-8")
        builder = PromptBuilder(template)
        with pytest.raises(PromptBuilderError, match="QUESTION"):
            builder.build_prompt("schema", "question")

    def test_rejects_missing_template(self):
        builder = PromptBuilder("/nonexistent/path.txt")
        with pytest.raises(PromptBuilderError, match="not found"):
            builder.build_prompt("schema", "question")

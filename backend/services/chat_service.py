"""Chat service: orchestrates one chat turn end-to-end.

Pipeline: question -> prompt -> SQL -> validate -> execute -> answer

Anti-hallucination design:
1. Schema-grounded prompts (LLM sees real schema)
2. SQL validation (SELECT-only, schema-aware)
3. Result-grounded answers (LLM sees only actual rows)
4. Meta-question shortcut (schema questions bypass LLM)
"""

from __future__ import annotations

from typing import Any

from backend.services.prompt_builder import PromptBuilder, PromptBuilderError
from backend.services.schema_manager import SchemaManager
from backend.services.sql_validator import SQLValidator
from backend.services.query_executor import QueryExecutor
from backend.services.llm_service import LLMService, LLMServiceError
from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.chat_service")

# ── Conversational / Greeting patterns ─────────────────────────
# These are caught BEFORE meta-questions and SQL pipeline.
# Returns a friendly reply without any LLM or database call.
GREETING_KEYWORDS = [
    "hello", "hi", "hey", "hlo", "hlw",
    "salaam", "assalamu alaikum", "assalam o alaikum",
    "good morning", "good afternoon", "good evening", "good night",
]

CASUAL_KEYWORDS = [
    "thanks", "thank you", "shukriya", "bohot shukriya",
    "bye", "goodbye", "alvida", "see you", "chalta hun", "chal",
    "ok", "okay", "theek hai", "acha", "accha",
]

ROMAN_URDU_GREETINGS = [
    "kya haal hai", "kaisay ho", "kaise ho", "kya chal raha hai",
    "kya kar rahe ho", "kya hal hai",
]

# Self-introduction / capability questions
CAPABILITY_KEYWORDS = [
    "tum kya kar sakte ho", "tum kya kar sakti ho",
    "what can you do", "what do you do", "what are you",
    "who are you", "who r u", "your capabilities",
    "help me", "help", "what can i ask",
    "kya kar saktay ho", "kya kar sakti ho",
]

# ── Meta-question patterns ──────────────────────────────────────
# These bypass SQL generation entirely — answered from cached schema.
# NOTE: deliberately NOT matching bare "column"/"field" — questions like
# "show fake column" are data requests and must go through the LLM +
# validator path. Only structural phrasings are intercepted here.
META_PATTERNS = [
    "how many tables", "what tables", "list tables", "list all tables",
    "show tables", "show me tables",
    "what columns", "how many columns", "show columns",
    "column names", "columns in", "what fields", "how many fields",
    "describe table", "describe the dataset", "schema of",
    "row count", "how many rows",
    # Roman Urdu variants and schema keywords
    "kitni tables", "kitne tables", "tables hain", "tables hai",
    "table count", "dataset mein tables",
    "what is the schema", "show schema", "describe schema",
    "schema of", "database schema",
]

# Patterns that mean "enumerate/count the tables"
TABLE_LIST_PATTERNS = [
    "how many tables", "what tables", "list tables", "list all tables",
    "show tables", "show me tables",
    "kitni tables", "kitne tables", "tables hain", "tables hai",
    "table count",
]


class ChatService:
    """Orchestrate a single chat turn: question -> answer."""

    def __init__(
        self,
        schema_manager: SchemaManager,
        llm_service: LLMService,
        db_path: str,
    ) -> None:
        self.schema_manager = schema_manager
        self.llm_service = llm_service
        self.prompt_builder = PromptBuilder()
        self.sql_validator = SQLValidator()
        self.query_executor = QueryExecutor(db_path)
        self.max_query_rows = 1000

    def handle_message(self, question: str) -> dict[str, Any]:
        """Process a user message and return a structured response."""
        if not question or not str(question).strip():
            return self._empty_question_response()

        question = str(question).strip()
        logger.info("Processing question: %s", question)

        # Step 0a: Conversational / greeting interception
        if self._is_conversational(question):
            return self._handle_conversational(question)

        # Step 0b: Meta-question shortcut
        if self._is_meta_question(question):
            return self._handle_meta_question(question)

        # Step 1: Build prompt with schema
        schema_text = self.schema_manager.build_schema_text()
        try:
            prompt = self.prompt_builder.build_prompt(schema_text, question)
        except PromptBuilderError as exc:
            logger.error("Prompt building failed: %s", exc)
            return self._error_response(str(exc))

        # Step 2: Generate SQL via LLM
        try:
            sql = self.llm_service.generate_sql(prompt)
        except LLMServiceError as exc:
            logger.error("LLM SQL generation failed: %s", exc)
            return self._error_response(
                "I couldn't generate a query for that question."
            )

        logger.info("Generated SQL: %s", sql)

        # Handle INVALID_SCHEMA_REFERENCE
        if sql == LLMService.INVALID_SCHEMA_REFERENCE:
            return self._no_data_response()

        # Step 3: Validate SQL against schema
        # Extract columns-only format for the validator
        schema_for_validator = {
            table: info.get("columns", [])
            for table, info in self.schema_manager.get_schema_dict().items()
        }
        validation = self.sql_validator.validate(sql, schema_for_validator)

        if not validation["is_valid"]:
            logger.warning("SQL validation failed: %s", validation["error_message"])
            return self._error_response(validation["error_message"])

        # Step 4: Execute query
        exec_result = self.query_executor.execute(sql)

        if not exec_result["success"]:
            logger.warning("Query execution failed: %s", exec_result["error_message"])
            return self._sql_error_response(exec_result["error_message"])

        # Step 5: Generate natural-language answer
        try:
            answer = self.llm_service.generate_answer(question, exec_result)
        except Exception as exc:
            logger.error("Answer generation failed: %s", exc)
            answer = "I found data but couldn't generate a natural language answer."

        return {
            "answer": answer,
            "sql": sql,
            "columns": exec_result["columns"],
            "rows": [
                list(row.values())
                for row in exec_result["rows"][: self.max_query_rows]
            ],
            "grounded": True,
        }

    # ── Conversational / Greeting handling ─────────────────────────

    @staticmethod
    def _is_conversational(question: str) -> bool:
        """Detect greetings, casual messages, and capability questions.

        These should be answered directly without touching the SQL pipeline.
        """
        import re as _re
        q = question.lower().strip()
        # Strip punctuation for casual matching
        q_clean = _re.sub(r'[!?.,;:]+$', '', q).strip()
        # Check greetings
        if any(kw in q for kw in GREETING_KEYWORDS):
            return True
        # Check Roman Urdu greetings
        if any(kw in q for kw in ROMAN_URDU_GREETINGS):
            return True
        # Check casual / farewell messages (use cleaned text)
        if q_clean in CASUAL_KEYWORDS:
            return True
        # Check capability questions (exact or loose match)
        if any(kw in q for kw in CAPABILITY_KEYWORDS):
            return True
        return False

    @staticmethod
    def _handle_conversational(question: str) -> dict[str, Any]:
        """Return a friendly response for greetings and casual messages."""
        q = question.lower().strip()

        # Capability / "who are you" questions
        if any(kw in q for kw in CAPABILITY_KEYWORDS):
            answer = (
                "I'm your FMCG Sales Data Assistant! Here's what I can help with:\n\n"
                "📊 **Data Queries** — Ask me about sales figures, inventory levels, "
                "customer counts, product prices, and more. For example:\n"
                "  \u2022 \"What were total sales in Lahore last month?\"\n"
                "  \u2022 \"Top 5 SKUs by gross profit\"\n"
                "  \u2022 \"How many customers are in each city?\"\n\n"
                "📋 **Schema Info** — Ask about the dataset structure:\n"
                "  \u2022 \"What tables do you have?\"\n"
                "  \u2022 \"What columns does Sales_Transactions have?\"\n\n"
                "I answer only from real data — no guessing, no hallucination. "
                "Just ask in English or Roman Urdu!"
            )
            return {
                "answer": answer,
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # Farewell messages
        if any(kw in q for kw in ["bye", "goodbye", "alvida", "see you", "chalta hun", "chal"]):
            return {
                "answer": "Goodbye! Feel free to come back anytime you have questions about the FMCG sales data. Have a great day! 😊",
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # Thank you messages
        if any(kw in q for kw in ["thanks", "thank you", "shukriya", "bohot shukriya"]):
            return {
                "answer": "You're welcome! If you have any more questions about the FMCG sales data, just ask. 😊",
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # Acknowledgments (ok, theek hai, etc.)
        if any(kw == q for kw in ["ok", "okay", "theek hai", "acha", "accha"]):
            return {
                "answer": "Got it! Let me know if you have any questions about the FMCG sales data.",
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # Default greeting response (catches hi, hello, kya haal hai, etc.)
        return {
            "answer": "Hello! 👋 I'm your FMCG Sales Data Assistant. I can help you explore sales data, inventory, customer info, and more. What would you like to know?",
            "sql": None,
            "columns": None,
            "rows": None,
            "grounded": True,
        }

    def _is_meta_question(self, question: str) -> bool:
        q = question.lower()
        return any(p in q for p in META_PATTERNS)

    def _handle_meta_question(self, question: str) -> dict[str, Any]:
        schema = self.schema_manager.schema_cache
        q = question.lower()

        # --- Specific table column query: "what columns does X have" ---
        specific_table = self._extract_table_from_question(q, schema)
        if specific_table and any(kw in q for kw in ["column", "field"]):
            info = schema[specific_table]
            cols = [c["column_name"] for c in info.get("columns", [])]
            row_count = info.get("row_count", 0)
            answer = (
                f"Table '{specific_table}' has {len(cols)} columns: "
                f"{', '.join(cols)}. "
                f"It contains {row_count:,} rows."
            )
            return {
                "answer": answer,
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # --- Row count for specific table ---
        if specific_table and any(kw in q for kw in ["row count", "how many rows"]):
            info = schema[specific_table]
            row_count = info.get("row_count", 0)
            answer = f"Table '{specific_table}' contains {row_count:,} rows."
            return {
                "answer": answer,
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # --- "How many tables" / "List tables" / "kitni tables" ---
        if any(kw in q for kw in TABLE_LIST_PATTERNS):
            tables = list(schema.keys())
            answer = f"The database contains {len(tables)} tables: {', '.join(tables)}."
            return {
                "answer": answer,
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # --- "What columns" (all tables) ---
        if any(
            kw in q for kw in [
                "what columns", "how many columns", "show columns",
                "column names", "columns in", "what fields", "how many fields",
            ]
        ):
            parts = []
            for table_name, info in schema.items():
                cols = [c["column_name"] for c in info.get("columns", [])]
                parts.append(f"{table_name}: {', '.join(cols)}")
            answer = "Here are the columns for each table:\n" + "\n".join(parts)
            return {
                "answer": answer,
                "sql": None,
                "columns": None,
                "rows": None,
                "grounded": True,
            }

        # --- General schema overview ---
        total_cols = sum(
            len(info.get("columns", [])) for info in schema.values()
        )
        total_rows = sum(
            info.get("row_count", 0) for info in schema.values()
        )
        parts = []
        for table_name, info in schema.items():
            cols = [c["column_name"] for c in info.get("columns", [])]
            parts.append(f"{table_name} ({len(cols)} cols, {info.get('row_count', 0):,} rows)")
        table_summary = ", ".join(parts)
        answer = (
            f"The dataset contains {len(schema)} tables with {total_cols} columns "
            f"and approximately {total_rows:,} rows total:\n{table_summary}"
        )
        return {
            "answer": answer,
            "sql": None,
            "columns": None,
            "rows": None,
            "grounded": True,
        }

    @staticmethod
    def _extract_table_from_question(question: str, schema: dict) -> str | None:
        """Extract a table name mentioned in the question."""
        for table_name in schema:
            if table_name.lower() in question:
                return table_name
        return None

    @staticmethod
    def _error_response(message: str) -> dict[str, Any]:
        return {
            "answer": message,
            "sql": None,
            "columns": [],
            "rows": [],
            "grounded": False,
            "error": "validation_error",
        }

    @staticmethod
    def _no_data_response() -> dict[str, Any]:
        return {
            "answer": "I couldn't find data matching that question in the available tables.",
            "sql": None,
            "columns": [],
            "rows": [],
            "grounded": False,
            "error": "no_matching_data",
        }

    @staticmethod
    def _sql_error_response(detail: str) -> dict[str, Any]:
        return {
            "answer": (
                "I encountered an issue while running the query. "
                "Please try rephrasing your question."
            ),
            "sql": None,
            "columns": [],
            "rows": [],
            "grounded": False,
            "error": "sql_error",
            "error_detail": detail,
        }

    @staticmethod
    def _empty_question_response() -> dict[str, Any]:
        return {
            "answer": "Please enter a question about the FMCG sales data.",
            "sql": None,
            "columns": [],
            "rows": [],
            "grounded": False,
            "error": "empty_question",
        }

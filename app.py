"""Streamlit user interface for AI-Powered Text-to-SQL Assistant.

Professional SaaS-style UI.

Flow: upload -> validate/save -> load DataFrames -> persist into SQLite
-> extract schema -> (chat) build prompt -> Gemini SQL -> validate
-> execute -> Gemini natural-language answer.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import settings
from database.database import Database, DatabaseError
from services.data_loader import DataLoader, DataLoaderError
from services.file_manager import FileManager, FileValidationError
from services.llm_service import LLMService, LLMServiceError
from services.prompt_builder import PromptBuilder, PromptBuilderError
from services.query_executor import QueryExecutor
from services.schema_generator import (
    RelationalSchemaGenerator,
    SchemaGenerationError,
)
from services.schema_manager import SchemaManager, SchemaManagerError
from services.sql_validator import SQLValidator
from utils.logger import get_logger

logger = get_logger(__name__)

SAMPLE_QUESTIONS = [
    "Show me the first 5 rows of the data.",
    "How many records are in the dataset?",
    "Give me a quick summary of the dataset.",
]

SESSION_DEFAULTS: dict[str, object] = {
    "loaded_file_name": None,
    "saved_path": None,
    "table_names": [],
    "row_count": 0,
    "column_count": 0,
    "schema_text": "",
    "schema": {},
    "chat_history": [],
    "sample_question": None,
}


# ----------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------


def _init_session_state() -> None:
    """Seed session state with safe defaults on first run."""
    for key, value in SESSION_DEFAULTS.items():
        st.session_state.setdefault(key, value)


def _reset_upload_state() -> None:
    """Clear upload, schema, and chat state so a new upload starts clean."""
    for key, value in SESSION_DEFAULTS.items():
        st.session_state[key] = value


# ----------------------------------------------------------------------
# STYLING
# ----------------------------------------------------------------------


def _inject_css() -> None:
    """Inject custom CSS for a modern, professional SaaS aesthetic."""
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #f6f8fb;
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        /* Header */
        .app-header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            border-radius: 16px;
            padding: 26px 32px;
            margin-bottom: 24px;
            color: #ffffff;
            box-shadow: 0 10px 30px rgba(79, 70, 229, 0.25);
        }
        .app-header-title {
            font-size: 1.9rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .app-header-subtitle {
            font-size: 1rem;
            opacity: 0.92;
            margin: 8px 0 14px 0;
        }
        .header-badges {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .badge {
            background: rgba(255, 255, 255, 0.16);
            border: 1px solid rgba(255, 255, 255, 0.35);
            border-radius: 999px;
            padding: 3px 12px;
            font-size: 0.78rem;
            font-weight: 600;
        }

        /* Panels */
        .panel-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 2px;
        }
        .panel-caption {
            color: #64748b;
            font-size: 0.9rem;
            margin-bottom: 12px;
        }

        /* Chat bubbles */
        [data-testid="stChatMessage"] {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 10px 14px;
            margin-bottom: 10px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
        }
        [data-testid="stChatMessage"] p {
            margin-bottom: 0.25rem;
        }

        /* Status pills */
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border-radius: 999px;
            padding: 6px 14px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .status-pill.green {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }
        .status-pill.amber {
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fcd34d;
        }

        /* Footer */
        .footer {
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            text-align: center;
            color: #94a3b8;
            font-size: 0.85rem;
        }

        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 12px 16px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    """Render the polished application header."""
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-header-title">
                <span>🤖</span>
                <span>{settings.APP_NAME}</span>
            </div>
            <p class="app-header-subtitle">
                Upload your dataset, ask questions in plain English, and receive
                AI-powered insights — with the generated SQL shown for transparency.
            </p>
            <div class="header-badges">
                <span class="badge">Text-to-SQL</span>
                <span class="badge">Gemini API</span>
                <span class="badge">SQLite</span>
                <span class="badge">Streamlit</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------------


def _render_sidebar() -> None:
    """Render project metadata, sample questions, and chat controls."""
    with st.sidebar:
        st.markdown("## 🤖 Assistant Info")
        st.divider()

        st.markdown("#### 📌 Project")
        st.caption(settings.APP_NAME)
        st.caption("**v2.0.0** · Production UI")

        st.markdown("#### 🌐 Environment")
        st.info(f"**{settings.ENVIRONMENT.title()}**")

        st.markdown("#### 📁 Supported Formats")
        st.markdown("`CSV` • `.XLSX` (all worksheets)")

        st.markdown("#### ⚡ Technology Stack")
        st.markdown(
            "- **Frontend:** Streamlit\n"
            "- **Backend:** Python\n"
            "- **Database:** SQLite\n"
            "- **AI Engine:** Gemini\n"
            "- **Data Processing:** Pandas"
        )

        st.markdown("#### 🗄️ Database")
        st.code(settings.DATABASE_NAME, language="text")

        st.divider()

        st.markdown("#### 🧪 Sample Questions")
        for index, question in enumerate(SAMPLE_QUESTIONS):
            if st.button(
                question,
                use_container_width=True,
                key=f"sample_{index}",
            ):
                st.session_state["sample_question"] = question

        if st.session_state.get("chat_history"):
            if st.button(
                "🗑️ Clear Conversation",
                use_container_width=True,
                key="clear_chat",
            ):
                st.session_state["chat_history"] = []
                st.rerun()


# ----------------------------------------------------------------------
# UPLOAD FLOW
# ----------------------------------------------------------------------


def _handle_upload(
    uploaded_file: object,
    file_manager: FileManager,
    data_loader: DataLoader,
    schema_generator: RelationalSchemaGenerator,
    schema_manager: SchemaManager,
    database: Database,
) -> None:
    """Validate, save, load, persist, and introspect an uploaded file."""

    if st.session_state.get("loaded_file_name") == uploaded_file.name:
        return

    _reset_upload_state()

    try:
        with st.spinner("Saving uploaded file..."):
            saved_path = file_manager.save_upload(uploaded_file)
    except FileValidationError as exc:
        st.error(f"**Upload rejected:** {exc}")
        return

    try:
        with st.spinner("Reading dataset..."):
            tables = data_loader.load_file(saved_path)

        with st.spinner("Loading into SQLite..."):
            counts = schema_generator.persist_tables(database, tables)
    except (DataLoaderError, SchemaGenerationError, DatabaseError) as exc:
        st.error(f"**Dataset could not be loaded:** {exc}")
        return

    try:
        table_names = list(counts.keys())

        schema_text = schema_manager.build_schema_text(table_names)
        schema = schema_manager.get_full_schema(table_names)
    except SchemaManagerError as exc:
        st.error(f"**Schema extraction failed:** {exc}")
        return

    st.session_state.update(
        {
            "loaded_file_name": uploaded_file.name,
            "saved_path": str(saved_path),
            "table_names": table_names,
            "row_count": sum(counts.values()),
            "column_count": sum(
                len(columns)
                for columns in schema.values()
            ),
            "schema_text": schema_text,
            "schema": schema,
        }
    )


def _render_dataset_summary() -> None:
    """Show metrics and schema for the active dataset."""
    st.success("✅ **Dataset ready**")

    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Tables",
        len(st.session_state["table_names"]),
    )
    metric_columns[1].metric(
        "Rows",
        f"{st.session_state['row_count']:,}",
    )
    metric_columns[2].metric(
        "Columns",
        st.session_state["column_count"],
    )

    with st.expander("🔍 View Extracted Schema", expanded=False):
        st.code(
            st.session_state["schema_text"],
            language="text",
        )


def _render_empty_state() -> None:
    """Show onboarding hints when no dataset is uploaded."""
    st.info("No dataset uploaded yet.")

    st.markdown("**How it works**")
    st.markdown(
        "1. Upload a **CSV** or **Excel** file above.\n"
        "2. Ask questions in plain English.\n"
        "3. Get natural-language answers with the generated SQL."
    )


# ----------------------------------------------------------------------
# CHAT FLOW
# ----------------------------------------------------------------------


def _process_question(
    question: str,
    prompt_builder: PromptBuilder,
    llm_service: LLMService | None,
    llm_error_message: str,
    sql_validator: SQLValidator,
    query_executor: QueryExecutor,
) -> dict[str, object]:
    """Run one question through the full Text-to-SQL pipeline."""

    schema_text = st.session_state.get("schema_text", "")

    if not schema_text:
        return {
            "question": question,
            "answer": "Please load a dataset first so the schema is available.",
            "is_error": True,
        }

    if llm_service is None:
        return {
            "question": question,
            "answer": (
                llm_error_message
                or "The AI service is unavailable."
            ),
            "is_error": True,
        }

    try:
        with st.spinner("Generating SQL..."):
            prompt = prompt_builder.build_prompt(
                schema_text,
                question,
            )
            sql = llm_service.generate_sql(prompt)

        validation = sql_validator.validate(
            sql,
            st.session_state.get("schema") or None,
        )

        if not validation["is_valid"]:
            return {
                "question": question,
                "answer": validation["error_message"],
                "is_error": True,
            }

        with st.spinner("Executing SQL..."):
            result = query_executor.execute(sql)

        if result.get("error_message"):
            return {
                "question": question,
                "answer": result["error_message"],
                "is_error": True,
            }

        with st.spinner("Generating natural-language answer..."):
            answer = llm_service.generate_answer(
                question,
                result,
            )

        return {
            "question": question,
            "answer": answer,
            "sql": sql,
            "result": result,
            "is_error": False,
        }

    except (PromptBuilderError, LLMServiceError) as exc:
        return {
            "question": question,
            "answer": str(exc),
            "is_error": True,
        }


def _render_chat_message(message: dict[str, object]) -> None:
    """Render one user/assistant exchange as chat bubbles."""

    with st.chat_message("user"):
        st.markdown(message["question"])

    with st.chat_message("assistant"):
        if message.get("is_error"):
            st.error(message["answer"])
        else:
            st.markdown(message["answer"])

        if message.get("sql"):
            with st.expander("🛠️ Generated SQL", expanded=False):
                st.code(message["sql"], language="sql")

        result = message.get("result")

        if isinstance(result, dict):
            rows = result.get("rows") or []
            columns = result.get("columns") or []

            with st.expander(
                f"📊 Raw Result — {len(rows)} row(s)",
                expanded=False,
            ):
                if rows:
                    st.dataframe(
                        pd.DataFrame(rows, columns=columns),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption("No rows returned.")


def _render_chat(
    prompt_builder: PromptBuilder,
    llm_service: LLMService | None,
    llm_error_message: str,
    sql_validator: SQLValidator,
    query_executor: QueryExecutor,
) -> None:
    """Render the conversation and the chat input."""

    # A sample question selected from the sidebar.
    pending_question = st.session_state.get("sample_question")

    if pending_question:
        st.session_state["sample_question"] = None

        message = _process_question(
            str(pending_question),
            prompt_builder,
            llm_service,
            llm_error_message,
            sql_validator,
            query_executor,
        )

        st.session_state["chat_history"].append(message)
        st.rerun()

    for message in st.session_state["chat_history"]:
        _render_chat_message(message)

    if not st.session_state["chat_history"]:
        st.info(
            "💡 Ask your first question about the uploaded dataset — "
            "e.g. *“Show the top 5 rows.”*"
        )

    has_dataset = bool(st.session_state.get("schema_text"))

    prompt = st.chat_input(
        "Ask a question about your data...",
        disabled=not has_dataset,
    )

    if prompt and prompt.strip():
        message = _process_question(
            prompt.strip(),
            prompt_builder,
            llm_service,
            llm_error_message,
            sql_validator,
            query_executor,
        )

        st.session_state["chat_history"].append(message)
        st.rerun()


# ----------------------------------------------------------------------
# STATUS
# ----------------------------------------------------------------------


def _render_status(
    llm_service: LLMService | None,
) -> None:
    """Render dataset and AI-service status pills."""
    st.markdown("### ⚡ System Status")

    left, right = st.columns(2)

    with left:
        if st.session_state.get("schema_text"):
            st.markdown(
                '<span class="status-pill green">🟢 '
                f"Dataset active — "
                f"{st.session_state['row_count']:,} rows · "
                f"{st.session_state['column_count']} columns"
                "</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="status-pill amber">🟡 No dataset uploaded</span>',
                unsafe_allow_html=True,
            )

    with right:
        if llm_service is None:
            st.markdown(
                '<span class="status-pill amber">⚠️ AI service unavailable — '
                "set GEMINI_API_KEY in .env</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="status-pill green">🤖 Gemini API connected</span>',
                unsafe_allow_html=True,
            )


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------


def main() -> None:
    """Render the professional Streamlit interface."""
    st.set_page_config(
        page_title=settings.APP_NAME,
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _init_session_state()
    _inject_css()

    # Backend services
    file_manager = FileManager()
    database = Database(settings.DATABASE_NAME)
    data_loader = DataLoader()
    schema_generator = RelationalSchemaGenerator()
    schema_manager = SchemaManager(database)
    prompt_builder = PromptBuilder()

    try:
        llm_service = LLMService()
    except LLMServiceError as exc:
        llm_service = None
        llm_error_message = str(exc)
    else:
        llm_error_message = ""

    sql_validator = SQLValidator()
    query_executor = QueryExecutor(database)

    _render_header()
    _render_sidebar()

    left_panel, right_panel = st.columns([1, 1.25], gap="large")

    # ---------------------------------------------------------------
    # LEFT PANEL: Dataset Upload
    # ---------------------------------------------------------------
    with left_panel:
        st.markdown(
            '<div class="panel-title">📊 Dataset Upload</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="panel-caption">'
            "Upload a CSV or Excel file to prepare your data for querying."
            "</div>",
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Upload Dataset",
            type=list(settings.SUPPORTED_FILES),
            accept_multiple_files=False,
            help="Supported formats: CSV and Excel (.xlsx). "
            "All worksheets are loaded.",
        )

        if uploaded_file is not None:
            _handle_upload(
                uploaded_file,
                file_manager,
                data_loader,
                schema_generator,
                schema_manager,
                database,
            )

            if st.session_state.get("schema_text"):
                _render_dataset_summary()
        else:
            if st.session_state.get("loaded_file_name"):
                _reset_upload_state()

            _render_empty_state()

    # ---------------------------------------------------------------
    # RIGHT PANEL: Chat Interface
    # ---------------------------------------------------------------
    with right_panel:
        st.markdown(
            '<div class="panel-title">💬 Chat with your data</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="panel-caption">'
            "Ask questions in plain English — SQL and raw results stay "
            "visible for learning."
            "</div>",
            unsafe_allow_html=True,
        )

        _render_chat(
            prompt_builder,
            llm_service,
            llm_error_message,
            sql_validator,
            query_executor,
        )

    st.divider()

    _render_status(llm_service)

    st.markdown(
        "<div class='footer'>"
        f"{settings.APP_NAME} · v2.0.0 · Built with Streamlit, "
        "SQLite & Gemini"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

"""Databricks Genie text-to-SQL tool.

Sends natural language questions to a pre-configured Databricks Genie
space and returns the generated SQL + natural language answer. Provides
an alternative query path alongside DuckDB for non-technical NGO planners.

Requires:
    - databricks-sdk
    - DATABRICKS_HOST, DATABRICKS_TOKEN, OASIS_GENIE_SPACE_ID env vars
"""

import logging
import time

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 2.0
_POLL_TIMEOUT_S = 45


def _ask_genie(question: str) -> dict:
    """Send a question to Databricks Genie and return the response.

    Returns:
        dict with keys: sql, description, answer, suggestions, error
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.dashboards import MessageStatus

    from oasis.databricks.config import get_config

    cfg = get_config()
    if not cfg.genie_available:
        return {
            "error": (
                "Genie not configured. Set DATABRICKS_HOST, DATABRICKS_TOKEN, "
                "and OASIS_GENIE_SPACE_ID environment variables."
            )
        }

    w = WorkspaceClient(host=cfg.host, token=cfg.token)
    space_id = cfg.genie_space_id

    # Start conversation with the question
    conv = w.genie.start_conversation(space_id=space_id, content=question)
    conv_id = conv.conversation_id
    msg_id = conv.message_id

    # Poll for completion
    elapsed = 0.0
    msg = None
    while elapsed < _POLL_TIMEOUT_S:
        msg = w.genie.get_message(
            space_id=space_id,
            conversation_id=conv_id,
            message_id=msg_id,
        )
        if msg.status == MessageStatus.COMPLETED:
            break
        time.sleep(_POLL_INTERVAL_S)
        elapsed += _POLL_INTERVAL_S
    else:
        return {"error": f"Genie timed out after {_POLL_TIMEOUT_S}s"}

    # Extract response from attachments
    result = {
        "sql": None,
        "description": None,
        "answer": None,
        "suggestions": [],
    }

    for att in msg.attachments or []:
        # SQL query attachment
        if att.query:
            result["sql"] = att.query.query
            result["description"] = att.query.description

        # Natural language answer
        if att.text and att.text.content:
            result["answer"] = att.text.content

        # Suggested follow-up questions
        if att.suggested_questions and att.suggested_questions.questions:
            result["suggestions"] = att.suggested_questions.questions

    return result


# ------------------------------------------------------------------
# MCP tool registration
# ------------------------------------------------------------------


def register_genie_tools(mcp) -> None:
    """Register the Genie text-to-SQL tool with the MCP server."""

    from oasis.databricks.tracing import traced

    @traced
    def _do_genie_query(question: str) -> dict:
        """Inner Genie call — traced by MLflow."""
        return _ask_genie(question)

    @mcp.tool()
    def ask_genie(question: str) -> str:
        """🧞 Ask a natural language question via Databricks Genie (text-to-SQL).

        Sends your question to a Databricks Genie space configured with the
        Ghana healthcare facilities data. Genie translates the question to SQL,
        executes it, and returns both the SQL and a natural language answer.

        Good for questions like:
        - "How many hospitals have cardiology?"
        - "Which region has the most clinics?"
        - "Show me facilities with more than 5 doctors"

        This provides an alternative to execute_query() for non-technical users.

        Args:
            question: Natural language question about the facility data.

        Returns:
            The SQL query Genie generated, its answer, and suggested follow-ups.
        """
        try:
            from databricks.sdk import WorkspaceClient  # noqa: F401
        except ImportError:
            return (
                "**Error:** databricks-sdk not installed. "
                "Install with: `pip install databricks-sdk`"
            )

        try:
            result = _do_genie_query(question)

            if "error" in result:
                return f"**Error:** {result['error']}"

            parts = ["**Databricks Genie Response**\n"]

            if result.get("description"):
                parts.append(f"**Interpretation:** {result['description']}\n")

            if result.get("sql"):
                parts.append("**Generated SQL:**")
                parts.append(f"```sql\n{result['sql']}\n```\n")

            if result.get("answer"):
                parts.append(f"**Answer:** {result['answer']}\n")

            if result.get("suggestions"):
                parts.append("**Suggested follow-ups:**")
                for q in result["suggestions"]:
                    parts.append(f"  - {q}")

            if not result.get("answer") and not result.get("sql"):
                parts.append("*(No answer returned — try rephrasing the question)*")

            return "\n".join(parts)

        except Exception as e:
            return f"**Error querying Genie:** {e}"

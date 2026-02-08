"""Databricks integration for OASIS.

Adds three capabilities to the MCP server:
1. MLflow tracing — citation-level transparency for every tool call
2. RAG search — semantic search over facility free-form text
3. Genie — Databricks text-to-SQL for non-technical users

All features are optional and degrade gracefully when dependencies
or credentials are missing. Existing M4 tools are unaffected.

Usage (in mcp_server.py):
    from oasis.databricks import register_databricks_tools
    register_databricks_tools(mcp)
"""

import logging

logger = logging.getLogger(__name__)


def register_databricks_tools(mcp) -> None:
    """Register all Databricks integration tools with the MCP server.

    Safe to call even when optional dependencies (mlflow, databricks-sdk,
    sentence-transformers) are not installed — each component fails
    gracefully and logs a warning.

    Args:
        mcp: The FastMCP server instance.
    """
    # 1. Configure MLflow tracing (wraps all subsequent tool registrations)
    from oasis.databricks.tracing import configure_tracing, register_tracing_tools

    configure_tracing()

    # 2. Register RAG semantic search tool
    try:
        from oasis.databricks.rag import register_rag_tools

        register_rag_tools(mcp)
        logger.info("Registered: databricks_search_facility_capabilities (RAG)")
    except Exception as e:
        logger.warning("RAG tool registration failed: %s", e)

    # 3. Register Genie text-to-SQL tool
    try:
        from oasis.databricks.genie import register_genie_tools

        register_genie_tools(mcp)
        logger.info("Registered: databricks_ask_genie (Databricks text-to-SQL)")
    except Exception as e:
        logger.warning("Genie tool registration failed: %s", e)

    # 4. Register citation trace retrieval tool
    try:
        register_tracing_tools(mcp)
        logger.info("Registered: databricks_mlflow_citation_trace (MLflow)")
    except Exception as e:
        logger.warning("Tracing tool registration failed: %s", e)

"""OASIS MCP Server - Thin MCP Protocol Adapter.

This module provides the FastMCP server that exposes OASIS tools via MCP protocol.
All business logic is delegated to tool classes in oasis.core.tools.

Architecture:
    mcp_server.py (this file) - MCP protocol adapter
        | delegates to
    core/tools/*.py - Tool implementations (return native types)
        | uses
    core/backends/*.py - Database backends

    The MCP layer uses the serialization module to convert native Python
    types to MCP-friendly strings. Exceptions are caught and formatted.

Tool Surface:
    The MCP tool surface is stable - all tools remain registered regardless of
    the active dataset. Compatibility is enforced per-call via proactive
    capability checking before tool invocation.
"""

from typing import Any

import pandas as pd
from fastmcp import FastMCP

# MCP Apps imports
from oasis.apps import init_apps
from oasis.core.datasets import DatasetRegistry
from oasis.core.exceptions import OASISError
from oasis.core.serialization import serialize_for_mcp
from oasis.core.tools import ToolRegistry, ToolSelector, init_tools
from oasis.core.tools.management import ListDatasetsInput, SetDatasetInput
from oasis.core.tools.tabular import (
    ExecuteQueryInput,
    GetDatabaseSchemaInput,
    GetTableInfoInput,
)

# Create FastMCP server instance
mcp = FastMCP("oasis")

# Initialize systems
init_tools()
init_apps()

# Tool selector for capability-based filtering
_tool_selector = ToolSelector()

# MCP-exposed tool names (for filtering in set_dataset snapshot)
_MCP_TOOL_NAMES = frozenset(
    {
        "list_datasets",
        "set_dataset",
        "get_database_schema",
        "get_table_info",
        "execute_query",
    }
)


# ===========================================
# SERIALIZATION HELPERS
# ===========================================


def _serialize_schema_result(result: dict[str, Any]) -> str:
    """Serialize get_database_schema result to MCP string."""
    backend_info = result.get("backend_info", "")
    tables = result.get("tables", [])

    if not tables:
        return f"{backend_info}\n**Available Tables:**\nNo tables found"

    table_list = "\n".join(f"  {t}" for t in tables)
    return f"{backend_info}\n**Available Tables:**\n{table_list}"


def _serialize_table_info_result(result: dict[str, Any]) -> str:
    """Serialize get_table_info result to MCP string."""
    backend_info = result.get("backend_info", "")
    table_name = result.get("table_name", "")
    schema = result.get("schema")
    sample = result.get("sample")

    parts = [
        backend_info,
        f"**Table:** {table_name}",
        "",
        "**Column Information:**",
    ]

    if schema is not None and isinstance(schema, pd.DataFrame):
        parts.append(schema.to_string(index=False))
    else:
        parts.append("(no schema information)")

    if sample is not None and isinstance(sample, pd.DataFrame) and not sample.empty:
        parts.extend(
            [
                "",
                "**Sample Data (first 3 rows):**",
                sample.to_string(index=False),
            ]
        )

    return "\n".join(parts)


def _serialize_datasets_result(result: dict[str, Any]) -> str:
    """Serialize list_datasets result to MCP string."""
    active = result.get("active_dataset") or "(unset)"
    backend = result.get("backend", "duckdb")
    datasets = result.get("datasets", {})

    if not datasets:
        return "No datasets detected."

    output = [f"Active dataset: {active}\n"]
    output.append(f"Backend: {'local (DuckDB)' if backend == 'duckdb' else backend}\n")

    for label, info in datasets.items():
        is_active = " (Active)" if info.get("is_active") else ""
        output.append(f"=== {label.upper()}{is_active} ===")

        parquet_icon = "+" if info.get("parquet_present") else "-"
        db_icon = "+" if info.get("db_present") else "-"

        output.append(f"  Local Parquet: {parquet_icon}")
        output.append(f"  Local Database: {db_icon}")
        output.append("")

    return "\n".join(output)


def _serialize_set_dataset_result(result: dict[str, Any]) -> str:
    """Serialize set_dataset result to MCP string."""
    dataset_name = result.get("dataset_name", "")
    warnings = result.get("warnings", [])

    status_msg = f"Active dataset switched to '{dataset_name}'."

    for warning in warnings:
        status_msg += f"\nWarning: {warning}"

    return status_msg


# ==========================================
# MCP TOOLS - Thin adapters to tool classes
# ==========================================


@mcp.tool()
def list_datasets() -> str:
    """List all available datasets and their status.

    Returns:
        A formatted string listing available datasets, indicating which one is active,
        and showing availability of local database.
    """
    try:
        tool = ToolRegistry.get("list_datasets")
        dataset = DatasetRegistry.get_active()
        result = tool.invoke(dataset, ListDatasetsInput())
        return _serialize_datasets_result(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def set_dataset(dataset_name: str) -> str:
    """Switch the active dataset.

    Args:
        dataset_name: The name of the dataset to switch to.

    Returns:
        Confirmation message with supported tools snapshot, or error if not found.
    """
    try:
        # Check if target dataset exists before switching
        target_dataset_def = DatasetRegistry.get(dataset_name.lower())

        tool = ToolRegistry.get("set_dataset")
        dataset = DatasetRegistry.get_active()
        result = tool.invoke(dataset, SetDatasetInput(dataset_name=dataset_name))
        output = _serialize_set_dataset_result(result)

        # Append supported tools snapshot if dataset is valid
        if target_dataset_def is not None:
            output += _tool_selector.get_supported_tools_snapshot(
                target_dataset_def, _MCP_TOOL_NAMES
            )

        return output
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def get_database_schema() -> str:
    """Discover what data is available in the database.

    **When to use:** Start here to understand what tables exist.

    Returns:
        List of all available tables in the database with current backend info.
    """
    try:
        dataset = DatasetRegistry.get_active()

        # Proactive capability check
        compat_result = _tool_selector.check_compatibility(
            "get_database_schema", dataset
        )
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("get_database_schema")
        result = tool.invoke(dataset, GetDatabaseSchemaInput())
        return _serialize_schema_result(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def get_table_info(table_name: str, show_sample: bool = True) -> str:
    """Explore a specific table's structure and see sample data.

    **When to use:** After identifying relevant tables from get_database_schema().

    Args:
        table_name: Exact table name (case-sensitive).
        show_sample: Whether to include sample rows (default: True).

    Returns:
        Table structure with column names, types, and sample data.
    """
    try:
        dataset = DatasetRegistry.get_active()

        # Proactive capability check
        compat_result = _tool_selector.check_compatibility("get_table_info", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("get_table_info")
        result = tool.invoke(
            dataset, GetTableInfoInput(table_name=table_name, show_sample=show_sample)
        )
        return _serialize_table_info_result(result)
    except OASISError as e:
        return f"**Error:** {e}"


@mcp.tool()
def execute_query(sql_query: str) -> str:
    """Execute SQL queries to analyze data.

    **Recommended workflow:**
    1. Use get_database_schema() to list tables
    2. Use get_table_info() to examine structure
    3. Write your SQL query with exact names

    Args:
        sql_query: Your SQL SELECT query (SELECT only).

    Returns:
        Query results or helpful error messages.
    """
    try:
        dataset = DatasetRegistry.get_active()

        # Proactive capability check
        compat_result = _tool_selector.check_compatibility("execute_query", dataset)
        if not compat_result.compatible:
            return compat_result.error_message

        tool = ToolRegistry.get("execute_query")
        result = tool.invoke(dataset, ExecuteQueryInput(sql_query=sql_query))
        # Result is a DataFrame - serialize it
        return serialize_for_mcp(result)
    except OASISError as e:
        return f"**Error:** {e}"


def main():
    """Main entry point for MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

"""OASIS Python API for direct access to data tools.

This module provides a clean Python API for code execution environments
like Claude Code. Functions delegate to the same tool classes used by
the MCP server, ensuring consistent behavior across interfaces.

Unlike the MCP server, this API returns native Python types:
- execute_query() returns pd.DataFrame
- get_schema() returns dict with tables list
- get_table_info() returns dict with schema DataFrame
- etc.

Example:
    from oasis import execute_query, set_dataset, get_schema
    import pandas as pd

    set_dataset("vf-ghana")
    schema = get_schema()  # Returns dict with 'tables' list
    print(schema['tables'])

    df = execute_query("SELECT COUNT(*) FROM vf.facilities")
    print(df)  # DataFrame

All queries use canonical schema.table names (e.g., vf.facilities)
that work on the DuckDB backend. Use set_dataset()
to switch between datasets.
"""

from typing import Any

import pandas as pd

from oasis.config import get_active_dataset as _get_active_dataset
from oasis.config import set_active_dataset as _set_active_dataset
from oasis.core.datasets import DatasetRegistry
from oasis.core.exceptions import DatasetError, ModalityError, OASISError, QueryError
from oasis.core.tools import ToolRegistry, ToolSelector, init_tools
from oasis.core.tools.tabular import (
    ExecuteQueryInput,
    GetDatabaseSchemaInput,
    GetTableInfoInput,
)

# Initialize tools on module import
init_tools()

# Tool selector for compatibility checking
_tool_selector = ToolSelector()

# Re-export exceptions for convenience
__all__ = [
    "DatasetError",
    "ModalityError",
    "OASISError",
    "QueryError",
    "execute_query",
    "get_active_dataset",
    "get_schema",
    "get_table_info",
    "list_datasets",
    "set_dataset",
]


# =============================================================================
# Dataset Management
# =============================================================================


def list_datasets() -> list[str]:
    """List all available datasets.

    Returns:
        List of dataset names that can be used with set_dataset().

    Example:
        >>> list_datasets()
        ['vf-ghana']
    """
    return [ds.name for ds in DatasetRegistry.list_all()]


def set_dataset(name: str) -> str:
    """Set the active dataset for subsequent queries.

    Args:
        name: Dataset name (e.g., 'vf-ghana')

    Returns:
        Confirmation message with dataset info.

    Raises:
        DatasetError: If dataset doesn't exist.

    Example:
        >>> set_dataset("vf-ghana")
        'Active dataset: vf-ghana (modalities: TABULAR)'
    """
    try:
        _set_active_dataset(name)
        dataset = DatasetRegistry.get(name)
        if not dataset:
            raise ValueError(f"Dataset '{name}' not found")
        modalities = ", ".join(m.name for m in dataset.modalities)
        return f"Active dataset: {name} (modalities: {modalities})"
    except ValueError as e:
        available = ", ".join(list_datasets())
        raise DatasetError(f"{e}. Available datasets: {available}") from e


def get_active_dataset() -> str:
    """Get the name of the currently active dataset.

    Returns:
        Name of the active dataset.

    Raises:
        DatasetError: If no dataset is active.
    """
    try:
        return _get_active_dataset()
    except ValueError as e:
        raise DatasetError(str(e)) from e


# =============================================================================
# Tabular Data Tools
# =============================================================================


def get_schema() -> dict[str, Any]:
    """Get database schema information for the active dataset.

    Returns:
        dict with:
            - backend_info: str - Backend description
            - tables: list[str] - List of table names

    Example:
        >>> set_dataset("vf-ghana")
        >>> schema = get_schema()
        >>> print(schema['tables'])
        ['vf.facilities', ...]
    """
    dataset = DatasetRegistry.get_active()
    tool = ToolRegistry.get("get_database_schema")
    return tool.invoke(dataset, GetDatabaseSchemaInput())


def get_table_info(table_name: str, show_sample: bool = True) -> dict[str, Any]:
    """Get column information and sample data for a table.

    Args:
        table_name: Name of the table to inspect.
        show_sample: If True, include sample rows (default: True).

    Returns:
        dict with:
            - backend_info: str - Backend description
            - table_name: str - Table name
            - schema: pd.DataFrame - Column information
            - sample: pd.DataFrame | None - Sample rows if requested

    Raises:
        QueryError: If table doesn't exist.

    Example:
        >>> info = get_table_info("vf.facilities")
        >>> print(info['schema'])  # DataFrame with column info
        >>> print(info['sample'])  # DataFrame with sample rows
    """
    dataset = DatasetRegistry.get_active()
    tool = ToolRegistry.get("get_table_info")
    return tool.invoke(
        dataset, GetTableInfoInput(table_name=table_name, show_sample=show_sample)
    )


def execute_query(sql: str) -> pd.DataFrame:
    """Execute a SQL SELECT query against the active dataset.

    Args:
        sql: SQL SELECT query string.

    Returns:
        pd.DataFrame with query results.

    Raises:
        SecurityError: If query violates security constraints.
        QueryError: If query execution fails.

    Example:
        >>> df = execute_query("SELECT name, specialties FROM vf.facilities LIMIT 5")
        >>> print(df)
    """
    dataset = DatasetRegistry.get_active()
    tool = ToolRegistry.get("execute_query")
    return tool.invoke(dataset, ExecuteQueryInput(sql_query=sql))

"""OASIS: Orchestrated Agentic System for Intelligent healthcare Synthesis.

OASIS provides infrastructure for AI-assisted healthcare facility analysis,
offering a safe interface for LLMs and autonomous agents to interact with
healthcare data for bridging medical deserts.

Quick Start:
    from oasis import execute_query, set_dataset, get_schema

    set_dataset("vf-ghana")
    print(get_schema())
    result = execute_query("SELECT COUNT(*) FROM vf.facilities")

For MCP server usage, run: oasis serve
"""

__version__ = "0.4.2"

# Expose API functions at package level for easy imports
from oasis.api import (
    # Exceptions
    DatasetError,
    ModalityError,
    OASISError,
    QueryError,
    # Tabular data
    execute_query,
    # Dataset management
    get_active_dataset,
    get_schema,
    get_table_info,
    list_datasets,
    set_dataset,
)

__all__ = [
    "DatasetError",
    "ModalityError",
    "OASISError",
    "QueryError",
    "__version__",
    "execute_query",
    "get_active_dataset",
    "get_schema",
    "get_table_info",
    "list_datasets",
    "set_dataset",
]

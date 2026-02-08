"""OASIS Core Backends - Database backend implementations.

This package provides the backend abstraction layer for OASIS:
- Backend protocol: Interface for all database backends
- DuckDBBackend: Local DuckDB database queries
- get_backend(): Factory function for backend selection
"""

import threading

from oasis.config import get_active_backend
from oasis.core.backends.base import (
    Backend,
    BackendError,
    ConnectionError,
    QueryExecutionError,
    QueryResult,
    TableNotFoundError,
)
from oasis.core.backends.duckdb import DuckDBBackend

# Cache for backend instances with thread safety
_backend_lock = threading.Lock()
_backend_cache: dict[str, Backend] = {}


def get_backend(backend_type: str | None = None) -> Backend:
    """Get a backend instance based on type.

    Args:
        backend_type: Type of backend ('duckdb').
                     If None, uses OASIS_BACKEND environment variable,
                     then config file, defaulting to 'duckdb'.

    Returns:
        Backend instance

    Raises:
        BackendError: If an unsupported backend type is requested
    """
    if backend_type is None:
        backend_type = get_active_backend()

    backend_type = backend_type.lower()

    with _backend_lock:
        # Check cache
        if backend_type in _backend_cache:
            return _backend_cache[backend_type]

        # Create new backend
        if backend_type == "duckdb":
            backend = DuckDBBackend()
        else:
            raise BackendError(
                f"Unsupported backend: {backend_type}. "
                "Supported backends: duckdb"
            )

        _backend_cache[backend_type] = backend
        return backend


def reset_backend_cache() -> None:
    """Clear the backend cache."""
    with _backend_lock:
        _backend_cache.clear()


__all__ = [
    "Backend",
    "BackendError",
    "ConnectionError",
    "DuckDBBackend",
    "QueryExecutionError",
    "QueryResult",
    "TableNotFoundError",
    "get_backend",
    "reset_backend_cache",
]

"""Exception hierarchy for OASIS.

This module defines all OASIS exceptions in a single location. Tools raise these
exceptions directly; the MCP server catches and formats them for users.

Exception Hierarchy:
    OASISError (base)
    |-- QueryError - SQL query failures
    |-- SecurityError - Security constraint violations
    |-- DatasetError - Dataset configuration issues
    |-- ModalityError - Tool/dataset modality mismatches
    +-- BackendError - Database backend failures
        |-- ConnectionError - Connection failures
        |-- TableNotFoundError - Missing table
        +-- QueryExecutionError - Query execution failures
"""


class OASISError(Exception):
    """Base exception for all OASIS errors.

    All OASIS-specific exceptions inherit from this class, making it easy
    to catch all OASIS errors with a single except clause.

    Example:
        try:
            result = tool.invoke(dataset, params)
        except OASISError as e:
            return f"**Error:** {e}"
    """

    pass


class QueryError(OASISError):
    """Raised when a SQL query fails.

    This covers SQL syntax errors, invalid table/column references,
    and other query execution failures.

    Attributes:
        message: Human-readable error description
        sql: The SQL query that failed (optional)
    """

    def __init__(self, message: str, sql: str | None = None):
        self.sql = sql
        super().__init__(message)


class SecurityError(OASISError):
    """Raised when a query violates security constraints.

    This is raised when a query attempts:
    - Non-SELECT statements (INSERT, UPDATE, DELETE, etc.)
    - Access to system tables
    - Other security-restricted operations

    Attributes:
        message: Human-readable error description
        query: The query that violated constraints (optional)
    """

    def __init__(self, message: str, query: str | None = None):
        self.query = query
        super().__init__(message)


class DatasetError(OASISError):
    """Raised when dataset configuration is invalid.

    This covers:
    - Unknown dataset names
    - Missing dataset configuration
    - Dataset initialization failures

    Attributes:
        message: Human-readable error description
        dataset_name: The dataset that caused the error (optional)
    """

    def __init__(self, message: str, dataset_name: str | None = None):
        self.dataset_name = dataset_name
        super().__init__(message)


class ModalityError(OASISError):
    """Raised when a tool is incompatible with the dataset.

    This is raised when attempting to use a tool that requires
    modalities the current dataset doesn't support.

    Attributes:
        message: Human-readable error description
        tool_name: The tool that was invoked
        required_modalities: Modalities the tool requires
        available_modalities: Modalities the dataset provides
    """

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        required_modalities: set[str] | None = None,
        available_modalities: set[str] | None = None,
    ):
        self.tool_name = tool_name
        self.required_modalities = required_modalities or set()
        self.available_modalities = available_modalities or set()
        super().__init__(message)


class BackendError(OASISError):
    """Base exception for backend errors.

    Attributes:
        message: Human-readable error description
        backend: Name of the backend that raised the error
        recoverable: Whether the error might be resolved by retrying
    """

    def __init__(
        self, message: str, backend: str = "unknown", recoverable: bool = False
    ):
        self.message = message
        self.backend = backend
        self.recoverable = recoverable
        super().__init__(message)


class ConnectionError(BackendError):
    """Raised when the backend cannot connect to the database."""

    def __init__(self, message: str, backend: str = "unknown"):
        super().__init__(message, backend, recoverable=True)


class TableNotFoundError(BackendError):
    """Raised when a requested table does not exist."""

    def __init__(self, table_name: str, backend: str = "unknown"):
        message = f"Table '{table_name}' not found"
        super().__init__(message, backend, recoverable=False)
        self.table_name = table_name


class QueryExecutionError(BackendError):
    """Raised when a query fails to execute."""

    def __init__(self, message: str, sql: str, backend: str = "unknown"):
        super().__init__(message, backend, recoverable=False)
        self.sql = sql

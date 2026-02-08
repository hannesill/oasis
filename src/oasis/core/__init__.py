"""OASIS Core - MCP-agnostic data platform core.

This package contains the core abstractions for OASIS, including:
- Dataset definitions with modality-based filtering
- Tool protocol and registry
- Backend abstractions
- SQL validation utilities

The core is intentionally MCP-agnostic to enable testing and reuse.
"""

from oasis.core.datasets import (
    DatasetDefinition,
    DatasetRegistry,
    Modality,
)
from oasis.core.validation import (
    format_error_with_guidance,
    is_safe_query,
)

__all__ = [
    "DatasetDefinition",
    "DatasetRegistry",
    "Modality",
    "format_error_with_guidance",
    "is_safe_query",
]

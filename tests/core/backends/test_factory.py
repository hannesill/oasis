"""Tests for oasis.core.backends factory functions.

Tests cover:
- get_backend() factory function
- Backend caching
- Environment variable handling
"""

import os
from unittest.mock import patch

import pytest

from oasis.core.backends import (
    BackendError,
    DuckDBBackend,
    get_backend,
    reset_backend_cache,
)


class TestGetBackend:
    """Test get_backend factory function."""

    def setup_method(self):
        """Reset backend cache before each test."""
        reset_backend_cache()

    def test_get_duckdb_backend_explicit(self):
        """Test getting DuckDB backend explicitly."""
        backend = get_backend("duckdb")

        assert isinstance(backend, DuckDBBackend)
        assert backend.name == "duckdb"

    def test_get_backend_case_insensitive(self):
        """Test that backend type is case-insensitive."""
        backend_lower = get_backend("duckdb")
        reset_backend_cache()
        backend_upper = get_backend("DUCKDB")
        reset_backend_cache()
        backend_mixed = get_backend("DuckDB")

        assert isinstance(backend_lower, DuckDBBackend)
        assert isinstance(backend_upper, DuckDBBackend)
        assert isinstance(backend_mixed, DuckDBBackend)

    def test_get_backend_default_is_duckdb(self):
        """Test that default backend is DuckDB when no env var or config set."""
        env_backup = os.environ.pop("OASIS_BACKEND", None)
        try:
            # Mock config to return no backend (simulating fresh install)
            with patch("oasis.config.load_runtime_config", return_value={}):
                reset_backend_cache()
                backend = get_backend()

                assert isinstance(backend, DuckDBBackend)
        finally:
            if env_backup:
                os.environ["OASIS_BACKEND"] = env_backup

    def test_get_backend_from_env_var(self):
        """Test getting backend type from environment variable."""
        with patch.dict(os.environ, {"OASIS_BACKEND": "duckdb"}):
            reset_backend_cache()
            backend = get_backend()

            assert isinstance(backend, DuckDBBackend)

    def test_invalid_backend_raises_error(self):
        """Test that invalid backend type raises BackendError."""
        with pytest.raises(BackendError) as exc_info:
            get_backend("invalid_backend")

        assert "Unsupported backend" in str(exc_info.value)
        assert "duckdb" in str(exc_info.value).lower()


class TestBackendCaching:
    """Test backend caching behavior."""

    def setup_method(self):
        """Reset backend cache before each test."""
        reset_backend_cache()

    def test_backend_is_cached(self):
        """Test that backends are cached and reused."""
        backend1 = get_backend("duckdb")
        backend2 = get_backend("duckdb")

        assert backend1 is backend2  # Same instance

    def test_reset_cache_clears_backends(self):
        """Test that reset_backend_cache clears the cache."""
        backend1 = get_backend("duckdb")
        reset_backend_cache()
        backend2 = get_backend("duckdb")

        assert backend1 is not backend2  # Different instances

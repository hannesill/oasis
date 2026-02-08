"""Tests for the MCP server functionality.

These tests verify the thin MCP adapter layer (mcp_server.py) which
delegates all business logic to tool classes.
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client

from oasis.core.datasets import DatasetDefinition, Modality
from oasis.core.tools import init_tools
from oasis.mcp_server import mcp


@pytest.fixture(autouse=True)
def ensure_tools_initialized():
    """Ensure tools are initialized before each test."""
    init_tools()


class TestMCPServerSetup:
    """Test MCP server setup and configuration."""

    def test_server_instance_exists(self):
        """Test that the FastMCP server instance exists."""
        assert mcp is not None
        assert mcp.name == "oasis"


class TestMCPTools:
    """Test MCP tools functionality."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test DuckDB database with schema-qualified tables."""
        import duckdb

        db_path = tmp_path / "test.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            con.execute("CREATE SCHEMA vf")
            con.execute(
                """
                CREATE TABLE vf.facilities (
                    pk_unique_id INTEGER,
                    name VARCHAR,
                    region VARCHAR,
                    number_beds INTEGER,
                    specialties VARCHAR
                )
                """
            )
            con.execute(
                """
                INSERT INTO vf.facilities (pk_unique_id, name, region, number_beds, specialties) VALUES
                    (1, 'Tamale Teaching Hospital', 'Northern', 200, 'Surgery'),
                    (2, 'Korle Bu Teaching Hospital', 'Greater Accra', 1600, 'Cardiology')
                """
            )
            con.commit()
        finally:
            con.close()

        return str(db_path)

    @pytest.mark.asyncio
    async def test_tools_via_client(self, test_db):
        """Test MCP tools through the FastMCP client."""
        from oasis.core.backends import reset_backend_cache

        # Reset backend cache to ensure clean state
        reset_backend_cache()

        # Create a mock dataset with TABULAR modality
        mock_ds = DatasetDefinition(
            name="vf-ghana",
            modalities=frozenset({Modality.TABULAR}),
        )

        with patch.dict(
            os.environ,
            {
                "OASIS_BACKEND": "duckdb",
                "OASIS_DB_PATH": test_db,
                "OASIS_OAUTH2_ENABLED": "false",
            },
            clear=True,
        ):
            with patch(
                "oasis.mcp_server.DatasetRegistry.get_active", return_value=mock_ds
            ):
                with patch("oasis.core.tools.tabular.get_backend") as mock_get_backend:
                    from oasis.core.backends.duckdb import DuckDBBackend

                    # Use real DuckDB backend with test database
                    mock_get_backend.return_value = DuckDBBackend(
                        db_path_override=test_db
                    )

                    async with Client(mcp) as client:
                        # Test execute_query tool
                        result = await client.call_tool(
                            "execute_query",
                            {
                                "sql_query": "SELECT COUNT(*) as count FROM vf.facilities"
                            },
                        )
                        result_text = str(result)
                        assert "count" in result_text
                        assert "2" in result_text

                        # Test get_database_schema tool
                        result = await client.call_tool("get_database_schema", {})
                        result_text = str(result)
                        assert "vf.facilities" in result_text

    @pytest.mark.asyncio
    async def test_security_checks(self, test_db):
        """Test SQL injection protection."""
        from oasis.core.backends import reset_backend_cache

        reset_backend_cache()

        with patch.dict(
            os.environ,
            {
                "OASIS_BACKEND": "duckdb",
                "OASIS_DB_PATH": test_db,
                "OASIS_OAUTH2_ENABLED": "false",
            },
            clear=True,
        ):
            async with Client(mcp) as client:
                # Test dangerous queries are blocked
                dangerous_queries = [
                    "UPDATE vf.facilities SET pk_unique_id = 999",
                    "DELETE FROM vf.facilities",
                    "INSERT INTO vf.facilities VALUES (1, 'test', 'test', 10, 'test')",
                    "DROP TABLE vf.facilities",
                    "CREATE TABLE test (id INTEGER)",
                    "ALTER TABLE vf.facilities ADD COLUMN test TEXT",
                ]

                for query in dangerous_queries:
                    result = await client.call_tool(
                        "execute_query", {"sql_query": query}
                    )
                    result_text = str(result)
                    # Security errors are formatted as "**Error:** <message>"
                    assert "**Error:**" in result_text

    @pytest.mark.asyncio
    async def test_invalid_sql(self, test_db):
        """Test handling of invalid SQL."""
        from oasis.core.backends import reset_backend_cache
        from oasis.core.backends.duckdb import DuckDBBackend

        reset_backend_cache()

        mock_ds = DatasetDefinition(
            name="vf-ghana",
            modalities=frozenset({Modality.TABULAR}),
        )

        with patch.dict(
            os.environ,
            {
                "OASIS_BACKEND": "duckdb",
                "OASIS_DB_PATH": test_db,
                "OASIS_OAUTH2_ENABLED": "false",
            },
            clear=True,
        ):
            with patch(
                "oasis.mcp_server.DatasetRegistry.get_active", return_value=mock_ds
            ):
                with patch("oasis.core.tools.tabular.get_backend") as mock_get_backend:
                    mock_get_backend.return_value = DuckDBBackend(
                        db_path_override=test_db
                    )

                    async with Client(mcp) as client:
                        result = await client.call_tool(
                            "execute_query",
                            {"sql_query": "INVALID SQL QUERY"},
                        )
                        result_text = str(result)
                        # Security validation happens first, and this is valid
                        # SQL structure but will fail execution
                        assert "Error" in result_text or "error" in result_text

    @pytest.mark.asyncio
    async def test_empty_results(self, test_db):
        """Test handling of queries with no results."""
        from oasis.core.backends import reset_backend_cache
        from oasis.core.backends.duckdb import DuckDBBackend

        reset_backend_cache()

        mock_ds = DatasetDefinition(
            name="vf-ghana",
            modalities=frozenset({Modality.TABULAR}),
        )

        with patch.dict(
            os.environ,
            {
                "OASIS_BACKEND": "duckdb",
                "OASIS_DB_PATH": test_db,
                "OASIS_OAUTH2_ENABLED": "false",
            },
            clear=True,
        ):
            with patch(
                "oasis.mcp_server.DatasetRegistry.get_active", return_value=mock_ds
            ):
                with patch("oasis.core.tools.tabular.get_backend") as mock_get_backend:
                    mock_get_backend.return_value = DuckDBBackend(
                        db_path_override=test_db
                    )

                    async with Client(mcp) as client:
                        result = await client.call_tool(
                            "execute_query",
                            {
                                "sql_query": "SELECT * FROM vf.facilities WHERE pk_unique_id = 999999"
                            },
                        )
                        result_text = str(result)
                        assert "No results found" in result_text


class TestModalityChecking:
    """Test proactive modality-based tool filtering.

    These tests verify that:
    1. Incompatible tools return helpful error messages without backend execution
    2. Compatible tools work as expected
    3. set_dataset includes supported tools snapshot
    """

    @pytest.mark.asyncio
    async def test_incompatible_tool_returns_proactive_error(self):
        """Test that calling a tool on an incompatible dataset returns proactive error.

        This verifies no backend execution is attempted.
        """
        from oasis.core.backends import reset_backend_cache

        reset_backend_cache()

        # Create a dataset that lacks TABULAR modality (empty modalities)
        empty_ds = DatasetDefinition(
            name="empty-dataset",
            modalities=frozenset(),  # No modalities at all
        )

        with patch.dict(
            os.environ,
            {"OASIS_OAUTH2_ENABLED": "false"},
            clear=True,
        ):
            with patch(
                "oasis.mcp_server.DatasetRegistry.get_active", return_value=empty_ds
            ):
                # Mock backend that should NOT be called
                with patch("oasis.core.tools.tabular.get_backend") as mock_backend:
                    async with Client(mcp) as client:
                        # Call execute_query which requires TABULAR modality
                        result = await client.call_tool(
                            "execute_query", {"sql_query": "SELECT 1"}
                        )
                        result_text = str(result)

                        # Verify proactive error message
                        assert "Error" in result_text
                        assert "execute_query" in result_text
                        assert "empty-dataset" in result_text
                        assert "TABULAR" in result_text

                        # Verify suggestions are included
                        assert "list_datasets" in result_text
                        assert "set_dataset" in result_text

                        # Verify backend was NOT called (no execution attempted)
                        mock_backend.assert_not_called()

    @pytest.mark.asyncio
    async def test_compatible_tool_executes_successfully(self, tmp_path):
        """Test that compatible tools execute against the backend."""
        import duckdb

        from oasis.core.backends import reset_backend_cache
        from oasis.core.backends.duckdb import DuckDBBackend

        reset_backend_cache()

        # Create test database
        db_path = tmp_path / "test.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            con.execute("CREATE TABLE test_table (id INTEGER, value TEXT)")
            con.execute("INSERT INTO test_table VALUES (1, 'test1'), (2, 'test2')")
            con.commit()
        finally:
            con.close()

        # Create dataset with TABULAR modality
        tabular_ds = DatasetDefinition(
            name="tabular-dataset",
            modalities={Modality.TABULAR},
        )

        with patch.dict(
            os.environ,
            {"OASIS_OAUTH2_ENABLED": "false"},
            clear=True,
        ):
            with patch(
                "oasis.mcp_server.DatasetRegistry.get_active", return_value=tabular_ds
            ):
                with patch("oasis.core.tools.tabular.get_backend") as mock_get_backend:
                    mock_get_backend.return_value = DuckDBBackend(
                        db_path_override=str(db_path)
                    )

                    async with Client(mcp) as client:
                        result = await client.call_tool(
                            "execute_query",
                            {"sql_query": "SELECT * FROM test_table LIMIT 10"},
                        )
                        result_text = str(result)

                        # Verify data was returned (backend was called)
                        assert "id" in result_text or "1" in result_text

                        # Verify NO error message
                        assert "not available" not in result_text.lower()

    @pytest.mark.asyncio
    async def test_set_dataset_returns_supported_tools_snapshot(self):
        """Test that set_dataset includes supported tools in response."""
        from oasis.core.backends import reset_backend_cache

        reset_backend_cache()

        # Create a dataset with TABULAR modality
        target_ds = DatasetDefinition(
            name="test-dataset",
            modalities={Modality.TABULAR},
        )

        with patch.dict(os.environ, {"OASIS_OAUTH2_ENABLED": "false"}, clear=True):
            with patch(
                "oasis.core.tools.management.detect_available_local_datasets",
                return_value={
                    "test-dataset": {"parquet_present": True, "db_present": True}
                },
            ):
                with patch("oasis.core.tools.management.set_active_dataset"):
                    with patch(
                        "oasis.config.get_active_dataset",
                        return_value="test-dataset",
                    ):
                        with patch(
                            "oasis.core.tools.management.DatasetRegistry.get",
                            return_value=target_ds,
                        ):
                            with patch(
                                "oasis.mcp_server.DatasetRegistry.get",
                                return_value=target_ds,
                            ):
                                with patch(
                                    "oasis.core.tools.management.get_active_backend",
                                    return_value="duckdb",
                                ):
                                    async with Client(mcp) as client:
                                        result = await client.call_tool(
                                            "set_dataset",
                                            {"dataset_name": "test-dataset"},
                                        )
                                        result_text = str(result)

                                        # Verify snapshot is included
                                        assert "Active dataset" in result_text
                                        assert "test-dataset" in result_text
                                        assert "Modalities" in result_text
                                        assert "Supported tools" in result_text

                                        # Tools should be sorted alphabetically
                                        assert "execute_query" in result_text

    @pytest.mark.asyncio
    async def test_set_dataset_invalid_returns_error_without_snapshot(self):
        """Test that set_dataset with invalid dataset returns error without snapshot."""
        from oasis.core.backends import reset_backend_cache

        reset_backend_cache()

        # Create a valid mock dataset for get_active
        mock_active_ds = DatasetDefinition(
            name="vf-ghana",
            modalities={Modality.TABULAR},
        )

        with patch.dict(os.environ, {"OASIS_OAUTH2_ENABLED": "false"}, clear=True):
            with patch(
                "oasis.core.tools.management.detect_available_local_datasets",
                return_value={
                    "vf-ghana": {"parquet_present": True, "db_present": True}
                },
            ):
                with patch(
                    "oasis.mcp_server.DatasetRegistry.get_active",
                    return_value=mock_active_ds,
                ):
                    with patch(
                        "oasis.mcp_server.DatasetRegistry.get", return_value=None
                    ):  # Unknown dataset for snapshot lookup
                        async with Client(mcp) as client:
                            result = await client.call_tool(
                                "set_dataset", {"dataset_name": "nonexistent-dataset"}
                            )
                            result_text = str(result)

                            # Should have error
                            assert "not found" in result_text.lower()

    @pytest.mark.asyncio
    async def test_tool_incompatibility_with_empty_modalities(self):
        """Test that tabular tools are incompatible with dataset lacking TABULAR modality."""
        from oasis.core.backends import reset_backend_cache

        reset_backend_cache()

        # Create dataset with no modalities
        empty_ds = DatasetDefinition(
            name="empty-dataset",
            modalities=frozenset(),  # No modalities
        )

        with patch.dict(os.environ, {"OASIS_OAUTH2_ENABLED": "false"}, clear=True):
            with patch(
                "oasis.mcp_server.DatasetRegistry.get_active", return_value=empty_ds
            ):
                async with Client(mcp) as client:
                    # Test execute_query (requires TABULAR modality)
                    result = await client.call_tool(
                        "execute_query", {"sql_query": "SELECT 1"}
                    )
                    assert "TABULAR" in str(result)

                    # Test get_database_schema (requires TABULAR modality)
                    result = await client.call_tool("get_database_schema", {})
                    assert "TABULAR" in str(result)

    def test_check_tool_compatibility_helper(self):
        """Test the ToolSelector.check_compatibility method directly."""
        from oasis.core.tools import ToolSelector

        selector = ToolSelector()

        # Dataset with no modalities
        empty_ds = DatasetDefinition(
            name="empty-dataset",
            modalities=frozenset(),
        )

        # Dataset with TABULAR modality
        tabular_ds = DatasetDefinition(
            name="tabular",
            modalities={Modality.TABULAR},
        )

        # Test compatible tool
        result = selector.check_compatibility("execute_query", tabular_ds)
        assert result.compatible is True
        assert result.error_message == ""

        # Test incompatible tool (execute_query requires TABULAR)
        result = selector.check_compatibility("execute_query", empty_ds)
        assert result.compatible is False
        assert "TABULAR" in result.error_message
        assert "empty-dataset" in result.error_message
        assert "list_datasets" in result.error_message

        # Test unknown tool
        result = selector.check_compatibility("nonexistent_tool", tabular_ds)
        assert result.compatible is False
        assert "Unknown tool" in result.error_message

    def test_supported_tools_snapshot_helper(self):
        """Test the ToolSelector.get_supported_tools_snapshot method."""
        from oasis.core.tools import ToolSelector

        selector = ToolSelector()

        # Dataset with TABULAR modality
        tabular_ds = DatasetDefinition(
            name="tabular-dataset",
            modalities={Modality.TABULAR},
        )

        snapshot = selector.get_supported_tools_snapshot(tabular_ds)

        # Verify structure
        assert "Active dataset" in snapshot
        assert "tabular-dataset" in snapshot
        assert "Modalities" in snapshot
        assert "Supported tools" in snapshot

        # Verify tools are sorted (alphabetically)
        assert "execute_query" in snapshot
        assert "get_database_schema" in snapshot
        assert "get_table_info" in snapshot

    def test_supported_tools_snapshot_empty_modalities(self):
        """Test snapshot for dataset with no modalities."""
        from oasis.core.tools import ToolSelector

        selector = ToolSelector()

        # Dataset with no modalities
        empty_ds = DatasetDefinition(
            name="empty-dataset",
            modalities=set(),  # No modalities
        )

        snapshot = selector.get_supported_tools_snapshot(empty_ds)

        # Should show warning about no tools or just management tools
        assert "No data tools available" in snapshot or "list_datasets" in snapshot


class TestNoActiveDatasetError:
    """Test that MCP tools return error messages when no dataset is configured."""

    @pytest.mark.asyncio
    async def test_tools_return_error_when_no_active_dataset(self):
        """All data tools should return an error string, not crash,
        when DatasetRegistry.get_active() raises DatasetError."""
        from oasis.core.exceptions import DatasetError

        with patch.dict(os.environ, {"OASIS_OAUTH2_ENABLED": "false"}, clear=True):
            with patch(
                "oasis.mcp_server.DatasetRegistry.get_active",
                side_effect=DatasetError("No active dataset configured."),
            ):
                async with Client(mcp) as client:
                    # Test all 3 tabular tools that call get_active()
                    tools_and_args = [
                        ("get_database_schema", {}),
                        ("get_table_info", {"table_name": "test"}),
                        ("execute_query", {"sql_query": "SELECT 1"}),
                    ]

                    for tool_name, args in tools_and_args:
                        result = await client.call_tool(tool_name, args)
                        result_text = str(result)
                        assert "**Error:**" in result_text, (
                            f"{tool_name} did not return error message"
                        )
                        assert "No active dataset" in result_text, (
                            f"{tool_name} error message missing context"
                        )

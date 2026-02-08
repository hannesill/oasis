"""End-to-end integration tests.

These tests exercise the full stack (Tool class -> Backend -> DuckDB -> Result)
with minimal mocking. They catch issues where individual layers work but the
combination fails.
"""

from unittest.mock import patch

import duckdb
import pandas as pd
import pytest

from oasis.core.backends.duckdb import DuckDBBackend
from oasis.core.datasets import DatasetDefinition, Modality
from oasis.core.exceptions import QueryError, SecurityError
from oasis.core.tools.tabular import (
    ExecuteQueryInput,
    ExecuteQueryTool,
    GetDatabaseSchemaInput,
    GetDatabaseSchemaTool,
    GetTableInfoInput,
    GetTableInfoTool,
)


@pytest.fixture
def integration_env(tmp_path):
    """Full stack test environment with real DuckDB.

    Creates a temp DuckDB database with schema-qualified tables
    matching the VF Ghana structure.
    """
    db_path = tmp_path / "integration_test.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        # Create vf schema with facilities table
        con.execute("CREATE SCHEMA vf")
        con.execute("""
            CREATE TABLE vf.facilities (
                pk_unique_id INTEGER PRIMARY KEY,
                name VARCHAR,
                region VARCHAR,
                number_beds INTEGER,
                specialties VARCHAR
            )
        """)
        con.execute("""
            INSERT INTO vf.facilities VALUES
                (1, 'Tamale Teaching Hospital', 'Northern', 200, 'Surgery'),
                (2, 'Korle Bu Teaching Hospital', 'Greater Accra', 1600, 'Cardiology'),
                (3, 'Ridge Hospital', 'Greater Accra', 420, 'General Medicine')
        """)
        con.commit()
    finally:
        con.close()

    dataset = DatasetDefinition(
        name="integration-test",
        modalities=frozenset({Modality.TABULAR}),
        schema_mapping={"": "vf"},
    )

    backend = DuckDBBackend(db_path_override=str(db_path))

    return dataset, backend, str(db_path)


class TestEndToEnd:
    """End-to-end integration tests exercising Tool -> Backend -> DuckDB."""

    def test_execute_query_full_stack(self, integration_env):
        """ExecuteQueryTool returns correct DataFrame through the full stack."""
        dataset, backend, db_path = integration_env

        tool = ExecuteQueryTool()
        with patch("oasis.core.tools.tabular.get_backend", return_value=backend):
            result = tool.invoke(
                dataset,
                ExecuteQueryInput(
                    sql_query="SELECT COUNT(*) as cnt FROM vf.facilities"
                ),
            )

        assert isinstance(result, pd.DataFrame)
        assert "cnt" in result.columns
        assert result["cnt"].iloc[0] == 3

    def test_get_database_schema_full_stack(self, integration_env):
        """GetDatabaseSchemaTool lists schema-qualified tables."""
        dataset, backend, db_path = integration_env

        tool = GetDatabaseSchemaTool()
        with patch("oasis.core.tools.tabular.get_backend", return_value=backend):
            result = tool.invoke(dataset, GetDatabaseSchemaInput())

        assert isinstance(result, dict)
        assert "tables" in result
        tables = result["tables"]
        assert "vf.facilities" in tables

    def test_get_table_info_full_stack(self, integration_env):
        """GetTableInfoTool returns schema and sample data for a real table."""
        dataset, backend, db_path = integration_env

        tool = GetTableInfoTool()
        with patch("oasis.core.tools.tabular.get_backend", return_value=backend):
            result = tool.invoke(
                dataset,
                GetTableInfoInput(table_name="vf.facilities"),
            )

        assert isinstance(result, dict)

        # Schema should be a DataFrame with column metadata
        schema = result["schema"]
        assert isinstance(schema, pd.DataFrame)
        column_names = schema["name"].tolist()
        assert "pk_unique_id" in column_names
        assert "name" in column_names

        # Sample should be a DataFrame with actual facility data
        sample = result["sample"]
        assert isinstance(sample, pd.DataFrame)
        assert len(sample) > 0

    def test_execute_query_error_full_stack(self, integration_env):
        """ExecuteQueryTool raises QueryError for a nonexistent table."""
        dataset, backend, db_path = integration_env

        tool = ExecuteQueryTool()
        with patch("oasis.core.tools.tabular.get_backend", return_value=backend):
            with pytest.raises(QueryError) as exc_info:
                tool.invoke(
                    dataset,
                    ExecuteQueryInput(sql_query="SELECT * FROM nonexistent_table"),
                )

        # The sanitized error message should contain user-friendly guidance
        error_msg = str(exc_info.value)
        assert "table" in error_msg.lower() or "not found" in error_msg.lower()

    def test_invalid_sql_full_stack(self, integration_env):
        """ExecuteQueryTool raises SecurityError for dangerous SQL."""
        dataset, backend, db_path = integration_env

        tool = ExecuteQueryTool()
        with patch("oasis.core.tools.tabular.get_backend", return_value=backend):
            with pytest.raises(SecurityError):
                tool.invoke(
                    dataset,
                    ExecuteQueryInput(sql_query="DROP TABLE facilities"),
                )

    def test_execute_query_with_aggregation(self, integration_env):
        """ExecuteQueryTool handles GROUP BY aggregation queries."""
        dataset, backend, db_path = integration_env

        tool = ExecuteQueryTool()
        sql = (
            "SELECT region, COUNT(*) as cnt FROM vf.facilities GROUP BY region"
        )
        with patch("oasis.core.tools.tabular.get_backend", return_value=backend):
            result = tool.invoke(dataset, ExecuteQueryInput(sql_query=sql))

        assert isinstance(result, pd.DataFrame)
        assert "region" in result.columns
        assert "cnt" in result.columns
        # 1 in Northern, 2 in Greater Accra
        region_counts = dict(zip(result["region"], result["cnt"]))
        assert region_counts["Northern"] == 1
        assert region_counts["Greater Accra"] == 2

    def test_execute_query_empty_result(self, integration_env):
        """ExecuteQueryTool returns empty DataFrame for no-match queries."""
        dataset, backend, db_path = integration_env

        tool = ExecuteQueryTool()
        sql = "SELECT * FROM vf.facilities WHERE pk_unique_id = -1"
        with patch("oasis.core.tools.tabular.get_backend", return_value=backend):
            result = tool.invoke(dataset, ExecuteQueryInput(sql_query=sql))

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

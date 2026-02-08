"""Tests for MCP server serialization helpers.

These functions transform tool return values (dicts with DataFrames)
into user-facing MCP strings. A bug here silently corrupts all output
that LLMs see, making these tests critical for reliability.

Tests cover:
- _serialize_schema_result: Table listing output
- _serialize_table_info_result: Column info + sample data
- _serialize_datasets_result: Dataset status display
- _serialize_set_dataset_result: Switch confirmation with warnings
"""

import pandas as pd

from oasis.mcp_server import (
    _serialize_datasets_result,
    _serialize_schema_result,
    _serialize_set_dataset_result,
    _serialize_table_info_result,
)


class TestSerializeSchemaResult:
    """Test _serialize_schema_result output formatting."""

    def test_schema_with_tables(self):
        """Schema result with tables lists them line by line."""
        result = _serialize_schema_result(
            {
                "backend_info": "Backend: DuckDB (local)",
                "tables": ["vf.facilities"],
            }
        )
        assert "DuckDB" in result
        assert "vf.facilities" in result
        assert "Available Tables" in result

    def test_schema_no_tables(self):
        """Schema result with no tables shows 'No tables found'."""
        result = _serialize_schema_result(
            {"backend_info": "Backend: DuckDB", "tables": []}
        )
        assert "No tables found" in result

    def test_schema_empty_result(self):
        """Schema result with missing keys uses defaults."""
        result = _serialize_schema_result({})
        assert "No tables found" in result


class TestSerializeTableInfoResult:
    """Test _serialize_table_info_result output formatting."""

    def test_table_info_with_schema_and_sample(self):
        """Table info with both schema and sample data."""
        schema_df = pd.DataFrame(
            {"name": ["pk_unique_id", "name"], "type": ["INTEGER", "VARCHAR"]}
        )
        sample_df = pd.DataFrame(
            {"pk_unique_id": [1, 2], "name": ["Facility A", "Facility B"]}
        )

        result = _serialize_table_info_result(
            {
                "backend_info": "Backend: DuckDB",
                "table_name": "vf.facilities",
                "schema": schema_df,
                "sample": sample_df,
            }
        )
        assert "vf.facilities" in result
        assert "Column Information" in result
        assert "pk_unique_id" in result
        assert "Sample Data" in result
        assert "Facility A" in result

    def test_table_info_no_sample(self):
        """Table info without sample data omits sample section."""
        schema_df = pd.DataFrame({"name": ["id"], "type": ["INT"]})
        result = _serialize_table_info_result(
            {
                "backend_info": "Backend: DuckDB",
                "table_name": "test",
                "schema": schema_df,
                "sample": None,
            }
        )
        assert "Sample Data" not in result
        assert "Column Information" in result

    def test_table_info_no_schema(self):
        """Table info without schema shows placeholder."""
        result = _serialize_table_info_result(
            {
                "backend_info": "Backend: DuckDB",
                "table_name": "test",
                "schema": None,
                "sample": None,
            }
        )
        assert "no schema information" in result


class TestSerializeDatasetsResult:
    """Test _serialize_datasets_result output formatting."""

    def test_no_datasets(self):
        """No datasets returns simple message."""
        result = _serialize_datasets_result({"active_dataset": None, "datasets": {}})
        assert "No datasets detected" in result

    def test_single_active_dataset(self):
        """Single active dataset shows status correctly."""
        result = _serialize_datasets_result(
            {
                "active_dataset": "vf-ghana",
                "backend": "duckdb",
                "datasets": {
                    "vf-ghana": {
                        "is_active": True,
                        "parquet_present": True,
                        "db_present": True,
                    }
                },
            }
        )
        assert "Active dataset: vf-ghana" in result
        assert "(Active)" in result
        assert "DuckDB" in result


class TestSerializeSetDatasetResult:
    """Test _serialize_set_dataset_result output formatting."""

    def test_successful_switch(self):
        """Successful switch shows confirmation."""
        result = _serialize_set_dataset_result(
            {"dataset_name": "vf-ghana", "warnings": []}
        )
        assert "vf-ghana" in result
        assert "switched" in result.lower()

    def test_switch_with_warnings(self):
        """Switch with warnings appends warning messages."""
        result = _serialize_set_dataset_result(
            {
                "dataset_name": "vf-ghana",
                "warnings": ["Local database not found."],
            }
        )
        assert "vf-ghana" in result
        assert "Local database not found" in result

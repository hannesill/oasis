"""Tests for OASIS Python API.

Tests cover the public API functions exposed at the package level
for use in code execution environments like Claude Code.

The API now returns native Python types (dict, DataFrame) instead
of formatted strings. Tools raise exceptions for errors.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from oasis.api import (
    DatasetError,
    OASISError,
    QueryError,
    execute_query,
    get_active_dataset,
    get_schema,
    get_table_info,
    list_datasets,
    set_dataset,
)
from oasis.core.datasets import DatasetDefinition, DatasetRegistry, Modality
from oasis.core.exceptions import SecurityError
from oasis.core.tools import init_tools

# Patch at the point of use in tool modules, not where defined
TABULAR_BACKEND_PATCH = "oasis.core.tools.tabular.get_backend"


@pytest.fixture(autouse=True)
def ensure_tools_initialized():
    """Ensure tools are initialized before each test."""
    init_tools()
    yield


@pytest.fixture
def mock_tabular_dataset():
    """Create a mock dataset with TABULAR modality."""
    dataset = DatasetDefinition(
        name="test-tabular",
        modalities=frozenset({Modality.TABULAR}),
    )
    DatasetRegistry.register(dataset)
    yield dataset
    DatasetRegistry._registry.pop("test-tabular", None)


class TestDatasetManagement:
    """Test dataset management API functions."""

    def test_list_datasets_returns_list(self):
        """Test list_datasets returns a list of strings."""
        datasets = list_datasets()
        assert isinstance(datasets, list)
        # Should have at least the built-in datasets
        assert len(datasets) > 0
        assert all(isinstance(d, str) for d in datasets)

    @patch("oasis.api._set_active_dataset")
    def test_set_dataset_success(self, mock_set, mock_tabular_dataset):
        """Test setting a valid dataset."""
        result = set_dataset("test-tabular")
        assert "test-tabular" in result
        mock_set.assert_called_once_with("test-tabular")

    @patch("oasis.api._set_active_dataset")
    def test_set_dataset_invalid_raises_error(self, mock_set):
        """Test setting invalid dataset raises DatasetError."""
        mock_set.side_effect = ValueError("Dataset not found")
        with pytest.raises(DatasetError) as exc_info:
            set_dataset("nonexistent-dataset")
        assert "Available datasets" in str(exc_info.value)

    @patch("oasis.api._get_active_dataset")
    def test_get_active_dataset(self, mock_get):
        """Test getting the active dataset name."""
        mock_get.return_value = "vf-ghana"
        assert get_active_dataset() == "vf-ghana"

    @patch("oasis.api._get_active_dataset")
    def test_get_active_dataset_none_raises_error(self, mock_get):
        """Test getting active dataset when none is set."""
        mock_get.side_effect = DatasetError("No active dataset")
        with pytest.raises(DatasetError):
            get_active_dataset()


class TestTabularDataAPI:
    """Test tabular data API functions."""

    @patch(TABULAR_BACKEND_PATCH)
    @patch("oasis.api.DatasetRegistry.get_active")
    def test_get_schema(self, mock_get_active, mock_get_backend, mock_tabular_dataset):
        """Test get_schema returns dict with tables."""
        mock_get_active.return_value = mock_tabular_dataset
        mock_backend = MagicMock()
        mock_backend.get_table_list.return_value = [
            "vf.facilities",
        ]
        mock_backend.get_backend_info.return_value = "Backend: DuckDB"
        mock_get_backend.return_value = mock_backend

        result = get_schema()

        # Result is now a dict with 'tables' key
        assert isinstance(result, dict)
        assert "vf.facilities" in result["tables"]
        mock_backend.get_table_list.assert_called_once()

    @patch(TABULAR_BACKEND_PATCH)
    @patch("oasis.api.DatasetRegistry.get_active")
    def test_get_schema_empty(
        self, mock_get_active, mock_get_backend, mock_tabular_dataset
    ):
        """Test get_schema with no tables."""
        mock_get_active.return_value = mock_tabular_dataset
        mock_backend = MagicMock()
        mock_backend.get_table_list.return_value = []
        mock_backend.get_backend_info.return_value = "Backend: DuckDB"
        mock_get_backend.return_value = mock_backend

        result = get_schema()

        assert result["tables"] == []

    @patch(TABULAR_BACKEND_PATCH)
    @patch("oasis.api.DatasetRegistry.get_active")
    def test_get_table_info(
        self, mock_get_active, mock_get_backend, mock_tabular_dataset
    ):
        """Test get_table_info returns dict with schema DataFrame."""
        mock_get_active.return_value = mock_tabular_dataset
        mock_backend = MagicMock()
        schema_df = pd.DataFrame({"name": ["pk_unique_id"], "type": ["INTEGER"]})
        sample_df = pd.DataFrame({"pk_unique_id": [1], "name": ["Facility A"]})

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.dataframe = schema_df
        mock_backend.get_table_info.return_value = mock_result

        mock_sample_result = MagicMock()
        mock_sample_result.success = True
        mock_sample_result.dataframe = sample_df
        mock_backend.get_sample_data.return_value = mock_sample_result
        mock_backend.get_backend_info.return_value = "Backend: DuckDB"
        mock_get_backend.return_value = mock_backend

        result = get_table_info("vf.facilities")

        # Result is now a dict
        assert isinstance(result, dict)
        assert result["table_name"] == "vf.facilities"
        assert isinstance(result["schema"], pd.DataFrame)
        assert isinstance(result["sample"], pd.DataFrame)

    @patch(TABULAR_BACKEND_PATCH)
    @patch("oasis.api.DatasetRegistry.get_active")
    def test_execute_query_success(
        self, mock_get_active, mock_get_backend, mock_tabular_dataset
    ):
        """Test execute_query returns DataFrame."""
        mock_get_active.return_value = mock_tabular_dataset
        mock_backend = MagicMock()
        result_df = pd.DataFrame({"count": [100]})
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.dataframe = result_df
        mock_backend.execute_query.return_value = mock_result
        mock_get_backend.return_value = mock_backend

        result = execute_query("SELECT COUNT(*) FROM vf.facilities")

        assert isinstance(result, pd.DataFrame)
        assert result["count"].iloc[0] == 100

    @patch(TABULAR_BACKEND_PATCH)
    @patch("oasis.api.DatasetRegistry.get_active")
    def test_execute_query_unsafe_raises_error(
        self, mock_get_active, mock_get_backend, mock_tabular_dataset
    ):
        """Test execute_query raises SecurityError for unsafe SQL."""
        mock_get_active.return_value = mock_tabular_dataset
        with pytest.raises(SecurityError):
            execute_query("DROP TABLE facilities")

    @patch(TABULAR_BACKEND_PATCH)
    @patch("oasis.api.DatasetRegistry.get_active")
    def test_execute_query_injection_blocked(
        self, mock_get_active, mock_get_backend, mock_tabular_dataset
    ):
        """Test execute_query raises SecurityError for SQL injection."""
        mock_get_active.return_value = mock_tabular_dataset
        with pytest.raises(SecurityError):
            execute_query("SELECT * FROM vf.facilities WHERE 1=1")


class TestExceptionHierarchy:
    """Test the exception class hierarchy."""

    def test_oasis_error_is_base(self):
        """Test OASISError is the base exception."""
        assert issubclass(DatasetError, OASISError)
        assert issubclass(QueryError, OASISError)

    def test_exceptions_are_catchable_as_base(self):
        """Test all exceptions can be caught as OASISError."""
        with pytest.raises(OASISError):
            raise DatasetError("test")

        with pytest.raises(OASISError):
            raise QueryError("test")

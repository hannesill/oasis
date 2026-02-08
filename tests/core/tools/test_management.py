"""Tests for management tools (list_datasets, set_dataset).

Tests cover:
- Tool invoke methods directly
- Edge cases and error conditions
- Backend warning messages

Note: Tools now return native types (dict) instead of ToolOutput.
"""

from unittest.mock import patch

import pytest

from oasis.core.datasets import DatasetDefinition
from oasis.core.exceptions import DatasetError
from oasis.core.tools.management import (
    ListDatasetsInput,
    ListDatasetsTool,
    SetDatasetInput,
    SetDatasetTool,
)


@pytest.fixture
def mock_availability():
    """Mock dataset availability data."""
    return {
        "vf-ghana": {
            "parquet_present": True,
            "db_present": True,
        },
    }


@pytest.fixture
def dummy_dataset():
    """Create a dummy dataset for passing to invoke (not actually used)."""
    return DatasetDefinition(
        name="dummy",
        modalities=set(),
    )


class TestListDatasetsTool:
    """Test ListDatasetsTool functionality."""

    def test_invoke_lists_available_datasets(self, mock_availability, dummy_dataset):
        """Test that invoke returns dict with dataset info."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch(
                "oasis.core.tools.management.get_active_dataset",
                return_value="vf-ghana",
            ):
                with patch("oasis.core.tools.management.DatasetRegistry.get") as mock_reg:
                    mock_ds = DatasetDefinition(
                        name="vf-ghana",
                    )
                    mock_reg.return_value = mock_ds

                    tool = ListDatasetsTool()
                    result = tool.invoke(dummy_dataset, ListDatasetsInput())

                    # Result is now a dict
                    assert "vf-ghana" in result["datasets"]
                    assert result["active_dataset"] == "vf-ghana"

    def test_invoke_shows_parquet_status(self, mock_availability, dummy_dataset):
        """Test that parquet availability is included."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch(
                "oasis.core.tools.management.get_active_dataset",
                return_value="vf-ghana",
            ):
                with patch("oasis.core.tools.management.DatasetRegistry.get") as mock_reg:
                    mock_reg.return_value = DatasetDefinition(
                        name="vf-ghana",
                    )

                    tool = ListDatasetsTool()
                    result = tool.invoke(dummy_dataset, ListDatasetsInput())

                    assert (
                        result["datasets"]["vf-ghana"]["parquet_present"] is True
                    )

    def test_invoke_shows_database_status(self, mock_availability, dummy_dataset):
        """Test that database availability is included."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch(
                "oasis.core.tools.management.get_active_dataset",
                return_value="vf-ghana",
            ):
                with patch("oasis.core.tools.management.DatasetRegistry.get") as mock_reg:
                    mock_reg.return_value = DatasetDefinition(
                        name="vf-ghana",
                    )

                    tool = ListDatasetsTool()
                    result = tool.invoke(dummy_dataset, ListDatasetsInput())

                    assert result["datasets"]["vf-ghana"]["db_present"] is True

    def test_invoke_handles_no_datasets(self, dummy_dataset):
        """Test handling when no datasets are available."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value={},
        ):
            with patch(
                "oasis.core.tools.management.get_active_dataset",
                return_value=None,
            ):
                tool = ListDatasetsTool()
                result = tool.invoke(dummy_dataset, ListDatasetsInput())

                assert result["datasets"] == {}

    def test_invoke_shows_backend_type(self, mock_availability, dummy_dataset):
        """Test that backend type is included."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch(
                "oasis.core.tools.management.get_active_dataset",
                return_value="vf-ghana",
            ):
                with patch("oasis.core.tools.management.DatasetRegistry.get") as mock_reg:
                    mock_reg.return_value = DatasetDefinition(
                        name="vf-ghana",
                    )
                    with patch.dict("os.environ", {"OASIS_BACKEND": "duckdb"}):
                        tool = ListDatasetsTool()
                        result = tool.invoke(dummy_dataset, ListDatasetsInput())

                        assert result["backend"] == "duckdb"

    def test_is_compatible_always_true(self):
        """Test that management tools are always compatible."""
        # Empty capabilities dataset
        empty_ds = DatasetDefinition(
            name="empty",
            modalities=set(),
        )

        tool = ListDatasetsTool()
        assert tool.is_compatible(empty_ds) is True

    def test_required_modalities_empty(self):
        """Test that management tool has no required modalities."""
        tool = ListDatasetsTool()
        assert tool.required_modalities == frozenset()


class TestSetDatasetTool:
    """Test SetDatasetTool functionality."""

    def test_invoke_switches_to_valid_dataset(self, mock_availability, dummy_dataset):
        """Test successful dataset switch."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch("oasis.core.tools.management.set_active_dataset") as mock_set:
                with patch("oasis.core.tools.management.DatasetRegistry.get") as mock_reg:
                    mock_reg.return_value = DatasetDefinition(
                        name="vf-ghana",
                    )
                    with patch(
                        "oasis.core.tools.management.get_active_backend",
                        return_value="duckdb",
                    ):
                        tool = SetDatasetTool()
                        params = SetDatasetInput(dataset_name="vf-ghana")
                        result = tool.invoke(dummy_dataset, params)

                        mock_set.assert_called_once_with("vf-ghana")
                        assert result["dataset_name"] == "vf-ghana"

    def test_invoke_rejects_unknown_dataset(self, mock_availability, dummy_dataset):
        """Test rejection of unknown dataset raises DatasetError."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch("oasis.core.tools.management.set_active_dataset") as mock_set:
                tool = SetDatasetTool()
                params = SetDatasetInput(dataset_name="unknown-dataset")

                with pytest.raises(DatasetError) as exc_info:
                    tool.invoke(dummy_dataset, params)

                mock_set.assert_not_called()
                assert "not found" in str(exc_info.value)

    def test_invoke_shows_supported_datasets_on_error(
        self, mock_availability, dummy_dataset
    ):
        """Test that error message lists supported datasets."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch("oasis.core.tools.management.set_active_dataset"):
                tool = SetDatasetTool()
                params = SetDatasetInput(dataset_name="nonexistent")

                with pytest.raises(DatasetError) as exc_info:
                    tool.invoke(dummy_dataset, params)

                assert "vf-ghana" in str(exc_info.value)

    def test_invoke_warns_missing_db_for_duckdb(self, dummy_dataset):
        """Test warning when database file is missing for DuckDB backend."""
        # Modify availability: parquet present but db missing
        availability = {
            "vf-ghana": {
                "parquet_present": True,
                "db_present": False,  # Missing!
            },
        }

        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=availability,
        ):
            with patch("oasis.core.tools.management.set_active_dataset"):
                with patch("oasis.core.tools.management.DatasetRegistry.get") as mock_reg:
                    mock_reg.return_value = DatasetDefinition(
                        name="vf-ghana",
                    )
                    with patch.dict("os.environ", {"OASIS_BACKEND": "duckdb"}):
                        tool = SetDatasetTool()
                        params = SetDatasetInput(dataset_name="vf-ghana")
                        result = tool.invoke(dummy_dataset, params)

                        assert "Local database not found" in result["warnings"][0]

    def test_invoke_case_insensitive(self, mock_availability, dummy_dataset):
        """Test that dataset name lookup is case-insensitive."""
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch("oasis.core.tools.management.set_active_dataset") as mock_set:
                with patch("oasis.core.tools.management.DatasetRegistry.get") as mock_reg:
                    mock_reg.return_value = DatasetDefinition(
                        name="vf-ghana",
                    )
                    with patch(
                        "oasis.core.tools.management.get_active_backend",
                        return_value="duckdb",
                    ):
                        tool = SetDatasetTool()
                        params = SetDatasetInput(dataset_name="VF-GHANA")
                        tool.invoke(dummy_dataset, params)

                        # Should normalize to lowercase
                        mock_set.assert_called_once_with("vf-ghana")

    def test_is_compatible_always_true(self):
        """Test that management tools are always compatible."""
        empty_ds = DatasetDefinition(
            name="empty",
            modalities=set(),
        )

        tool = SetDatasetTool()
        assert tool.is_compatible(empty_ds) is True


class TestManagementToolProtocol:
    """Test that management tools conform to the Tool protocol."""

    def test_list_datasets_has_required_attributes(self):
        """Test ListDatasetsTool has all required attributes."""
        tool = ListDatasetsTool()

        assert tool.name == "list_datasets"
        assert (
            "available" in tool.description.lower()
            or "list" in tool.description.lower()
        )
        assert tool.input_model == ListDatasetsInput
        assert isinstance(tool.required_modalities, frozenset)
        assert tool.supported_datasets is None  # Always available

    def test_set_dataset_has_required_attributes(self):
        """Test SetDatasetTool has all required attributes."""
        tool = SetDatasetTool()

        assert tool.name == "set_dataset"
        assert "switch" in tool.description.lower() or "set" in tool.description.lower()
        assert tool.input_model == SetDatasetInput
        assert isinstance(tool.required_modalities, frozenset)
        assert tool.supported_datasets is None  # Always available

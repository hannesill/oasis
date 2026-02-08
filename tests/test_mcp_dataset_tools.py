"""Tests for dataset management MCP tools."""

from unittest.mock import Mock, patch

import pytest
from fastmcp import Client

from oasis.core.tools import init_tools
from oasis.mcp_server import mcp


class TestMCPDatasetTools:
    """Test MCP dataset management tools."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure tools are initialized before each test."""
        init_tools()

    @pytest.mark.asyncio
    async def test_list_datasets(self):
        """Test list_datasets tool."""
        mock_availability = {
            "vf-ghana": {
                "parquet_present": True,
                "db_present": True,
                "parquet_root": "/tmp/vf_ghana_parquet",
                "db_path": "/tmp/vf_ghana.duckdb",
            },
        }

        # Patch at the location where it's imported (oasis.core.tools.management)
        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch(
                "oasis.core.tools.management.get_active_dataset",
                return_value="vf-ghana",
            ):
                with patch(
                    "oasis.config.get_active_dataset",
                    return_value="vf-ghana",
                ):
                    with patch(
                        "oasis.core.tools.management.DatasetRegistry.get"
                    ) as mock_get:
                        # Mock ds_def
                        mock_ds = Mock()
                        mock_ds.modalities = frozenset()
                        mock_get.return_value = mock_ds

                        async with Client(mcp) as client:
                            result = await client.call_tool("list_datasets", {})
                            result_text = str(result)

                        assert "Active dataset: vf-ghana" in result_text
                        assert "=== VF-GHANA (Active) ===" in result_text
                        assert "Local Database: +" in result_text

    @pytest.mark.asyncio
    async def test_set_dataset_success(self):
        """Test set_dataset tool with valid dataset."""
        mock_availability = {
            "vf-ghana": {"parquet_present": True, "db_present": True}
        }

        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch("oasis.core.tools.management.set_active_dataset") as mock_set:
                with patch(
                    "oasis.config.get_active_dataset", return_value="vf-ghana"
                ):
                    with patch("oasis.core.tools.management.DatasetRegistry.get"):
                        async with Client(mcp) as client:
                            result = await client.call_tool(
                                "set_dataset", {"dataset_name": "vf-ghana"}
                            )
                            result_text = str(result)

                            assert (
                                "Active dataset switched to 'vf-ghana'"
                                in result_text
                            )
                            mock_set.assert_called_once_with("vf-ghana")

    @pytest.mark.asyncio
    async def test_set_dataset_invalid(self):
        """Test set_dataset tool with invalid dataset."""
        mock_availability = {"vf-ghana": {}}

        with patch(
            "oasis.core.tools.management.detect_available_local_datasets",
            return_value=mock_availability,
        ):
            with patch("oasis.core.tools.management.set_active_dataset") as mock_set:
                with patch(
                    "oasis.config.get_active_dataset", return_value="vf-ghana"
                ):
                    with patch("oasis.core.tools.management.DatasetRegistry.get"):
                        async with Client(mcp) as client:
                            result = await client.call_tool(
                                "set_dataset", {"dataset_name": "invalid-ds"}
                            )
                            result_text = str(result)

                            assert "**Error:**" in result_text
                            assert "invalid-ds" in result_text
                            assert "not found" in result_text
                            mock_set.assert_not_called()

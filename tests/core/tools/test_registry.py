"""Tests for ToolRegistry and ToolSelector."""

import pytest

from oasis.core.datasets import DatasetDefinition, DatasetRegistry, Modality
from oasis.core.tools import Tool, ToolInput, ToolOutput, ToolRegistry, ToolSelector


# Mock tool classes for testing
class MockTabularTool:
    """Mock tool requiring TABULAR modality."""

    name = "mock_tabular"
    description = "Mock tabular tool"
    input_model = ToolInput
    output_model = ToolOutput
    required_modalities = frozenset({Modality.TABULAR})
    supported_datasets = None

    def invoke(self, dataset: DatasetDefinition, params: ToolInput) -> ToolOutput:
        return ToolOutput(result="tabular data")

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True


class MockVFGhanaOnlyTool:
    """Mock tool that only works with VF Ghana dataset."""

    name = "mock_vf_ghana_only"
    description = "Mock VF Ghana-only tool"
    input_model = ToolInput
    output_model = ToolOutput
    required_modalities = frozenset({Modality.TABULAR})
    supported_datasets = frozenset({"vf-ghana"})

    def invoke(self, dataset: DatasetDefinition, params: ToolInput) -> ToolOutput:
        return ToolOutput(result="vf ghana data")

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True


@pytest.fixture(autouse=True)
def reset_registries():
    """Reset tool registry before and after each test."""
    ToolRegistry.reset()
    yield
    ToolRegistry.reset()


class TestToolRegistry:
    """Test ToolRegistry functionality."""

    def test_register_tool(self):
        """Test registering a tool."""
        tool = MockTabularTool()
        ToolRegistry.register(tool)

        registered = ToolRegistry.get("mock_tabular")
        assert registered is not None
        assert registered.name == "mock_tabular"

    def test_register_duplicate_name_raises_error(self):
        """Test that registering a duplicate tool name raises ValueError."""
        tool1 = MockTabularTool()
        tool2 = MockTabularTool()

        ToolRegistry.register(tool1)
        with pytest.raises(ValueError, match="already registered"):
            ToolRegistry.register(tool2)

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        result = ToolRegistry.get("nonexistent")
        assert result is None

    def test_list_all_tools(self):
        """Test listing all registered tools."""
        tool1 = MockTabularTool()
        tool2 = MockVFGhanaOnlyTool()

        ToolRegistry.register(tool1)
        ToolRegistry.register(tool2)

        all_tools = ToolRegistry.list_all()
        assert len(all_tools) == 2
        assert tool1 in all_tools
        assert tool2 in all_tools

    def test_list_all_empty(self):
        """Test listing tools when registry is empty."""
        all_tools = ToolRegistry.list_all()
        assert all_tools == []

    def test_reset_clears_registry(self):
        """Test that reset clears all registered tools."""
        ToolRegistry.register(MockTabularTool())
        ToolRegistry.register(MockVFGhanaOnlyTool())

        assert len(ToolRegistry.list_all()) == 2

        ToolRegistry.reset()
        assert len(ToolRegistry.list_all()) == 0


class TestToolSelector:
    """Test ToolSelector filtering logic."""

    def test_selector_returns_compatible_tools(self):
        """Test that selector returns only compatible tools."""
        ToolRegistry.register(MockTabularTool())
        ToolRegistry.register(MockVFGhanaOnlyTool())

        selector = ToolSelector()
        vf_ghana = DatasetRegistry.get("vf-ghana")

        compatible = selector.tools_for_dataset(vf_ghana)

        # Both tools should be compatible with vf-ghana
        assert len(compatible) == 2
        tool_names = {tool.name for tool in compatible}
        assert "mock_tabular" in tool_names
        assert "mock_vf_ghana_only" in tool_names

    def test_selector_filters_by_modality(self):
        """Test selector filters by required modalities."""
        ToolRegistry.register(MockTabularTool())

        selector = ToolSelector()
        vf_ghana = DatasetRegistry.get("vf-ghana")

        compatible = selector.tools_for_dataset(vf_ghana)

        # vf-ghana has TABULAR modality
        tool_names = {tool.name for tool in compatible}
        assert "mock_tabular" in tool_names

    def test_selector_filters_by_dataset_name(self):
        """Test that selector respects supported_datasets restrictions."""
        ToolRegistry.register(MockVFGhanaOnlyTool())

        selector = ToolSelector()

        # Should work with VF Ghana dataset
        vf_ghana = DatasetRegistry.get("vf-ghana")
        compatible = selector.tools_for_dataset(vf_ghana)
        assert len(compatible) == 1

        # Create a non-VF Ghana dataset with same modalities
        other_ds = DatasetDefinition(
            name="other-dataset",
            description="Other database",
            modalities={Modality.TABULAR},
        )

        # Should NOT work with non-VF Ghana datasets (even with modalities)
        compatible = selector.tools_for_dataset(other_ds)
        assert len(compatible) == 0

    def test_selector_by_dataset_name_string(self):
        """Test selector using dataset name as string."""
        ToolRegistry.register(MockTabularTool())

        selector = ToolSelector()

        # Use string instead of DatasetDefinition
        compatible = selector.tools_for_dataset("vf-ghana")

        # Only tabular tool should match (vf-ghana has TABULAR modality)
        tool_names = {tool.name for tool in compatible}
        assert "mock_tabular" in tool_names

    def test_selector_unknown_dataset_returns_empty(self):
        """Test selector with unknown dataset name."""
        ToolRegistry.register(MockTabularTool())

        selector = ToolSelector()
        compatible = selector.tools_for_dataset("unknown-dataset")

        assert compatible == []

    def test_is_tool_available_by_name(self):
        """Test checking if a specific tool is available."""
        ToolRegistry.register(MockTabularTool())
        ToolRegistry.register(MockVFGhanaOnlyTool())

        selector = ToolSelector()

        # Tabular tool available for vf-ghana (has TABULAR modality)
        assert selector.is_tool_available("mock_tabular", "vf-ghana")

        # VF Ghana-only tool is available for vf-ghana
        assert selector.is_tool_available("mock_vf_ghana_only", "vf-ghana")

    def test_is_tool_available_with_dataset_definition(self):
        """Test is_tool_available with DatasetDefinition object."""
        ToolRegistry.register(MockTabularTool())

        selector = ToolSelector()
        vf_ghana = DatasetRegistry.get("vf-ghana")

        assert selector.is_tool_available("mock_tabular", vf_ghana)

    def test_is_tool_available_nonexistent_tool(self):
        """Test is_tool_available with tool that doesn't exist."""
        selector = ToolSelector()
        assert not selector.is_tool_available("nonexistent", "vf-ghana")

    def test_is_tool_available_unknown_dataset(self):
        """Test is_tool_available with unknown dataset."""
        ToolRegistry.register(MockTabularTool())

        selector = ToolSelector()
        assert not selector.is_tool_available("mock_tabular", "unknown-dataset")

    def test_tools_for_dataset_empty_registry(self):
        """Test tools_for_dataset when no tools are registered."""
        selector = ToolSelector()
        compatible = selector.tools_for_dataset("vf-ghana")

        assert compatible == []


class TestIntegration:
    """Integration tests for registry and selector together."""

    def test_multiple_tools_with_varying_requirements(self):
        """Test complex scenario with multiple tools and datasets."""
        # Register tools
        ToolRegistry.register(MockTabularTool())
        ToolRegistry.register(MockVFGhanaOnlyTool())

        selector = ToolSelector()

        # Test with vf-ghana (has TABULAR modality)
        vf_tools = selector.tools_for_dataset("vf-ghana")
        vf_names = {t.name for t in vf_tools}
        assert "mock_tabular" in vf_names
        assert "mock_vf_ghana_only" in vf_names

    def test_tool_protocol_conformance(self):
        """Test that tools conform to the Tool protocol."""
        tool = MockTabularTool()

        # Check protocol conformance
        assert isinstance(tool, Tool)
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert hasattr(tool, "invoke")
        assert hasattr(tool, "is_compatible")


class TestInitTools:
    """Tests for init_tools function and real tool registration."""

    def test_init_tools_registers_all_tools(self):
        """Test that init_tools registers all expected tools."""
        from oasis.core.tools import init_tools, reset_tools

        # Ensure clean state
        reset_tools()

        # Initialize tools
        init_tools()

        # Verify all tools are registered
        all_tools = ToolRegistry.list_all()
        tool_names = {t.name for t in all_tools}

        # Management tools
        assert "list_datasets" in tool_names
        assert "set_dataset" in tool_names

        # Tabular tools
        assert "get_database_schema" in tool_names
        assert "get_table_info" in tool_names
        assert "execute_query" in tool_names

        # Total: 5 tools (2 management + 3 tabular)
        assert len(all_tools) == 5

        # Cleanup
        reset_tools()

    def test_init_tools_is_idempotent(self):
        """Test that calling init_tools multiple times is safe."""
        from oasis.core.tools import init_tools, reset_tools

        reset_tools()

        # Call multiple times
        init_tools()
        init_tools()
        init_tools()

        # Should still have exactly 5 tools
        all_tools = ToolRegistry.list_all()
        assert len(all_tools) == 5

        reset_tools()

    def test_reset_tools_clears_everything(self):
        """Test that reset_tools clears all registered tools."""
        from oasis.core.tools import init_tools, reset_tools

        init_tools()
        assert len(ToolRegistry.list_all()) == 5

        reset_tools()
        assert len(ToolRegistry.list_all()) == 0

        # Can reinitialize after reset
        init_tools()
        assert len(ToolRegistry.list_all()) == 5

        reset_tools()

    def test_real_tools_conform_to_protocol(self):
        """Test that all real tool classes conform to the Tool protocol."""
        from oasis.core.tools import (
            ExecuteQueryTool,
            GetDatabaseSchemaTool,
            GetTableInfoTool,
            ListDatasetsTool,
            SetDatasetTool,
        )

        tool_classes = [
            GetDatabaseSchemaTool,
            GetTableInfoTool,
            ExecuteQueryTool,
            ListDatasetsTool,
            SetDatasetTool,
        ]

        for tool_class in tool_classes:
            tool = tool_class()
            assert isinstance(tool, Tool), f"{tool_class.__name__} is not a Tool"
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "input_model")
            # output_model removed - tools now return native types
            assert hasattr(tool, "required_modalities")
            assert hasattr(tool, "invoke")
            assert hasattr(tool, "is_compatible")

    def test_selector_with_real_tools(self):
        """Test ToolSelector with the actual registered tools."""
        from oasis.core.tools import init_tools, reset_tools

        reset_tools()
        init_tools()

        selector = ToolSelector()

        # Test with vf-ghana dataset (has TABULAR modality)
        vf_tools = selector.tools_for_dataset("vf-ghana")
        vf_names = {t.name for t in vf_tools}

        # Management tools should always be available
        assert "list_datasets" in vf_names
        assert "set_dataset" in vf_names

        # Tabular tools should be available for vf-ghana
        assert "get_database_schema" in vf_names
        assert "get_table_info" in vf_names
        assert "execute_query" in vf_names

        reset_tools()

    def test_management_tools_always_compatible(self):
        """Test that management tools work with any dataset."""
        from oasis.core.tools import ListDatasetsTool, SetDatasetTool

        list_tool = ListDatasetsTool()
        set_tool = SetDatasetTool()

        # Create a minimal dataset
        minimal_ds = DatasetDefinition(
            name="minimal",
            modalities=set(),  # No modalities
        )

        # Management tools should be compatible with any dataset
        assert list_tool.is_compatible(minimal_ds)
        assert set_tool.is_compatible(minimal_ds)

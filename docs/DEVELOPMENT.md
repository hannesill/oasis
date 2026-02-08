# Development Guide

## Setup

### Clone and install

```bash
git clone https://github.com/hannesill/oasis.git
cd oasis
uv venv
uv sync
```

## CLI Commands

### Dataset Management

```bash
# Initialize a dataset from CSV
uv run oasis init vf-ghana --src /path/to/csv

# Switch active dataset
uv run oasis use vf-ghana

# Show active dataset status (detailed view)
uv run oasis status

# List all datasets (compact table)
uv run oasis status --all
```

### MCP Client Configuration

```bash
# Auto-configure Claude Desktop
uv run oasis config claude

# Generate config for other clients
uv run oasis config --quick
```

### Development Commands

```bash
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_mcp_server.py -v

# Run tests matching pattern
uv run pytest -k "test_name" -v

# Lint and format
uv run pre-commit run --all-files

# Lint only
uv run ruff check src/

# Format only
uv run ruff format src/
```

## MCP Configuration for Development

Point your MCP client to your local development environment:

```json
{
  "mcpServers": {
    "oasis": {
      "command": "/absolute/path/to/oasis/.venv/bin/python",
      "args": ["-m", "oasis.mcp_server"],
      "cwd": "/absolute/path/to/oasis"
    }
  }
}
```

## Architecture Overview

OASIS has three main layers:

```
MCP Layer (mcp_server.py)
    │
    ├── Exposes tools via Model Context Protocol
    └── Thin adapter over core functionality

Core Layer (src/oasis/core/)
    │
    ├── datasets.py    - Dataset definitions and modalities
    ├── tools/         - Tool implementations (tabular, management)
    └── backends/      - Database backend (DuckDB)

Infrastructure Layer
    │
    ├── data_io.py     - Convert CSV, initialize databases
    ├── cli.py         - Command-line interface
    └── config.py      - Configuration management
```

### Modality-Based Tool System

Tools declare required modalities to specify which data types they need:

```python
class ExecuteQueryTool:
    required_modalities = frozenset({Modality.TABULAR})
```

The `ToolSelector` automatically filters tools based on the active dataset's modalities.

## Adding a New Tool

OASIS uses a **protocol-based design** (structural typing). Tools don't inherit from a base class — they implement the required interface.

1. Create the tool class in `src/oasis/core/tools/`:

```python
from dataclasses import dataclass
from oasis.core.datasets import DatasetDefinition, Modality
from oasis.core.tools.base import ToolInput, ToolOutput

@dataclass
class MyNewToolInput(ToolInput):
    param1: str
    limit: int = 10

class MyNewTool:
    """Tool description for documentation."""

    name = "my_new_tool"
    description = "Description shown to LLMs"
    input_model = MyNewToolInput
    output_model = ToolOutput

    required_modalities: frozenset[Modality] = frozenset({Modality.TABULAR})
    supported_datasets: frozenset[str] | None = None  # None = all compatible

    def invoke(
        self, dataset: DatasetDefinition, params: MyNewToolInput
    ) -> ToolOutput:
        """Execute the tool."""
        return ToolOutput(result="Success")

    def is_compatible(self, dataset: DatasetDefinition) -> bool:
        """Check if tool works with this dataset."""
        if self.supported_datasets and dataset.name not in self.supported_datasets:
            return False
        if not self.required_modalities.issubset(dataset.modalities):
            return False
        return True
```

2. Register it in `src/oasis/core/tools/__init__.py`:

```python
from .my_module import MyNewTool

def init_tools():
    ToolRegistry.register(MyNewTool())
```

3. Add the MCP handler in `mcp_server.py`:

```python
@mcp.tool()
def my_new_tool(param1: str, limit: int = 10) -> str:
    dataset = DatasetRegistry.get_active()
    result = _tool_selector.check_compatibility("my_new_tool", dataset)
    if not result.compatible:
        return result.error_message
    tool = ToolRegistry.get("my_new_tool")
    return tool.invoke(dataset, MyNewToolInput(param1=param1, limit=limit)).result
```

## Code Style

- **Formatter:** Ruff (line-length 88)
- **Type hints:** Required on all functions
- **Tests:** pytest with `asyncio_mode = "auto"`

## Testing

Tests mirror the `src/oasis/` structure:

```
tests/
├── test_mcp_server.py
├── core/
│   ├── test_datasets.py
│   ├── tools/
│   │   └── test_tabular.py
│   └── backends/
│       └── test_duckdb.py
```

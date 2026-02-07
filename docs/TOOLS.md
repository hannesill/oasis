# MCP Tools Reference

OASIS exposes these tools to AI clients via the Model Context Protocol. Tools are filtered based on the active dataset's modality.

## Dataset Management

### `list_datasets`
List all available datasets and their status.

**Parameters:** None

### `set_dataset`
Switch the active dataset.

**Parameters:**
- `dataset_name` (string, required): Name of the dataset to activate

---

## Tabular Data Tools

These tools are available for datasets with the `TABULAR` modality.

### `get_database_schema`
List all tables in the current dataset.

**Parameters:** None

**Returns:** Table names with row counts

### `get_table_info`
Get detailed information about a specific table.

**Parameters:**
- `table_name` (string, required): Name of the table
- `sample_rows` (int, optional): Number of sample rows to return (default: 5)

**Returns:** Column names, types, and sample data

### `execute_query`
Execute a read-only SQL SELECT query.

**Parameters:**
- `query` (string, required): SQL SELECT statement
- `limit` (int, optional): Maximum rows to return (default: 100)

**Security:**
- Only SELECT statements allowed
- DROP, DELETE, INSERT, UPDATE blocked
- Query validation before execution

---

## Modality-Based Tool Availability

Tools declare required modalities. Only datasets with matching modalities expose the tool:

| Tool | Required Modality |
|------|-------------------|
| `get_database_schema` | TABULAR |
| `get_table_info` | TABULAR |
| `execute_query` | TABULAR |
| `list_datasets` | (always) |
| `set_dataset` | (always) |

---

## Error Handling

When a tool is unavailable for the current dataset, it returns a helpful error:

```
Error: Tool `search_notes` is not available for dataset 'vf-ghana'.

This tool requires the NOTES modality, but 'vf-ghana' only has: TABULAR

Suggestions:
   - Use `list_datasets()` to see all available datasets
   - Use `set_dataset(...)` to switch to a compatible dataset
```

---

## Python API Alternative

For complex analysis beyond simple queries, OASIS provides a Python API that returns native types (DataFrames) instead of formatted strings:

```python
from oasis import set_dataset, execute_query

set_dataset("vf-ghana")
df = execute_query("SELECT * FROM vf.facilities LIMIT 10")  # Returns pandas DataFrame
```

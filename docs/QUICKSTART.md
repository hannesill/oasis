# Quickstart

Get OASIS running in under 5 minutes. Two paths: **MCP** (use OASIS tools in Claude Desktop) or **Python API** (call OASIS from your own scripts).

Both paths start the same way.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Install

```bash
git clone https://github.com/hannesill/oasis.git
cd oasis
uv sync
```

## Initialize the VF Ghana dataset

```bash
uv run oasis init vf-ghana
```

This auto-detects `vf-ghana.csv` at the project root, converts it to Parquet, creates a DuckDB database, and sets `vf-ghana` as the active dataset. Verify it worked:

```bash
uv run oasis status
```

You should see the dataset name, backend (DuckDB), modalities (TABULAR), and a row count for `vf.facilities`.

---

## Path 1: MCP (Claude Desktop)

### Configure Claude Desktop

The fastest way:

```bash
uv run oasis config claude
```

This writes the MCP server entry to your Claude Desktop config. Restart Claude Desktop to pick it up.

<details>
<summary>Manual config (if auto-config doesn't work)</summary>

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "oasis": {
      "command": "/absolute/path/to/oasis/.venv/bin/python",
      "args": ["-m", "oasis.mcp_server"],
      "cwd": "/absolute/path/to/oasis",
      "env": {
        "PYTHONPATH": "/absolute/path/to/oasis/src",
        "OASIS_DATA_DIR": "/absolute/path/to/oasis/oasis_data"
      }
    }
  }
}
```

Replace `/absolute/path/to/oasis` with your actual project path.

</details>

### Available MCP tools

Once connected, Claude Desktop can use these tools:

| Tool | What it does |
|------|-------------|
| `list_datasets` | List all datasets and their status |
| `set_dataset` | Switch the active dataset |
| `get_database_schema` | List all tables in the active dataset |
| `get_table_info` | Show columns, types, and sample rows for a table |
| `execute_query` | Run a read-only SQL query and return results |

### Try it

Open Claude Desktop and ask:

> "What tables are available in the database?"

Claude will call `get_database_schema` and show you `vf.facilities`.

> "Show me 5 healthcare facilities in Accra."

Claude will call `execute_query` with something like:

```sql
SELECT name, facilityTypeId, specialties
FROM vf.facilities
WHERE address_city = 'Accra'
LIMIT 5
```

> "How many facilities have surgical capabilities listed in their procedure field?"

Claude will reason about the free-form text fields and write a query to find them.

---

## Path 2: Python API

### Basic usage

```python
from oasis import set_dataset, get_schema, get_table_info, execute_query

# Activate the VF Ghana dataset
set_dataset("vf-ghana")

# See what tables are available
schema = get_schema()
print(schema["tables"])
# ['vf.facilities']

# Inspect the table structure
info = get_table_info("vf.facilities", show_sample=True)
print(info["schema"])   # DataFrame of column names and types
print(info["sample"])   # DataFrame with sample rows

# Query the data
df = execute_query("SELECT COUNT(*) AS total FROM vf.facilities")
print(df)
#    total
# 0   1002
```

### Querying facility data

```python
from oasis import execute_query

# Facilities by region
df = execute_query("""
    SELECT address_stateOrRegion AS region, COUNT(*) AS count
    FROM vf.facilities
    GROUP BY region
    ORDER BY count DESC
""")
print(df)

# Facilities with specific specialties
df = execute_query("""
    SELECT name, address_city, specialties
    FROM vf.facilities
    WHERE specialties IS NOT NULL
      AND specialties != '[]'
    LIMIT 10
""")

# Search free-form text fields (IDP targets)
df = execute_query("""
    SELECT name, procedure, equipment, capability
    FROM vf.facilities
    WHERE procedure IS NOT NULL
      AND procedure != '[]'
    LIMIT 5
""")
```

### Working with results

`execute_query` returns a pandas DataFrame, so you can use the full pandas API:

```python
df = execute_query("SELECT * FROM vf.facilities")

# Filter in Python
hospitals = df[df["facilityTypeId"] == "hospital"]

# Check data completeness
print(df["equipment"].notna().sum(), "facilities have equipment data")
print(df["procedure"].notna().sum(), "facilities have procedure data")

# Export
df.to_csv("facilities_export.csv", index=False)
```

### Error handling

```python
from oasis import execute_query, QueryError, DatasetError

try:
    df = execute_query("DROP TABLE vf.facilities")  # blocked — read-only
except QueryError as e:
    print(f"Query rejected: {e}")

try:
    from oasis import set_dataset
    set_dataset("nonexistent")
except DatasetError as e:
    print(f"Dataset error: {e}")
```

### Listing datasets

```python
from oasis import list_datasets

datasets = list_datasets()
print(datasets)
# ['vf-ghana']
```

---

## Environment variables

Override defaults without touching config files:

| Variable | Purpose | Default |
|----------|---------|---------|
| `OASIS_DATA_DIR` | Data directory location | `<project>/oasis_data` |
| `OASIS_DATASET` | Force active dataset | From `config.json` |
| `OASIS_BACKEND` | Backend engine | `duckdb` |
| `OASIS_DUCKDB_MEM` | DuckDB memory limit | `3GB` |
| `OASIS_DUCKDB_THREADS` | DuckDB thread count | `2` |

---

## Next steps

- [Custom Datasets](CUSTOM_DATASETS.md) — Add your own CSV data
- [Tools Reference](TOOLS.md) — Full tool documentation
- [Development Guide](DEVELOPMENT.md) — Add new tools, run tests
- [OASIS Apps](OASIS_APPS.md) — Build interactive UI apps
- [Skills Guide](SKILLS.md) — Install and create agent skills

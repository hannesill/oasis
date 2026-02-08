# Adding Custom Datasets

OASIS supports custom datasets loaded from CSV files. This guide shows how to add your own.

## Quick Start: JSON Definition

Create a JSON file in `oasis_data/datasets/`:

**Example: `oasis_data/datasets/vf-ghana.json`**
```json
{
  "name": "vf-ghana",
  "description": "Virtue Foundation Ghana Healthcare Facilities",
  "primary_verification_table": "vf.facilities",
  "modalities": ["TABULAR"],
  "schema_mapping": {"": "vf"}
}
```

Then initialize:
```bash
oasis init vf-ghana --src /path/to/your/csv/files
```

## JSON Fields Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier (used in `oasis use <name>`) |
| `description` | Yes | Human-readable description |
| `primary_verification_table` | Yes | Table to verify initialization succeeded |
| `modalities` | No | Data types in this dataset (see below). Defaults to `["TABULAR"]` |
| `schema_mapping` | No | Maps filesystem subdirectories to canonical schema names (see below) |

### Available Modalities

| Modality | Description | Available Tools |
|----------|-------------|-----------------|
| `TABULAR` | Structured tables | `get_database_schema`, `get_table_info`, `execute_query` |

Tools are filtered based on the dataset's declared modalities. If not specified, defaults to `["TABULAR"]`.

### Schema Mapping (Canonical Table Names)

OASIS uses canonical `schema.table` names (e.g., `vf.facilities`) that work with the DuckDB backend. The `schema_mapping` field controls how these canonical names are constructed.

**`schema_mapping`** maps filesystem subdirectories to canonical schema names. When DuckDB creates views, files from each subdirectory are placed into the corresponding schema:

```json
{
  "schema_mapping": {
    "": "vf"
  }
}
```

With this, a file `facilities.csv` becomes queryable as `vf.facilities`.

For datasets with subdirectories, map each subdirectory to a schema name:

```json
{
  "schema_mapping": {
    "hospitals": "gh_hospitals",
    "clinics": "gh_clinics"
  }
}
```

Custom datasets without `schema_mapping` still work — tables will be created with flat names in the `main` schema.

## Initialization Process

When you run `oasis init <dataset> --src /path/to/csvs`:

1. **Convert** CSV files to Parquet format
2. **Create** DuckDB views over the Parquet files
3. **Verify** by querying `primary_verification_table`
4. **Set** as active dataset

## Directory Structure

OASIS organizes data like this:

```
oasis_data/
├── datasets/           # Custom JSON definitions
│   └── vf-ghana.json
├── parquet/            # Converted Parquet files
│   └── vf-ghana/
│       └── *.parquet
└── databases/          # DuckDB databases
    └── vf_ghana.duckdb
```

## Programmatic Registration

For more control, register datasets in Python:

```python
from oasis.core.datasets import DatasetDefinition, DatasetRegistry, Modality

my_dataset = DatasetDefinition(
    name="vf-ghana",
    description="Virtue Foundation Ghana Healthcare Facilities",
    primary_verification_table="vf.facilities",
    modalities=frozenset({Modality.TABULAR}),
    schema_mapping={"": "vf"},
)

DatasetRegistry.register(my_dataset)
```

## Tips

- **Check table names:** Use `get_database_schema` tool to see available tables
- **Verify initialization:** `oasis status` shows if Parquet and DuckDB are ready
- **Force reinitialize:** `oasis init <dataset> --force` recreates the database

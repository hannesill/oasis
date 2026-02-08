# 🌴 OASIS

**Orchestrated Agentic System for Intelligent healthcare Synthesis**

> "Today is gonna be the day that they're gonna throw it back to you..."

OASIS is an agentic intelligence layer that analyzes ~1,000 healthcare facilities across Ghana to identify medical deserts, detect anomalies in facility claims, and route patients to the nearest capable care — all through natural language in Claude Desktop.

Built for the [Virtue Foundation](https://virtuefoundation.org/) hackathon, sponsored by Databricks.

## The Problem

Rural Ghana has vast gaps in healthcare coverage. Facility data exists but is messy — free-form text fields describing procedures, equipment, and capabilities alongside structured records with missing values. Understanding where care truly exists and where it's absent requires parsing unstructured data, cross-referencing it with structured schemas, and reasoning geospatially.

## What OASIS Does

Ask Claude a question like *"Where are the surgical deserts in Northern Ghana?"* and OASIS:

1. **Parses unstructured data** — Extracts capabilities from free-form `procedure`, `equipment`, and `capability` fields
2. **Synthesizes with structured data** — Cross-references extracted insights against facility type, specialties, bed counts, and staffing
3. **Reasons geospatially** — Identifies coverage gaps, calculates distances, finds the nearest capable facilities
4. **Visualizes on an interactive 3D map** — Launches a Mapbox GL JS map inside Claude Desktop showing facilities, deserts, and routes

### MCP Tools

| Tool | What it does |
|------|-------------|
| `find_facilities_in_radius` | Search for facilities by condition, location, and radius |
| `find_coverage_gaps` | Identify geographic areas lacking a specific specialty or procedure |
| `count_facilities` | Aggregate facility counts by region, type, or specialty |
| `calculate_distance` | Haversine distance between any two locations |
| `geocode_facilities` | Generate GeoJSON for map visualization |
| `execute_query` | Run SQL against the facility database for custom analysis |
| `geo_map` | Launch the interactive Medical Desert Mapper |

### Medical Desert Mapper

Interactive 3D map running inside Claude Desktop via the MCP Apps protocol:

- Dark globe with 3D terrain and facility markers color-coded by type
- Heatmap overlay showing facility density
- Search by condition + location + radius
- Coverage gap visualization with desert highlighting
- Facility detail cards with specialties, equipment, and distance
- Text-to-speech narration (ElevenLabs, optional)

## Architecture

```
Claude Desktop
    │
    └── OASIS MCP Server (FastMCP)
            │
            ├── Geospatial Tools ── DuckDB (VF Ghana data)
            ├── Tabular Tools ───── SQL queries + free-form text parsing
            ├── Management Tools ── Dataset switching, schema introspection
            │
            └── Medical Desert Mapper App
                    └── Mapbox GL JS + Three.js (bundled via Vite)
```

**Data flow:** `vf-ghana.csv` → `oasis init` → Parquet → DuckDB → MCP tools → Claude reasoning → structured answers + map visualizations

## Quickstart

```bash
# Install dependencies
uv sync
source .venv/bin/activate

# Initialize the VF Ghana dataset
oasis init vf-ghana

# Verify everything works
oasis status

# Configure Claude Desktop integration
oasis config claude
```

After `oasis config claude`, restart Claude Desktop. OASIS tools will be available for natural language queries against the Ghana healthcare facility data.

### Environment Variables

Create a `.env` file in the project root:

```
MAPBOX_TOKEN=your_mapbox_token_here
ELEVENLABS_API_KEY=your_key_here  # optional, for TTS narration
```

### Building the Map UI

```bash
cd src/oasis/apps/geo_map/ui
npm install
npm run build
```

The built bundle is output to `src/oasis/apps/geo_map/mcp-app.html` and served directly by the MCP server.

## Dataset

**Virtue Foundation Ghana v0.3** — ~1,002 healthcare facility records with:

- **Structured fields:** facility type, specialties, region, district, bed count, staffing
- **Free-form text:** JSON arrays of procedures, equipment, and capabilities (the richest data source)
- **Geographic coordinates:** latitude/longitude for geospatial analysis

Many fields are null or empty — detecting these gaps is the core feature. See `docs/challenge/Virtue Foundation Scheme Documentation.md` for the full schema.

## Stack

- **Python 3.10+** with DuckDB for fast local analytics
- **FastMCP** for Claude Desktop integration
- **Mapbox GL JS** + **Three.js** for 3D map visualization (Vite-bundled)
- **Databricks** integration available for Vector Search (RAG) and MLflow tracing

## Project Structure

```
src/oasis/
├── mcp_server.py          # FastMCP entry point
├── core/
│   ├── tools/
│   │   ├── geospatial.py  # Facility search, coverage gaps, routing
│   │   ├── tabular.py     # SQL queries, schema introspection
│   │   └── management.py  # Dataset management
│   ├── backends/
│   │   └── duckdb.py      # DuckDB backend
│   └── datasets.py        # Dataset registry
├── apps/
│   └── geo_map/           # Medical Desert Mapper (Mapbox GL JS)
├── databricks/            # Vector Search, Genie, MLflow tracing
└── skills/                # Agent skill framework (markdown + YAML)
docs/
├── challenge/             # Hackathon brief and VF agent questions
├── OASIS_APPS.md          # MCP App protocol guide
├── TOOLS.md               # Tool documentation
└── DEVELOPMENT.md         # Developer guide
tests/                     # pytest suite
vf-ghana.csv              # Source dataset
```

## Tests

```bash
pytest
```

## Documentation

| Topic | File |
|-------|------|
| App development | `docs/OASIS_APPS.md` |
| Tool reference | `docs/TOOLS.md` |
| Custom datasets | `docs/CUSTOM_DATASETS.md` |
| Developer guide | `docs/DEVELOPMENT.md` |
| Geospatial tools | `docs/GEOSPATIAL_SUMMARY.md` |
| Challenge brief | `docs/challenge/CHALLENGE.md` |
| VF Agent Questions | `docs/challenge/Virtue Foundation Agent Questions - Hack Nation.md` |

## License

Hackathon project — Virtue Foundation / Hack Nation 2025.

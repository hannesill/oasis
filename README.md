# 🌴 OASIS

**Orchestrated Agentic System for Intelligent healthcare Synthesis**

> "Today is gonna be the day that they're gonna throw it back to you..."

Agentic intelligence layer for bridging medical deserts. Built for the Virtue Foundation hackathon, sponsored by Databricks.

## What it does

OASIS analyzes ~1,000 healthcare facilities across Ghana to identify coverage gaps, detect anomalies in facility claims, and route patients to the nearest capable care — all through natural language in Claude Desktop.

**Core capabilities:**
- **Medical desert identification** — Find regions lacking specific specialties or surgical capability
- **Facility analysis** — Deep-dive into any facility combining structured data with free-form text (procedures, equipment, capabilities)
- **Anomaly detection** — Flag inconsistencies in facility claims (e.g., claims emergency surgery but lists no surgical equipment)
- **Patient routing** — Given a medical need and location, find the nearest capable facility

## Setup

```bash
uv sync
source .venv/bin/activate
```

## Dataset

Virtue Foundation Ghana v0.3 — healthcare facility records with structured fields (specialties, facility type, location) and free-form text (procedures, equipment, capabilities).

## Stack

- Python + DuckDB for data
- MCP server for Claude Desktop integration
- Mapbox GL JS for interactive map visualization

## Quickstart

```bash
# 1. Install dependencies
uv sync
source .venv/bin/activate

# 2. Initialize the VF Ghana dataset
oasis init vf-ghana

# 3. Verify everything is working
oasis status

# 4. Configure Claude Desktop integration
oasis config claude
```

After running `oasis config claude`, restart Claude Desktop. You'll have access to OASIS tools for querying Ghana healthcare facility data through natural language.

# OASIS — "Today is gonna be the day..."

## Mission: Ship the Demo

We are in **demo mode**. Everything we build must serve the 50-second Screen.studio recording. The demo has 4 beats — each must work flawlessly. If it doesn't appear in the demo, it doesn't matter right now.

## The 4 Demo Beats

| Beat | User Types | Tools Called | Status |
|------|-----------|-------------|--------|
| 1 — The Question | "Where are the surgical deserts in Northern Ghana?" | `geo_map(mode="deserts", condition="surgery", highlight_region="Northern", initial_zoom=7, narrative_focus="deserts")` | geo_map EXISTS |
| 2 — The Investigation | "I see a facility near Tamale claims surgical capability. Can you verify that?" | `search_facility_capabilities(query="surgical capability Tamale", limit=5)` → `execute_query(sql_query="SELECT ... WHERE pk_unique_id='[id]'")` | search_facility_capabilities NEEDS WORK; execute_query EXISTS |
| 3 — The Recommendation | "Where should we deploy one surgical team to save the most lives?" | `geo_map(mode="deserts", condition="surgery", narrative_focus="impact", highlight_region="Northern", initial_zoom=7)` | geo_map EXISTS |
| 4 — The Closer | "Show me the evidence trail" | `get_citation_trace(limit=5)` | NEEDS WORK (Databricks/MLflow optional) |

### What Must Work for the Demo

**Beat 1 + 3 (geo_map):** Already functional. Needs to support `narrative_focus="deserts"` and `narrative_focus="impact"` parameters cleanly, return gap count, worst location, distance, and estimated population. Verify these params work and the map renders the right visualization for each mode.

**Beat 2 (anomaly detection):** This is the IDP Innovation showpiece (30% of score). Two-step flow:
1. `search_facility_capabilities` — semantic/text search over facility free-form fields. Currently declared in `src/oasis/databricks/rag.py` but needs to work without Databricks too (DuckDB full-text search fallback).
2. `execute_query` — already works. Fetches structured data to cross-reference against the RAG result.
3. Claude compares the two and spots the anomaly. The response names a specific facility, specific procedures it claims, and specific staff/equipment numbers that contradict the claim.

**Beat 4 (citations):** `get_citation_trace` in `src/oasis/databricks/tracing.py`. If MLflow isn't available, this needs a local fallback that returns the tool call chain from the conversation. The response text is fixed — this beat is about the visual of a citation trace appearing.

### Demo Preset Prompt

The full preset prompt for Claude Desktop's project instructions is in `SCRIPT.md`. It makes Claude follow the exact script — tool calls, response text, everything deterministic. Before recording, do a dry run and update the preset prompt with real numbers from tool results.

## Priority Order

1. **Make Beat 2 work end-to-end** — `search_facility_capabilities` with DuckDB fallback + the anomaly detection flow
2. **Make Beat 4 work** — `get_citation_trace` with local fallback
3. **Verify Beat 1 + 3** — geo_map with the exact params from the script, ensure narrative_focus modes return the right data
4. **Dry run** — Run all 4 beats, capture real numbers, update preset prompt
5. **Polish map visuals** — Heatmap pulses, camera fly animations, warning badges, impact overlays

Everything else (route_patient, extract_capabilities, detect_anomalies, analyze_facility as standalone tools) is deferred until after the recording is done.

## Project Identity

**OASIS** (Orchestrated Agentic System for Intelligent healthcare Synthesis). Named after the band behind *Wonderwall* — "the one that saves you."

**Hackathon:** "Bridging Medical Deserts" for Virtue Foundation, sponsored by Databricks.

**Scoring:**
| Criterion | Weight | Demo Beat |
|-----------|--------|-----------|
| Technical Accuracy | 35% | All — real tools, real data, real results |
| IDP Innovation | 30% | Beat 2 — free-form text extraction + structured cross-reference + anomaly |
| Social Impact | 25% | Beat 3 — actionable deployment recommendation |
| User Experience | 10% | All — entire demo is natural language conversation |

## Architecture

```
Claude Desktop → OASIS MCP Server → DuckDB (VF Ghana data, ~1,002 facilities)
                                  → Medical Desert Mapper (Mapbox GL JS 3D map)
                                  → Optional: Databricks Vector Search + MLflow
```

## What's Working Now

**11 MCP tools registered:**
- Management: `list_datasets`, `set_dataset`
- Tabular: `get_database_schema`, `get_table_info`, `execute_query`
- Geospatial: `count_facilities`, `find_facilities_in_radius`, `find_coverage_gaps`, `calculate_distance`, `geocode_facilities`
- App: `geo_map` (GeoMapTool + Vite UI bundle)

**3 Databricks tools (optional, graceful degradation):**
- `search_facility_capabilities` (RAG) — needs DuckDB fallback for demo
- `ask_genie` (Text2SQL) — not in demo
- `get_citation_trace` (MLflow) — needs local fallback for demo

## Dataset: Virtue Foundation Ghana

~1,002 healthcare facilities. Free-form fields (`procedure`, `equipment`, `capability`) are JSON arrays of strings — richest data. Many fields null/empty — detecting gaps IS the feature. Schema: `docs/challenge/Virtue Foundation Scheme Documentation.md`.

## Development Conventions

- Python 3.10+, type hints, Ruff (line length 88), pytest
- **Tools return native Python types** — MCP layer serializes via `serialize_for_mcp()`
- **Canonical schema names** — `schema.table` format (e.g., `vf.facilities`)
- **DuckDB only** — Databricks optional for demo
- Branch: `main` (hackathon, move fast). Don't commit secrets or node_modules.

## Key Files

| What | Where |
|------|-------|
| Demo script & preset prompt | `SCRIPT.md` |
| MCP server | `src/oasis/mcp_server.py` |
| Tool protocol | `src/oasis/core/tools/base.py` |
| geo_map app | `src/oasis/apps/geo_map/` |
| Databricks tools | `src/oasis/databricks/` |
| VF Ghana data | `vf-ghana.csv` |
| Schema docs | `docs/challenge/Virtue Foundation Scheme Documentation.md` |
| Apps guide | `docs/OASIS_APPS.md` |
| VF Agent Questions | `docs/challenge/Virtue Foundation Agent Questions - Hack Nation.md` |

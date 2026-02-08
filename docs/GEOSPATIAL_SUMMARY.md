# OASIS Geospatial Intelligence

## Overview

OASIS provides a suite of MCP tools for geospatial analysis of healthcare facilities in Ghana, plus an interactive 3D map that runs inside Claude Desktop.

## MCP Geospatial Tools

| Tool | Description |
|------|-------------|
| `count_facilities` | Count total facilities, optionally filtered by condition. Returns regional breakdown. |
| `find_facilities_in_radius` | Search within X km of a location using Haversine distance. |
| `find_coverage_gaps` | Identify medical deserts — areas beyond a threshold distance from the nearest capable facility. |
| `calculate_distance` | Haversine great-circle distance between any two locations. |
| `geocode_facilities` | Export all facilities as GeoJSON for map visualization. |

## Data Backend

- **DuckDB** with the Virtue Foundation Ghana dataset (~1,004 facilities)
- **Haversine distance** for accurate great-circle calculations
- **Geocoding** using curated Ghana city/landmark coordinates
- **Jittered coordinates** to prevent exact overlaps at shared locations

## Medical Desert Mapper

Interactive 3D map running inside Claude Desktop via the MCP Apps protocol.

**Features:**
- 3D globe with terrain exaggeration and facility markers
- Heatmap overlay for facility density
- Coverage gap visualization with desert highlighting and isochrone rings
- Facility detail cards showing specialties, equipment, procedures, and capabilities
- 3D hospital models rendered with Three.js at street zoom levels
- Text-to-speech narration via ElevenLabs (optional)
- Region highlighting and fly-to navigation

### Architecture

```
Claude Desktop
    │
    └── OASIS MCP Server (FastMCP)
            │
            ├── Geospatial Tools ── DuckDB (VF Ghana data)
            │
            └── Medical Desert Mapper App
                    ├── tool.py         — query + result packaging
                    ├── query_builder.py — SQL generation
                    └── ui/             — Vite-bundled Mapbox GL JS + Three.js
```

## Key Files

| File | Purpose |
|------|---------|
| `src/oasis/core/tools/geospatial.py` | All 5 geospatial tool implementations |
| `src/oasis/mcp_server.py` | MCP protocol adapter and tool registration |
| `src/oasis/apps/geo_map/tool.py` | GeoMap app tool (launches the map webview) |
| `src/oasis/apps/geo_map/ui/src/mcp-app.ts` | Map UI source (TypeScript) |
| `src/oasis/apps/geo_map/mcp-app.html` | Built bundle served by the MCP server |

## Usage Examples

```bash
# Count facilities with a specialty
count_facilities(condition='cardiology')
# → 30 facilities across Ghana

# Radius search
find_facilities_in_radius(location='Accra', radius_km=50, condition='cardiology')
# → 21 facilities, closest: Yaaba Medical (0.09 km)

# Coverage gaps
find_coverage_gaps(procedure_or_specialty='cardiology', min_gap_km=50)
# → 15 desert areas identified with severity rankings
```

## Desert Detection Algorithm

1. Filter facilities by capability (keyword matching across specialties, equipment, procedures, capability fields)
2. Generate a grid covering Ghana (lat 4.5–11.2, lng -3.3–1.3)
3. For each grid point, compute the Haversine distance to the nearest capable facility
4. Normalize distances to produce a heat value (0–1)
5. Render as a heatmap layer — hot zones indicate areas far from any capable facility
6. Generate isochrone rings (30min, 60min, 120min travel time estimates) around each capable facility using simplex noise for natural irregularity

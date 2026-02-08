# OASIS Geospatial Intelligence - Summary

## ✅ What's Built

### 5 MCP Geospatial Tools

1. **`count_facilities`** - Count total facilities (no location filter)
   - "How many hospitals have cardiology?" → 30 facilities across Ghana
   - Returns regional breakdown

2. **`find_facilities_in_radius`** - Search within X km of location
   - "Cardiology hospitals within 50km of Accra" → 21 facilities
   - Uses Haversine distance calculation

3. **`find_coverage_gaps`** - Identify medical deserts
   - "Where are cardiology deserts?" → Areas >50km from nearest facility
   - Returns severity rankings

4. **`calculate_distance`** - Distance between two locations
   - "Distance from Accra to Kumasi" → 247 km

5. **`geocode_facilities`** - Export facilities as GeoJSON
   - Returns all facilities with coordinates for mapping

### Data Backend
- **DuckDB** with Virtue Foundation Ghana dataset (1004 facilities)
- **Haversine distance** for accurate great-circle calculations
- **Geocoding** using curated Ghana city/landmark coordinates
- **Jittered coordinates** to prevent exact overlaps

### Two Interfaces

#### 1. MCP Protocol (Claude Desktop)
- Tools registered in `mcp_server.py`
- Claude can call tools conversationally
- Returns structured data + summaries

#### 2. Standalone 3D Map (Demo)
- **File**: `map_local_test.html` + `map_api.py`
- **Run**: `python map_api.py` → `localhost:8000`
- **Features**:
  - 3D globe with Mapbox GL JS
  - 3D hospital buildings (three.js)
  - Heatmaps for capability density
  - Medical desert visualization
  - ElevenLabs audio narration
  - Real-time search calling same MCP tools via HTTP

## 🚀 How to Use

### For Claude Desktop
1. Restart Claude Desktop (Cmd+Q, reopen)
2. Ask questions:
   - "How many hospitals have cardiology?"
   - "Show facilities near Tamale within 100km"
   - "Where are medical deserts for surgery?"

### For Demo/Judges
```bash
cd /Users/rajnu/Desktop/Hackathon/Hacknation/oasis
python map_api.py
# Open http://localhost:8000
```

## 📁 Key Files

### Backend (MCP Tools)
- `src/m4/core/tools/geospatial.py` - All 5 tool implementations
- `src/m4/mcp_server.py` - MCP protocol adapter
- `map_api.py` - HTTP API wrapper for standalone map

### Frontend (Map UI)
- `map_local_test.html` - Standalone 3D map (1284 lines)
- `src/m4/apps/geo_map/` - MCP App (webview, experimental)

### Data
- `m4_data/databases/vf_ghana.duckdb` - DuckDB database
- `facilities.geojson` - Geocoded facilities for map

## 🎯 Architecture

```
┌─────────────────────────────────────────────┐
│         User Interfaces                      │
│  ┌──────────────┐      ┌─────────────────┐  │
│  │ Claude       │      │ Browser         │  │
│  │ Desktop      │      │ localhost:8000  │  │
│  └──────┬───────┘      └────────┬────────┘  │
│         │ MCP                   │ HTTP       │
└─────────┼───────────────────────┼───────────┘
          │                       │
          ▼                       ▼
┌─────────────────────────────────────────────┐
│         Protocol Adapters                    │
│  ┌──────────────┐      ┌─────────────────┐  │
│  │ mcp_server.py│      │ map_api.py      │  │
│  └──────┬───────┘      └────────┬────────┘  │
│         │ Python import         │            │
└─────────┼───────────────────────┼───────────┘
          │                       │
          └───────────┬───────────┘
                      ▼
          ┌───────────────────────┐
          │  Tool Classes         │
          │  geospatial.py        │
          │  - CountFacilitiesTool│
          │  - FindFacilitiesIn...│
          │  - FindCoverageGaps...│
          │  - CalculateDistance..│
          │  - GeocodeFacilities..│
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  DuckDB Backend       │
          │  vf_ghana.duckdb      │
          └───────────────────────┘
```

## ✨ Key Features

### Smart Tool Selection
- **No location** → Uses `count_facilities` (total count)
- **With location** → Uses `find_facilities_in_radius` (geospatial)
- **Medical deserts** → Uses `find_coverage_gaps` (cold spots)

### No Hardcoding
- All "Accra" and "50km" are **defaults only**
- Fully configurable via all interfaces
- Works with any Ghana location

### Production Ready
- Clean, tested code
- Proper error handling
- Thread-safe tool registry
- Comprehensive docstrings

## 🐛 Known Issues

### MCP App Webview
- Tool executes correctly in Claude Desktop
- Returns proper data
- But webview doesn't render (experimental feature)
- **Workaround**: Use standalone map for demos

## 📊 Test Results

```bash
# Count facilities
count_facilities(condition='cardiology')
→ 30 facilities across Ghana

# Radius search
find_facilities_in_radius(location='Accra', radius_km=50, condition='cardiology')
→ 21 facilities, closest: Yaaba Medical (0.09 km)

# Coverage gaps
find_coverage_gaps(procedure_or_specialty='cardiology', min_gap_km=50)
→ 15 desert areas identified
```

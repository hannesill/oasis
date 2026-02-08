# OASIS Local Map - Usage Guide

## Quick Start

The local map uses the existing `map_api.py` server and `map_local_test.html` interface.

### 1. Start the Map Server

```bash
python map_api.py
```

You should see:
```
🌍 OASIS Map API
────────────────────────────────────────
  UI:     http://localhost:8000
  API:    http://localhost:8000/api/search?condition=cardiology&location=Accra
  Health: http://localhost:8000/api/health
────────────────────────────────────────
```

### 2. Open in Browser

Navigate to: **http://localhost:8000**

## Features

### ✅ Category Selection

The map automatically loads **all available specialties** from your facilities data and populates a dropdown menu. Categories include:

- Cardiology
- Surgery
- Maternity
- Emergency
- ICU
- Pediatric
- Oncology
- Radiology
- Laboratory
- And more (dynamically loaded from your data)

### ✅ Search by Category

1. **Select a condition** from the dropdown (e.g., "Cardiology")
2. **Enter a location** (e.g., "Accra", "Kumasi", "Tamale")
3. **Set radius** (10-300 km slider)
4. **Click "Find Facilities"**

The map will:
- Query the real OASIS tools (FindFacilitiesInRadiusTool)
- Show facilities matching that category
- Display results in the sidebar
- Highlight markers on the map
- Show distance and relevance scores

### ✅ Medical Deserts

Click **"Find Medical Deserts"** to identify coverage gaps for the selected category.

### ✅ Interactive Map

- **Click markers** to see facility details
- **Toggle layers**: Markers, Heatmap, 3D Buildings, Deserts
- **Navigate**: Quick buttons for Accra, Kumasi, Tamale
- **3D models**: Zoom in to see 3D hospital models

## How It Works

```
Browser (map_local_test.html)
    ↓ HTTP requests
map_api.py (FastAPI server)
    ↓ Direct tool calls
OASIS Core Tools (FindFacilitiesInRadiusTool, etc.)
    ↓ Queries
DuckDB Database
```

**No LLM required** - all queries are direct tool calls with category selection.

## API Endpoints

The server exposes these endpoints:

- `GET /` - Serves the map UI
- `GET /api/search?condition=X&location=Y&radius_km=Z` - Find facilities
- `GET /api/gaps?specialty=X` - Find medical deserts
- `GET /api/config` - Get Mapbox token
- `GET /facilities.geojson` - All facilities GeoJSON

## Categories

Categories are **dynamically loaded** from your facilities data. The dropdown is populated by:

1. Loading all facilities from `/facilities.geojson`
2. Extracting unique specialties from each facility
3. Sorting and displaying them in the dropdown

This means:
- ✅ No hard-coding needed
- ✅ Automatically includes all specialties in your data
- ✅ Updates when your data changes

## Troubleshooting

### Map doesn't load
- Check `.env` has `MAPBOX_TOKEN=pk.ey...`
- Restart `map_api.py` after adding token

### No categories in dropdown
- Check that facilities.geojson loads successfully
- Check browser console for errors
- Verify database has facilities with specialties

### Search returns no results
- Try a larger radius
- Check that the condition exists in your data
- Verify location name is correct (e.g., "Accra" not "accra")

## Next Steps

The map is fully functional with:
- ✅ Category selection (dynamic from data)
- ✅ Real OASIS tool integration
- ✅ Interactive 3D map
- ✅ Medical desert analysis
- ✅ No LLM/API credits needed

Just run `python map_api.py` and open http://localhost:8000!


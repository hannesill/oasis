# Plan: Fix Hospital Point Rendering & Coordinate Distribution

## Context

Hospital markers on the geo map have two major problems: (1) they **disappear above zoom 10** because the marker layer has `maxzoom: 10`, and when a user clicks a marker the map flies to zoom 16 where nothing is visible; (2) all facilities in the same city **cluster within ~0.5km of city center** because the jitter is too small (±0.005°), making Accra's 309 hospitals appear as a single blob. The user wants clearly visible, spread-out, clickable points that look realistic for a demo.

## Files to Modify

| File | Changes |
|------|---------|
| `src/oasis/core/tools/geospatial.py` | Add cities to lookup, replace jitter with golden-angle spiral distribution |
| `src/oasis/apps/geo_map/ui/src/mcp-app.ts` | Fix marker visibility at all zoom levels, improve styling |

## Part 1: Backend — Spiral Coordinate Distribution

**File:** `src/oasis/core/tools/geospatial.py`

### 1a. Expand `GHANA_CITY_COORDS` (line 37-108)

Add ~50 missing cities to improve geocoding coverage. Currently 55 of 264 unique cities are mapped. Priority cities (3+ facilities each): berekum, atebubu, weija, battor, bibiani, oyarifa, sekondi, akwatia, akosombo, walewale, bechem, ejisu, kwadaso, mampong, dompoase, nkwanta, dzodze. Plus ~30 cities with 2 facilities each. Look up real coordinates from OpenStreetMap.

### 1b. Add `_spiral_offset()` helper (insert above tool classes, ~line 160)

Replace uniform random jitter with a **golden angle spiral** (Fermat spiral). This distributes N points evenly in a circle — no overlaps, deterministic, looks natural.

```python
import math

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))  # ~137.508°

def _spiral_offset(index: int, total: int, base_lat: float, base_lng: float) -> tuple[float, float]:
    if total <= 1:
        return (base_lat, base_lng)

    # Scale radius by cluster size
    if total <= 5:      max_r = 0.01    # ~1.1 km
    elif total <= 20:   max_r = 0.025   # ~2.8 km
    elif total <= 50:   max_r = 0.045   # ~5.0 km
    elif total <= 100:  max_r = 0.065   # ~7.2 km
    else:               max_r = 0.09    # ~10 km (Accra's 309)

    r = max_r * math.sqrt(index / total)
    theta = index * GOLDEN_ANGLE
    lat_off = r * math.cos(theta)
    lng_off = r * math.sin(theta) / max(math.cos(math.radians(base_lat)), 0.01)
    return (base_lat + lat_off, base_lng + lng_off)
```

### 1c. Refactor `GeocodeFacilitiesTool.invoke()` (lines 927-976)

Replace per-facility random jitter with two-pass grouped spiral:

1. **Pass 1:** Iterate rows, resolve city→coords (with region fallback), group by geocode key
2. **Sort** each city group alphabetically by facility name (deterministic ordering)
3. **Pass 2:** For each group, call `_spiral_offset(index, total, base_lat, base_lng)` to get the final coordinates

This means Accra's 309 facilities spread over ~10km radius in an even spiral pattern instead of a ~0.5km random blob.

### 1d. Refactor `FindFacilitiesInRadiusTool.invoke()` (lines 398-450)

Same spiral approach. Pre-compute all facility positions using the grouped spiral, then filter by haversine distance from the search center. This ensures coordinates are consistent between the map display and radius searches.

## Part 2: Frontend — Fix Marker Visibility & Interaction

**File:** `src/oasis/apps/geo_map/ui/src/mcp-app.ts`

### 2a. Remove `maxzoom: 10` from markers layer (line 268)

Delete the `maxzoom: 10` property. Markers must be visible at ALL zoom levels.

### 2b. Extend marker sizing to zoom 20 (line 270)

```
Before: ['interpolate', ['linear'], ['zoom'], 4, 2.5, 8, 5, 10, 8]
After:  ['interpolate', ['linear'], ['zoom'], 4, 3, 8, 5, 12, 7, 16, 10, 20, 14]
```

### 2c. Remove `circle-blur: 0.1` (line 273)

Delete `'circle-blur': 0.1` — makes points fuzzy. Crisp circles look better.

### 2d. Extend stroke interpolation & improve contrast (lines 272-273)

```
stroke-width: ['interpolate', ['linear'], ['zoom'], 4, 0.5, 10, 1.5, 16, 2.5]
stroke-color: 'rgba(255,255,255,0.9)'  (was 0.6)
```

### 2e. Extend glow layer sizing (line 259)

Add stops for zoom 16 and 20 so glow scales with markers at high zoom.

### 2f. Adjust flyTo zoom on click (line 281)

Lower from `zoom: 16` to `zoom: 14` — shows surrounding facilities for context while still being close enough to see the selected one.

### 2g. Add click handler to glow layer (after line 287)

Fallback click target: `map.on('click', 'layer-glow', handleClick)` with matching cursor handlers.

### 2h. Build the frontend

Run `npm run build` in `src/oasis/apps/geo_map/ui/` to regenerate the bundled `mcp-app.html`.

## Building Snap — Not Implementing

The user asked about snapping to buildings. **Skipping this** because:
- Mapbox building tiles only load at zoom 15+ and only for the visible viewport — can't pre-snap 987 points
- The golden-angle spiral with ~10km radius already distributes points across the urban footprint realistically
- At demo zoom levels (6-14), individual buildings aren't visible anyway
- User said "okay to fake it a bit" — the spiral IS the realistic-looking fake

## Verification

1. Run `oasis status` to confirm MCP server connects
2. In Claude Desktop, trigger `geocode_facilities` — verify GeoJSON has spread-out coordinates
3. Open the map app — verify:
   - Points visible at zoom 4 (country level) through zoom 18+ (building level)
   - Accra facilities visibly spread across the metro area (not a single cluster)
   - Clicking any point opens the detail card
   - Points stay crisp and sized appropriately at every zoom level
4. Test `find_facilities_in_radius` for Accra — verify consistent coordinates with the map
